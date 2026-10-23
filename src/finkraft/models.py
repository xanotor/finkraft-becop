"""Domain data models and enums for Finkraft E-Invoicing Platform."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class InvoiceState(str, Enum):
    """Internal lifecycle states of an invoice within Finkraft."""
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    SUBMITTING = "SUBMITTING"
    SUBMISSION_AMBIGUOUS = "SUBMISSION_AMBIGUOUS"
    ACKNOWLEDGED_C2 = "ACKNOWLEDGED_C2"
    VALIDATED_C2 = "VALIDATED_C2"
    DELIVERED_C3 = "DELIVERED_C3"
    REPORTED_C5 = "REPORTED_C5"
    COMPLIANT_AND_DELIVERED = "COMPLIANT_AND_DELIVERED"  # Terminal Success (both C3 and C5 satisfied)
    REJECTED = "REJECTED"                                # Terminal Failure


class NormalizedStatus(str, Enum):
    """Normalized status values returned by ASP adapters."""
    ACKNOWLEDGED = "ACKNOWLEDGED"          # C2 received / queued payload
    VALIDATED = "VALIDATED"                # C2 validated schema / tax rules
    DELIVERED_C3 = "DELIVERED_C3"          # C3 buyer ASP received invoice
    REPORTED_C5 = "REPORTED_C5"            # C5 FTA tax reporting confirmed
    REJECTED = "REJECTED"                  # Fatal rejection by C2, C3, or C5


@dataclass(frozen=True)
class NormalizedError:
    """Standardized error model mapping heterogeneous ASP and internal errors."""
    code: str
    message: str
    field_reference: Optional[str] = None
    is_transient: bool = False


@dataclass(frozen=True)
class CanonicalInvoice:
    """Standardized business invoice representation ready for ASP submission."""
    seller_trn: str
    invoice_number: str
    buyer_trn: str
    issue_date: str
    total_amount: float
    vat_amount: float
    currency: str = "AED"
    pint_ae_xml: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubmissionResult:
    """Unified response returned by ASPAdapter.submit_invoice()."""
    success: bool
    is_ambiguous: bool
    external_id: Optional[str]
    initial_status: NormalizedStatus
    errors: List[NormalizedError] = field(default_factory=list)
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StatusUpdate:
    """Unified status payload from polling or inbound webhooks."""
    external_id: str
    status: NormalizedStatus
    timestamp: datetime
    errors: List[NormalizedError] = field(default_factory=list)
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ASPCapabilities:
    """Operational profile and rate constraints of an ASP."""
    asp_id: str
    supports_sync_submit: bool
    supports_polling: bool
    supports_webhooks: bool
    rate_limit_rps: int
    has_native_idempotency: bool


@dataclass
class Invoice:
    """Internal invoice domain entity with milestone tracking and audit history."""
    seller_trn: str
    invoice_number: str
    buyer_trn: str
    issue_date: str
    total_amount: float
    vat_amount: float
    currency: str = "AED"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: InvoiceState = InvoiceState.DRAFT
    assigned_asp_id: Optional[str] = None
    external_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    c3_delivered_at: Optional[datetime] = None
    c5_reported_at: Optional[datetime] = None
    errors: List[NormalizedError] = field(default_factory=list)
    history: List[Tuple[datetime, InvoiceState, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append((self.created_at, self.state, "Invoice created in DRAFT state"))

    @property
    def business_key(self) -> Tuple[str, str]:
        """Returns the unique business key (seller_trn, invoice_number)."""
        return self.seller_trn, self.invoice_number

    def record_transition(self, new_state: InvoiceState, reason: str = "") -> None:
        """Appends a transition to the audit history and updates timestamp."""
        now = datetime.utcnow()
        self.state = new_state
        self.updated_at = now
        self.history.append((now, new_state, reason))
