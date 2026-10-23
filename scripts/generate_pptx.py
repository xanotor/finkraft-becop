#!/usr/bin/env python3
"""
Generates a modern, publication-grade PowerPoint (.pptx) presentation
for Finkraft E-Invoicing Platform Architecture and State Machine.
Contains fully editable native shapes, text boxes, and milestone lattices.
"""

import os
import sys

# Add vendor directory
vendor_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vendor"))
if vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)

import pptx
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR

# Color Palette
NAVY = RGBColor(19, 50, 91)
BLUE = RGBColor(37, 99, 235)
BLUE_LIGHT = RGBColor(239, 246, 255)
BLUE_BORDER = RGBColor(147, 197, 253)

GREEN = RGBColor(22, 101, 52)
GREEN_LIGHT = RGBColor(240, 253, 244)
GREEN_BORDER = RGBColor(134, 239, 172)

AMBER = RGBColor(180, 83, 9)
AMBER_LIGHT = RGBColor(254, 243, 199)
AMBER_BORDER = RGBColor(252, 211, 77)

RED = RGBColor(153, 27, 27)
RED_LIGHT = RGBColor(254, 242, 242)
RED_BORDER = RGBColor(252, 165, 165)

GRAY_BG = RGBColor(249, 250, 251)
GRAY_CARD = RGBColor(243, 244, 246)
GRAY_BORDER = RGBColor(209, 213, 219)
TEXT_DARK = RGBColor(17, 24, 39)
TEXT_MUTED = RGBColor(107, 114, 128)
WHITE = RGBColor(255, 255, 255)


def add_rounded_box(slide, left, top, width, height, title, subtitle="", bg_color=WHITE, border_color=BLUE, title_color=NAVY):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = bg_color
    shape.line.color.rgb = border_color
    shape.line.width = Pt(1.5)

    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.08)
    tf.margin_top = Inches(0.06)
    tf.margin_bottom = Inches(0.06)

    p1 = tf.paragraphs[0]
    p1.text = title
    p1.alignment = PP_ALIGN.CENTER
    p1.font.bold = True
    p1.font.size = Pt(10)
    p1.font.name = "Calibri"
    p1.font.color.rgb = title_color

    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.alignment = PP_ALIGN.CENTER
        p2.font.size = Pt(8)
        p2.font.name = "Calibri"
        p2.font.color.rgb = TEXT_MUTED

    return shape


def add_arrow_label(slide, left, top, width, height, text):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(7.5)
    p.font.name = "Calibri"
    p.font.color.rgb = TEXT_MUTED
    p.font.italic = True
    return tb


def add_connector(slide, x1, y1, x2, y2, color=BLUE_BORDER, width=1.5):
    line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    line.line.color.rgb = color
    line.line.width = Pt(width)
    return line


