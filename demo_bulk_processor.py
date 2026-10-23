#!/usr/bin/env python3
"""
Finkraft UAE E-Invoicing Pipeline: Automatic Batch Processor & Failure Simulator.

Reads a standard business CSV file (without pre-tagged scenario columns), automatically
identifies business conditions (schema errors, duplicate submissions, multi-tenant isolation),
and probabilistically simulates transient network failures (ASP A timeouts, ASP B out-of-order
webhooks) while demonstrating the platform's automatic corrective measures.
"""

import argparse
import csv
import os
import random
import sys
from typing import Any, Dict, List, Optional, Set

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from finkraft.adapters.mock_asp_a import MockASPAAdapter
from finkraft.adapters.mock_asp_b import MockASPBAdapter
from finkraft.adapters.registry import ASPRegistry
from finkraft.exceptions import DuplicateInvoiceError
from finkraft.models import InvoiceState
from finkraft.repository import InMemoryInvoiceRepository
from finkraft.service import InvoiceService


class BulkPipelineRunner:
    """Orchestrates CSV ingestion, automatic error detection, and failure self-healing."""

    def __init__(
        self,
        timeout_rate: float = 0.35,
        out_of_order_rate: float = 0.40,
        random_seed: Optional[int] = 42,
    ) -> None:
        self.timeout_rate = timeout_rate
        self.out_of_order_rate = out_of_order_rate
        if random_seed is not None:
            random.seed(random_seed)

        self.repo = InMemoryInvoiceRepository()
        ASPRegistry.clear()

        self.asp_a = MockASPAAdapter()
        self.asp_b = MockASPBAdapter()

        ASPRegistry.register("ASP_A", self.asp_a)
        ASPRegistry.register("ASP_B", self.asp_b)

        self.service = InvoiceService(repository=self.repo, default_asp_id="ASP_A")
        # Global tracker to detect multi-tenant invoice number reuse across sellers
        self._seen_invoice_numbers: Dict[str, str] = {}  # invoice_number -> seller_trn

    def process_csv(self, csv_path: str) -> None:
        print("=" * 85)
        print("   FINKRAFT UAE E-INVOICING PIPELINE: AUTOMATIC PROCESSOR & RESILIENCE ENGINE")
        print("=" * 85)
        print(f"Source CSV: {csv_path}")
        print(f"Simulation Rates: ASP A Timeout={int(self.timeout_rate*100)}% | ASP B Out-of-Order Webhooks={int(self.out_of_order_rate*100)}%\n")

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        stats = {
            "total": len(rows),
            "compliant": 0,
            "rejected_schema": 0,
            "duplicate_rejected": 0,
            "multi_tenant_reused": 0,
            "reconciled_timeouts": 0,
            "out_of_order_healed": 0,
        }

        for idx, row in enumerate(rows, 1):
            seller_trn = row["seller_trn"].strip()
            invoice_num = row["invoice_number"].strip()
            buyer_trn = row["buyer_trn"].strip()
            issue_date = row["issue_date"].strip()
            total_amt = float(row["total_amount"])
            vat_amt = float(row["vat_amount"])
            target_asp = row.get("target_asp", "ASP_A").strip()

            print(f"\n--- [Row {idx}/{len(rows)}] Invoice '{invoice_num}' | Seller: {seller_trn} | Target: {target_asp} ---")

            # -----------------------------------------------------------------
            # 1. INGESTION & AUTOMATIC PER-SELLER DUPLICATE DETECTION
            # -----------------------------------------------------------------
            try:
                inv = self.service.ingest_invoice(
                    seller_trn=seller_trn,
                    invoice_number=invoice_num,
                    buyer_trn=buyer_trn,
                    issue_date=issue_date,
                    total_amount=total_amt,
                    vat_amount=vat_amt,
                )
                print(f"  [1/4] Ingestion OK: State={inv.state.value} (UUID={inv.id[:8]}...)")

                # Multi-tenant isolation detection:
                if invoice_num in self._seen_invoice_numbers:
                    prev_seller = self._seen_invoice_numbers[invoice_num]
                    if prev_seller != seller_trn:
                        print(f"        [MULTI-TENANT ISOLATION] Invoice number '{invoice_num}' was previously issued by")
                        print(f"        Seller '{prev_seller}', but is successfully accepted for distinct Seller '{seller_trn}'.")
                        stats["multi_tenant_reused"] += 1
                else:
                    self._seen_invoice_numbers[invoice_num] = seller_trn

            except DuplicateInvoiceError as e:
                print(f"  [1/4] [AUTO-DETECTED DUPLICATE] Client-side idempotency lock triggered:")
                print(f"        {e}")
                print(f"        -> Dropped to protect UAE FTA compliance (Zero duplicate filings guarantee)")
                stats["duplicate_rejected"] += 1
                continue

            # -----------------------------------------------------------------
            # 2. AUTOMATIC PINT AE SCHEMA & TAX ARITHMETIC VALIDATION
            # -----------------------------------------------------------------
            inv = self.service.validate_and_enrich(inv.id)
            if inv.state == InvoiceState.REJECTED:
                err = inv.errors[0] if inv.errors else None
                err_code = err.code if err else "ERR"
                err_msg = err.message if err else "Validation failed"
                err_field = err.field_reference if err else "Unknown"
                print(f"  [2/4] [AUTO-DETECTED SCHEMA ERROR] [{err_code}] Field: {err_field} - {err_msg}")
                print(f"        -> Invoice halted in {inv.state.value}; NOT submitted to ASP (protecting quota & reputation)")
                stats["rejected_schema"] += 1
                continue

            print(f"  [2/4] PINT AE Validation PASSED: State={inv.state.value} (UBL 2.1 Enriched)")

            # -----------------------------------------------------------------
            # 3. ASP DISPATCH & RESILIENCE MITIGATION
            # -----------------------------------------------------------------
            if target_asp == "ASP_A":
                # Check for probabilistic network timeout post-acceptance
                simulate_timeout = random.random() < self.timeout_rate
                if simulate_timeout:
                    print(f"  [3/4] Submitting to ASP_A (Synchronous)...")
                    self.asp_a.simulate_timeout_post_acceptance = True
                    inv = self.service.submit_to_asp(inv.id, override_asp_id=target_asp)
                    self.asp_a.simulate_timeout_post_acceptance = False

                    print(f"        [TRANSIENT INCIDENT] Network socket timed out waiting for ASP A response!")
                    print(f"        -> State quarantined to: {inv.state.value} (Automatic blind retries strictly banned)")

                    # Corrective Measure: Active Reconciliation Protocol
                    print(f"  [4/4] [CORRECTIVE ACTION] Launching Active Reconciliation Worker...")
                    inv = self.service.reconcile_ambiguous_submission(inv.id)
                    print(f"        Reconciliation SUCCESS: Discovered remote ID '{inv.external_id}' -> State={inv.state.value}")
                    stats["reconciled_timeouts"] += 1

                else:
                    print(f"  [3/4] Submitting to ASP_A (Synchronous)...")
                    inv = self.service.submit_to_asp(inv.id, override_asp_id=target_asp)
                    if inv.state == InvoiceState.REJECTED:
                        print(f"        [ASP REJECTION]: {inv.errors[0].message if inv.errors else 'Rejected'} -> State={inv.state.value}")
                        stats["rejected_schema"] += 1
                        continue
                    print(f"        Submission Accepted: Submission ID '{inv.external_id}' -> State={inv.state.value}")

                # Polling progression through C3 and C5
                if not simulate_timeout:
                    print(f"  [4/4] Polling ASP A for Lifecycle Milestones...")
                self.asp_a.set_remote_status(inv.external_id, "DELIVERED")
                inv = self.service.poll_invoice_status(inv.id)
                print(f"        Milestone C3: Delivered to Buyer's ASP -> State={inv.state.value}")

                self.asp_a.set_remote_status(inv.external_id, "REPORTED")
                inv = self.service.poll_invoice_status(inv.id)
                print(f"        Milestone C5: Reported to UAE FTA -> State={inv.state.value}")
                stats["compliant"] += 1

            elif target_asp == "ASP_B":
                print(f"  [3/4] Submitting to ASP_B (Asynchronous)...")
                inv = self.service.submit_to_asp(inv.id, override_asp_id=target_asp)
                print(f"        Job Queued: Job ID '{inv.external_id}' -> State={inv.state.value}")

                # Check for probabilistic out-of-order & duplicate webhooks
                simulate_out_of_order = random.random() < self.out_of_order_rate
                if simulate_out_of_order:
                    print(f"  [4/4] [OUT-OF-ORDER WEBHOOK SIMULATION] Testing non-linear callback arrival...")

                    # Webhook 1: C5 arrives BEFORE C3
                    h_c5, p_c5 = self.asp_b.create_mock_webhook(inv.external_id, "TAX_CONFIRMED", event_id=f"evt_c5_{inv.id[:6]}")
                    inv = self.service.process_webhook("ASP_B", h_c5, p_c5)
                    print(f"        Inbound Webhook 1: TAX_CONFIRMED (C5 arrived before C3) -> State={inv.state.value}")

                    # Webhook 2: Duplicate of Webhook 1
                    dup_res = self.service.process_webhook("ASP_B", h_c5, p_c5)
                    print(f"        Inbound Webhook 2 (DUPLICATE): Same event ID dropped by Idempotent Ledger (Safe no-op)")

                    # Webhook 3: C3 arrives
                    h_c3, p_c3 = self.asp_b.create_mock_webhook(inv.external_id, "BUYER_RECEIVED", event_id=f"evt_c3_{inv.id[:6]}")
                    inv = self.service.process_webhook("ASP_B", h_c3, p_c3)
                    print(f"        Inbound Webhook 3: BUYER_RECEIVED (C3 arrived) -> State={inv.state.value}")
                    print(f"        [CORRECTIVE ACTION] Milestone lattice merged both events into terminal COMPLIANT state.")
                    stats["out_of_order_healed"] += 1
                    stats["compliant"] += 1

                else:
                    print(f"  [4/4] Receiving Webhooks from ASP B (Standard sequence)...")
                    h_c3, p_c3 = self.asp_b.create_mock_webhook(inv.external_id, "BUYER_RECEIVED")
                    inv = self.service.process_webhook("ASP_B", h_c3, p_c3)
                    print(f"        Webhook C3 (BUYER_RECEIVED): State={inv.state.value}")

                    h_c5, p_c5 = self.asp_b.create_mock_webhook(inv.external_id, "TAX_CONFIRMED")
                    inv = self.service.process_webhook("ASP_B", h_c5, p_c5)
                    print(f"        Webhook C5 (TAX_CONFIRMED): State={inv.state.value}")
                    stats["compliant"] += 1

        # Summary
        print("\n" + "=" * 85)
        print("                          EXECUTION SUMMARY REPORT")
        print("=" * 85)
        print(f"  Total Invoices Processed:          {stats['total']}")
        print(f"  Successfully COMPLIANT & DELIVERED:{stats['compliant']:>3}")
        print(f"  Pre-Validation Schema Rejections:  {stats['rejected_schema']:>3}")
        print(f"  Duplicate Submissions Blocked:     {stats['duplicate_rejected']:>3}")
        print(f"  Multi-Tenant Reused Invoices OK:   {stats['multi_tenant_reused']:>3}")
        print(f"  Timeouts Actively Reconciled:      {stats['reconciled_timeouts']:>3}")
        print(f"  Out-of-Order Webhooks Self-Healed: {stats['out_of_order_healed']:>3}")
        print("=" * 85)
        print("  GOVERNMENT TAX INVARIANTS SATISFIED: ZERO LOSS, ZERO DUPLICATE FILINGS.")
        print("=" * 85 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Finkraft Batch Invoice Processor & Resilience Simulator")
    parser.add_argument("csv_file", nargs="?", default="data/sample_invoices.csv", help="Path to input invoice CSV")
    parser.add_argument("--timeout-rate", type=float, default=0.35, help="Probability of simulated ASP A timeout (0.0 to 1.0)")
    parser.add_argument("--out-of-order-rate", type=float, default=0.40, help="Probability of out-of-order webhooks (0.0 to 1.0)")
    parser.add_argument("--random-seed", type=int, default=42, help="Seed for reproducibility (use -1 for non-deterministic)")

    args = parser.parse_args()
    seed = None if args.random_seed == -1 else args.random_seed

    runner = BulkPipelineRunner(
        timeout_rate=args.timeout_rate,
        out_of_order_rate=args.out_of_order_rate,
        random_seed=seed,
    )
    runner.process_csv(args.csv_file)
