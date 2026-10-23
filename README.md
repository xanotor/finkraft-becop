# Finkraft B2B E-Invoicing Compliance Engine (UAE Mandate)

A Python implementation of Finkraft's core e-invoicing compliance and dispatch engine designed for the **UAE Federal Tax Authority (FTA) 5-Corner DCTCE Mandate** (C1 Seller $\to$ C2 Seller ASP $\to$ C3 Buyer ASP $\to$ C4 Buyer, with C5 FTA tax clearance).

---

## Architecture Overview

```
 [ C1: Seller ERP ] ---> [ Finkraft Ingestion & PINT AE Engine ]
                                       |
                   +-------------------+-------------------+
                   |                                       |
         [ ASP A: Sync / Polling ]               [ ASP B: Async / Webhook ]
         - 10 req/s rate limiter                 - 202 Accepted + Job ID
         - Polling reconciliation                - HMAC Signature Verification
         - 409 duplicate rejection               - No duplicate detection (Finkraft-protected)
                   |                                       |
                   +-------------------+-------------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
         [ C3: Buyer's ASP ]                     [ C5: UAE FTA Clearance ]
                   |                                       |
                   +-------------------+-------------------+
                                       |
                                       v
                     [ COMPLIANT_AND_DELIVERED (Terminal) ]
```

### Key Components

1. **Invoice State Machine (`src/finkraft/state_machine.py`)**:
   - Strictly enforces valid lifecycle transitions and rejects illegal jumps (e.g. `DRAFT` $\to$ `COMPLIANT_AND_DELIVERED`).
   - Manages independent milestone timestamps (`c3_delivered_at`, `c5_reported_at`).
   - Handles concurrent or out-of-order events: whether C3 (Buyer Delivery) arrives before C5 (FTA Clearance) or vice versa, the invoice deterministically reaches `COMPLIANT_AND_DELIVERED`.
   - Protects terminal states (`COMPLIANT_AND_DELIVERED` and `REJECTED`) from backwards or stale updates.

