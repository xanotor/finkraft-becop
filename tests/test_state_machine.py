"""Unit tests for the Invoice State Machine."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from datetime import datetime

from finkraft.exceptions import InvalidStateTransitionError
from finkraft.models import Invoice, InvoiceState, NormalizedStatus
from finkraft.state_machine import InvoiceStateMachine


class TestInvoiceStateMachine(unittest.TestCase):

    def setUp(self) -> None:
        self.invoice = Invoice(
            seller_trn="100123456789001",
            invoice_number="INV-2026-001",
            buyer_trn="100987654321002",
            issue_date="2026-10-23",
            total_amount=1050.0,
            vat_amount=50.0,
        )

    def test_initial_state_is_draft(self) -> None:
        self.assertEqual(self.invoice.state, InvoiceState.DRAFT)
        self.assertEqual(len(self.invoice.history), 1)

    def test_valid_forward_progression(self) -> None:
        # DRAFT -> VALIDATED
        InvoiceStateMachine.transition(self.invoice, InvoiceState.VALIDATED, "Passed validation")
        self.assertEqual(self.invoice.state, InvoiceState.VALIDATED)

        # VALIDATED -> SUBMITTING
        InvoiceStateMachine.transition(self.invoice, InvoiceState.SUBMITTING, "Locked for submit")
        self.assertEqual(self.invoice.state, InvoiceState.SUBMITTING)

        # SUBMITTING -> ACKNOWLEDGED_C2
        InvoiceStateMachine.transition(self.invoice, InvoiceState.ACKNOWLEDGED_C2, "Accepted by ASP")
        self.assertEqual(self.invoice.state, InvoiceState.ACKNOWLEDGED_C2)

        # ACKNOWLEDGED_C2 -> VALIDATED_C2
        InvoiceStateMachine.transition(self.invoice, InvoiceState.VALIDATED_C2, "ASP validated")
        self.assertEqual(self.invoice.state, InvoiceState.VALIDATED_C2)

    def test_invalid_state_transition_raises_error(self) -> None:
        # Cannot jump from DRAFT straight to DELIVERED_C3
        with self.assertRaises(InvalidStateTransitionError) as ctx:
            InvoiceStateMachine.transition(self.invoice, InvoiceState.DELIVERED_C3)
        self.assertIn("DRAFT", str(ctx.exception))
        self.assertIn("DELIVERED_C3", str(ctx.exception))

        # Cannot jump from DRAFT straight to COMPLIANT_AND_DELIVERED
        with self.assertRaises(InvalidStateTransitionError):
            InvoiceStateMachine.transition(self.invoice, InvoiceState.COMPLIANT_AND_DELIVERED)

    def test_terminal_state_cannot_transition(self) -> None:
        # Set invoice to COMPLIANT_AND_DELIVERED
        self.invoice.state = InvoiceState.COMPLIANT_AND_DELIVERED

        # Attempting any transition from terminal state must fail
        with self.assertRaises(InvalidStateTransitionError):
            InvoiceStateMachine.transition(self.invoice, InvoiceState.DRAFT)

        with self.assertRaises(InvalidStateTransitionError):
            InvoiceStateMachine.transition(self.invoice, InvoiceState.REJECTED)

    def test_c3_then_c5_milestone_progression(self) -> None:
        """Scenario: C3 (buyer delivery) arrives first, followed by C5 (FTA tax clearance)."""
        InvoiceStateMachine.transition(self.invoice, InvoiceState.VALIDATED)
        InvoiceStateMachine.transition(self.invoice, InvoiceState.SUBMITTING)
        InvoiceStateMachine.transition(self.invoice, InvoiceState.ACKNOWLEDGED_C2)

        # 1. C3 Buyer delivery arrives
        changed = InvoiceStateMachine.apply_normalized_status(
            self.invoice, NormalizedStatus.DELIVERED_C3
        )
        self.assertTrue(changed)
        self.assertEqual(self.invoice.state, InvoiceState.DELIVERED_C3)
        self.assertIsNotNone(self.invoice.c3_delivered_at)
        self.assertIsNone(self.invoice.c5_reported_at)

        # 2. C5 FTA tax clearance arrives -> transitions to COMPLIANT_AND_DELIVERED
        changed = InvoiceStateMachine.apply_normalized_status(
            self.invoice, NormalizedStatus.REPORTED_C5
        )
        self.assertTrue(changed)
        self.assertEqual(self.invoice.state, InvoiceState.COMPLIANT_AND_DELIVERED)
        self.assertIsNotNone(self.invoice.c5_reported_at)

    def test_c5_then_c3_milestone_progression(self) -> None:
        """Scenario: C5 (FTA clearance) arrives first, followed by C3 (buyer delivery)."""
        InvoiceStateMachine.transition(self.invoice, InvoiceState.VALIDATED)
        InvoiceStateMachine.transition(self.invoice, InvoiceState.SUBMITTING)
        InvoiceStateMachine.transition(self.invoice, InvoiceState.ACKNOWLEDGED_C2)

        # 1. C5 FTA clearance arrives first
        changed = InvoiceStateMachine.apply_normalized_status(
            self.invoice, NormalizedStatus.REPORTED_C5
        )
        self.assertTrue(changed)
        self.assertEqual(self.invoice.state, InvoiceState.REPORTED_C5)
        self.assertIsNotNone(self.invoice.c5_reported_at)
        self.assertIsNone(self.invoice.c3_delivered_at)

        # 2. C3 Buyer delivery arrives -> transitions to COMPLIANT_AND_DELIVERED
        changed = InvoiceStateMachine.apply_normalized_status(
            self.invoice, NormalizedStatus.DELIVERED_C3
        )
        self.assertTrue(changed)
        self.assertEqual(self.invoice.state, InvoiceState.COMPLIANT_AND_DELIVERED)
        self.assertIsNotNone(self.invoice.c3_delivered_at)

    def test_stale_or_duplicate_status_ignored_idempotently(self) -> None:
        """Out-of-order stale callbacks must be dropped safely without raising exceptions."""
        InvoiceStateMachine.transition(self.invoice, InvoiceState.VALIDATED)
        InvoiceStateMachine.transition(self.invoice, InvoiceState.SUBMITTING)
        InvoiceStateMachine.transition(self.invoice, InvoiceState.ACKNOWLEDGED_C2)
        InvoiceStateMachine.apply_normalized_status(self.invoice, NormalizedStatus.REPORTED_C5)
        self.assertEqual(self.invoice.state, InvoiceState.REPORTED_C5)

        # Late arrival of ACKNOWLEDGED must be ignored
        changed = InvoiceStateMachine.apply_normalized_status(
            self.invoice, NormalizedStatus.ACKNOWLEDGED
        )
        self.assertFalse(changed)
        self.assertEqual(self.invoice.state, InvoiceState.REPORTED_C5)

        # Late arrival of VALIDATED must be ignored
        changed = InvoiceStateMachine.apply_normalized_status(
            self.invoice, NormalizedStatus.VALIDATED
        )
        self.assertFalse(changed)
        self.assertEqual(self.invoice.state, InvoiceState.REPORTED_C5)


if __name__ == "__main__":
    unittest.main()
