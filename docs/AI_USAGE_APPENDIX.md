# Appendix: AI Usage Disclosure
**Author:** Srinivas Senniappan | **Document:** Submission Appendix 

---

### 1. AI Tools Used
* **Antigravity / Gemini 3.8 Flash**: Primary architectural reasoning, technical documentation drafting, test scaffolding, and code generation.
* **Google Search Tool**: Verification of the UAE Federal Tax Authority (FTA) Peppol 5-Corner DCTCE framework and PINT AE (Peppol International Invoice, UAE Profile) technical requirements.

### 2. What AI Was Used For
* **Domain Grounding & Verification:** Researching the UAE 5-Corner model (C1 Seller $\to$ C2 Seller ASP $\to$ C3 Buyer ASP $\to$ C4 Buyer, with C5 FTA clearance) and PINT AE UBL 2.1 validation rules (15-digit TRN, VAT category BT-48).
* **Architecture & State Machine Modeling:** Formulating the monotonic transition lattice, mapping matrix for heterogeneous ASP statuses (ASP A polling vs. ASP B webhooks), and handling out-of-order C3/C5 arrivals.
* **Failure Mode Synthesis:** Designing the active reconciliation protocol for ASP A's post-acceptance timeouts and client-side idempotency locks to protect ASP B (which lacks native duplicate detection).
* **Code Scaffolding & Test Generation:** Rapidly generating boilerplate for typed dataclasses, state machine transitions, and a comprehensive 24-test suite with zero external dependencies.

### 3. Key AI Outputs Changed or Rejected (and Why)

1. **Rejected In-Line Python Code in Executive Design Note:**
   - *AI Output:* The initial draft of `PART_1_DESIGN_NOTE.md` embedded extensive Python dataclasses and method signatures directly in Section 2.
   - *Why Rejected & Modified:* The Design Note is a max 2-page document meant for both executive leadership and engineering evaluators. Raw code syntax consumed excessive vertical space and obscured high-level architectural trade-offs. We extracted the code into a dedicated technical specification (`docs/TECHNICAL_CONTRACT_SPEC.md`) and replaced it in the Design Note with clean, business-accessible method and capability tables. This preserved the 2-page budget and allowed deep-dive elaboration on the **Submission Timeout Reconciliation Protocol** and business risk mitigation.

2. **Rejected Pre-Tagged "Scenario" Columns in Batch Ingestion CSV:**
   - *AI Output:* The initial bulk processing demo script relied on an explicit `scenario` column in the CSV (`HAPPY_PATH`, `TIMEOUT_POST_ACCEPT_RECONCILE`, `SCHEMA_FAIL_BAD_TRN`) to branch logic.
   - *Why Rejected & Modified:* In production, enterprise ERP invoice feeds never come tagged with test scenarios; an compliance platform must inspect payloads dynamically. We removed the scenario column entirely, making the CSV a 100% natural business data feed, and updated the runner to automatically detect business errors (PINT AE schema violations, duplicate keys, cross-seller multi-tenancy) while simulating transient network failures probabilistically.
