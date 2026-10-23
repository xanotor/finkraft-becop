# Finkraft CTO Take-Home Assignment: Master Submission

**Candidate:** CTO Finalist  
**Target:** UAE Federal Tax Authority (FTA) Peppol E-Invoicing Compliance Platform  
**Repository:** [GitHub Repository / Shared Link]  
**Submission Deliverables:**
* **PDF Deliverable:** [`pdf/Finkraft_CTO_Assignment_Submission.pdf`](file:///Users/ss/code/finkraft-becop/pdf/Finkraft_CTO_Assignment_Submission.pdf) (Contains Parts 1, 3, and Appendix strictly adhering to page limits)
* **Code Implementation:** Python 3 standard library package (`src/finkraft/`), unit/integration test suite (`tests/`), and live batch processor (`demo_bulk_processor.py`)

---

## Table of Contents
1. [Part 1: Architecture Design Note (Max 2 Pages)](#part-1-architecture-design-note)
2. [Part 2: Code Implementation Summary & Test Execution](#part-2-code-implementation-summary)
3. [Part 3: 30-Day CTO Execution Plan (1 Page)](#part-3-30-day-cto-execution-plan)
4. [Appendix: AI Usage Disclosure (Max 0.5 Page)](#appendix-ai-usage-disclosure)

---

# Part 1: Architecture Design Note

### 1. Business Context & Explicit Assumptions

Under the UAE Federal Tax Authority (FTA) mandate, e-invoicing is governed by a **Decentralized Continuous Transaction Control and Exchange (DCTCE) 5-Corner Model**:
* **Corner 1 (C1):** Seller (Finkraft’s enterprise customer generating invoice data).
* **Corner 2 (C2):** Seller’s Accredited Service Provider (ASP) that validates and transmits invoices.
* **Corner 3 (C3):** Buyer’s ASP that receives electronic invoices over the Peppol network.
* **Corner 4 (C4):** Buyer who receives compliant invoice data into their ERP.
* **Corner 5 (C5):** UAE Federal Tax Authority (FTA) receiving the Tax Data Document (TDD).

```
   [ C1: Seller ]  ---> [ Finkraft Engine ] ---> [ C2: Seller's ASP ]
                                                        |
                            +---------------------------+---------------------------+
                            |                                                       |
                            v                                                       v
                   [ C3: Buyer's ASP ]                                     [ C5: UAE FTA ]
                            |                                               (Tax Clearance)
                            v
                   [ C4: Buyer ERP ]
```

#### Business Stakes
Invoice records represent sovereign tax documents. Errors, duplicate submissions, or lost records lead to direct financial penalties from the FTA, frozen VAT input credits for buyers, and customer churn. Finkraft must guarantee **100% data integrity, zero lost invoices, and zero duplicate submissions**.

#### Explicit Assumptions
1. **Business Key Uniqueness:** The compound key `(seller_trn, invoice_number)` is globally unique and immutable across the platform lifecycle.
2. **Pre-Submission Enrichment:** Finkraft validates and enriches raw customer feeds into compliant **PINT AE UBL 2.1 XML** before calling any ASP. Syntax and business-rule errors (e.g., missing 15-digit TRN, VAT code BT-48) are rejected internally to protect ASP quotas and reputation.
3. **ASP A Profile:** Synchronous submission (`POST /invoices`), status polling (`GET /invoices/{id}`), rate limit of 10 requests/sec. Native idempotency rejects duplicate invoice numbers with HTTP 409. Network timeouts occasionally occur *after* ASP A has accepted the invoice.
4. **ASP B Profile:** Asynchronous submission (`POST /v2/submissions` $\to$ HTTP 202 with `job_id`), webhook callbacks only (no query endpoint). **Zero duplicate checking** (submitting twice creates duplicate tax filings at the FTA). Webhooks can arrive late, duplicated, or out-of-order.
5. **ASP Switching Semantics:** Customers can change or add ASPs via configuration. In-flight invoices retain their originating ASP adapter until reaching a terminal state. New submissions route to the newly selected ASP.
6. **Webhook Authenticity:** Inbound webhooks from ASP B are signed via HMAC-SHA256 headers (`X-ASP-Signature`) and carry an immutable `event_id`.

---

### 2. Unified Adapter Contract & Dynamic ASP Switching

To shield core business logic from ASP idiosyncrasies, Finkraft employs an **Adapter Pattern** orchestrated via an **ASP Registry**. Customers can switch or add ASPs without core code modifications.

```
                           +---------------------------+
                           |       <<Contract>>        |
                           |        ASP Adapter        |
                           +---------------------------+
                           | - submit_invoice()        |
                           | - poll_status()           |
                           | - parse_webhook()         |
                           | - get_capabilities()      |
                           +---------------------------+
                                         ^
                     +-------------------+-------------------+
                     |                                       |
        +-------------------------+             +-------------------------+
        |       ASP A Adapter     |             |       ASP B Adapter     |
        +-------------------------+             +-------------------------+
        | - Rate Limiter (10 rps) |             | - HMAC Signature Verif  |
        | - Sync Submit + Polling |             | - Async Submit (202)    |
        | - Timeout Reconciler    |             | - Webhook Normalizer    |
        +-------------------------+             +-------------------------+
```

#### Standardized Methods & Capabilities

| Method | Input | Output | Business Purpose |
|---|---|---|---|
| `submit_invoice` | `CanonicalInvoice` (PINT AE payload, metadata) | `SubmissionResult` | Dispatches invoice to ASP; normalizes synchronous responses (ASP A) and asynchronous job receipts (ASP B). |
| `poll_status` | `external_id` (ASP submission/job ID) | `StatusUpdate` | Actively checks status for polling-based ASPs (ASP A). Raises `NotSupported` for webhook-only ASPs. |
| `parse_webhook` | HTTP Headers, JSON Payload | `StatusUpdate` | Verifies webhook cryptographic signature, deduplicates event ID, and translates ASP B events into standard status updates. |
| `get_capabilities` | *None* | `ASPCapabilities` | Exposes operational metadata (sync/async, polling support, rate limits, native idempotency) to configure routing and rate limiters. |

#### Standardized Data Models (Conceptual Summary)
* **`CanonicalInvoice`**: Standardized business invoice containing seller TRN, buyer TRN, invoice number, issue date, monetary totals, and validated PINT AE XML.
* **`SubmissionResult`**: Encapsulates submission success, ambiguous timeout indicators, ASP-assigned reference ID, normalized initial status, and standardized errors.
* **`StatusUpdate`**: Uniform status payload containing ASP reference ID, normalized milestone status, timestamp, and error details.
* **`NormalizedError`**: Standardized error schema (`code`, `message`, `field_reference`, `is_transient`) translating vendor codes (e.g., ASP A `{"code": "E104", "field": "BT-48"}` or ASP B `{"rule": "...", "message": "..."}`).

---

### 3. Invoice State Machine & Normalization

Finkraft manages an internal state machine that decouples internal lifecycle management from ASP-specific statuses.

#### Finkraft Internal States

| State | Category | Description |
|---|---|---|
| `DRAFT` | Initial | Ingested via customer bulk upload or ERP connector. |
| `VALIDATED` | Internal | Passed internal PINT AE validation and tax arithmetic. Ready for C2 dispatch. |
| `SUBMITTING` | Transient | Distributed lock acquired on `(seller_trn, invoice_number)`. In-flight to C2. |
| `SUBMISSION_AMBIGUOUS` | Incident | Network timeout or drop during submission. Awaiting active reconciliation. |
| `ACKNOWLEDGED_C2` | Processing | C2 accepted the payload (ASP A `RECEIVED`, ASP B `QUEUED` / `ACCEPTED`). |
| `VALIDATED_C2` | Processing | C2 verified Peppol schema and digital signature (ASP A `VALIDATED`). |
| `DELIVERED_C3` | Intermediate | Buyer’s ASP confirmed receipt. Awaiting C5 FTA clearance. |
| `REPORTED_C5` | Intermediate | FTA confirmed tax clearance. Awaiting C3 buyer delivery. |
| `COMPLIANT_AND_DELIVERED` | **Terminal Success** | **Both C3 Delivery and C5 FTA Clearance confirmed.** Immutable end state. |
| `REJECTED` | **Terminal Failure** | Validation or tax rule failure at C2, C3, or C5. Non-reversible. |

#### Status Normalization Matrix

| ASP Status | Raw Value | Normalized Status | Finkraft Target State |
|---|---|---|---|
| **ASP A** | `RECEIVED` | `ACKNOWLEDGED` | `ACKNOWLEDGED_C2` |
| **ASP A** | `VALIDATED` | `VALIDATED` | `VALIDATED_C2` |
| **ASP A** | `DELIVERED` | `DELIVERED_C3` | `DELIVERED_C3` (or `COMPLIANT_AND_DELIVERED` if C5 met) |
| **ASP A** | `REPORTED` | `REPORTED_C5` | `REPORTED_C5` (or `COMPLIANT_AND_DELIVERED` if C3 met) |
| **ASP A** | `REJECTED` | `REJECTED` | `REJECTED` |
| **ASP B** | `QUEUED`, `ACCEPTED` | `ACKNOWLEDGED` | `ACKNOWLEDGED_C2` |
| **ASP B** | `BUYER_RECEIVED` | `DELIVERED_C3` | `DELIVERED_C3` (or `COMPLIANT_AND_DELIVERED` if C5 met) |
| **ASP B** | `TAX_CONFIRMED` | `REPORTED_C5` | `REPORTED_C5` (or `COMPLIANT_AND_DELIVERED` if C3 met) |
| **ASP B** | `FAILED` | `REJECTED` | `REJECTED` |

#### State Transition Diagram & Monotonic Milestones

```
   [DRAFT] ---> [VALIDATED] ---> [SUBMITTING] ---> [ACKNOWLEDGED_C2] ---> [VALIDATED_C2]
                                       |                     |                     |
                            (Timeout)  v                     v (C3 First)          v (C5 First)
                     [SUBMISSION_AMBIGUOUS]            [DELIVERED_C3]        [REPORTED_C5]
                               | (Active Recon)              \                     /
                               +---> [ACKNOWLEDGED_C2]        v                   v
                                                          [COMPLIANT_AND_DELIVERED] (Terminal)
```

**Milestone Lattice Logic:** Every invoice maintains `c3_delivered_at` and `c5_reported_at` timestamps. The terminal state `COMPLIANT_AND_DELIVERED` is reached whichever order C3 and C5 arrive in. Out-of-order or duplicate events (e.g., an `ACCEPTED` webhook arriving after `REPORTED_C5`) are safely dropped as idempotent no-ops.

---

### 4. Failure Handling & Reliability Engineering

| Failure Mode | Root Cause / Trigger | Business Impact | Technical Mitigation Strategy |
|---|---|---|---|
| **Submission Timeout** | ASP A occasionally times out *after* accepting the invoice. Network drops on ASP B submit. | Naive retries create duplicate invoices or trigger false rejections, delaying commercial billing. | **State Isolation to `SUBMISSION_AMBIGUOUS` & Active Reconciliation:** Automatic retries are strictly blocked. Finkraft triggers a background reconciliation worker to query ASP A by invoice number. If found, external ID is attached and state advances to `ACKNOWLEDGED_C2`. Only if verified absent is a retry allowed. |
| **Duplicate Submission** | ASP B has **no duplicate checking**. Retrying a bulk upload duplicates invoices. | **Severe:** Filing duplicate tax documents with the FTA creates duplicate VAT liabilities, leading to tax audits and fines. | **Client-Side Pessimistic Idempotency Lock:** Database unique index on `(seller_trn, invoice_number)`. Atomic compare-and-swap transitions (`VALIDATED` $\to$ `SUBMITTING`). Any concurrent upload of an existing invoice is blocked before reaching the network. |
| **Late / Duplicate Webhooks** | ASP B redelivers webhooks hours later or out of sequence. | Outdated callbacks could revert an invoice from completed to in-progress, corrupting audit trails. | **Idempotent Webhook Event Ledger & Monotonic Guards:** Inbound webhooks log `(asp_id, event_id)` in an append-only ledger with a unique key. Redeliveries return HTTP 200 immediately. State machine enforces a monotonic lattice: backwards transitions are rejected. |
| **Out-of-Order Webhooks** | ASP B delivers `TAX_CONFIRMED` (C5) before `BUYER_RECEIVED` (C3). | Invoice could get stuck in intermediate state if the system expects a strict linear progression. | **Milestone-Based Accumulation:** Independent milestone flags (`c3_delivered_at`, `c5_reported_at`). The platform transitions to `COMPLIANT_AND_DELIVERED` as soon as both flags are non-null, regardless of sequence. |
| **ASP Rate Limiting (10 req/s)** | Customer bulk upload of 10,000 invoices overwhelms ASP A's quota. | HTTP 429 throttling errors, failed bulk uploads, and poor customer experience. | **Token Bucket Outbound Throttler:** Outbound dispatcher throttles traffic to 10 req/s per ASP A tenant. Overflow is buffered in persistent message queues with exponential jittered backoff. |

#### Deep-Dive: Submission Timeout Reconciliation Protocol
1. Client initiates submission to ASP A $\to$ HTTP socket times out after 30 seconds.
2. Finkraft marks invoice as `SUBMISSION_AMBIGUOUS` and commits to DB (releasing lock).
3. Reconciliation Worker schedules an inquiry task with exponential backoff (10s, 30s, 60s).
4. Worker queries ASP A (`GET /invoices?reference={invoice_number}`).
   - **Case A (Found):** ASP A accepted the record prior to timeout. Extract `submission_id`, transition invoice directly to `ACKNOWLEDGED_C2`, and resume normal tracking.
   - **Case B (Not Found after 3 checks):** Record does not exist at ASP A. Mark safe to re-dispatch, transition back to `SUBMITTING`, and call `POST /invoices`.
   - **Case C (Persistent Error):** Escalate to Operations Alert Queue for human inspection. **Never blind-retry.**

---

### 5. Architectural Trade-offs & Strategic Decisions

#### Decision 1: Asynchronous Unified Event-Driven Pipeline vs. Synchronous Passthrough
* **Context:** ASP A supports synchronous submissions with immediate responses, whereas ASP B is strictly asynchronous (`POST /v2/submissions` $\to$ HTTP 202). Finkraft could have exposed a dual API.
* **Strategic Choice:** Finkraft enforces a **unified asynchronous ingestion pipeline** for all customers regardless of ASP. Bulk uploads and single invoices receive an immediate HTTP 202 acknowledgment with an internal tracking ID. Background workers handle ASP communication.
* **Business & Technical Gains:**
  - **Seamless ASP Portability:** Customers can switch from ASP A to ASP B with zero changes to their ERP integration or webhook ingestion.
  - **Rate Limit & Burst Protection:** Enterprise customers uploading thousands of invoices at month-end will not exhaust ASP A’s strict 10 req/s limit or cause gateway timeouts.
  - **Resilience Against ASP Outages:** Transient ASP downtime is absorbed by internal retry queues without failing the customer's batch upload.
* **What We Sacrificed:**
  - **Immediate Single-Invoice Feedback:** Interactive POS or retail systems cannot receive an immediate C2 confirmation within the same HTTP connection; they must query an endpoint or listen to Finkraft webhooks.

#### Decision 2: Pessimistic Idempotency & Reconciliation State vs. Optimistic Fast Retries
* **Context:** ASP B has **zero duplicate detection**, meaning any duplicate submission directly creates duplicate tax documents at the UAE FTA. Furthermore, ASP A times out *after* accepting invoices.
* **Strategic Choice:** We implemented **pessimistic, database-enforced idempotency locks** and an explicit `SUBMISSION_AMBIGUOUS` quarantine state, strictly banning automated blind retries without prior reconciliation.
* **Business & Technical Gains:**
  - **Zero Duplicate Tax Filings:** Completely eliminates the catastrophic business risk of duplicate tax reporting to the UAE government, protecting customers from severe VAT penalties, audits, and inflated tax liabilities.
  - **Deterministic Audit Trail:** Every ambiguous state is logged and reconciled explicitly, providing a tamper-proof audit trail for tax authorities and enterprise compliance officers.
* **What We Sacrificed:**
  - **Throughput & Fast Auto-Recovery:** In the rare event of a network glitch, the invoice cannot instantly self-heal in a tight 1-second retry loop. It enters a reconciliation queue that may take 30–60 seconds to safely resolve.
  - **Write Contention:** Strict locking on `(seller_trn, invoice_number)` prevents parallel ingestion of multiple revisions of the same invoice, requiring ERPs to sequence updates.

---

# Part 2: Code Implementation Summary

The codebase is built with zero external third-party dependencies, adhering strictly to Python 3 standard library best practices.

### Verification Commands
```bash
# Run unit and integration tests (24 passing tests):
python3 run_tests.py

# Run live batch invoice processor with automatic error detection & self-healing:
python3 demo_bulk_processor.py
```

### Key Technical Achievements
1. **Invoice State Machine (`src/finkraft/state_machine.py`)**: Monotonic transition lattice, independent C3/C5 milestone timestamps, and idempotent rejection of stale callbacks.
2. **Unified Adapter Architecture (`src/finkraft/adapters/`)**: Polymorphic `ASPAdapter` interface implemented for both `MockASPA` (sync, polling, 409 conflict, timeout simulation) and `MockASPB` (async 202, HMAC webhook verification, zero duplicate checking).
3. **Dynamic ASP Switching (`src/finkraft/adapters/registry.py`)**: `ASPRegistry` allows customers to switch ASPs at runtime while maintaining in-flight tracking on originating adapters.
4. **Per-Seller Idempotency (`src/finkraft/repository.py`)**: Thread-safe in-memory repository enforcing `(seller_trn, invoice_number)` compound uniqueness, rejecting duplicates per seller while allowing multi-tenant reuse.
5. **Batch Processor & Simulator (`demo_bulk_processor.py`)**: Ingests standard business CSVs, automatically identifies schema and duplicate errors, probabilistically simulates network timeouts and out-of-order webhooks, and demonstrates automatic self-healing.

---

# Part 3: 30-Day CTO Execution Plan

### 1. Executive Strategy & Squad Allocation
With 3 Backend Engineers (BE1, BE2, BE3) and 1 Frontend Engineer (FE1), we operate as a high-velocity, single-threaded squad focused strictly on the compliant critical path. Weeks 1–4 achieve feature freeze; Weeks 5–6 are reserved for partner UAT, security review, and launch hardening.

```
+--------------------------------------------------------------------------------------------------+
| WEEK 1: Architectural Alignment, Strict Scope Freeze & Core Foundations                         |
| WEEK 2: End-to-End "Walking Skeleton" (Customer Upload -> ASP -> FTA Clearance)                  |
| WEEKS 3-4: Failure Resilience, Bulk Scaling, Operational Triage & Feature Freeze                 |
| (WEEKS 5-6: Partner Integration, Penetration Testing, Pilot Customer UAT & Production Launch)   |
+--------------------------------------------------------------------------------------------------+
```

---

### 2. Weekly Execution Schedule (Weeks 1 to 4)

#### Week 1: Alignment, Scope Freeze & Critical Foundations
* **CTO**: Enforce scope freeze with CEO/Product; audit ASP sandbox contracts, rate limits, and network connectivity; establish trunk-based CI/CD with automated tests and branch previews.
* **BE1 (State Machine & Idempotency)**: Implement the core state machine, PostgreSQL schema, and client-side pessimistic idempotency locks (`UNIQUE INDEX` on `seller_trn, invoice_number` with row-level locks).
* **BE2 (ASP Adapter)**: Implement the unified `ASPAdapter` contract for our primary launch ASP (ASP A/B), isolating authentication, submission normalization, and rate limiting.
* **BE3 (PINT AE Engine)**: Implement core UAE PINT AE validation rules (15-digit TRN validation, BT-48 tax category codes, and VAT math).
* **FE1 (Ingestion UI)**: Deliver authenticated bulk CSV upload UI with drag-and-drop file ingestion and client-side file format validation.
* *Deliverable:* Test suite passing with 100% coverage on state transitions and duplicate rejection.

#### Week 2: The "Walking Skeleton" (End-to-End Ingestion to Clearance)
* **CTO**: Drive integration across components; establish centralized structured JSON logging with correlation IDs (`seller_trn:invoice_number`).
* **BE1 + BE2**: Connect Ingestion $\to$ PINT AE $\to$ ASP Adapter. Implement asynchronous worker queue (PostgreSQL/Redis Streams) and inbound webhook endpoint with HMAC signature verification.
* **BE3**: Implement the **Active Reconciliation Worker** for submission timeouts and the idempotent webhook event ledger.
* **FE1**: Build the Invoice Status Dashboard (search by invoice number, state badges: `ACKNOWLEDGED`, `DELIVERED_C3`, `REPORTED_C5`, `REJECTED`).
* *Deliverable:* First real test invoice successfully uploaded via UI, submitted to ASP sandbox, and tracked to C5 clearance in staging.

#### Weeks 3–4: Failure Resilience, Bulk Load Testing & Feature Freeze
* **BE1 (Bulk Processing & Throttling)**: Implement streaming CSV parsing to ingest 10,000-invoice batches without memory spikes; tune token-bucket rate limiting (10 req/s for ASP A).
* **BE2 (Secondary ASP & Failover)**: Finalize secondary mock adapter in `ASPRegistry` to enable customer-level ASP switching; build dead-letter queue (DLQ) handlers.
* **BE3 (Observability & Compliance Audit)**: Implement tamper-evident audit logging for FTA inspection; instrument Prometheus metrics and PagerDuty alert policies.
* **FE1 (Error Triage UI)**: Add downloadable error reports for rejected invoices (row-level PINT AE errors with remediation hints) so customers can self-correct and re-upload.
* **CTO + Squad (Chaos Testing & Hardening)**: Execute simulated Game Day: inject network timeouts, duplicate bulk re-uploads, and out-of-order webhooks. **Feature freeze at the end of Week 4.**

---

### 3. Deliberate Scope Cuts (What We Cut and Why)

1. **Custom ERP Connectors (SAP, Oracle, Dynamics plugins)**:
   - *Why Cut:* Native ERP plugins require long integration cycles, customer-specific permissions, and complex support.
   - *Alternative:* Standardized CSV/Excel bulk upload and a clean REST API. Enterprise finance teams can export CSVs from ERPs in days without custom software.
2. **Dynamic Active-Active Multi-ASP Load Balancing**:
   - *Why Cut:* Dynamically splitting or re-routing single batches across multiple ASPs introduces distributed concurrency races and risks duplicate FTA reporting.
   - *Alternative:* Single-ASP assignment per customer with manual/config-driven switching via `ASPRegistry`.
3. **In-Browser Invoice Editor & Line-Item Correction UI**:
   - *Why Cut:* Building an interactive web tax invoice editor would consume 100% of FE1's 6-week runway.
   - *Alternative:* "Reject & Download Error CSV" workflow. Users fix errors in Excel/ERP and re-upload cleanly.
4. **Buyer Portal & Advanced Financial Analytics**:
   - *Why Cut:* Compliance is driven by the Seller (C1) and the FTA (C5). Buyer portals add zero regulatory value for Day 1.

---

### 4. The First Two Things to Measure

#### Metric 1: Zero-Duplicate Submission Rate & Idempotency Violations
$$\text{Duplicate Leakage} = \text{Duplicate Filings Reaching ASP or FTA} \quad (\mathbf{\text{Target: Exactly } 0})$$
* **Why:** Sovereign tax data invariant. Filing duplicate invoices creates artificial VAT liabilities on customer balance sheets, invalidates buyer tax credits, and incurs severe FTA fines.
* **Instrumentation:** Counter for `finkraft_duplicate_submissions_blocked_total` (edge prevention) and an immediate P0 PagerDuty trigger if any duplicate submission reaches an ASP.

#### Metric 2: Compliance Latency & Ambiguous State Dwell Time
$$\text{P95 Time-to-Compliant} = T_{\text{COMPLIANT\_AND\_DELIVERED}} - T_{\text{INGESTED}} \quad (\mathbf{\text{Target: } < 120\text{ seconds}})$$
$$\text{Max Ambiguous Dwell Time} = T_{\text{RECONCILED}} - T_{\text{SUBMISSION\_AMBIGUOUS}} \quad (\mathbf{\text{Target: } < 60\text{ seconds}})$$
* **Why:** Invoices that linger in intermediate or `SUBMISSION_AMBIGUOUS` states block enterprise commercial shipping and payment releases. Monitoring dwell time verifies that our reconciliation workers self-heal network glitches automatically.

---

# Appendix: AI Usage Disclosure

### 1. AI Tools Used
* **Antigravity / Gemini 3.8 Flash**: Primary architectural reasoning, technical documentation drafting, test scaffolding, and code generation.
* **Google Search Tool**: Verification of the UAE Federal Tax Authority (FTA) Peppol 5-Corner DCTCE framework and PINT AE technical requirements.

### 2. What AI Was Used For
* **Domain Grounding & Verification:** Researching the UAE 5-Corner model (C1 $\to$ C2 $\to$ C3 $\to$ C4 + C5) and PINT AE UBL 2.1 validation rules (15-digit TRN, VAT category BT-48).
* **Architecture & State Machine Modeling:** Formulating the monotonic transition lattice, mapping matrix for heterogeneous ASP statuses, and handling out-of-order C3/C5 arrivals.
* **Failure Mode Synthesis:** Designing the active reconciliation protocol for ASP A's post-acceptance timeouts and client-side idempotency locks to protect ASP B.
* **Code Scaffolding & Test Generation:** Accelerating implementation of 24 unit and integration tests with zero third-party dependencies.

### 3. Key AI Outputs Changed or Rejected (and Why)

1. **Rejected In-Line Python Code in Executive Design Note:**
   - *AI Output:* The initial draft of `PART_1_DESIGN_NOTE.md` embedded extensive Python dataclasses directly in Section 2.
   - *Why Rejected & Modified:* The Design Note is a max 2-page document evaluated on architectural judgment and business risk management. Raw code syntax consumed excessive vertical space. We decoupled the code into `docs/TECHNICAL_CONTRACT_SPEC.md` and replaced it in the Design Note with clean, business-accessible method tables. This preserved the 2-page budget and allowed deep-dive elaboration on the **Submission Timeout Reconciliation Protocol**.

2. **Rejected Pre-Tagged "Scenario" Columns in Batch Ingestion CSV:**
   - *AI Output:* The initial bulk processing demo script relied on an explicit `scenario` column in the CSV (`HAPPY_PATH`, `TIMEOUT_POST_ACCEPT_RECONCILE`, `SCHEMA_FAIL_BAD_TRN`) to branch logic.
   - *Why Rejected & Modified:* In production, enterprise ERP invoice feeds never come tagged with test scenarios; a compliance platform must inspect payloads dynamically. We removed the scenario column entirely, making the CSV a 100% natural business data feed, and updated the runner to automatically detect business errors while simulating transient network failures probabilistically.
