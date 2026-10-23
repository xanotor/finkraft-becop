# Finkraft E-Invoicing Platform: Technical Contract Specification
**Scope:** Developer Reference – Type Definitions, Interfaces & Adapter Protocol

---

## 1. Domain Types & Enums

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

class NormalizedStatus(str, Enum):
    """Normalized status values across all heterogeneous ASPs."""
    ACKNOWLEDGED = "ACKNOWLEDGED"          # C2 received/queued payload
    VALIDATED = "VALIDATED"                # C2 validated schema/tax rules
    DELIVERED_C3 = "DELIVERED_C3"          # C3 buyer ASP received invoice
    REPORTED_C5 = "REPORTED_C5"            # C5 FTA tax reporting confirmed
    REJECTED = "REJECTED"                  # Fatal rejection by C2, C3, or C5

@dataclass(frozen=True)
class NormalizedError:
    """Standardized error model mapping heterogeneous ASP errors."""
    code: str                             # E.g. "E104", "ERR_VAT_RULE"
    message: str                          # Human-readable explanation
    field_reference: Optional[str] = None # E.g. "BT-48", "cac:TaxTotal"
    is_transient: bool = False            # True for 5xx/timeouts, False for 4xx/validation

@dataclass(frozen=True)
class CanonicalInvoice:
    """Standardized representation of a PINT AE validated invoice."""
    seller_trn: str                       # 15-digit UAE TRN
    invoice_number: str                   # Unique seller invoice identifier
    buyer_trn: str                        # 15-digit buyer TRN
    issue_date: str                       # YYYY-MM-DD
    total_amount: float                   # Invoice total (AED)
    vat_amount: float                     # VAT amount (AED)
    currency: str = "AED"                 # Currency code
    pint_ae_xml: str = ""                 # Enriched UBL 2.1 PINT AE XML payload
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class SubmissionResult:
    """Unified response returned by ASPAdapter.submit_invoice()."""
    success: bool
    is_ambiguous: bool                    # True on network timeout/connection drop
    external_id: Optional[str]            # ASP submission_id or job_id
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
    has_native_idempotency: bool          # ASP A=True (409), ASP B=False
```

---

## 2. Adapter Abstract Interface

```python
from abc import ABC, abstractmethod

class ASPAdapter(ABC):
    """Polymorphic contract implemented by all ASP integrations."""

    @abstractmethod
    def submit_invoice(self, invoice: CanonicalInvoice) -> SubmissionResult:
        """
        Dispatches a PINT AE invoice to the ASP.
        Handles serialization, authentication, and error normalization.
        """
        pass

    @abstractmethod
    def poll_status(self, external_id: str) -> StatusUpdate:
        """
        Queries current status from ASP polling endpoint.
        Raises NotImplementedError if the ASP is webhook-only.
        """
        pass

    @abstractmethod
    def parse_webhook(self, headers: Dict[str, str], payload: Dict[str, Any]) -> StatusUpdate:
        """
        Validates webhook signatures, unpacks ASP-specific payloads,
        and translates them into standardized StatusUpdate instances.
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> ASPCapabilities:
        """Returns the operational profile and constraints of the ASP."""
        pass
```

---

## 3. Dynamic Adapter Registry

```python
class ASPRegistry:
    """Central registry facilitating dynamic switching of ASP adapters."""
    _adapters: Dict[str, ASPAdapter] = {}

    @classmethod
    def register(cls, asp_id: str, adapter: ASPAdapter) -> None:
        cls._adapters[asp_id] = adapter

    @classmethod
    def get(cls, asp_id: str) -> ASPAdapter:
        if asp_id not in cls._adapters:
            raise ValueError(f"Unknown ASP adapter: '{asp_id}'. Available: {list(cls._adapters.keys())}")
        return cls._adapters[asp_id]
```
