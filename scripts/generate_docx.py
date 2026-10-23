#!/usr/bin/env python3
"""
Generates a professionally styled Microsoft Word document (.docx)
for the Finkraft CTO Take-Home Assignment Submission.
"""

import os
import sys

# Add vendor directory
vendor_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vendor"))
if vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)

import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

NAVY_HEX = "13325B"
NAVY_RGB = RGBColor(19, 50, 91)
DARK_TEXT = RGBColor(35, 35, 35)
MUTED_TEXT = RGBColor(100, 110, 120)
BORDER_GRAY = "D1D5DB"
BG_LIGHT_GRAY = "F3F4F6"
BG_LIGHT_BLUE = "EFF6FF"
BORDER_BLUE = "93C5FD"


def set_cell_background(cell, hex_color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tcPr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def add_callout_box(doc, text: str, title: str = "", hex_bg=BG_LIGHT_GRAY, hex_border=BORDER_GRAY):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    set_cell_background(cell, hex_bg)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=200)

    # Set left border thick
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{NAVY_HEX}"/>'
        f'<w:top w:val="single" w:sz="4" w:space="0" w:color="{hex_border}"/>'
        f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="{hex_border}"/>'
        f'<w:right w:val="single" w:sz="4" w:space="0" w:color="{hex_border}"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    if title:
        run_t = p.add_run(title + "\n")
        run_t.bold = True
        run_t.font.name = "Calibri"
        run_t.font.size = Pt(9.5)
        run_t.font.color.rgb = NAVY_RGB

    run_body = p.add_run(text)
    run_body.font.name = "Calibri"
    run_body.font.size = Pt(9.0)
    run_body.font.color.rgb = DARK_TEXT

    # Spacer after table
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(4)