2. **Unified Adapter Contract & Dynamic ASP Switching (`src/finkraft/adapters/`)**:
   - **`ASPAdapter`**: Common interface exposing `submit_invoice()`, `poll_status()`, `parse_webhook()`, and `get_capabilities()`.
   - **`ASPRegistry`**: Central registry supporting runtime dynamic switching between ASPs per customer without code modifications.
   - **`MockASPAAdapter`**: Simulates synchronous `POST /invoices` (200 OK), polling status, native 409 conflict on duplicate invoice numbers, and simulated HTTP timeouts post-acceptance.
   - **`MockASPBAdapter`**: Simulates asynchronous `POST /v2/submissions` (202 Accepted), HMAC-SHA256 webhook callbacks, and **zero duplicate checking** (exposing why Finkraft's client-side idempotency is essential).

3. **Client-Side Idempotency & Repository (`src/finkraft/repository.py`)**:
   - Thread-safe in-memory store enforcing a strict compound unique constraint on `(seller_trn, invoice_number)`.
   - Guaranteed rejection of duplicate invoice numbers per seller (`DuplicateInvoiceError`), while allowing distinct sellers to issue identical invoice numbers concurrently.

4. **Orchestration Service (`src/finkraft/service.py`)**:
   - Coordinates ingestion, PINT AE pre-validation (15-digit TRN, VAT arithmetic), submission dispatch, timeout reconciliation, and webhook processing.

---

## How to Run

The codebase has **zero external dependencies** and runs out-of-the-box using the Python 3 standard library.

### 1. Run the Test Suite

```bash
# Option A: Using the built-in runner
python3 run_tests.py

# Option B: Using Python's standard unittest discovery
python3 -m unittest discover tests -v

# Option C: Using pytest (if installed in your virtual environment)
pytest tests/ -v
```

### 2. Run the CSV Bulk Processor & Resilience Simulator

The repository includes a live pipeline processor (`demo_bulk_processor.py`) that reads a standard business invoice CSV and demonstrates end-to-end processing across the UAE 5-corner lifecycle.

```bash
# Run with default sample dataset and deterministic simulation seed
python3 demo_bulk_processor.py

# Run on a custom CSV file
python3 demo_bulk_processor.py path/to/invoices.csv

# Customize failure simulation rates or run non-deterministically
python3 demo_bulk_processor.py --timeout-rate 0.50 --out-of-order-rate 0.50 --random-seed -1
```

#### Automatic Scenario Detection & Corrective Self-Healing
The CSV template (`data/sample_invoices.csv`) contains **standard business invoice columns** without artificial test flags:
`seller_trn, invoice_number, buyer_trn, issue_date, total_amount, vat_amount, target_asp`

The runner automatically recognizes and mitigates real-world conditions via code:
1. **Schema Validation Rejections (Automatic)**:
   - Invoices with malformed TRNs (e.g., fewer than 15 digits) or invalid tax amounts are trapped by `validate_and_enrich()`, halting them in `REJECTED` and shielding the ASP quota and reputation.
2. **Per-Seller Duplicate Submissions (Automatic)**:
   - When a seller attempts to re-submit an existing invoice number, the repository triggers a client-side idempotency lock (`DuplicateInvoiceError`), blocking duplicate tax filings to the UAE FTA.
3. **Multi-Tenant Isolation (Automatic)**:
   - Confirms that distinct sellers can legitimately issue identical invoice numbers (`INV-2026-001`) without cross-tenant collisions.
4. **Network Timeouts & Active Reconciliation (Configurable Probability)**:
   - Simulates ASP A network drops post-acceptance. The invoice is quarantined into `SUBMISSION_AMBIGUOUS` (banning blind retries). The runner automatically executes the **Active Reconciliation Protocol**, queries ASP A by reference, discovers the remote `submission_id`, and resumes polling to completion.
5. **Out-of-Order & Duplicate Webhooks (Configurable Probability)**:
   - Simulates ASP B delivering `TAX_CONFIRMED` (C5) before `BUYER_RECEIVED` (C3), accompanied by duplicate webhook deliveries. The idempotent ledger drops duplicates safely, and the milestone lattice merges out-of-order events into terminal `COMPLIANT_AND_DELIVERED`.

### 3. Verify Output

The test suite runs 24 comprehensive unit and integration tests verifying:
- Happy paths for both ASP A (polling) and ASP B (webhooks).
- Rejection of invalid state transitions.
- Per-seller duplicate invoice rejection.
- Independent, out-of-order C3/C5 milestone arrivals.
- ASP A timeout post-acceptance and active reconciliation.
- ASP B webhook HMAC signature verification and event deduplication.
- Pre-submission PINT AE validation rules.

---

## What We Skipped (Deliberate Scope Cuts)

In accordance with the 2-hour exercise guidelines and the constraint (*"No database, web server or UI needed. In-memory storage is fine"*):

1. **Persistent Relational Database**: Skipped PostgreSQL in favor of a thread-safe `InMemoryInvoiceRepository` that simulates database unique index behavior on `(seller_trn, invoice_number)`.
2. **Distributed Queue & Worker Infrastructure**: Skipped Celery / RabbitMQ / Redis Streams in favor of synchronous Python calls. The architecture isolates the interfaces so background workers can be dropped in without refactoring.
3. **Full Peppol Schematron / XSLT Validation**: Skipped comprehensive ISO Schematron compilation via `lxml`, implementing instead the primary PINT AE business checks (15-digit TRN format, BT-48 VAT category check, tax arithmetic).
4. **HTTP Server & Web Framework**: Skipped FastAPI / Flask boilerplate to focus exclusively on business domain modeling, state machine precision, and failure resilience.

---

## What We Would Do Next (Production Roadmap)

1. **Transactional Outbox & Distributed Message Broker**:
   - Persist invoices to PostgreSQL using atomic transactions with an `outbox` table.
   - Publish submission tasks to Kafka/RabbitMQ with at-least-once delivery guarantees and dead-letter queues (DLQ).
2. **Optimistic Concurrency & Distributed Row Locking**:
   - Implement PostgreSQL row-level locks (`SELECT FOR UPDATE`) or optimistic version checks (`xmin` / `version`) to guarantee bulletproof concurrency during high-volume bulk uploads.
3. **Background Reconciliation Daemon**:
   - Stand up a dedicated polling/reconciliation worker with exponential jittered backoff to proactively heal `SUBMISSION_AMBIGUOUS` records against ASP A without blocking API threads.
4. **Production PINT AE XML Engine**:
   - Integrate with certified Schematron engines to validate full Peppol UBL 2.1 XML documents against UAE National Rules before hitting C2 ASPs.
5. **Observability & Audit Trail**:
   - Instrument Prometheus metrics (`finkraft_submissions_total`, `asp_latency_seconds_bucket`, `finkraft_duplicate_rejections_total`).
   - Implement WORM (Write Once, Read Many) tamper-evident audit logging for FTA regulatory inspections.
