"""Domain exceptions for Finkraft E-Invoicing Platform."""

from typing import Optional


class FinkraftError(Exception):
    """Base exception for all Finkraft platform domain errors."""
    pass


class InvalidStateTransitionError(FinkraftError):
    """Raised when an illegal state machine transition is attempted."""

    def __init__(self, from_state: str, to_state: str, reason: str = ""):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        msg = f"Invalid state transition from '{from_state}' to '{to_state}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class DuplicateInvoiceError(FinkraftError):
    """Raised when an invoice number already exists for a given seller TRN."""

    def __init__(self, seller_trn: str, invoice_number: str):
        self.seller_trn = seller_trn
        self.invoice_number = invoice_number
        super().__init__(
            f"Duplicate invoice rejected: Invoice '{invoice_number}' already exists for seller TRN '{seller_trn}'"
        )


class InvoiceNotFoundError(FinkraftError):
    """Raised when an invoice is not found in the repository."""

    def __init__(self, invoice_id: str):
        self.invoice_id = invoice_id
        super().__init__(f"Invoice not found: '{invoice_id}'")


class ASPAdapterNotFoundError(FinkraftError):
    """Raised when an unregistered ASP adapter identifier is requested."""

    def __init__(self, asp_id: str):
        self.asp_id = asp_id
        super().__init__(f"No ASP adapter registered for ID: '{asp_id}'")


class ASPCommunicationError(FinkraftError):
    """Raised when communication with an ASP fails or times out."""

    def __init__(self, asp_id: str, message: str, is_transient: bool = True):
        self.asp_id = asp_id
        self.is_transient = is_transient
        super().__init__(f"ASP '{asp_id}' communication error: {message}")


class ASPValidationError(FinkraftError):
    """Raised when an ASP rejects an invoice due to validation or schema errors."""

    def __init__(self, asp_id: str, code: str, message: str, field_ref: Optional[str] = None):
        self.asp_id = asp_id
        self.code = code
        self.field_ref = field_ref
        super().__init__(f"ASP '{asp_id}' validation error [{code}]: {message} (field: {field_ref})")


class WebhookSignatureVerificationError(FinkraftError):
    """Raised when an incoming webhook signature fails verification."""

    def __init__(self, asp_id: str, reason: str = "Invalid signature"):
        super().__init__(f"Webhook signature verification failed for ASP '{asp_id}': {reason}")
