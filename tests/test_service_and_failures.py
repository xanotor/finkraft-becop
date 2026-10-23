"""Integration and failure mode tests for InvoiceService."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from finkraft.adapters.mock_asp_a import MockASPAAdapter
from finkraft.adapters.mock_asp_b import MockASPBAdapter
from finkraft.adapters.registry import ASPRegistry
from finkraft.exceptions import DuplicateInvoiceError
from finkraft.models import InvoiceState
from finkraft.repository import InMemoryInvoiceRepository
from finkraft.service import InvoiceService


class TestServiceAndFailures(unittest.TestCase):

    def setUp(self) -> None:
        self.repo = InMemoryInvoiceRepository()
        ASPRegistry.clear()

        self.mock_asp_a = MockASPAAdapter()
        self.mock_asp_b = MockASPBAdapter()

        ASPRegistry.register("ASP_A", self.mock_asp_a)
        ASPRegistry.register("ASP_B", self.mock_asp_b)

        self.service = InvoiceService(repository=self.repo, default_asp_id="ASP_A")

    # --- End-to-End Success with ASP A ---

    def test_e2e_asp_a_success_flow(self) -> None:
        # 1. Ingest
        inv = self.service.ingest_invoice(
            seller_trn="100111111111001",
            invoice_number="INV-2026-A01",
            buyer_trn="100222222222002",
            issue_date="2026-10-23",
            total_amount=1000.0,
            vat_amount=50.0,
        )
        self.assertEqual(inv.state, InvoiceState.DRAFT)

        # 2. Validate
        inv = self.service.validate_and_enrich(inv.id)
        self.assertEqual(inv.state, InvoiceState.VALIDATED)

        # 3. Submit
        inv = self.service.submit_to_asp(inv.id)
        self.assertEqual(inv.state, InvoiceState.ACKNOWLEDGED_C2)
        self.assertIsNotNone(inv.external_id)

        # 4. Remote ASP A progresses: C3 Delivered
        self.mock_asp_a.set_remote_status(inv.external_id, "DELIVERED")
        inv = self.service.poll_invoice_status(inv.id)
        self.assertEqual(inv.state, InvoiceState.DELIVERED_C3)

        # 5. Remote ASP A progresses: C5 Reported to FTA -> Terminal Compliant
        self.mock_asp_a.set_remote_status(inv.external_id, "REPORTED")
        inv = self.service.poll_invoice_status(inv.id)
        self.assertEqual(inv.state, InvoiceState.COMPLIANT_AND_DELIVERED)
        self.assertIsNotNone(inv.c3_delivered_at)
        self.assertIsNotNone(inv.c5_reported_at)

    # --- Dynamic ASP Switching (ASP A -> ASP B) ---

    def test_dynamic_asp_switching(self) -> None:
        seller_trn = "100999999999009"

        # Invoice 1 submitted under ASP A
        inv1 = self.service.ingest_invoice(
            seller_trn=seller_trn,
            invoice_number="INV-SWITCH-01",
            buyer_trn="100222222222002",
            issue_date="2026-10-23",
            total_amount=500.0,
            vat_amount=25.0,
        )
        self.service.validate_and_enrich(inv1.id)
        inv1 = self.service.submit_to_asp(inv1.id)
        self.assertEqual(inv1.assigned_asp_id, "ASP_A")

        # Seller switches active ASP to ASP B
        self.service.configure_seller_asp(seller_trn, "ASP_B")
        self.assertEqual(self.service.get_seller_asp(seller_trn), "ASP_B")

        # Invoice 2 submitted under ASP B
        inv2 = self.service.ingest_invoice(
            seller_trn=seller_trn,
            invoice_number="INV-SWITCH-02",
            buyer_trn="100222222222002",
            issue_date="2026-10-23",
            total_amount=750.0,
            vat_amount=37.5,
        )
        self.service.validate_and_enrich(inv2.id)
        inv2 = self.service.submit_to_asp(inv2.id)
        self.assertEqual(inv2.assigned_asp_id, "ASP_B")
        self.assertTrue(inv2.external_id.startswith("job_asp_b_"))

        # In-flight Invoice 1 continues tracking via ASP A
        self.mock_asp_a.set_remote_status(inv1.external_id, "DELIVERED")
        inv1 = self.service.poll_invoice_status(inv1.id)
        self.assertEqual(inv1.state, InvoiceState.DELIVERED_C3)

    # --- Failure Case 1: Timeout & Active Reconciliation (ASP A) ---

    def test_timeout_and_active_reconciliation_workflow(self) -> None:
        """
        Simulates ASP A accepting invoice but timing out on HTTP response.
        Platform sets SUBMISSION_AMBIGUOUS, avoids blind retry, and reconciles.
        """
        self.mock_asp_a.simulate_timeout_post_acceptance = True

        inv = self.service.ingest_invoice(
            seller_trn="100111111111001",
            invoice_number="INV-TIMEOUT-01",
            buyer_trn="100222222222002",
            issue_date="2026-10-23",
            total_amount=1200.0,
            vat_amount=60.0,
        )
        self.service.validate_and_enrich(inv.id)

        # Submission times out
        inv = self.service.submit_to_asp(inv.id)
        self.assertEqual(inv.state, InvoiceState.SUBMISSION_AMBIGUOUS)
        self.assertIsNone(inv.external_id)

        # Run Active Reconciliation
        inv = self.service.reconcile_ambiguous_submission(inv.id)
        self.assertEqual(inv.state, InvoiceState.ACKNOWLEDGED_C2)
        self.assertIsNotNone(inv.external_id)

    # --- Failure Case 2: Duplicate Ingestion Prevention (Protects ASP B) ---

    def test_duplicate_prevention_protects_asp_b(self) -> None:
        """
        ASP B has no duplicate checking. Finkraft client-side uniqueness
        must reject duplicate invoice numbers before calling ASP B.
        """
        seller_trn = "100888888888008"
        self.service.configure_seller_asp(seller_trn, "ASP_B")

        # Ingest first invoice
        self.service.ingest_invoice(
            seller_trn=seller_trn,
            invoice_number="INV-DUP-999",
            buyer_trn="100222222222002",
            issue_date="2026-10-23",
            total_amount=300.0,
            vat_amount=15.0,
        )

        # Duplicate ingest attempt rejected immediately
        with self.assertRaises(DuplicateInvoiceError):
            self.service.ingest_invoice(
                seller_trn=seller_trn,
                invoice_number="INV-DUP-999",
                buyer_trn="100222222222002",
                issue_date="2026-10-23",
                total_amount=300.0,
                vat_amount=15.0,
            )

        # Ensure ASP B was never hit with a duplicate
        self.assertEqual(self.mock_asp_b.submission_counter.get("INV-DUP-999", 0), 0)

    # --- Failure Case 3: Out-of-Order and Late Webhooks (ASP B) ---

    def test_out_of_order_and_duplicate_webhooks(self) -> None:
        seller_trn = "100777777777007"
        self.service.configure_seller_asp(seller_trn, "ASP_B")

        inv = self.service.ingest_invoice(
            seller_trn=seller_trn,
            invoice_number="INV-WEBHOOK-01",
            buyer_trn="100222222222002",
            issue_date="2026-10-23",
            total_amount=2000.0,
            vat_amount=100.0,
        )
        self.service.validate_and_enrich(inv.id)
        inv = self.service.submit_to_asp(inv.id)
        job_id = inv.external_id

        # 1. Out-of-order: TAX_CONFIRMED (C5) arrives BEFORE BUYER_RECEIVED (C3)
        h1, p1 = self.mock_asp_b.create_mock_webhook(job_id, "TAX_CONFIRMED", event_id="evt_c5_01")
        inv = self.service.process_webhook("ASP_B", h1, p1)
        self.assertEqual(inv.state, InvoiceState.REPORTED_C5)

        # 2. Duplicate webhook arrives (same event_id)
        dup = self.service.process_webhook("ASP_B", h1, p1)
        self.assertIsNone(dup)  # Safely dropped by event ledger

        # 3. BUYER_RECEIVED (C3) arrives -> completes lifecycle
        h2, p2 = self.mock_asp_b.create_mock_webhook(job_id, "BUYER_RECEIVED", event_id="evt_c3_02")
        inv = self.service.process_webhook("ASP_B", h2, p2)
        self.assertEqual(inv.state, InvoiceState.COMPLIANT_AND_DELIVERED)

        # 4. Very late QUEUED webhook arrives -> dropped safely as stale
        h3, p3 = self.mock_asp_b.create_mock_webhook(job_id, "QUEUED", event_id="evt_queued_late")
        late_inv = self.service.process_webhook("ASP_B", h3, p3)
        self.assertEqual(late_inv.state, InvoiceState.COMPLIANT_AND_DELIVERED)

    # --- Failure Case 4: Pre-Validation Schema Failure ---

    def test_schema_failure_pre_submission(self) -> None:
        # Invalid seller TRN (only 5 digits)
        inv = self.service.ingest_invoice(
            seller_trn="12345",
            invoice_number="INV-BAD-TRN",
            buyer_trn="100222222222002",
            issue_date="2026-10-23",
            total_amount=100.0,
            vat_amount=5.0,
        )
        inv = self.service.validate_and_enrich(inv.id)
        self.assertEqual(inv.state, InvoiceState.REJECTED)
        self.assertEqual(inv.errors[0].code, "PINT_AE_001")


if __name__ == "__main__":
    unittest.main()
