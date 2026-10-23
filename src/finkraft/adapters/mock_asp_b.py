"""Mock implementation of ASP B.

Characteristics:
- Asynchronous POST /v2/submissions returning 202 with job_id.
- Status updates via Webhook callbacks ONLY (no polling endpoint).
- NO duplicate checking (blind submissions will create duplicate tax filings at FTA).
- Status values: QUEUED, ACCEPTED, FAILED, BUYER_RECEIVED (C3), TAX_CONFIRMED (C5).
- Errors: {"errors": [{"rule": "...", "message": "..."}]}.
- Known behaviour: Webhooks can arrive late, out of order, or more than once.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from finkraft.adapters.base import ASPAdapter
from finkraft.exceptions import WebhookSignatureVerificationError
from finkraft.models import (
    ASPCapabilities,
    CanonicalInvoice,
    NormalizedError,
    NormalizedStatus,
    StatusUpdate,
    SubmissionResult,
)


class MockASPBAdapter(ASPAdapter):
    """Mock implementation of ASP B adapter."""

    ASP_ID = "ASP_B"
    WEBHOOK_SECRET = "secret_asp_b_key_2026"

    STATUS_MAP: Dict[str, NormalizedStatus] = {
        "QUEUED": NormalizedStatus.ACKNOWLEDGED,
        "ACCEPTED": NormalizedStatus.ACKNOWLEDGED,
        "FAILED": NormalizedStatus.REJECTED,
        "BUYER_RECEIVED": NormalizedStatus.DELIVERED_C3,
        "TAX_CONFIRMED": NormalizedStatus.REPORTED_C5,
    }

    def __init__(self, verify_signature: bool = True) -> None:
        self.verify_signature = verify_signature
        # Remote mock jobs: job_id -> record
        self._jobs: Dict[str, Dict[str, Any]] = {}
        # Count submissions per invoice number to demonstrate lack of duplicate checking
        self.submission_counter: Dict[str, int] = {}
        # Track seen webhook event IDs for idempotency auditing
        self.seen_webhook_events: Set[str] = set()

    def get_capabilities(self) -> ASPCapabilities:
        return ASPCapabilities(
            asp_id=self.ASP_ID,
            supports_sync_submit=False,
            supports_polling=False,
            supports_webhooks=True,
            rate_limit_rps=100,
            has_native_idempotency=False,  # NO duplicate checking!
        )

    def submit_invoice(self, invoice: CanonicalInvoice) -> SubmissionResult:
        # ASP B has NO duplicate checking! It will accept the submission every time.
        self.submission_counter[invoice.invoice_number] = (
            self.submission_counter.get(invoice.invoice_number, 0) + 1
        )

        job_id = f"job_asp_b_{uuid.uuid4().hex[:12]}"
        self._jobs[job_id] = {
            "job_id": job_id,
            "invoice_number": invoice.invoice_number,
            "seller_trn": invoice.seller_trn,
            "status": "QUEUED",
            "created_at": datetime.utcnow(),
        }

        # Returns HTTP 202 Accepted with job_id
        return SubmissionResult(
            success=True,
            is_ambiguous=False,
            external_id=job_id,
            initial_status=NormalizedStatus.ACKNOWLEDGED,
            raw_response={"status": 202, "job_id": job_id, "message": "Submission queued"},
        )

    def poll_status(self, external_id: str) -> StatusUpdate:
        raise NotImplementedError("ASP B does not provide a polling endpoint; updates arrive via webhooks.")

    def parse_webhook(self, headers: Dict[str, str], payload: Dict[str, Any]) -> StatusUpdate:
        # Validate HMAC signature if enabled
        if self.verify_signature:
            signature = headers.get("X-ASP-Signature") or headers.get("x-asp-signature")
            if not signature:
                raise WebhookSignatureVerificationError(self.ASP_ID, "Missing X-ASP-Signature header")

            computed = self.compute_signature(payload)
            if not hmac.compare_digest(signature, computed):
                raise WebhookSignatureVerificationError(self.ASP_ID, "Signature mismatch")

        event_id = headers.get("X-Event-ID") or payload.get("event_id", "")
        if event_id:
            self.seen_webhook_events.add(event_id)

        job_id = payload.get("job_id", "")
        raw_status = payload.get("status", "")
        norm_status = self.STATUS_MAP.get(raw_status, NormalizedStatus.REJECTED)

        normalized_errors: List[NormalizedError] = []
        raw_errors = payload.get("errors", [])
        for err in raw_errors:
            normalized_errors.append(
                NormalizedError(
                    code="ASP_B_ERR",
                    message=err.get("message", "Validation error"),
                    field_reference=err.get("rule"),
                )
            )

        event_time_str = payload.get("timestamp")
        event_time = (
            datetime.fromisoformat(event_time_str)
            if event_time_str
            else datetime.utcnow()
        )

        return StatusUpdate(
            external_id=job_id,
            status=norm_status,
            timestamp=event_time,
            errors=normalized_errors,
            raw_payload=payload,
        )

    # --- Webhook Simulation Helpers ---

    def compute_signature(self, payload: Dict[str, Any]) -> str:
        """Computes HMAC-SHA256 signature for payload."""
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hmac.new(self.WEBHOOK_SECRET.encode("utf-8"), data, hashlib.sha256).hexdigest()

    def create_mock_webhook(
        self,
        job_id: str,
        status: str,
        errors: Optional[List[Dict[str, str]]] = None,
        event_id: Optional[str] = None,
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """Generates a signed webhook payload and headers for testing."""
        evt_id = event_id or f"evt_{uuid.uuid4().hex[:8]}"
        payload = {
            "event_id": evt_id,
            "job_id": job_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "errors": errors or [],
        }
        headers = {
            "X-ASP-Signature": self.compute_signature(payload),
            "X-Event-ID": evt_id,
            "Content-Type": "application/json",
        }
        return headers, payload
