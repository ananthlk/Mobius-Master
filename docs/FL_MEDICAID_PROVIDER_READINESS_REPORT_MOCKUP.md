# FL Medicaid Provider Readiness Report — Mockup

**Report Date:** February 1, 2026  
**Run Date:** February 23, 2026

---

## Credentialing Issue Taxonomy

Credentialing problems fall into these categories. **Multiple checks per category** — flag when any check triggers. Use deterministic and probabilistic methods.

| Code | Category | Description |
|------|----------|-------------|
| **A** | Enrollment / contract status | Not in PML, contract expired, contract not yet effective |
| **B** | Address mismatch | See sub-types below |
| **C** | Taxonomy mismatch | See sub-types below; multiple checks, flag on any |
| **D** | Taxonomy not approved for service | Billed HCPCS not aligned with provider taxonomy (probabilistic) |
| **E** | NPI not in NPPES | Provider not found in NPPES registry |
| **F** | Entity type mismatch | NPPES entity type vs probabilistic signals disagree |

### Entity Type Validation (probabilistic)

NPPES has `entity_type_code` (1=Individual, 2=Organization). Validate against signals:

| Signal | Individual (person) | Organization (entity) |
|--------|---------------------|------------------------|
| **Name** | "John Smith, MD" — no LLC/PA/Inc | "Sunshine Health LLC", "Medical Group PA" |
| **Spend variance** | Lower (single provider) | Higher (multiple providers under one NPI) |
| **Taxonomy** | Individual taxonomy codes | Organizational / group practice codes |
| **Locations** | Typically 1 | Often multiple addresses |
| **Servicing NPIs** | Self (billing = servicing) or few | Many distinct servicing NPIs |

**Logic:** Score each NPI; flag when NPPES says "Individual" but signals suggest "Organization" (or vice versa). Low-confidence = review.

**B — Address mismatch (sub-types):**
- **B1** — NPPES ≠ PML: Service address in NPPES doesn't match PML
- **B2** — NPPES internal: Multiple addresses for same NPI vary slightly (mailing vs practice, typo, format)
- **B3** — Within billing org: Address differs from other servicing NPIs under same billing NPI (clustering; outlier or typo)

**C — Taxonomy mismatch (sub-types; probabilistic where noted):**
- **C1** — Not in TML: NPPES/PML taxonomy not in FL TML (deterministic)
- **C2** — NPPES ≠ PML: NPPES taxonomy differs from PML taxonomy (deterministic)
- **C3** — Org outlier: Provider's taxonomy totally different from others under same billing NPI (probabilistic; clustering)
- **C4** — Inconsistent with entity/name: Taxonomy doesn't align with entity type or name pattern (probabilistic)

*Multiple checks per category; flag when any triggers. TML alignment required. Strictly provider-focused.*

---

## Roster Upload

DOGE is at least 1 year old. Allow a **roster upload** so the report can be run against a fresh provider list:

| Input | Purpose |
|-------|---------|
| **Roster file** | CSV: billing_npi, servicing_npi (optional). Or billing_npi only. |
| **Source** | Upload to GCS / BigQuery landing; or paste in chat |
| **Logic** | Join roster with NPPES, PML, TML, DOGE. Use roster to define scope; DOGE adds volume where available. |
| **Use case** | Current contracted roster, plan-specific list, new provider batch — run report without waiting for DOGE refresh |

Roster-only providers (no DOGE history) get NPPES/PML/TML validation; volume = 0. Report still actionable for enrollment/taxonomy status.

---

## Report Variants

### A. Executive-Ready Report
Summary metrics, high-level status, trend. For leadership / boards.

### B. Recommendation-Oriented Report
Actionable items, specific next steps, ranked by impact. For ops / provider relations.

### AI-First Design
Both reports are structured (section headers, tables, issue codes) so an LLM can:
- Answer "What's the status of org X?"
- Answer "What should we do about provider Y?"
- Generate executive or recommendation output from the same underlying data

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Billing Orgs (FL) | 1,247 |
| Total Servicing Providers | 8,432 |
| Total Billed Volume (2024) | $142.3M |
| **Status** | |
| Green (Ready) | 6,891 (82%) |
| Yellow (Attention needed) | 892 (11%) |
| Red (Action required) | 649 (8%) |
| **By Issue** | |
| A — Enrollment/contract | 412 |
| B — Address mismatch | 98 |
| C — Taxonomy mismatch (vs TML) | 156 |
| D — Taxonomy not approved for service | 73 |
| F — Entity type mismatch | 42 |

