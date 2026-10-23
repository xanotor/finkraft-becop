"""Abstract base class and contract for ASP adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from finkraft.models import ASPCapabilities, CanonicalInvoice, StatusUpdate, SubmissionResult


class ASPAdapter(ABC):
    """
    Polymorphic interface that all Accredited Service Provider (ASP) adapters must implement.
    Normalizes synchronous/asynchronous submissions, polling, and inbound webhooks.
    """

    @abstractmethod
    def submit_invoice(self, invoice: CanonicalInvoice) -> SubmissionResult:
        """
        Submits a PINT AE invoice to the ASP.
        Normalizes ASP response into SubmissionResult.
        """
        pass

    @abstractmethod
    def poll_status(self, external_id: str) -> StatusUpdate:
        """
        Queries current status from the ASP polling endpoint.
        Raises NotImplementedError if the ASP is webhook-only.
        """
        pass

    @abstractmethod
    def parse_webhook(self, headers: Dict[str, str], payload: Dict[str, Any]) -> StatusUpdate:
        """
        Validates webhook signatures and normalizes payload into a StatusUpdate.
        Raises NotImplementedError if the ASP does not support webhooks.
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> ASPCapabilities:
        """Returns the operational profile and constraints of the ASP."""
        pass
