"""Mock implementation of ASP A.

Characteristics:
- Synchronous POST /invoices returning 200 with submission_id and status 'RECEIVED'.
- Polling status updates via GET /invoices/{submission_id}.
- Rejects duplicate invoice numbers with HTTP 409.
- Status values: RECEIVED, VALIDATED, REJECTED, DELIVERED (C3), REPORTED (C5).
- Errors: {"code": "E104", "field": "BT-48"}.
- Known behaviour: Rate limit 10 req/s, occasional timeouts after invoice was accepted.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from finkraft.adapters.base import ASPAdapter
from finkraft.models import (
    ASPCapabilities,
    CanonicalInvoice,
    NormalizedError,
    NormalizedStatus,
    StatusUpdate,
    SubmissionResult,
)


class MockASPAAdapter(ASPAdapter):
    """Mock implementation of ASP A adapter."""

    ASP_ID = "ASP_A"

    STATUS_MAP: Dict[str, NormalizedStatus] = {
        "RECEIVED": NormalizedStatus.ACKNOWLEDGED,
        "VALIDATED": NormalizedStatus.VALIDATED,
        "DELIVERED": NormalizedStatus.DELIVERED_C3,
        "REPORTED": NormalizedStatus.REPORTED_C5,
        "REJECTED": NormalizedStatus.REJECTED,
    }

    def __init__(self, rate_limit_rps: int = 10) -> None:
        self.rate_limit_rps = rate_limit_rps
        # Remote mock database: submission_id -> record
        self._submissions: Dict[str, Dict[str, Any]] = {}
        # Duplicate detection by invoice_number (ASP A enforces global invoice uniqueness)
        self._seen_invoice_numbers: Dict[str, str] = {}  # invoice_number -> submission_id

        # Simulation flags for test scenarios
        self.simulate_timeout_post_acceptance: bool = False
        self.simulate_validation_failure: bool = False

    def get_capabilities(self) -> ASPCapabilities:
        return ASPCapabilities(
            asp_id=self.ASP_ID,
            supports_sync_submit=True,
            supports_polling=True,
            supports_webhooks=False,
            rate_limit_rps=self.rate_limit_rps,
            has_native_idempotency=True,
        )

    def submit_invoice(self, invoice: CanonicalInvoice) -> SubmissionResult:
        # Check simulated validation failure (e.g. BT-48 rule)
        if self.simulate_validation_failure or (
            invoice.metadata and invoice.metadata.get("simulate_error") == "BT-48"
        ):
            return SubmissionResult(
                success=False,
                is_ambiguous=False,
                external_id=None,
                initial_status=NormalizedStatus.REJECTED,
                errors=[
                    NormalizedError(
                        code="E104",
                        message="Missing or invalid VAT category code",
                        field_reference="BT-48",
                        is_transient=False,
                    )
                ],
                raw_response={"code": "E104", "field": "BT-48"},
            )

        # Check native idempotency (HTTP 409 Conflict)
        if invoice.invoice_number in self._seen_invoice_numbers:
            return SubmissionResult(
                success=False,
                is_ambiguous=False,
                external_id=self._seen_invoice_numbers[invoice.invoice_number],
                initial_status=NormalizedStatus.REJECTED,
                errors=[
                    NormalizedError(
                        code="409",
                        message=f"Duplicate invoice number '{invoice.invoice_number}' rejected with 409 Conflict",
                        field_reference="invoice_number",
                        is_transient=False,
                    )
                ],
                raw_response={"status": 409, "error": "Duplicate invoice number"},
            )

        # Register submission at ASP A
        sub_id = f"asp_a_sub_{uuid.uuid4().hex[:12]}"
        self._submissions[sub_id] = {
            "submission_id": sub_id,
            "invoice_number": invoice.invoice_number,
            "seller_trn": invoice.seller_trn,
            "status": "RECEIVED",
            "errors": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        self._seen_invoice_numbers[invoice.invoice_number] = sub_id

        # Simulate timeout after acceptance
        if self.simulate_timeout_post_acceptance or (
            invoice.metadata and invoice.metadata.get("simulate_timeout")
        ):
            return SubmissionResult(
                success=False,
                is_ambiguous=True,
                external_id=None,  # Client socket dropped before receiving ID
                initial_status=NormalizedStatus.ACKNOWLEDGED,
                errors=[
                    NormalizedError(
                        code="TIMEOUT",
                        message="HTTP 504 Gateway Timeout: connection dropped waiting for ASP A response",
                        is_transient=True,
                    )
                ],
                raw_response={"error": "Gateway Timeout"},
            )

        return SubmissionResult(
            success=True,
            is_ambiguous=False,
            external_id=sub_id,
            initial_status=NormalizedStatus.ACKNOWLEDGED,
            raw_response={"submission_id": sub_id, "status": "RECEIVED"},
        )

    def poll_status(self, external_id: str) -> StatusUpdate:
        record = self._submissions.get(external_id)
        if not record:
            return StatusUpdate(
                external_id=external_id,
                status=NormalizedStatus.REJECTED,
                timestamp=datetime.utcnow(),
                errors=[
                    NormalizedError(
                        code="404",
                        message=f"Submission '{external_id}' not found at ASP A",
                        is_transient=False,
                    )
                ],
                raw_payload={"error": "Not Found"},
            )

        raw_status = record["status"]
        norm_status = self.STATUS_MAP.get(raw_status, NormalizedStatus.REJECTED)
        errors = [
            NormalizedError(code=e.get("code", "ERR"), message=e.get("message", "Error"), field_reference=e.get("field"))
            for e in record.get("errors", [])
        ]

        return StatusUpdate(
            external_id=external_id,
            status=norm_status,
            timestamp=record["updated_at"],
            errors=errors,
            raw_payload={"submission_id": external_id, "status": raw_status},
        )

    def parse_webhook(self, headers: Dict[str, str], payload: Dict[str, Any]) -> StatusUpdate:
        raise NotImplementedError("ASP A does not support webhooks; status is retrieved via polling only.")

    # --- Test and Reconciliation Utilities ---

    def set_remote_status(self, submission_id: str, raw_status: str, errors: Optional[List[Dict[str, str]]] = None) -> None:
        """Helper to advance remote status in tests."""
        if submission_id in self._submissions:
            self._submissions[submission_id]["status"] = raw_status
            self._submissions[submission_id]["updated_at"] = datetime.utcnow()
            if errors:
                self._submissions[submission_id]["errors"] = errors

    def lookup_by_invoice_number(self, invoice_number: str) -> Optional[str]:
        """Allows reconciliation worker to search by invoice number after timeout."""
        return self._seen_invoice_numbers.get(invoice_number)