---

## 1. Org-Level Summary (by Billing NPI)

| Status | Billing NPI | Org Name | Provider Count | Total Spend | Issue Codes | TML Aligned | Status Message |
|--------|-------------|----------|----------------|-------------|-------------|-------------|----------------|
| G | 1234567890 | Sunshine Health Partners LLC | 12 | $2.4M | — | Yes | Ready today and set for next 3 months |
| Y | 2345678901 | Gulf Coast Medical Group | 8 | $1.1M | A | Yes | 3 providers: PML contract expires within 90 days |
| R | 3456789012 | Central FL Practice PA | 5 | $890K | A, C | 2 No | 2 providers not enrolled; 1 taxonomy not in TML |

---

## 2. Provider-Level Detail (Billing NPI → Servicing NPI)

**Org: Sunshine Health Partners LLC** (Billing NPI: 1234567890)  
Address: 100 Main St, Tampa, FL 33602

| Status | Servicing NPI | Provider Name | Total Paid | Top Services | TML | Issue | Status Message |
|--------|---------------|---------------|------------|--------------|-----|-------|----------------|
| G | 1111111111 | John Smith, MD | $312,000 | 99213, 99214 | Yes | — | Ready today and set for next 3 months |
| G | 2222222222 | Jane Doe, NP | $89,000 | 99213, 99214 | Yes | — | Ready today and set for next 3 months |
| Y | 3333333333 | Robert Jones, MD | $156,000 | 99215, 99214 | Yes | A | PML contract expires 2026-04-15 — renew enrollment |

---

**Org: Gulf Coast Medical Group** (Billing NPI: 2345678901)  
Address: 200 Oak Ave, Miami, FL 33101

| Status | Servicing NPI | Provider Name | Total Paid | Top Services | TML | Issue | Status Message |
|--------|---------------|---------------|------------|--------------|-----|-------|----------------|
| G | 4444444444 | Maria Garcia, MD | $420,000 | 99213, 99214, 97110 | Yes | — | Ready today and set for next 3 months |
| Y | 5555555555 | David Lee, PA | $98,000 | 99213, 99214 | Yes | A | PML contract expires 2026-04-30 — renew enrollment |
| R | 6666666666 | Susan White, NP | $85,000 | 99213, 99214 | — | A | Not enrolled in FL Medicaid — complete enrollment |

---

## 3. Action Items (Red / Yellow)

### Red — Action Required

| Billing NPI | Org Name | Servicing NPI | Provider Name | Spend | Issue | TML |
|-------------|----------|---------------|---------------|-------|-------|-----|
| 3456789012 | Central FL Practice PA | 7777777777 | Amy Brown, MD | $420,000 | A — Not enrolled | — |
| 3456789012 | Central FL Practice PA | 8888888888 | Tom Green, NP | $190,000 | E — NPI not in NPPES | — |
| 3456789012 | Central FL Practice PA | 9999999999 | Lisa Chen, MD | $120,000 | C — Taxonomy 207R00000X not in TML | No |
| 2345678901 | Gulf Coast Medical Group | 6666666666 | Susan White, NP | $85,000 | A — Not enrolled | — |

### Yellow — Attention Needed (3 months)

| Billing NPI | Org Name | Servicing NPI | Provider Name | Spend | Issue | Action |
|-------------|----------|---------------|---------------|-------|-------|--------|
| 2345678901 | Gulf Coast Medical Group | 5555555555 | David Lee, PA | $98,000 | A — PML expires 2026-04-30 | Renew enrollment before Apr 30 |
| 1234567890 | Sunshine Health Partners LLC | 3333333333 | Robert Jones, MD | $156,000 | A — PML expires 2026-04-15 | Renew enrollment before Apr 15 |

---

## 4. NPI Detail Cards (expandable / on demand)

**Servicing NPI: 6666666666 — Susan White, NP**