def style_table(table, col_widths, headers, data_rows):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    # Header row
    hdr_cells = table.rows[0].cells
    for i, h_text in enumerate(headers):
        hdr_cells[i].text = h_text
        set_cell_background(hdr_cells[i], NAVY_HEX)
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=150, right=150)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.font.name = "Calibri"
            run.font.size = Pt(8.5)
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)

    # Data rows
    for r_idx, row_data in enumerate(data_rows):
        row_cells = table.add_row().cells
        bg_col = "FFFFFF" if r_idx % 2 == 0 else "F9FAFB"
        for c_idx, val in enumerate(row_data):
            row_cells[c_idx].text = val
            set_cell_background(row_cells[c_idx], bg_col)
            set_cell_margins(row_cells[c_idx], top=80, bottom=80, left=140, right=140)
            p = row_cells[c_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.font.name = "Calibri"
                run.font.size = Pt(8.0)
                run.font.color.rgb = DARK_TEXT

    # Apply column widths
    for row in table.rows:
        for i, w in enumerate(col_widths):
            row.cells[i].width = Inches(w)


def build_docx(output_path: str):
    doc = Document()

    # Set 0.75-inch margins
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Document Title Block
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(2)
    run_t = p_title.add_run("Finkraft B2B E-Invoicing Platform: Master CTO Submission")
    run_t.font.name = "Calibri"
    run_t.font.size = Pt(20)
    run_t.font.bold = True
    run_t.font.color.rgb = NAVY_RGB

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(12)
    run_s = p_sub.add_run("UAE Federal Tax Authority (FTA) Peppol 5-Corner DCTCE Compliance Platform\nCandidate: CTO Finalist | Submission Deliverable: Parts 1, 2, 3 & AI Appendix")
    run_s.font.name = "Calibri"
    run_s.font.size = Pt(10)
    run_s.font.color.rgb = MUTED_TEXT

    # Divider
    p_div = doc.add_paragraph()
    p_div.paragraph_format.space_before = Pt(0)
    p_div.paragraph_format.space_after = Pt(12)
    run_d = p_div.add_run("―" * 55)
    run_d.font.color.rgb = RGBColor(200, 205, 215)

    # =========================================================================
    # PART 1: ARCHITECTURE DESIGN NOTE
    # =========================================================================
    h1 = doc.add_heading(level=1)
    run_h1 = h1.add_run("Part 1: Architecture Design Note (Max 2 Pages)")
    run_h1.font.name = "Calibri"
    run_h1.font.color.rgb = NAVY_RGB

    # 1. Context & Assumptions
    h2 = doc.add_heading(level=2)
    run_h2 = h2.add_run("1. Business Context & Explicit Assumptions")
    run_h2.font.name = "Calibri"
    run_h2.font.color.rgb = NAVY_RGB

    doc.add_paragraph(
        "Under the UAE Federal Tax Authority (FTA) mandate, e-invoicing is governed by a Decentralized Continuous "
        "Transaction Control and Exchange (DCTCE) 5-Corner Model: C1 (Seller / Finkraft Customer) -> C2 (Seller ASP / "
        "Finkraft Integration Point) -> C3 (Buyer ASP) -> C4 (Buyer), with concurrent C5 (FTA Clearance). "
        "Invoice records represent sovereign tax documents: zero invoices may be lost, and zero duplicates may be filed."
    )

    add_callout_box(
        doc,
        "* Business Key Uniqueness: Compound key (seller_trn, invoice_number) is globally unique and immutable.\n"
        "* Pre-Submission Enrichment: Finkraft validates and enriches raw customer feeds into compliant PINT AE UBL 2.1 XML prior to ASP dispatch. Schema errors (BT-48, bad TRNs) are trapped internally.\n"
        "* ASP A Profile: Synchronous POST /invoices (200), polling GET, 409 duplicate check, 10 req/s limit; network timeouts occasionally occur AFTER acceptance.\n"
        "* ASP B Profile: Asynchronous POST /v2/submissions (202), webhooks only, ZERO duplicate checks, out-of-order/duplicate webhooks.\n"
        "* ASP Switching: In-flight invoices finish tracking on originating ASP adapter; new submissions route to updated preferred ASP.",
        title="Explicit Architectural Assumptions",
        hex_bg=BG_LIGHT_GRAY,
    )

    # 2. Unified Adapter Contract
    h2 = doc.add_heading(level=2)
    run_h2 = h2.add_run("2. Unified Adapter Contract & Dynamic ASP Switching")
    run_h2.font.name = "Calibri"
    run_h2.font.color.rgb = NAVY_RGB

    doc.add_paragraph(
        "To shield core business logic from ASP idiosyncrasies, Finkraft implements an extensible Adapter Pattern "
        "coordinated via ASPRegistry. Customers switch or add ASPs dynamically without codebase changes."
    )

    tbl1 = doc.add_table(rows=1, cols=4)
    tbl1_headers = ["Method", "Input Signature", "Output Return", "Operational Purpose"]
    tbl1_widths = [1.4, 1.6, 1.4, 2.6]
    tbl1_data = [
        ["submit_invoice", "CanonicalInvoice (PINT AE)", "SubmissionResult", "Dispatches payload; normalizes sync (ASP A) vs async job (ASP B)."],
        ["poll_status", "external_id: str", "StatusUpdate", "Polls status for GET ASPs (A); raises NotSupported for webhook-only ASPs."],
        ["parse_webhook", "headers: dict, payload: dict", "StatusUpdate", "Verifies HMAC signature, deduplicates event ID, normalizes C3/C5 status."],
        ["get_capabilities", "None", "ASPCapabilities", "Exposes rate limits (10 rps), sync/async traits, and native idempotency flags."],
    ]
    style_table(tbl1, tbl1_widths, tbl1_headers, tbl1_data)

    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(6)
    p_sp.paragraph_format.space_after = Pt(2)

    # 3. State Machine & Normalization
    h2 = doc.add_heading(level=2)
    run_h2 = h2.add_run("3. Invoice State Machine & Normalization Matrix")
    run_h2.font.name = "Calibri"
    run_h2.font.color.rgb = NAVY_RGB

    doc.add_paragraph(
        "Finkraft manages an internal state machine that decouples internal lifecycle management from ASP-specific statuses. "
        "Milestones c3_delivered_at and c5_reported_at accumulate independently to resolve into COMPLIANT_AND_DELIVERED."
    )

    tbl2 = doc.add_table(rows=1, cols=4)
    tbl2_headers = ["ASP A Status", "ASP B Status", "Normalized Status", "Finkraft Internal State & Target"]
    tbl2_widths = [1.3, 1.5, 1.4, 2.8]
    tbl2_data = [
        ["RECEIVED", "QUEUED / ACCEPTED", "ACKNOWLEDGED", "ACKNOWLEDGED_C2 (Payload accepted by C2 ASP)"],
        ["VALIDATED", "N/A (Implicit)", "VALIDATED", "VALIDATED_C2 (ASP schema & PEPPOL signature verified)"],
        ["DELIVERED (C3)", "BUYER_RECEIVED (C3)", "DELIVERED_C3", "DELIVERED_C3 (or COMPLIANT_AND_DELIVERED if C5 already recorded)"],
        ["REPORTED (C5)", "TAX_CONFIRMED (C5)", "REPORTED_C5", "REPORTED_C5 (or COMPLIANT_AND_DELIVERED if C3 already recorded)"],
        ["REJECTED", "FAILED", "REJECTED", "REJECTED (Terminal failure; captures BT-xx schema/tax errors)"],
    ]
    style_table(tbl2, tbl2_widths, tbl2_headers, tbl2_data)

    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(6)
    p_sp.paragraph_format.space_after = Pt(2)

    # 4. Failure Handling
    h2 = doc.add_heading(level=2)
    run_h2 = h2.add_run("4. Failure Handling & Reliability Engineering")
    run_h2.font.name = "Calibri"
    run_h2.font.color.rgb = NAVY_RGB

    tbl3 = doc.add_table(rows=1, cols=3)
    tbl3_headers = ["Failure Mode", "Root Cause & Business Risk", "Finkraft Technical Mitigation"]
    tbl3_widths = [1.6, 2.3, 3.1]
    tbl3_data = [
        ["Submission Timeout (ASP A)", "ASP A times out AFTER invoice accepted. Naive retries duplicate invoices or fail.", "Quarantine to SUBMISSION_AMBIGUOUS. Automatic retries strictly banned. Background active reconciliation queries ASP A by invoice number. If found, advances to ACKNOWLEDGED_C2; if absent, safe retry."],
        ["Duplicate Submissions (ASP B)", "ASP B has ZERO duplicate checks. Re-submitting creates duplicate tax records at FTA.", "Client-Side Pessimistic Idempotency Lock: DB unique index on (seller_trn, invoice_number) + atomic compare-and-swap (VALIDATED -> SUBMITTING). In-memory repository catches DuplicateInvoiceError."],
        ["Out-of-Order Webhooks (ASP B)", "TAX_CONFIRMED (C5) arrives before BUYER_RECEIVED (C3).", "Milestone Lattice Resolution: Tracks independent c3_delivered_at and c5_reported_at timestamps. Invoice transitions to COMPLIANT_AND_DELIVERED as soon as both milestones are satisfied."],
        ["Late / Duplicate Webhooks", "ASP B re-delivers callbacks hours later.", "Idempotent Webhook Event Ledger: Unique constraint on (asp_id, event_id). Duplicates return HTTP 200 immediately. Monotonic transition guards reject retroactive state regressions as safe no-ops."],
        ["ASP A Rate Limiting (10 req/s)", "Bulk upload bursts exceed ASP A quota (429).", "Token-Bucket Egress Throttler: Dispatcher meters traffic to 10 req/s per tenant. Excess jobs remain buffered in persistent queues with exponential jittered backoff."],
    ]
    style_table(tbl3, tbl3_widths, tbl3_headers, tbl3_data)

    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(6)
    p_sp.paragraph_format.space_after = Pt(2)

    # 5. Strategic Trade-offs
    h2 = doc.add_heading(level=2)
    run_h2 = h2.add_run("5. Architectural Trade-offs & Strategic Decisions")
    run_h2.font.name = "Calibri"
    run_h2.font.color.rgb = NAVY_RGB

    add_callout_box(
        doc,
        "Decision 1: Asynchronous Unified Event-Driven Pipeline vs. Synchronous Passthrough\n"
        "* Choice: Unified async ingestion for both ASPs. Bulk uploads receive immediate HTTP 202 with internal receipt.\n"
        "* What We Gained: Vendor portability (customers switch ASPs without API changes); absorbs ASP A 10 req/s quota; fault isolation.\n"
        "* What We Sacrificed: Single-invoice POS clients cannot get synchronous C2 clearance within the same HTTP connection.\n\n"
        "Decision 2: Pessimistic Idempotency & Reconciliation Quarantine vs. Optimistic Fast Retries\n"
        "* Choice: Strict unique index on (seller_trn, invoice_number) + quarantine state (SUBMISSION_AMBIGUOUS).\n"
        "* What We Gained: 100% guarantee against duplicate tax reporting to UAE FTA (zero customer tax penalties); tamper-proof audit trail.\n"
        "* What We Sacrificed: Recovery latency (ambiguous network glitches resolve via 30s recon worker rather than 1s instant retry).",
        title="Key Architectural Trade-offs",
        hex_bg=BG_LIGHT_BLUE,
        hex_border=BORDER_BLUE,
    )

    doc.add_page_break()

    # =========================================================================
    # PART 3: 30-DAY CTO PLAN
    # =========================================================================
    h1 = doc.add_heading(level=1)
    run_h1 = h1.add_run("Part 3: 30-Day CTO Execution Plan (1 Page)")
    run_h1.font.name = "Calibri"
    run_h1.font.color.rgb = NAVY_RGB

    h2 = doc.add_heading(level=2)
    run_h2 = h2.add_run("1. Executive Strategy & Squad Allocation")
    run_h2.font.name = "Calibri"
    run_h2.font.color.rgb = NAVY_RGB

    doc.add_paragraph(
        "With 3 Backend Engineers (BE1, BE2, BE3) and 1 Frontend Engineer (FE1), we operate as a single-threaded squad "
        "focused strictly on the compliant critical path. Weeks 1–4 execute feature delivery and achieve full feature freeze; "
        "Weeks 5–6 are strictly reserved for partner UAT, security penetration testing, and zero-defect launch hardening."
    )

    h2 = doc.add_heading(level=2)
    run_h2 = h2.add_run("2. Weekly Execution Schedule (Weeks 1 to 4)")
    run_h2.font.name = "Calibri"
    run_h2.font.color.rgb = NAVY_RGB

    doc.add_paragraph(
        "Week 1: Architectural Alignment, Scope Freeze & Core Foundations\n"
        "* CTO: Enforce scope freeze with CEO/Product; audit ASP sandboxes and rate limits; establish trunk CI/CD with ephemeral previews.\n"
        "* BE1 (State Machine & Locks): Core state machine, PostgreSQL schema, unique index on (seller_trn, invoice_number) with row locks.\n"
        "* BE2 (ASP Adapter): Unified ASPAdapter contract for primary launch ASP (A/B), isolating authentication and rate-limiting queues.\n"
        "* BE3 (PINT AE Validation): PINT AE business validation engine (15-digit TRN validation, BT-48 VAT category codes, tax arithmetic).\n"
        "* FE1 (Ingestion UI): Authenticated drag-and-drop CSV/Excel bulk upload interface with instant client-side format checks.\n"
        "* Milestone: Test suite passing with 100% coverage on state transitions, validation errors, and duplicate rejection."
    )

    doc.add_paragraph(
        "Week 2: The 'Walking Skeleton' (End-to-End Ingestion to Clearance)\n"
        "* CTO: Drive end-to-end integration across components; establish structured JSON logging with correlation IDs (seller_trn:invoice_number).\n"
        "* BE1 + BE2: Wire Ingestion -> PINT AE -> ASP Adapter. Implement async worker queue and webhook ingress with HMAC verification.\n"
        "* BE3: Build Active Reconciliation Worker for submission timeouts and the idempotent webhook event ledger.\n"
        "* FE1: Invoice Status Dashboard (search by invoice number, state badges: ACKNOWLEDGED, DELIVERED_C3, REPORTED_C5, REJECTED).\n"
        "* Milestone: First real test invoice uploaded via UI, submitted to ASP sandbox, and tracked to C5 clearance in staging."
    )

    doc.add_paragraph(
        "Weeks 3–4: Failure Resilience, Bulk Scaling & Feature Freeze\n"
        "* BE1 (Bulk Processing): Streaming CSV parser (10k+ rows) without memory spikes; tune token-bucket throttler (10 req/s for ASP A).\n"
        "* BE2 (Secondary ASP & Failover): Finalize secondary adapter in registry to enable customer ASP switching; build Dead Letter Queues.\n"
        "* BE3 (Observability & Audit): Implement tamper-evident audit logging for FTA inspection; instrument Prometheus metrics and PagerDuty.\n"
        "* FE1 (Error Triage UI): Row-level error remediation view (download invalid rows with BT-xx error hints so users fix and re-upload).\n"
        "* CTO + Squad: Chaos Testing Game Day (inject ASP 504 timeouts, duplicate uploads, out-of-order webhooks). FEATURE FREEZE END W4."
    )

    h2 = doc.add_heading(level=2)
    run_h2 = h2.add_run("3. Deliberate Scope Cuts (What We Cut and Why)")
    run_h2.font.name = "Calibri"
    run_h2.font.color.rgb = NAVY_RGB

    doc.add_paragraph(
        "1. Native ERP Connectors (SAP, Oracle, Dynamics): Cut due to multi-month integration cycles. Replaced by standardized CSV/Excel uploads and REST API.\n"
        "2. Active-Active Multi-ASP Dynamic Load Balancing: Cut to eliminate distributed concurrency races and double-filing risks. Replaced by single ASP per seller with config switching.\n"
        "3. In-Browser Invoice Editor & Line-Item Correction: Cut because interactive UI tax calculators would consume 100% of FE1's runway. Replaced by 'Reject & Download Error CSV'.\n"
        "4. Buyer Portal & Advanced Financial Analytics: Cut because compliance is driven by Seller (C1) and FTA (C5). Buyer portals add zero regulatory value for Day 1."
    )

    h2 = doc.add_heading(level=2)
    run_h2 = h2.add_run("4. The First Two Things to Measure")
    run_h2.font.name = "Calibri"
    run_h2.font.color.rgb = NAVY_RGB

    doc.add_paragraph(
        "Metric 1: Zero-Duplicate Submission Rate & Idempotency Violations (Target: Exactly 0)\n"
        "* Rationale: Sovereign tax invariant. Submitting twice creates phantom tax liability on customer balance sheets and triggers FTA audits.\n"
        "* Instrumentation: Counter finkraft_duplicates_blocked_total at edge; immediate P0 alert if any duplicate payload reaches an ASP.\n\n"
        "Metric 2: End-to-End Compliance Latency (P95 < 120s) & Ambiguous State Dwell Time (< 60s)\n"
        "* Rationale: Invoices stuck in intermediate or ambiguous states delay commercial payments. Verifies reconciliation auto-heals glitches."
    )

    doc.add_page_break()

    # =========================================================================
    # APPENDIX: AI USAGE DISCLOSURE
    # =========================================================================
    h1 = doc.add_heading(level=1)
    run_h1 = h1.add_run("Appendix: AI Usage Disclosure (Max 0.5 Page)")
    run_h1.font.name = "Calibri"
    run_h1.font.color.rgb = NAVY_RGB

    doc.add_paragraph(
        "1. AI Tools Utilized\n"
        "* Antigravity / Gemini 3.8 Flash: Architecture reasoning, state machine lattice design, test suite scaffolding, and documentation.\n"
        "* Google Search API: Grounding against official UAE Federal Tax Authority (FTA) Peppol PINT AE UBL 2.1 specifications.\n\n"
        "2. What AI Was Used For\n"
        "* Domain Synthesis: Validating the 5-Corner DCTCE model (C1 -> C2 -> C3 -> C4 + C5) and standard business terms (BT-31, BT-48).\n"
        "* Edge-Case Modeling: Analyzing failure modes between synchronous timeout post-acceptance (ASP A) and asynchronous zero-idempotency (ASP B).\n"
        "* Test Scaffolding: Accelerating implementation of 24 unit and integration tests with zero external third-party dependencies.\n\n"
        "3. Key AI Outputs Changed or Rejected (and Why)\n"
        "* Rejection 1 (In-Line Code in Design Note): The AI originally embedded extensive Python dataclasses directly in Section 2 of the 2-page Design Note. Raw code syntax consumed excessive vertical space and was overly developer-centric. We decoupled the Python code into docs/TECHNICAL_CONTRACT_SPEC.md and replaced it with structured functional capability tables, leaving space to elaborate on the Submission Timeout Reconciliation Protocol.\n"
        "* Rejection 2 (Pre-Tagged Scenario Columns in CSV): The initial CSV processor script relied on an artificial 'scenario' column in the CSV to branch logic. Real enterprise ERP invoice feeds never arrive tagged with test flags. We stripped the scenario column completely to create a realistic business CSV, and updated the runner to automatically detect business errors (bad TRNs, duplicate keys, multi-tenant reuse) while injecting transient network failures probabilistically."
    )

    doc.save(output_path)
    print(f"Successfully generated DOCX: {output_path}")


if __name__ == "__main__":
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "Finkraft_CTO_Assignment_Submission.docx")
    build_docx(out_file)