def create_presentation(output_path: str):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 1: Title Slide
    # =========================================================================
    slide1 = prs.slides.add_slide(blank_layout)

    # Background banner
    bg = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = RGBColor(15, 23, 42)
    bg.line.fill.background()

    # Title box
    tb = slide1.shapes.add_textbox(Inches(1.2), Inches(2.0), Inches(11.0), Inches(3.5))
    tf = tb.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "FINKRAFT B2B E-INVOICING PLATFORM"
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.name = "Calibri"
    p.font.color.rgb = WHITE

    p2 = tf.add_paragraph()
    p2.text = "UAE Federal Tax Authority (FTA) Peppol 5-Corner DCTCE Compliance Platform"
    p2.font.size = Pt(20)
    p2.font.name = "Calibri"
    p2.font.color.rgb = RGBColor(147, 197, 253)
    p2.space_before = Pt(12)

    p3 = tf.add_paragraph()
    p3.text = "CTO Take-Home Assignment Deliverable | Architecture & Editable State Machine"
    p3.font.size = Pt(14)
    p3.font.name = "Calibri"
    p3.font.color.rgb = RGBColor(203, 213, 225)
    p3.space_before = Pt(20)

    # Bottom pill badges
    add_rounded_box(slide1, 1.2, 5.8, 3.2, 0.6, "Part 1: Architecture Design Note", "Unified Adapter & State Lattice", bg_color=RGBColor(30, 41, 59), border_color=BLUE_BORDER, title_color=WHITE)
    add_rounded_box(slide1, 4.8, 5.8, 3.2, 0.6, "Part 2: Working Python Codebase", "24 Tests, Batch Processor, Zero Deps", bg_color=RGBColor(30, 41, 59), border_color=BLUE_BORDER, title_color=WHITE)
    add_rounded_box(slide1, 8.4, 5.8, 3.2, 0.6, "Part 3: 30-Day CTO Execution Plan", "6-Week Roadmap for 3 BE + 1 FE", bg_color=RGBColor(30, 41, 59), border_color=BLUE_BORDER, title_color=WHITE)

    # =========================================================================
    # SLIDE 2: UAE FTA 5-Corner DCTCE Architecture Flow
    # =========================================================================
    slide2 = prs.slides.add_slide(blank_layout)

    # Header
    tb = slide2.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.5), Inches(1.0))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    p.text = "UAE FTA 5-Corner DCTCE Architecture"
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = NAVY
    p2 = tf.add_paragraph()
    p2.text = "End-to-End Invoice Lifecyle: From Seller ERP (C1) through ASPs (C2 & C3) to Buyer (C4) with FTA Clearance (C5)"
    p2.font.size = Pt(11)
    p2.font.color.rgb = TEXT_MUTED

    # Top Row Cards: C1, Finkraft, C2
    add_rounded_box(slide2, 0.8, 2.0, 2.2, 1.8, "Corner 1 (C1)\nSeller ERP", "Customer Ingestion\nBulk CSV / REST API\nRaw Tax Invoices", bg_color=GRAY_CARD, border_color=GRAY_BORDER, title_color=NAVY)
    add_rounded_box(slide2, 3.8, 1.7, 3.0, 2.4, "FINKRAFT PLATFORM\nCompliance Engine", "- PINT AE UBL 2.1 Validation\n- Client Idempotency Locks\n- ASP Adapter & Registry\n- Timeout Active Reconciler\n- Webhook Monotonic Ledger", bg_color=BLUE_LIGHT, border_color=BLUE, title_color=NAVY)
    add_rounded_box(slide2, 7.6, 2.0, 2.2, 1.8, "Corner 2 (C2)\nSeller's ASP", "Accredited Service Provider\n(ASP A or ASP B)\nDigital Signatures & Peppol", bg_color=GRAY_CARD, border_color=GRAY_BORDER, title_color=NAVY)

    # Connectors Top Row
    add_connector(slide2, 3.0, 2.9, 3.8, 2.9, color=BLUE, width=2)
    add_arrow_label(slide2, 2.95, 2.45, 0.9, 0.4, "Raw Batch")
    add_connector(slide2, 6.8, 2.9, 7.6, 2.9, color=BLUE, width=2)
    add_arrow_label(slide2, 6.75, 2.45, 0.9, 0.4, "PINT AE XML")

    # Bottom Row Cards: C3, C4, C5
    add_rounded_box(slide2, 6.0, 5.0, 2.4, 1.8, "Corner 3 (C3)\nBuyer's ASP", "Receives from Peppol Network\nReports BUYER_RECEIVED\n(Delivery Confirmation)", bg_color=BLUE_LIGHT, border_color=BLUE_BORDER, title_color=NAVY)
    add_rounded_box(slide2, 9.4, 5.0, 2.4, 1.8, "Corner 4 (C4)\nBuyer ERP", "Final Invoice Recipient\nERP Accounts Payable\nValidates Input Tax Credit", bg_color=GRAY_CARD, border_color=GRAY_BORDER, title_color=NAVY)
    add_rounded_box(slide2, 10.4, 2.0, 2.4, 1.8, "Corner 5 (C5)\nUAE FTA", "Federal Tax Authority\nReceives TDD Document\nReal-Time Tax Clearance\n(TAX_CONFIRMED)", bg_color=GREEN_LIGHT, border_color=GREEN, title_color=GREEN)

    # Cross Connectors
    # C2 to C3
    add_connector(slide2, 8.4, 3.8, 7.2, 5.0, color=BLUE, width=2)
    add_arrow_label(slide2, 7.2, 4.2, 1.4, 0.4, "Peppol Network Exchange")

    # C3 to C4
    add_connector(slide2, 8.4, 5.9, 9.4, 5.9, color=BLUE, width=2)
    add_arrow_label(slide2, 8.35, 5.5, 1.1, 0.4, "Commercial Delivery")

    # C2 to C5
    add_connector(slide2, 9.8, 2.9, 10.4, 2.9, color=GREEN, width=2)
    add_arrow_label(slide2, 9.7, 2.45, 1.0, 0.4, "Tax Clearance (TDD)")

    # Bottom Invariant Note
    note_box = slide2.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(6.9), Inches(11.7), Inches(0.45))
    note_box.fill.solid()
    note_box.fill.fore_color.rgb = RGBColor(254, 242, 242)
    note_box.line.color.rgb = RED_BORDER
    p = note_box.text_frame.paragraphs[0]
    p.text = "Sovereign Tax Data Invariant: No invoice can ever be lost, and no duplicate invoice can ever be filed with the UAE FTA."
    p.font.size = Pt(8.5)
    p.font.bold = True
    p.font.color.rgb = RED
    p.alignment = PP_ALIGN.CENTER

    # =========================================================================
    # SLIDE 3: The Lifecycle State Machine Flow & Milestone Lattice (REQUESTED)
    # =========================================================================
    slide3 = prs.slides.add_slide(blank_layout)

    # Header
    tb = slide3.shapes.add_textbox(Inches(0.8), Inches(0.35), Inches(11.5), Inches(1.0))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    p.text = "Lifecycle State Machine Flow & Milestone Lattice"
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = NAVY
    p2 = tf.add_paragraph()
    p2.text = "All elements below are native, fully editable PowerPoint shapes. Click, re-color, drag, or edit as needed."
    p2.font.size = Pt(11)
    p2.font.color.rgb = TEXT_MUTED

    # Core Horizontal Pipeline
    # 1. DRAFT
    add_rounded_box(slide3, 0.6, 2.6, 1.6, 1.1, "DRAFT", "Ingested from\nCustomer Upload", bg_color=GRAY_CARD, border_color=GRAY_BORDER, title_color=NAVY)

    # 2. VALIDATED
    add_rounded_box(slide3, 2.7, 2.6, 1.7, 1.1, "VALIDATED", "Enriched & Verified\nPINT AE UBL 2.1", bg_color=BLUE_LIGHT, border_color=BLUE_BORDER, title_color=NAVY)

    # 3. SUBMITTING
    add_rounded_box(slide3, 4.9, 2.6, 1.7, 1.1, "SUBMITTING", "Idempotency Lock\n(seller_trn, inv_num)", bg_color=BLUE_LIGHT, border_color=BLUE, title_color=NAVY)

    # 4. ACKNOWLEDGED_C2
    add_rounded_box(slide3, 7.3, 2.6, 1.8, 1.1, "ACKNOWLEDGED_C2", "C2 ASP Accepted\n(ASP A 200 / ASP B 202)", bg_color=BLUE_LIGHT, border_color=BLUE, title_color=NAVY)

    # 5. VALIDATED_C2
    add_rounded_box(slide3, 9.6, 2.6, 1.6, 1.1, "VALIDATED_C2", "C2 Verified Peppol\nSchema & Rules", bg_color=BLUE_LIGHT, border_color=BLUE, title_color=NAVY)

    # Connectors main line
    add_connector(slide3, 2.2, 3.15, 2.7, 3.15, color=BLUE, width=2)
    add_connector(slide3, 4.4, 3.15, 4.9, 3.15, color=BLUE, width=2)
    add_connector(slide3, 6.6, 3.15, 7.3, 3.15, color=BLUE, width=2)
    add_connector(slide3, 9.1, 3.15, 9.6, 3.15, color=BLUE, width=2)

    # Incident Branch: SUBMISSION_AMBIGUOUS (Timeout post-acceptance)
    add_rounded_box(slide3, 4.9, 4.3, 1.9, 1.2, "SUBMISSION_AMBIGUOUS", "HTTP Timeout on Submit\nBlind Retry Banned!", bg_color=AMBER_LIGHT, border_color=AMBER, title_color=AMBER)
    add_connector(slide3, 5.75, 3.7, 5.75, 4.3, color=AMBER, width=2)
    add_arrow_label(slide3, 5.8, 3.85, 1.5, 0.4, "Socket Timeout")

    # Reconciliation Arrow back to ACKNOWLEDGED_C2
    add_connector(slide3, 6.8, 4.9, 8.2, 4.9, color=AMBER, width=2)
    add_connector(slide3, 8.2, 4.9, 8.2, 3.7, color=AMBER, width=2)
    add_arrow_label(slide3, 6.9, 5.0, 2.2, 0.4, "Active Recon: Found at ASP")

    # Fork: Milestone Lattice (C3 vs C5)
    # Upper Fork: DELIVERED_C3
    add_rounded_box(slide3, 11.5, 1.5, 1.7, 1.1, "DELIVERED_C3", "C3 Buyer ASP Received\n(Milestone Flag Set)", bg_color=BLUE_LIGHT, border_color=BLUE, title_color=NAVY)
    add_connector(slide3, 10.4, 2.6, 11.5, 2.05, color=BLUE, width=2)
    add_arrow_label(slide3, 10.3, 1.95, 1.3, 0.4, "C3 Delivered First")

    # Lower Fork: REPORTED_C5
    add_rounded_box(slide3, 11.5, 3.7, 1.7, 1.1, "REPORTED_C5", "C5 FTA Tax Cleared\n(Milestone Flag Set)", bg_color=BLUE_LIGHT, border_color=BLUE, title_color=NAVY)
    add_connector(slide3, 10.4, 3.7, 11.5, 4.25, color=BLUE, width=2)
    add_arrow_label(slide3, 10.3, 3.85, 1.3, 0.4, "C5 Reported First")

    # Convergence: COMPLIANT_AND_DELIVERED (Terminal Success)
    add_rounded_box(slide3, 11.3, 5.6, 1.9, 1.3, "COMPLIANT_AND_DELIVERED", "TERMINAL SUCCESS\nBoth C3 Delivery & C5 Clearance\nGuaranteed Compliant", bg_color=GREEN_LIGHT, border_color=GREEN, title_color=GREEN)

    # Convergence Connectors
    add_connector(slide3, 12.35, 2.6, 12.35, 3.4, color=GREEN, width=2)
    add_connector(slide3, 12.35, 4.8, 12.35, 5.6, color=GREEN, width=2)
    add_arrow_label(slide3, 11.1, 5.0, 1.2, 0.4, "C3+C5 Met")

    # Terminal Rejection Box (Bottom Left)
    add_rounded_box(slide3, 1.5, 5.6, 2.2, 1.2, "REJECTED (Terminal)", "Schema Failure (BT-48)\nor ASP Business Error\nNon-Reversible", bg_color=RED_LIGHT, border_color=RED, title_color=RED)
    # Reject arrows from DRAFT and VALIDATED
    add_connector(slide3, 1.4, 3.7, 2.0, 5.6, color=RED, width=1.5)
    add_connector(slide3, 3.2, 3.7, 2.8, 5.6, color=RED, width=1.5)

    # Status Legend (Bottom Center)
    leg = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(4.3), Inches(6.1), Inches(6.4), Inches(0.7))
    leg.fill.solid()
    leg.fill.fore_color.rgb = GRAY_CARD
    leg.line.color.rgb = GRAY_BORDER
    p = leg.text_frame.paragraphs[0]
    p.text = "State Machine Legend: [Blue] In-Flight Pipeline | [Amber] Ambiguous Quarantine & Recon | [Green] Terminal Compliant | [Red] Terminal Rejected"
    p.font.size = Pt(8.5)
    p.font.bold = True
    p.font.color.rgb = NAVY
    p.alignment = PP_ALIGN.CENTER
    p2 = leg.text_frame.add_paragraph()
    p2.text = "Monotonic Lattice Rule: Inbound webhooks/polls can arrive out-of-order or duplicate. State only advances forward; stale events are safe no-ops."
    p2.font.size = Pt(7.5)
    p2.font.color.rgb = TEXT_MUTED
    p2.alignment = PP_ALIGN.CENTER

    # =========================================================================
    # SLIDE 4: Heterogeneous ASP Normalization & Idempotency Shield
    # =========================================================================
    slide4 = prs.slides.add_slide(blank_layout)

    # Header
    tb = slide4.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.5), Inches(1.0))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    p.text = "Heterogeneous ASP Integration & Resilience Engineering"
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = NAVY
    p2 = tf.add_paragraph()
    p2.text = "How Finkraft abstracts ASP A (Sync/Polling) and ASP B (Async/Webhooks) while guaranteeing Zero Duplicate Filings"
    p2.font.size = Pt(11)
    p2.font.color.rgb = TEXT_MUTED

    # 3 Comparison Columns
    # Card 1: ASP A Profile
    add_rounded_box(
        slide4, 0.8, 1.8, 3.6, 4.8,
        "ASP A Profile (Synchronous / Polling)",
        "\nSubmission Model:\n* POST /invoices (HTTP 200 Sync)\n* Returns submission_id immediately\n\nStatus Updates:\n* Polling only: GET /invoices/{id}\n* Statuses: RECEIVED, VALIDATED,\n  DELIVERED (C3), REPORTED (C5)\n\nKnown Behaviors & Failure Modes:\n* Native 409 duplicate rejection\n* Strict rate limit: 10 requests/sec\n* Occasional network timeout\n  AFTER invoice was accepted\n\nFinkraft Mitigation:\n* Token bucket throttler at 10 rps\n* Active reconciliation worker\n  before any retry (bans blind retry)",
        bg_color=WHITE, border_color=BLUE_BORDER, title_color=NAVY
    )

    # Card 2: Center - Finkraft Protective Shield
    add_rounded_box(
        slide4, 4.8, 1.8, 3.7, 4.8,
        "Finkraft Idempotency & Abstraction Shield",
        "\nUnified Adapter Contract:\n* Single polymorphic ASPAdapter\n* Dynamic ASPRegistry resolution\n* Runtime customer ASP switching\n\nClient-Side Idempotency Lock:\n* Compound DB unique index on:\n  (seller_trn, invoice_number)\n* Atomic compare-and-swap on submit\n* Blocks duplicates at the edge\n  BEFORE hitting ASP network\n\nMilestone Accumulator Lattice:\n* Independent c3_delivered_at\n* Independent c5_reported_at\n* Completes upon both non-null\n\nResult:\n* 100% Zero Invoices Lost\n* 100% Zero Duplicate Tax Filings",
        bg_color=BLUE_LIGHT, border_color=BLUE, title_color=NAVY
    )

    # Card 3: ASP B Profile
    add_rounded_box(
        slide4, 8.9, 1.8, 3.6, 4.8,
        "ASP B Profile (Asynchronous / Webhooks)",
        "\nSubmission Model:\n* POST /v2/submissions (HTTP 202)\n* Returns job_id receipt immediately\n\nStatus Updates:\n* Webhook callbacks ONLY\n* No polling query endpoint\n* Statuses: QUEUED, ACCEPTED,\n  BUYER_RECEIVED (C3), TAX_CONFIRMED (C5)\n\nKnown Behaviors & Failure Modes:\n* ZERO DUPLICATE CHECKING\n  (Blind retries duplicate tax filings!)\n* Late, duplicate, out-of-order webhooks\n\nFinkraft Mitigation:\n* HMAC-SHA256 signature verification\n* Idempotent event ledger (event_id)\n* Monotonic forward transition guards",
        bg_color=WHITE, border_color=AMBER_BORDER, title_color=AMBER
    )

    prs.save(output_path)
    print(f"Successfully generated PowerPoint presentation: {output_path}")


if __name__ == "__main__":
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "Finkraft_State_Machine_and_Architecture.pptx")
    create_presentation(out_file)
