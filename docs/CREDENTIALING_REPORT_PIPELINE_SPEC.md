# Credentialing Report Pipeline — Spec (Locked)

*Alignment doc for report generation. Last updated: 2025-02.*

---

## Pipeline Flow

```
Steps 1–10 outputs (CSVs, methodology)
         ↓
    First draft (MD + chart specs)
         ↓
    Validate (2 steps run in parallel):
         a) Number validation (tick-and-tie, NPI traceability, totals)
         b) Narrative critique (language, storyline, tone, risky claims)
         ↓
    Final draft (incorporates both validations)
         ↓
    PDF (reuse existing infra)
         ↓
    Download + Communicator display
```

**Same flow** for chat and standalone report runs.

---

## Decisions

| Topic | Decision |
|-------|----------|
| Draft vs critique vs final | Draft → Critique (validator) → Final draft |
| FL Medicaid NPI docs | Static docs (no RAG for this) |
| Charts | LLM guides → chart engine interprets |
| PDF | Reuse existing PDF generation |
| Scope | Full chain: 1–10 → draft → critique → final → PDF → download + communicator |
| Integration | Same flow for chat and standalone |

---

## Components

1. **Inputs:** Step 1–10 outputs, methodology, static FL Medicaid NPI docs
2. **First draft:** LLM produces MD + chart specs from inputs
3. **Critique:** Validator checks tick-and-tie, traceability, flags issues
4. **Final draft:** LLM incorporates critique → MD + charts
5. **PDF:** Existing md→PDF path
6. **Communicator:** Report view + waterfall chart + download

---

## Report Structure (6–10 pages)

1. **Executive Summary** — One-line methodology (outside-in, caveats); opportunity focus; projected revenue at current run rate (softer than "guaranteed"); opportunities (B–E); immediate actions to unlock.
2. **Section 1: Methodology** — What was actually done (steps 1–10); caveats in using this process.
3. **Section 2: About the Organization** — Location summary; number of clinicians; type of services; historic utilization patterns; billing overview; benchmarking overview; major services.
4. **Section 3: Opportunity Waterfall** — Waterfall (A→E) as primary visual; high-level totals.
5. **Section 4: Elements of the Waterfall** — For each level A–E: brief narrative, **top 10 table** (Provider, Service type, Location, Amount — user-friendly, no NPI/taxonomy_code/internal keys), and actionable recommendation.
6. **Section 5: Sources** — Data sources (roster, PML, DOGE, NPPES, AHCA); traceability.
