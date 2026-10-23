"""Invoice State Machine enforcing UAE 5-Corner transition rules and milestone progression."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional, Set

from finkraft.exceptions import InvalidStateTransitionError
from finkraft.models import Invoice, InvoiceState, NormalizedError, NormalizedStatus


class InvoiceStateMachine:
    """
    Governs state transitions for invoices in Finkraft.
    Enforces a monotonic transition lattice, prevents illegal state jumps,
    and manages concurrent/out-of-order C3 (Buyer ASP) and C5 (FTA) milestones.
    """

    # Explicit directed graph of permissible forward transitions
    VALID_TRANSITIONS: Dict[InvoiceState, Set[InvoiceState]] = {
        InvoiceState.DRAFT: {
            InvoiceState.VALIDATED,
            InvoiceState.REJECTED,
        },
        InvoiceState.VALIDATED: {
            InvoiceState.SUBMITTING,
            InvoiceState.REJECTED,
        },
        InvoiceState.SUBMITTING: {
            InvoiceState.ACKNOWLEDGED_C2,
            InvoiceState.SUBMISSION_AMBIGUOUS,
            InvoiceState.REJECTED,
        },
        InvoiceState.SUBMISSION_AMBIGUOUS: {
            InvoiceState.ACKNOWLEDGED_C2,     # Reconciled: found at ASP
            InvoiceState.SUBMITTING,          # Reconciled: verified absent, safe retry
            InvoiceState.REJECTED,            # Unrecoverable error
        },
        InvoiceState.ACKNOWLEDGED_C2: {
            InvoiceState.VALIDATED_C2,
            InvoiceState.DELIVERED_C3,        # Some ASPs jump straight to delivery
            InvoiceState.REPORTED_C5,         # Some ASPs jump straight to FTA clearance
            InvoiceState.REJECTED,
        },
        InvoiceState.VALIDATED_C2: {
            InvoiceState.DELIVERED_C3,
            InvoiceState.REPORTED_C5,
            InvoiceState.REJECTED,
        },
        InvoiceState.DELIVERED_C3: {
            InvoiceState.COMPLIANT_AND_DELIVERED,  # C5 milestone arrived
            InvoiceState.REJECTED,
        },
        InvoiceState.REPORTED_C5: {
            InvoiceState.COMPLIANT_AND_DELIVERED,  # C3 milestone arrived
            InvoiceState.REJECTED,
        },
        # Terminal states have no valid forward transitions
        InvoiceState.COMPLIANT_AND_DELIVERED: set(),
        InvoiceState.REJECTED: set(),
    }

    # Ordinal ranking for detecting stale / backwards transitions
    STATE_RANK: Dict[InvoiceState, int] = {
        InvoiceState.DRAFT: 0,
        InvoiceState.VALIDATED: 1,
        InvoiceState.SUBMITTING: 2,
        InvoiceState.SUBMISSION_AMBIGUOUS: 2,
        InvoiceState.ACKNOWLEDGED_C2: 3,
        InvoiceState.VALIDATED_C2: 4,
        InvoiceState.DELIVERED_C3: 5,
        InvoiceState.REPORTED_C5: 5,
        InvoiceState.COMPLIANT_AND_DELIVERED: 6,
        InvoiceState.REJECTED: 6,
    }

    @classmethod
    def can_transition(cls, current_state: InvoiceState, target_state: InvoiceState) -> bool:
        """Checks if a transition from current_state to target_state is permissible."""
        return target_state in cls.VALID_TRANSITIONS.get(current_state, set())

    @classmethod
    def transition(
        cls,
        invoice: Invoice,
        target_state: InvoiceState,
        reason: str = "",
        errors: Optional[list] = None,
    ) -> None:
        """
        Executes a direct state transition on an invoice.
        Raises InvalidStateTransitionError if the transition is illegal.
        """
        if invoice.state == target_state:
            # Idempotent re-affirmation of current state
            return

        if not cls.can_transition(invoice.state, target_state):
            raise InvalidStateTransitionError(
                from_state=invoice.state.value,
                to_state=target_state.value,
                reason=reason or f"Transition from '{invoice.state.value}' to '{target_state.value}' is disallowed.",
            )

        if errors:
            invoice.errors.extend(errors)

        invoice.record_transition(target_state, reason=reason)

    @classmethod
    def apply_normalized_status(
        cls,
        invoice: Invoice,
        status: NormalizedStatus,
        event_time: Optional[datetime] = None,
        errors: Optional[list] = None,
        reason: str = "",
    ) -> bool:
        """
        Applies a normalized status from an ASP (via polling or webhook) to an invoice.
        Resolves out-of-order C3 and C5 arrivals into the terminal COMPLIANT_AND_DELIVERED state.
        Returns True if state changed, False if safely ignored as an idempotent or stale event.
        """
        now = event_time or datetime.utcnow()

        # Handle fatal rejection
        if status == NormalizedStatus.REJECTED:
            if invoice.state == InvoiceState.COMPLIANT_AND_DELIVERED:
                # Cannot reject an invoice that was already cleared by FTA and delivered
                raise InvalidStateTransitionError(
                    from_state=invoice.state.value,
                    to_state=InvoiceState.REJECTED.value,
                    reason="Cannot reject an invoice that is already COMPLIANT_AND_DELIVERED",
                )
            cls.transition(invoice, InvoiceState.REJECTED, reason=reason or "Rejected by ASP", errors=errors)
            return True

        # Terminal state protects against retroactive updates
        if invoice.state == InvoiceState.COMPLIANT_AND_DELIVERED:
            # Idempotent ignore: invoice is already fully cleared and delivered
            return False

        if invoice.state == InvoiceState.REJECTED:
            # Rejection is terminal
            return False

        # Process C3 Buyer Delivery Milestone
        if status == NormalizedStatus.DELIVERED_C3:
            invoice.c3_delivered_at = invoice.c3_delivered_at or now

            if invoice.c5_reported_at is not None or invoice.state == InvoiceState.REPORTED_C5:
                # C5 already confirmed! Advance directly to terminal success
                cls.transition(
                    invoice,
                    InvoiceState.COMPLIANT_AND_DELIVERED,
                    reason="C3 Buyer Delivery confirmed; C5 FTA clearance already satisfied",
                )
                return True

            if invoice.state != InvoiceState.DELIVERED_C3:
                cls.transition(
                    invoice,
                    InvoiceState.DELIVERED_C3,
                    reason="C3 Buyer Delivery confirmed; awaiting C5 FTA clearance",
                )
                return True
            return False

        # Process C5 FTA Clearance Milestone
        if status == NormalizedStatus.REPORTED_C5:
            invoice.c5_reported_at = invoice.c5_reported_at or now

            if invoice.c3_delivered_at is not None or invoice.state == InvoiceState.DELIVERED_C3:
                # C3 already confirmed! Advance directly to terminal success
                cls.transition(
                    invoice,
                    InvoiceState.COMPLIANT_AND_DELIVERED,
                    reason="C5 FTA clearance confirmed; C3 Buyer Delivery already satisfied",
                )
                return True

            if invoice.state != InvoiceState.REPORTED_C5:
                cls.transition(
                    invoice,
                    InvoiceState.REPORTED_C5,
                    reason="C5 FTA clearance confirmed; awaiting C3 Buyer Delivery",
                )
                return True
            return False

        # Handle earlier lifecycle states: ACKNOWLEDGED, VALIDATED
        if status == NormalizedStatus.ACKNOWLEDGED:
            if cls.STATE_RANK[invoice.state] >= cls.STATE_RANK[InvoiceState.ACKNOWLEDGED_C2]:
                # Stale duplicate callback (e.g. late QUEUED/ACCEPTED webhook) -> safe no-op
                return False
            cls.transition(invoice, InvoiceState.ACKNOWLEDGED_C2, reason=reason or "Acknowledged by C2 ASP")
            return True

        if status == NormalizedStatus.VALIDATED:
            if cls.STATE_RANK[invoice.state] >= cls.STATE_RANK[InvoiceState.VALIDATED_C2]:
                # Stale duplicate callback -> safe no-op
                return False
            cls.transition(invoice, InvoiceState.VALIDATED_C2, reason=reason or "Validated by C2 ASP")
            return True

        return False
