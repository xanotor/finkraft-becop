# Finkraft 30-Day CTO Execution Plan & Launch Roadmap
**Author:** CTO Candidate | **Context:** 3 Backend + 1 Frontend Engineers | **Deadline:** Production Launch in 6 Weeks

---

## 1. Context & Leadership Strategy

As incoming CTO facing a 6-week production deadline for the UAE FTA e-invoicing mandate, my primary mandate is **regulatory correctness, zero lost invoices, and zero duplicate filings**. With 3 Backend Engineers (BE1, BE2, BE3) and 1 Frontend Engineer (FE1), we operate as a high-velocity, single-threaded squad focused strictly on the compliant critical path. Weeks 1–4 achieve feature freeze; Weeks 5–6 are reserved for partner UAT, security review, and launch hardening.

```
+--------------------------------------------------------------------------------------------------+
| WEEK 1: Architectural Alignment, Strict Scope Freeze & Core Foundations                         |
| WEEK 2: End-to-End "Walking Skeleton" (Customer Upload -> ASP -> FTA Clearance)                  |
| WEEKS 3-4: Failure Resilience, Bulk Scaling, Operational Triage & Feature Freeze                 |
| (WEEKS 5-6: Partner Integration, Penetration Testing, Pilot Customer UAT & Production Launch)   |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Weekly Execution Roadmap (Weeks 1 to 4)

### Week 1: Alignment, Scope Freeze & Critical Foundations
* **CTO**: Enforce scope freeze with CEO/Product; audit ASP sandbox contracts, rate limits, and network connectivity; establish trunk-based CI/CD with automated automated tests and branch previews.
* **BE1 (State Machine & Idempotency)**: Implement the core state machine, PostgreSQL schema, and client-side pessimistic idempotency locks (`UNIQUE INDEX` on `seller_trn, invoice_number` with row-level locks).
* **BE2 (ASP Adapter)**: Implement the unified `ASPAdapter` contract for our primary launch ASP (ASP A/B), isolating authentication, submission normalization, and rate limiting.
* **BE3 (PINT AE Engine)**: Implement core UAE PINT AE validation rules (15-digit TRN validation, BT-48 tax category codes, and VAT math).
* **FE1 (Ingestion UI)**: Deliver authenticated bulk CSV upload UI with drag-and-drop file ingestion and client-side file format validation.
* *Deliverable:* Test suite passing with 100% coverage on state transitions and duplicate rejection.

### Week 2: The "Walking Skeleton" (End-to-End Ingestion to Clearance)
* **CTO**: Drive integration across components; establish centralized structured JSON logging with correlation IDs (`seller_trn:invoice_number`).
* **BE1 + BE2**: Connect Ingestion $\to$ PINT AE $\to$ ASP Adapter. Implement asynchronous worker queue (PostgreSQL/Redis Streams) and inbound webhook endpoint with HMAC signature verification.
* **BE3**: Implement the **Active Reconciliation Worker** for submission timeouts and the idempotent webhook event ledger.
* **FE1**: Build the Invoice Status Dashboard (search by invoice number, state badges: `ACKNOWLEDGED`, `DELIVERED_C3`, `REPORTED_C5`, `REJECTED`).
* *Deliverable:* First real test invoice successfully uploaded via UI, submitted to ASP sandbox, and tracked to C5 clearance in staging.

### Weeks 3–4: Failure Resilience, Bulk Load Testing & Feature Freeze
* **BE1 (Bulk Processing & Throttling)**: Implement streaming CSV parsing to ingest 10,000-invoice batches without memory spikes; tune token-bucket rate limiting (10 req/s for ASP A).
* **BE2 (Secondary ASP & Failover)**: Finalize secondary mock adapter in `ASPRegistry` to enable customer-level ASP switching; build dead-letter queue (DLQ) handlers.
* **BE3 (Observability & Compliance Audit)**: Implement tamper-evident audit logging for FTA inspection; instrument Prometheus metrics and PagerDuty alert policies.
* **FE1 (Error Triage UI)**: Add downloadable error reports for rejected invoices (row-level PINT AE errors with remediation hints) so customers can self-correct and re-upload.
* **CTO + Squad (Chaos Testing & Hardening)**: Execute simulated Game Day: inject network timeouts, duplicate bulk re-uploads, and out-of-order webhooks. **Feature freeze at the end of Week 4.**

---

## 3. Deliberate Scope Cuts (What We Cut and Why)

To guarantee an on-time, zero-defect release, we ruthlessly cut non-critical complexity:

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

## 4. The First Two Things to Measure

### Metric 1: Zero-Duplicate Submission Rate & Idempotency Violations
$$\text{Duplicate Leakage} = \text{Duplicate Filings Reaching ASP or FTA} \quad (\mathbf{\text{Target: Exactly } 0})$$
* **Why:** Sovereign tax data invariant. Filing duplicate invoices creates artificial VAT liabilities on customer balance sheets, invalidates buyer tax credits, and incurs severe FTA fines.
* **Instrumentation:** Counter for `finkraft_duplicate_submissions_blocked_total` (edge prevention) and an immediate P0 PagerDuty trigger if any duplicate submission reaches an ASP.

### Metric 2: Compliance Latency & Ambiguous State Dwell Time
$$\text{P95 Time-to-Compliant} = T_{\text{COMPLIANT\_AND\_DELIVERED}} - T_{\text{INGESTED}} \quad (\mathbf{\text{Target: } < 120\text{ seconds}})$$
$$\text{Max Ambiguous Dwell Time} = T_{\text{RECONCILED}} - T_{\text{SUBMISSION\_AMBIGUOUS}} \quad (\mathbf{\text{Target: } < 60\text{ seconds}})$$
* **Why:** Invoices that linger in intermediate or `SUBMISSION_AMBIGUOUS` states block enterprise commercial shipping and payment releases. Monitoring dwell time verifies that our reconciliation workers self-heal network glitches automatically.
