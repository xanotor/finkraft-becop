"""Thread-safe in-memory invoice repository enforcing per-seller invoice uniqueness."""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Tuple

from finkraft.exceptions import DuplicateInvoiceError, InvoiceNotFoundError
from finkraft.models import Invoice


class InMemoryInvoiceRepository:
    """
    In-memory storage for invoices with strict compound uniqueness on (seller_trn, invoice_number).
    Thread-safe using re-entrant locks to simulate transactional database integrity.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._by_id: Dict[str, Invoice] = {}
        # Compound key index: (seller_trn, invoice_number) -> invoice_id
        self._by_business_key: Dict[Tuple[str, str], str] = {}
        # Index on external ASP reference: external_id -> invoice_id
        self._by_external_id: Dict[str, str] = {}

    def create(self, invoice: Invoice) -> Invoice:
        """
        Inserts a new invoice.
        Raises DuplicateInvoiceError if an invoice with the same (seller_trn, invoice_number) already exists.
        """
        with self._lock:
            key = invoice.business_key
            if key in self._by_business_key:
                raise DuplicateInvoiceError(seller_trn=invoice.seller_trn, invoice_number=invoice.invoice_number)

            if invoice.id in self._by_id:
                raise ValueError(f"Primary key collision on ID '{invoice.id}'")

            self._by_id[invoice.id] = invoice
            self._by_business_key[key] = invoice.id

            if invoice.external_id:
                self._by_external_id[invoice.external_id] = invoice.id

            return invoice

    def update(self, invoice: Invoice) -> Invoice:
        """
        Updates an existing invoice. Ensures business key has not collided.
        """
        with self._lock:
            if invoice.id not in self._by_id:
                raise InvoiceNotFoundError(invoice.id)

            # Re-index external_id if updated
            if invoice.external_id:
                self._by_external_id[invoice.external_id] = invoice.id

            self._by_id[invoice.id] = invoice
            return invoice

    def get_by_id(self, invoice_id: str) -> Optional[Invoice]:
        """Fetches an invoice by internal UUID."""
        with self._lock:
            return self._by_id.get(invoice_id)

    def get_by_business_key(self, seller_trn: str, invoice_number: str) -> Optional[Invoice]:
        """Fetches an invoice by the compound business key (seller_trn, invoice_number)."""
        with self._lock:
            invoice_id = self._by_business_key.get((seller_trn, invoice_number))
            if invoice_id:
                return self._by_id.get(invoice_id)
            return None

    def get_by_external_id(self, external_id: str) -> Optional[Invoice]:
        """Fetches an invoice by the ASP external reference ID (submission_id or job_id)."""
        with self._lock:
            invoice_id = self._by_external_id.get(external_id)
            if invoice_id:
                return self._by_id.get(invoice_id)
            return None

    def list_by_seller(self, seller_trn: str) -> List[Invoice]:
        """Returns all invoices for a given seller TRN."""
        with self._lock:
            return [inv for inv in self._by_id.values() if inv.seller_trn == seller_trn]

    def list_all(self) -> List[Invoice]:
        """Returns all invoices in the repository."""
        with self._lock:
            return list(self._by_id.values())

    def count(self) -> int:
        """Returns total invoice count."""
        with self._lock:
            return len(self._by_id)

    def clear(self) -> None:
        """Wipes the in-memory repository (for test isolation)."""
        with self._lock:
            self._by_id.clear()
            self._by_business_key.clear()
            self._by_external_id.clear()