| Field | Value |
|-------|-------|
| Provider Name | Susan White |
| Entity Type | Individual (NP) |
| Address | 200 Oak Ave, Miami, FL 33101 |
| Primary Taxonomy | 363L00000X (Nurse Practitioner) |
| TML Aligned | — (not in PML) |
| Billing NPI | 2345678901 (Gulf Coast Medical Group) |
| 2024 Volume | $85,000 / 1,100 claims / 420 beneficiaries |
| Top HCPCS | 99213 ($42K), 99214 ($28K), 99215 ($15K) |
| **Status** | **Red** — Not enrolled in FL Medicaid |
| **Action** | Complete FL Medicaid provider enrollment application |

---

## 5. NPPES & PML Data by NPI (lookup view)

**Lookup:** Enter NPI → view NPPES and PML data side-by-side (used in detail cards and chat).

### NPI: 6666666666

| Source | Field | Value |
|--------|-------|-------|
| **NPPES** | Name | Susan White |
| **NPPES** | Entity Type | 1 (Individual) |
| **NPPES** | Address Line 1 | 200 Oak Ave |
| **NPPES** | Address Line 2 | Ste 101 |
| **NPPES** | City | Miami |
| **NPPES** | State | FL |
| **NPPES** | Zip | 33101 |
| **NPPES** | Primary Taxonomy | 363L00000X |
| **NPPES** | Taxonomies (all) | 363L00000X, 363LA2200X |
| **NPPES** | NPI Deactivation Date | (active) |
| **PML** | Medicaid Provider ID | — |
| **PML** | Enrolled | No |
| **PML** | Contract Effective | — |
| **PML** | Contract End | — |
| **PML** | Status | — |

### NPI: 5555555555 (Yellow — contract expiring)

| Source | Field | Value |
|--------|-------|-------|
| **NPPES** | Name | David Lee |
| **NPPES** | Entity Type | 1 (Individual) |
| **NPPES** | Address | 200 Oak Ave, Miami, FL 33101 |
| **NPPES** | Primary Taxonomy | 363A00000X (PA) |
| **PML** | Medicaid Provider ID | FL-MED-123456 |
| **PML** | Enrolled | Yes |
| **PML** | Contract Effective | 2023-01-01 |
| **PML** | Contract End | **2026-04-30** |
| **PML** | Status | Active |

*Tables to feed this: `npi_optimized` (NPPES), `stg_pml` (PML), `stg_tml` (TML). Python/chat: "Show NPPES and PML for NPI 6666666666" → render this view.*

### NPI: 9999999999 (C — taxonomy not in TML)

| Source | Field | Value |
|--------|-------|-------|
| **NPPES** | Primary Taxonomy | 207R00000X (Internal Medicine) |
| **NPPES** | Taxonomies (all) | 207R00000X, 207RN0300X |
| **TML** | 207R00000X in TML? | **No** — not approved for FL Medicaid |
| **PML** | Enrolled | Yes |
| **Recommendation** | Update taxonomy to TML-approved code or submit TML approval for 207R00000X |

---

## 6. Recommendation-Oriented Report (AI-first)

Structured for ops / provider relations. Same data, different framing: **what to do**.

### Top Recommendations (by spend at risk)

| Rank | Billing NPI | Org | Servicing NPI | Provider | Spend at Risk | Issue | Recommendation |
|------|-------------|-----|---------------|----------|---------------|-------|----------------|
| 1 | 3456789012 | Central FL Practice PA | 7777777777 | Amy Brown, MD | $420,000 | A — Not enrolled | Submit FL Medicaid enrollment application |
| 2 | 3456789012 | Central FL Practice PA | 8888888888 | Tom Green, NP | $190,000 | E — NPI not in NPPES | Verify NPI with provider; register in NPPES if missing |
| 3 | 3456789012 | Central FL Practice PA | 9999999999 | Lisa Chen, MD | $120,000 | C — Taxonomy not in TML | Update NPPES/PML taxonomy to TML-approved code |
| 4 | 2345678901 | Gulf Coast Medical Group | 6666666666 | Susan White, NP | $85,000 | A — Not enrolled | Submit FL Medicaid enrollment application |
| 5 | 1234567890 | Sunshine Health Partners LLC | 3333333333 | Robert Jones, MD | $156,000 | A — PML expires 2026-04-15 | Renew enrollment; complete before Apr 15 |

### Recommendations by Issue Type

