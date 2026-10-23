"""Unit tests for InMemoryInvoiceRepository and duplicate invoice prevention."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from finkraft.exceptions import DuplicateInvoiceError, InvoiceNotFoundError
from finkraft.models import Invoice
from finkraft.repository import InMemoryInvoiceRepository


class TestInvoiceRepository(unittest.TestCase):

    def setUp(self) -> None:
        self.repo = InMemoryInvoiceRepository()

    def test_duplicate_invoice_number_rejected_for_same_seller(self) -> None:
        seller_trn = "100123456789001"
        inv1 = Invoice(
            seller_trn=seller_trn,
            invoice_number="INV-100",
            buyer_trn="100987654321002",
            issue_date="2026-10-23",
            total_amount=500.0,
            vat_amount=25.0,
        )
        self.repo.create(inv1)
        self.assertEqual(self.repo.count(), 1)

        # Attempting to insert another invoice with same seller_trn and invoice_number
        inv2 = Invoice(
            seller_trn=seller_trn,
            invoice_number="INV-100",
            buyer_trn="100555555555003",
            issue_date="2026-10-24",
            total_amount=999.0,
            vat_amount=49.0,
        )
        with self.assertRaises(DuplicateInvoiceError) as ctx:
            self.repo.create(inv2)

        self.assertEqual(ctx.exception.seller_trn, seller_trn)
        self.assertEqual(ctx.exception.invoice_number, "INV-100")
        self.assertEqual(self.repo.count(), 1)

    def test_different_sellers_can_reuse_same_invoice_number(self) -> None:
        """Invoices are partitioned by seller TRN; two sellers can use 'INV-100' simultaneously."""
        inv_seller_a = Invoice(
            seller_trn="100111111111001",
            invoice_number="INV-100",
            buyer_trn="100987654321002",
            issue_date="2026-10-23",
            total_amount=100.0,
            vat_amount=5.0,
        )
        inv_seller_b = Invoice(
            seller_trn="100222222222002",
            invoice_number="INV-100",  # Same invoice number, different seller
            buyer_trn="100987654321002",
            issue_date="2026-10-23",
            total_amount=200.0,
            vat_amount=10.0,
        )
        self.repo.create(inv_seller_a)
        self.repo.create(inv_seller_b)
        self.assertEqual(self.repo.count(), 2)

        # Verify lookups by business key
        found_a = self.repo.get_by_business_key("100111111111001", "INV-100")
        found_b = self.repo.get_by_business_key("100222222222002", "INV-100")
        self.assertIsNotNone(found_a)
        self.assertIsNotNone(found_b)
        self.assertNotEqual(found_a.id, found_b.id)

    def test_lookup_by_external_id(self) -> None:
        inv = Invoice(
            seller_trn="100123456789001",
            invoice_number="INV-555",
            buyer_trn="100987654321002",
            issue_date="2026-10-23",
            total_amount=500.0,
            vat_amount=25.0,
            external_id="job_asp_b_xyz123",
        )
        self.repo.create(inv)

        found = self.repo.get_by_external_id("job_asp_b_xyz123")
        self.assertIsNotNone(found)
        self.assertEqual(found.invoice_number, "INV-555")


if __name__ == "__main__":
    unittest.main()
