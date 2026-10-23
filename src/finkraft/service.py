"""Core application service orchestrating invoice lifecycle, ASP adapters, and resilience."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from finkraft.adapters.base import ASPAdapter
from finkraft.adapters.registry import ASPRegistry
from finkraft.exceptions import (
    ASPCommunicationError,
    DuplicateInvoiceError,
    InvoiceNotFoundError,
)
from finkraft.models import (
    CanonicalInvoice,
    Invoice,
    InvoiceState,
    NormalizedError,
    NormalizedStatus,
    StatusUpdate,
)
from finkraft.repository import InMemoryInvoiceRepository
from finkraft.state_machine import InvoiceStateMachine


class InvoiceService:
    """
    Main orchestration service for Finkraft E-Invoicing.
    Coordinates validation, submission, status polling, webhook handling, and ASP switching.
    """

    def __init__(
        self,
        repository: Optional[InMemoryInvoiceRepository] = None,
        default_asp_id: str = "ASP_A",
    ) -> None:
        self.repository = repository or InMemoryInvoiceRepository()
        self.default_asp_id = default_asp_id
        # Per-seller preferred ASP mapping: seller_trn -> asp_id
        self._seller_asp_preferences: Dict[str, str] = {}
        # Webhook idempotency ledger: event_id -> timestamp
        self._processed_webhook_events: Set[str] = set()

    # --- Customer ASP Configuration ---

    def configure_seller_asp(self, seller_trn: str, asp_id: str) -> None:
        """Configures or switches the active ASP for a seller."""
        # Verify ASP adapter exists in registry
        ASPRegistry.get(asp_id)
        self._seller_asp_preferences[seller_trn] = asp_id

    def get_seller_asp(self, seller_trn: str) -> str:
        """Returns the configured ASP for a seller, or the platform default."""
        return self._seller_asp_preferences.get(seller_trn, self.default_asp_id)

    # --- Ingestion & PINT AE Pre-Validation ---

    def ingest_invoice(
        self,
        seller_trn: str,
        invoice_number: str,
        buyer_trn: str,
        issue_date: str,
        total_amount: float,
        vat_amount: float,
        currency: str = "AED",
    ) -> Invoice:
        """
        Ingests a raw invoice from customer bulk upload.
        Enforces client-side per-seller uniqueness on (seller_trn, invoice_number).
        """
        invoice = Invoice(
            seller_trn=seller_trn,
            invoice_number=invoice_number,
            buyer_trn=buyer_trn,
            issue_date=issue_date,
            total_amount=total_amount,
            vat_amount=vat_amount,
            currency=currency,
            state=InvoiceState.DRAFT,
        )
        return self.repository.create(invoice)

    def validate_and_enrich(self, invoice_id: str) -> Invoice:
        """
        Validates invoice against UAE PINT AE rules and tax math.
        Transitions DRAFT -> VALIDATED (or REJECTED on schema failure).
        """
        invoice = self.repository.get_by_id(invoice_id)
        if not invoice:
            raise InvoiceNotFoundError(invoice_id)

        errors: List[NormalizedError] = []

        # PINT AE Rule: 15-digit UAE TRN format
        trn_pattern = r"^100\d{12}$"  # Typical 15-digit UAE TRN starting with 100
        if not re.match(r"^\d{15}$", invoice.seller_trn):
            errors.append(
                NormalizedError(
                    code="PINT_AE_001",
                    message="Seller TRN must be exactly 15 digits",
                    field_reference="BT-31",
                )
            )

        if not re.match(r"^\d{15}$", invoice.buyer_trn):
            errors.append(
                NormalizedError(
                    code="PINT_AE_002",
                    message="Buyer TRN must be exactly 15 digits",
                    field_reference="BT-48",
                )
            )

        # Tax arithmetic validation
        if invoice.total_amount <= 0:
            errors.append(
                NormalizedError(
                    code="PINT_AE_003",
                    message="Invoice total amount must be strictly positive",
                    field_reference="BT-112",
                )
            )

        if invoice.vat_amount < 0 or invoice.vat_amount > invoice.total_amount:
            errors.append(
                NormalizedError(
                    code="PINT_AE_004",
                    message="VAT amount must be non-negative and not exceed total amount",
                    field_reference="BT-110",
                )
            )

        if errors:
            InvoiceStateMachine.transition(
                invoice,
                InvoiceState.REJECTED,
                reason="Failed internal PINT AE validation",
                errors=errors,
            )
        else:
            InvoiceStateMachine.transition(
                invoice,
                InvoiceState.VALIDATED,
                reason="Passed PINT AE schema and tax validation",
            )

        return self.repository.update(invoice)

    # --- ASP Submission & Dispatch ---

    def submit_to_asp(self, invoice_id: str, override_asp_id: Optional[str] = None) -> Invoice:
        """
        Submits a VALIDATED invoice to the seller's configured ASP.
        Transitions VALIDATED -> SUBMITTING -> ACKNOWLEDGED_C2 / SUBMISSION_AMBIGUOUS.
        """
        invoice = self.repository.get_by_id(invoice_id)
        if not invoice:
            raise InvoiceNotFoundError(invoice_id)

        # Determine target ASP
        target_asp_id = override_asp_id or self.get_seller_asp(invoice.seller_trn)
        adapter = ASPRegistry.get(target_asp_id)
        invoice.assigned_asp_id = target_asp_id

        # Acquire idempotency lock & transition to SUBMITTING
        InvoiceStateMachine.transition(
            invoice,
            InvoiceState.SUBMITTING,
            reason=f"Dispatching payload to {target_asp_id}",
        )
        self.repository.update(invoice)

        # Prepare Canonical Invoice
        canonical = CanonicalInvoice(
            seller_trn=invoice.seller_trn,
            invoice_number=invoice.invoice_number,
            buyer_trn=invoice.buyer_trn,
            issue_date=invoice.issue_date,
            total_amount=invoice.total_amount,
            vat_amount=invoice.vat_amount,
            currency=invoice.currency,
        )

        # Call Adapter
        result = adapter.submit_invoice(canonical)

        if result.is_ambiguous:
            # Network timeout occurred post-acceptance
            InvoiceStateMachine.transition(
                invoice,
                InvoiceState.SUBMISSION_AMBIGUOUS,
                reason="Submission timeout; active reconciliation required",
                errors=result.errors,
            )
        elif result.success:
            invoice.external_id = result.external_id
            InvoiceStateMachine.apply_normalized_status(
                invoice,
                result.initial_status,
                reason=f"Submission accepted by {target_asp_id}",
            )
        else:
            # Fatal synchronous rejection (e.g. 409 duplicate or validation error)
            InvoiceStateMachine.transition(
                invoice,
                InvoiceState.REJECTED,
                reason=f"Rejected by {target_asp_id}",
                errors=result.errors,
            )

        return self.repository.update(invoice)

    # --- Timeout Active Reconciliation ---

    def reconcile_ambiguous_submission(self, invoice_id: str) -> Invoice:
        """
        Active reconciliation protocol for SUBMISSION_AMBIGUOUS invoices.
        Queries ASP to confirm whether invoice was recorded before the timeout.
        """
        invoice = self.repository.get_by_id(invoice_id)
        if not invoice:
            raise InvoiceNotFoundError(invoice_id)

        if invoice.state != InvoiceState.SUBMISSION_AMBIGUOUS:
            return invoice

        adapter = ASPRegistry.get(invoice.assigned_asp_id)

        # For ASP A, lookup remote record by invoice number
        if hasattr(adapter, "lookup_by_invoice_number"):
            found_sub_id = adapter.lookup_by_invoice_number(invoice.invoice_number)
            if found_sub_id:
                # Invoice was indeed accepted by ASP before timeout!
                invoice.external_id = found_sub_id
                InvoiceStateMachine.transition(
                    invoice,
                    InvoiceState.ACKNOWLEDGED_C2,
                    reason="Reconciled successfully: record found at ASP A",
                )
            else:
                # Invoice confirmed absent; reset to SUBMITTING for safe retry
                InvoiceStateMachine.transition(
                    invoice,
                    InvoiceState.SUBMITTING,
                    reason="Reconciled: record absent at ASP A; ready for safe re-dispatch",
                )
        else:
            # If no lookup method, escalate
            invoice.errors.append(
                NormalizedError(
                    code="RECON_PENDING",
                    message="Manual reconciliation required for adapter",
                    is_transient=True,
                )
            )

        return self.repository.update(invoice)

    # --- Polling Status Updates ---

    def poll_invoice_status(self, invoice_id: str) -> Invoice:
        """
        Polls the assigned ASP for status updates (for polling-capable ASPs like ASP A).
        """
        invoice = self.repository.get_by_id(invoice_id)
        if not invoice:
            raise InvoiceNotFoundError(invoice_id)

        if not invoice.external_id:
            return invoice

        adapter = ASPRegistry.get(invoice.assigned_asp_id)
        status_update = adapter.poll_status(invoice.external_id)

        InvoiceStateMachine.apply_normalized_status(
            invoice,
            status_update.status,
            event_time=status_update.timestamp,
            errors=status_update.errors,
            reason=f"Polled from {invoice.assigned_asp_id}",
        )
        return self.repository.update(invoice)

    # --- Webhook Callback Processing ---

    def process_webhook(
        self,
        asp_id: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> Optional[Invoice]:
        """
        Processes inbound webhook callback (e.g. from ASP B).
        Enforces signature verification, event deduplication, and monotonic status progression.
        """
        event_id = headers.get("X-Event-ID") or payload.get("event_id", "")
        if event_id and event_id in self._processed_webhook_events:
            # Idempotent return: event already processed
            return None

        adapter = ASPRegistry.get(asp_id)
        status_update = adapter.parse_webhook(headers, payload)

        if event_id:
            self._processed_webhook_events.add(event_id)

        # Lookup invoice by external job_id / submission_id
        invoice = self.repository.get_by_external_id(status_update.external_id)
        if not invoice:
            return None

        InvoiceStateMachine.apply_normalized_status(
            invoice,
            status_update.status,
            event_time=status_update.timestamp,
            errors=status_update.errors,
            reason=f"Webhook event received from {asp_id}",
        )
        return self.repository.update(invoice)