| Issue | Count | Total Spend | Recommended Actions |
|-------|-------|-------------|---------------------|
| **A** — Enrollment/contract | 412 | $8.2M | Submit enrollment; renew contracts before expiry |
| **B** — Address mismatch | 98 | $1.1M | Align NPPES and PML addresses |
| **C** — Taxonomy mismatch | 156 | $2.4M | Update taxonomy to TML-approved; reconcile NPPES vs PML |
| **D** — Taxonomy not approved for service | 73 | $0.9M | Review billed HCPCS vs taxonomy; add taxonomy or change billing |
| **E** — NPI not in NPPES | 21 | $0.4M | Register provider in NPPES; verify NPI |
| **F** — Entity type mismatch | 42 | $0.6M | Reconcile entity type in NPPES; verify Individual vs Organization |

### Chat Prompts (AI-first)

- "What's the status of Central FL Practice PA?" → Executive summary + issue codes
- "What should we do about provider 7777777777?" → Recommendation + NPPES/PML/TML detail
- "Show me all providers with taxonomy not in TML" → Filtered list + recommendations
- "Generate executive summary for board" → Section 1 + metrics
- "Generate action list for provider relations" → Recommendation-oriented table

---

## 7. Three Output Formats — Design Characteristics

Each format has distinct structure, use case, and design principles.

### PDF (Long-form, shareable)

| Characteristic | Design |
|----------------|--------|
| **Audience** | Leadership, board, external parties |
| **Structure** | Narrative flow: executive summary → org summaries → action items → appendices |
| **Length** | Condensed; 2–5 pages typical |
| **Visual** | Tables, status flags (G/Y/R), clear section headers |
| **Interactivity** | None; static snapshot |
| **Refresh** | Run monthly; download per report date |
| **Content** | Executive summary, top 10–20 orgs by spend, Red/Yellow action tables, issue breakdown |

### CSV (Downloadable long-form data)

| Characteristic | Design |
|----------------|--------|
| **Audience** | Analysts, ops, provider relations (Excel, BI tools) |
| **Structure** | Flat or multi-sheet; one row per provider (or per org); all columns for filtering |
| **Length** | Full dataset; no summarization |
| **Visual** | N/A; raw structured data |
| **Interactivity** | Filter, pivot, sort in Excel/Sheets |
| **Refresh** | Run monthly; same report date as PDF |
| **Content** | All columns: report_date, billing_npi, servicing_npi, org_name, provider_name, address, status_flag, reason_today, reason_3mo, issue_codes (A/B/C/D/E), tml_aligned, total_paid, claim_count, top_hcpcs, nppes_*, pml_* |

### Chat (Answerable, conversational)

| Characteristic | Design |
|----------------|--------|
| **Audience** | Internal users; ad-hoc questions |
| **Structure** | Q&A; LLM fetches from tables and formats response |
| **Length** | Variable; depends on question |
| **Visual** | Markdown tables, bullet lists, inline status |
| **Interactivity** | Ask follow-ups; "drill down" by NPI, org, issue |
| **Refresh** | Real-time (queries current tables) |
| **Content** | Same underlying tables; responses tailored to prompt |

### Format Comparison

| | PDF | CSV | Chat |
|---|-----|-----|------|
| **Output** | Fixed narrative | Full dataset | Dynamic answer |
| **Use** | Share, present | Analyze, filter | Ask, explore |
| **Scope** | Curated | Exhaustive | On-demand |

### Implementation

| Component | Location |
|-----------|----------|
| `provider_readiness` | dbt: `mobius_medicaid_npi_dev.provider_readiness` |
| `provider_readiness_summary` | dbt: `mobius_medicaid_npi_dev.provider_readiness_summary` |
| `provider_readiness_report` | dbt: `mobius_medicaid_npi_dev.provider_readiness_report` |
| Report generator | `mobius-dbt/scripts/generate_provider_readiness_report.py` |
| Output | `mobius-dbt/reports/provider_readiness_{date}.csv`, `.md`, `_chat.json` |

```bash
# 1. Run dbt (set report_date)
BQ_PROJECT=mobius-os-dev BQ_MARTS_MEDICAID_DATASET=mobius_medicaid_npi_dev \
  uv run dbt run --vars '{"report_date": "2026-02-01"}' --select provider_readiness provider_readiness_summary provider_readiness_report

# 2. Generate report (full)
REPORT_DATE=2026-02-01 uv run python scripts/generate_provider_readiness_report.py

# Or single org first (faster; validate before full run)
REPORT_DATE=2026-02-01 BILLING_NPI=<billing_npi> uv run python scripts/generate_provider_readiness_report.py
```
