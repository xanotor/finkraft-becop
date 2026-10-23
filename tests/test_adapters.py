"""Unit tests for Mock ASP Adapters (ASP A and ASP B)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from finkraft.adapters.mock_asp_a import MockASPAAdapter
from finkraft.adapters.mock_asp_b import MockASPBAdapter
from finkraft.exceptions import WebhookSignatureVerificationError
from finkraft.models import CanonicalInvoice, NormalizedStatus


class TestAdapters(unittest.TestCase):

    def setUp(self) -> None:
        self.invoice = CanonicalInvoice(
            seller_trn="100123456789001",
            invoice_number="INV-ASP-01",
            buyer_trn="100987654321002",
            issue_date="2026-10-23",
            total_amount=1500.0,
            vat_amount=75.0,
        )

    # --- ASP A Tests ---

    def test_asp_a_sync_submit_and_polling(self) -> None:
        adapter = MockASPAAdapter()
        caps = adapter.get_capabilities()
        self.assertTrue(caps.supports_sync_submit)
        self.assertTrue(caps.supports_polling)
        self.assertFalse(caps.supports_webhooks)

        # Synchronous submission
        result = adapter.submit_invoice(self.invoice)
        self.assertTrue(result.success)
        self.assertFalse(result.is_ambiguous)
        self.assertIsNotNone(result.external_id)
        self.assertEqual(result.initial_status, NormalizedStatus.ACKNOWLEDGED)

        # Poll status
        poll_res = adapter.poll_status(result.external_id)
        self.assertEqual(poll_res.status, NormalizedStatus.ACKNOWLEDGED)

        # Update remote status and poll again
        adapter.set_remote_status(result.external_id, "VALIDATED")
        poll_res2 = adapter.poll_status(result.external_id)
        self.assertEqual(poll_res2.status, NormalizedStatus.VALIDATED)

    def test_asp_a_native_idempotency_409(self) -> None:
        adapter = MockASPAAdapter()
        # First submission succeeds
        res1 = adapter.submit_invoice(self.invoice)
        self.assertTrue(res1.success)

        # Second submission with same invoice number is rejected with 409 Conflict
        res2 = adapter.submit_invoice(self.invoice)
        self.assertFalse(res2.success)
        self.assertEqual(res2.errors[0].code, "409")

    def test_asp_a_timeout_simulation(self) -> None:
        adapter = MockASPAAdapter()
        adapter.simulate_timeout_post_acceptance = True

        result = adapter.submit_invoice(self.invoice)
        self.assertFalse(result.success)
        self.assertTrue(result.is_ambiguous)
        self.assertIsNone(result.external_id)
        self.assertEqual(result.errors[0].code, "TIMEOUT")

        # Remote record was registered before timeout, so lookup succeeds
        sub_id = adapter.lookup_by_invoice_number(self.invoice.invoice_number)
        self.assertIsNotNone(sub_id)

    def test_asp_a_webhook_not_supported(self) -> None:
        adapter = MockASPAAdapter()
        with self.assertRaises(NotImplementedError):
            adapter.parse_webhook({}, {})

    # --- ASP B Tests ---

    def test_asp_b_async_submit_and_no_duplicate_check(self) -> None:
        adapter = MockASPBAdapter()
        caps = adapter.get_capabilities()
        self.assertFalse(caps.supports_sync_submit)
        self.assertFalse(caps.supports_polling)
        self.assertTrue(caps.supports_webhooks)
        self.assertFalse(caps.has_native_idempotency)

        # First submission
        res1 = adapter.submit_invoice(self.invoice)
        self.assertTrue(res1.success)
        self.assertEqual(res1.raw_response["status"], 202)
        job1 = res1.external_id

        # Second submission (demonstrates LACK of duplicate checking!)
        res2 = adapter.submit_invoice(self.invoice)
        self.assertTrue(res2.success)
        job2 = res2.external_id

        self.assertNotEqual(job1, job2)
        self.assertEqual(adapter.submission_counter[self.invoice.invoice_number], 2)

    def test_asp_b_polling_not_supported(self) -> None:
        adapter = MockASPBAdapter()
        with self.assertRaises(NotImplementedError):
            adapter.poll_status("job_123")

    def test_asp_b_webhook_parsing_and_signature_verification(self) -> None:
        adapter = MockASPBAdapter(verify_signature=True)
        headers, payload = adapter.create_mock_webhook(
            job_id="job_asp_b_test1",
            status="BUYER_RECEIVED",
        )

        update = adapter.parse_webhook(headers, payload)
        self.assertEqual(update.external_id, "job_asp_b_test1")
        self.assertEqual(update.status, NormalizedStatus.DELIVERED_C3)

    def test_asp_b_webhook_signature_failure(self) -> None:
        adapter = MockASPBAdapter(verify_signature=True)
        headers, payload = adapter.create_mock_webhook(
            job_id="job_asp_b_test2",
            status="TAX_CONFIRMED",
        )
        # Tamper with signature
        headers["X-ASP-Signature"] = "invalid_tampered_signature"

        with self.assertRaises(WebhookSignatureVerificationError):
            adapter.parse_webhook(headers, payload)


if __name__ == "__main__":
    unittest.main()
