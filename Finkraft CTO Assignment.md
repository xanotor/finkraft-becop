## Finkraft CTO Take-Home Assignment


## Overview

This assignment has three parts: design, code, and a 30-day plan.

| Part | Deliverable | Time |
| --- | --- | --- |
| 1. Design | Design note, max 2 pages | 2 hours |
| 2. Code | Python repository with tests 2 hours |   |
| 3. 30-day plan 1 page |   | 30 minutes |

- Submit to: [EMAIL] as a GitHub link (shared with [GITHUB HANDLE]) or a zip, plus one PDF for Parts 1 and 3.

- Questions: email [EMAIL]. If something is unclear, state your assumption and continue.

- Follow-up: shortlisted candidates walk through their submission in a 60-minute review.

## Context

Finkraft is building a B2B e-invoicing compliance platform for the UAE Federal Tax Authority (FTA) mandate. Finkraft is not an Accredited Service Provider (ASP); it integrates with accredited ASPs through their APIs.

The UAE uses a five-corner model:

- C1: seller (Finkraft's customer)

- C2: seller's ASP (receives the invoice from Finkraft)

- C3: buyer's ASP

- C4: buyer

- C5: FTA (tax data reported by the ASP)

## Finkraft's platform:

- Accepts invoices from customers via bulk upload

- Validates and enriches them to the PINT AE (Peppol International invoice, UAE) standard


- Submits them to the customer's chosen ASP (C2)

- Tracks status through C3 and C5

Customers must be able to switch or add ASPs. Invoice data is government tax data: no invoice can be lost or submitted twice.

## Mock ASP APIs

Both ASPs are fictional. Treat these specs as complete; state any assumption you add.

|   | ASP A | ASP B |
| --- | --- | --- |
| Submit | POST /invoices (synchronous) | POST /v2/submissions |
|   |   | (asynchronous) |
| Submit | 200 with submission_id and status | 202 with job_id |
| response |   |   |
| Status | Polling only: GET | Webhook callbacks; no polling |
| updates | /invoices/{submission_id} | endpoint |
| Status values | RECEIVED , VALIDATED , REJECTED , | QUEUED , ACCEPTED , FAILED , |
|   | DELIVERED (C3), REPORTED (C5) | BUYER_RECEIVED (C3), |
|   |   | TAX_CONFIRMED (C5) |
| Errors | {"code": "E104", "field": "BT- | {"errors": [{"rule": "...", |
|   | 48"} | "message": "..."}]} |
| Idempotency | Rejects duplicate invoice numbers | No duplicate check |
|   | with 409 |   |
| Known | Rate limit 10 requests/second; | Webhooks can arrive late, out of |
| behaviour | occasional timeouts after the invoice | order, or more than once |
|   | was accepted |   |

## Part 1: Design (2 hours, max 2 pages)

Design how Finkraft submits invoices to both ASPs and tracks their status. Cover:

- 1. Adapter contract: one interface that supports both ASPs. Show its methods and data types.

- 2. Invoice state machine: Finkraft's own states and transitions, and how each ASP's statuses map to them.

- 3. Failure handling: timeouts, retries, duplicate submissions, late or out-of-order webhooks.

- 4. Trade-offs: two decisions you made and what you gave up.

Diagrams are welcome. Hand-drawn photos are fine.

## Part 2: Code (2 hours, Python)

Implement a minimal version of your design:

- The invoice state machine, rejecting invalid transitions

- The adapter interface plus one mock adapter (ASP A or ASP B)

- Duplicate invoice number rejection per seller

- Tests for the main transitions and at least one failure case

- A README: how to run it, what you skipped, what you would do next

No database, web server or UI needed. In-memory storage is fine.

## Part 3: 30-day plan (30 minutes, 1 page)

You join as CTO. The team is 3 backend engineers and 1 frontend engineer, and the first production release is due in 6 weeks.

- What you do in weeks 1, 2 and 3-4

- What you would cut from scope, and why

- The first two things you would measure

## How we evaluate

| Area | What we look for |
| --- | --- |
| Design | Clear contract, correct state handling, failure cases |
|   | covered |
| Code | Readable, tested, runs from the README |
| Judgement Explicit assumptions and trade-offs; sensible |   |
|   | scope cuts |
| Plan | Realistic sequencing for the team size and deadline |

We value a smaller, correct submission over a larger, incomplete one.


## AI usage

AI tools are allowed. Add a short appendix (max half a page):

- Tools used

- What you used them for

- One output you changed or rejected, and why
