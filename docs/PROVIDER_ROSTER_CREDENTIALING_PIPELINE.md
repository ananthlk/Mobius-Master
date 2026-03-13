# Provider Roster Credentialing Pipeline: End-to-End Flow

This document traces the full pipeline from dbt models through report generation to LLM output. Use it to understand what happens at each step and where to look when debugging.

---

## Table of Contents

1. [Overview](#1-overview)
2. [API / Chat Flow Step Sequence (1–11)](#2-api--chat-flow-step-sequence-111)
3. [Step 1: dbt Models (BigQuery)](#3-step-1-dbt-models-bigquery)
4. [Step 2: Report Generation Script](#4-step-2-report-generation-script)
5. [Step 3: Core Report Build (Python)](#5-step-3-core-report-build-python)
6. [Step 4: Confidence Algorithm](#6-step-4-confidence-algorithm)
7. [Step 5: LLM Enhancement (Optional)](#7-step-5-llm-enhancement-optional)
8. [Outputs](#8-outputs)
9. [Environment & Commands](#9-environment--commands)

---

## 1. Overview

```
┌─────────────────────┐     ┌──────────────────────────────┐     ┌─────────────────────┐
│   dbt run           │     │  build_full_report()         │     │  --enhance          │
│   bh_roster+        │────▶│  (provider-roster-cred)      │────▶│  LLM pipeline       │
│                     │     │                              │     │  + charts + PDF     │
└─────────────────────┘     └──────────────────────────────┘     └─────────────────────┘
        │                                    │
        ▼                                    ▼
  BigQuery marts                    CSVs, metrics.json,
  (bh_roster, readiness, etc.)      raw summary MD
```

- **dbt** builds the roster and readiness data in BigQuery.
- **Python** (provider-roster-credentialing skill) queries BigQuery and builds the report structure.
- **LLM** (when `--enhance`) turns raw metrics into a white-paper narrative.

---

## 2. API / Chat Flow Step Sequence (1–11)

When the user asks for a credentialing report in chat (or runs `run_roster_api_flow.py`), the provider-roster API executes these steps in order:

| # | Step | Description |
|---|------|-------------|
| 1 | **Ensure revenue metrics** | Populate `taxonomy_utilization_benchmarks` (utilization benchmarking). Runs first. |
| 2 | **Identify organization** | Search org by name → org NPIs |
| 3 | **Find practice locations** | Locations for org NPIs |
| 4 | **Find associated providers** | Roster + active roster (score ≥ 50) |
| 5 | **Org benchmark** | Utilization metrics for this org's active roster (DOGE) |
| 6 | **Find services by location** | Taxonomies, Medicaid approval |
| 7 | **Historic billing patterns** | DOGE, HCPCS breakdown |
| 8 | **PML validation** | NPI, taxonomy, ZIP, Medicaid ID checks |
| 9 | **Missing PML enrollment** | Active roster NPIs not in PML (suggest taxonomy + location) |
| 10 | **Opportunity sizing** | Revenue waterfall A–E: Guaranteed, At-risk, Enrollment, Taxonomy opt, Rate gap |
| 11 | **Build credentialing report** | Final report via MCP |

**Step 1** = utilization benchmarking (revenue metrics). **Step 11** = report generation.

---

## 3. Step 1: dbt Models (BigQuery)

**Run:** `cd mobius-dbt && uv run dbt run --select bh_roster+`

### Model Dependency Order

| Model | Description |
|-------|-------------|
| `bh_roster` | Core roster: org + servicing NPI pairs. **Points-based matching** (threshold 28): nppes_addr=25, pml_addr=20, zip9=18, pml_zip9=15, zip5=6 (exclusive), city_state=3. Billing pairs from DOGE kept separately. `address_match_type`: strong (≥50), medium (35–49), partial (28–34). **Site derivation**: Base sites = org addresses (entity type 1 or 2, NPPES or PML union). Additional sites = practice addresses of servicing NPIs who billed under the org (DOGE), from NPPES or PML (union). For billing-based rows with different servicing-NPI address: `site_*` = that address; else `site_*` = org address. `site_source`: base \| additional. |
| `bh_roster_sites` | Distinct site-level details per org with reasoning. One row per (org_npi, site address). `site_source`: base (org address) \| additional (servicing NPI practice address from DOGE). `site_reason` explains why the site was added. Consumed by `get_locations()` for report locations. |
| `bh_roster_readiness` | Four Medicaid NPI checks per roster row: (1) NPI in PML, (2) ZIP+4 valid, (3) taxonomy on TML, (4) NPI+taxonomy+ZIP9 combo in PML. Outputs `readiness_all_pass`, `readiness_status`, `readiness_summary`, `confidence_score`, `total_claims_3yr`. |
| `fl_medicaid_taxonomy_revenue_rates` | Taxonomy-level revenue rates from DOGE 2024. |
| `bh_roster_revenue_impact` | Joins readiness to revenue rates → `est_revenue_low`, `est_revenue_mid`, `est_revenue_high` per combo. |
| `ghost_billing_fl` | NPIs that bill under org (DOGE) but have weak roster match (`confidence_score < 40`). |

### Key Tables

- **Inputs:** `stg_doge`, `stg_pml`, `nppes_public.npi_raw`, `bh_provider_locations`, `nucc_lookup`, `stg_bh_taxonomy_whitelist`
- **Schema:** `BQ_MARTS_MEDICAID_DATASET` (default `mobius_medicaid_npi_dev`)

---

## 4. Step 2: Report Generation Script

**Run:** `uv run python scripts/generate_provider_roster_credentialing_report.py --org-name "Aspire Health Partners" [--locations-override path/to.json] [--enhance]`

**File:** `mobius-dbt/scripts/generate_provider_roster_credentialing_report.py`

### CLI Arguments

| Argument | Purpose |
|----------|---------|
| `--org-name` | Org name (pattern match on roster). |
| `--locations-override` | JSON file: user-validated L2 locations. **Replaces** system L1 list. Required for full location coverage (e.g. 24 sites vs 3 from roster). |
| `--locations` | JSON file: list of `location_id`s to include (subset). |
| `--npi-overrides` | JSON: per `location_id` add/remove NPIs. |
| `--enhance` | Run LLM pipeline (charts + white-paper + PDF). |
| `--no-pipeline` | With `--enhance`: use single Drafter only (no Validator/Critic/Composer). |
| `--no-pdf` | Skip PDF generation. |

### Flow Inside Script

1. Load env (mobius-dbt/.env, mobius-config/.env).
2. Parse `--locations-override`, `--npi-overrides`.
3. Call `build_full_report()` from `mobius-skills/provider-roster-credentialing`.
4. Write CSVs (primary + detailed).
5. Write `metrics.json`.
6. If `--enhance`: generate charts → run LLM pipeline → write PDF.

---

## 5. Step 3: Core Report Build (Python)

**Entry point:** `build_full_report()` in `mobius-skills/provider-roster-credentialing/app/core.py`

### 4.1 Locations (L1 / L2 / L3)

| Step | Function | What Happens |
|------|----------|--------------|
| L1 | `get_locations()` | Query `bh_roster` for distinct (org_npi, site_address, city, state, zip) where org_name LIKE `%{org_name}%`. State filtered (default FL). |
| L2 | `merge_locations_l1_l2()` | If `locations_override` is provided, it **replaces** L1. Otherwise use L1 as-is. |
| L3 | (result) | Final location list. `match_source`: `l1` or `l2_new`. Each location has `location_id` (hash of org_npi + address). |

**Without `--locations-override`:** Only L1 locations appear (often 3–5 for an org).

### 4.2 NPIs Per Location

| Step | Function | What Happens |
|------|----------|--------------|
| Roster match | `get_npis_per_location()` | Query `bh_roster` by org name + `location_id`. Returns NPIs at each location. Includes `confidence_score` from roster. |
| L2-new | `get_npis_by_address()` | For L2-new locations: match bh_roster rows by address (street+zip strong, zip partial). Uses Google Address Validation when available. |

### 4.3 Readiness & Revenue

| Step | Function | What Happens |
|------|----------|--------------|
| Readiness | `get_readiness_and_revenue_impact()` | Prefer `bh_roster_revenue_impact` (has est_revenue_*). Fallback: `bh_roster_readiness`. Filter by org_npis and servicing_npis. |
| Fallback | `get_readiness_and_combos()` | Used when revenue_impact table missing. |
| Ghost | `get_ghost_billing()` | Query `ghost_billing_fl` for org’s billing NPIs. |

### 4.4 Derived Structures

| Structure | Source | Purpose |
|-----------|--------|---------|
| `confidence_report` | All combos stratified by confidence_band (perfect/good/medium/low). Each row has checks (Medicaid ID, approved NPI, etc.) that tally. |
| `invalid_combos` | `readiness_rows` where `readiness_all_pass = false` | Combos needing remediation. |
| `missed_opportunities` | Locations with no ready NPI; NPIs in PML but combo fail | Gaps. |
| `per_npi_validation` | One row per NPI from readiness | Per-NPI check summary. |
| `executive_summary` | `build_executive_summary()` | Metrics, revenue, confidence breakdown, recommendations. |
| `primary_report` | `_build_primary_report()` | Simple sheet: locations, distinct NPIs (with why_belongs, confidence_band), taxonomies, billing. |

### 4.5 Primary Report (`_build_primary_report`)

- **locations**: Address, city, state, zip, match_source.
- **distinct_npis**: NPI, name, why_belongs, confidence_score, confidence_band (perfect/good/medium/low), roster_org_names.
- **taxonomies_covered**: From combos.
- **billing_activity**: Aggregated by taxonomy from combos. Uses `claim_count`, `total_paid` from combos — **note:** readiness rows have `total_claims_3yr`, not `claim_count`/`total_paid`, so billing_activity often shows 0s unless wired correctly.

### 4.6 Confidence for Distinct NPIs

- From **combos** (readiness_rows): `confidence_score` per row.
- From **npis_per_location**: roster `confidence_score` for each NPI.
- Per NPI: `max(combo confidence, roster confidence)`.
- Band: `perfect` ≥90, `good` 70–89, `medium` 50–69, `low` &lt;50 or null.

---

## 6. Step 4: Confidence Algorithm

**Location:** `mobius-dbt/models/marts/bh_roster/bh_roster.sql` (CASE expression)

### Four-Tier Rules (Score → Band)

| Band | Score | Condition |
|------|-------|-----------|
| **perfect** | 95–100 | Same address + ZIP9 + historic billing |
| **good** | 70–90 | Historic billing + (ZIP9 or address); billing corroborates |
| **medium** | 50–65 | Same address + ZIP9, no billing (likely new joiners) |
| **low** | 15–45 | Partial address only; or address-only + bills elsewhere |

### Definitions (for report text)

Defined in `core.py` → `CONFIDENCE_DEFINITIONS`.

---

## 7. Step 5: LLM Enhancement (Optional)

**When:** `--enhance` is passed.

### 6.1 Charts

- **Source:** `report_visuals.py` → `get_chart_spec_from_llm()`, `generate_charts()`.
- **Outputs:** `*_executive_dashboard.png`, `*_revenue_by_status.png`, `*_revenue_by_confidence.png`, `*_confidence_breakdown.png`, etc.

### 6.2 LLM Pipeline (default: full pipeline)

| Stage | Role | Output |
|-------|------|--------|
| Drafter | Generate initial white-paper | `*_draft.md` |
| Validator | Compare report numbers to CSVs | `*_validation_report.md` |
| Critic | Narrative quality feedback | `*_critique_report.md` |
| Composer | Merge feedback into final report | `*_<ts>.md` |

**Single-Drafter mode** (`--no-pipeline`): Only Drafter; no Validator/Critic/Composer.

### 6.3 PDF

- **Source:** `report_pdf.py` → `markdown_to_pdf()`.
- Converts final MD to PDF.

---

## 8. Outputs

### Without `--enhance`

| File | Content |
|------|---------|
| `*_primary_locations.csv` | L3 locations with site_source, site_reason (why site was added). |
| `*_primary_distinct_npis.csv` | Distinct NPIs, why_belongs, confidence_score, confidence_band. |
| `*_primary_taxonomies_covered.csv` | Taxonomies with labels. |
| `*_primary_billing_activity.csv` | Billing by taxonomy (currently often 0s; needs `total_claims_3yr`/`total_spend_3yr` wiring). |
| `*_locations.csv` | L3 locations with org_npi, site_*, location_id, site_source, site_reason. |
| `*_npis_per_location.csv`, etc. | Detailed CSVs. |
| `*_metrics.json` | Canonical metrics. |
| `*.md` | Raw executive summary. |

### With `--enhance`

All of the above, plus:

| File | Content |
|------|---------|
| `*_executive_dashboard.png` | Summary dashboard. |
| `*_revenue_by_confidence.png` | Revenue by perfect/good/medium/low. |
| `*_draft.md` | LLM draft. |
| `*_validation_report.md` | Numeric validation vs CSVs. |
| `*_critique_report.md` | Narrative critique. |
| `*.md` | Final white-paper. |
| `*.pdf` | PDF of final report. |
| `*_raw_summary.md` | Raw metrics snapshot. |

---

## 9. Environment & Commands

### Environment Variables

| Var | Purpose |
|-----|---------|
| `BQ_PROJECT` | BigQuery project (default: mobius-os-dev). |
| `BQ_MARTS_MEDICAID_DATASET` | Mart schema (default: mobius_medicaid_npi_dev). |
| `BQ_LANDING_MEDICAID_DATASET` | Landing schema. |
| For LLM | `OPENAI_API_KEY` or `GEMINI_API_KEY` or `VERTEX_PROJECT_ID` / `CHAT_VERTEX_PROJECT_ID` |

### End-to-End Commands

```bash
# 1. Run dbt (from mobius-dbt)
cd mobius-dbt
uv run dbt run --select bh_roster+

# 2. Generate report (no LLM)
uv run python scripts/generate_provider_roster_credentialing_report.py \
  --org-name "Aspire Health Partners"

# 3. Generate report with L2 locations override
uv run python scripts/generate_provider_roster_credentialing_report.py \
  --org-name "Aspire Health Partners" \
  --locations-override path/to/aspire_locations_override.json

# 4. Full pipeline with LLM + PDF
uv run python scripts/generate_provider_roster_credentialing_report.py \
  --org-name "Aspire Health Partners" \
  [--locations-override path/to/aspire_locations_override.json] \
  --enhance
```

### API Flow: Roster Run with Baseline Comparison

For before/after comparison (e.g. after roster logic changes: penalties, active cutoff, org name mismatch):

1. **Start the provider-roster API** (from `mobius-skills/provider-roster-credentialing`):

   ```bash
   uvicorn app.main:app --port 8010
   ```

2. **First run (baseline)** – save outputs:

   ```bash
   cd mobius-skills/provider-roster-credentialing
   uv run python scripts/run_roster_api_flow.py --org-name "David Lawrence" --output-dir reports/baseline
   ```

3. **Second run (after changes)** – compare to baseline:

   ```bash
   uv run python scripts/run_roster_api_flow.py --org-name "David Lawrence" \
     --output-dir reports/new --baseline-dir reports/baseline
   ```

4. **Outputs per step:** `step1_identify_org.csv`, `step2_find_locations.csv`, `step3_find_associated_providers.csv`, `step3_active_roster.csv`, `step4_find_services_by_location.csv`, `step5_historic_billing.csv`, `step6_pml_validation.csv`, plus `summary.json` for counts. The script prints a before/after comparison when `--baseline-dir` is given.

### Key File Paths

| Component | Path |
|-----------|------|
| dbt models | `mobius-dbt/models/marts/bh_roster/` |
| Report script | `mobius-dbt/scripts/generate_provider_roster_credentialing_report.py` |
| Core logic | `mobius-skills/provider-roster-credentialing/app/core.py` |
| Report writer | `mobius-skills/provider-roster-credentialing/app/report_writer.py` |
| Report pipeline | `mobius-skills/provider-roster-credentialing/app/report_pipeline.py` |
| Report visuals | `mobius-skills/provider-roster-credentialing/app/report_visuals.py` |
| Output | `mobius-dbt/reports/<Org_Name>/<YYYYMMDD_HHMM>/` |
| API flow script | `mobius-skills/provider-roster-credentialing/scripts/run_roster_api_flow.py` |

---

## Known Gaps (As of This Doc)

1. **primary_billing_activity**: Uses `claim_count` and `total_paid`, but readiness/combos expose `total_claims_3yr` and `total_spend_3yr`. Needs mapping or schema alignment.
2. **Procedure-code billing**: Report is taxonomy-based. A yearly HCPCS/procedure-code view would require new queries (e.g. from stg_doge or taxonomy_hcpcs_volume_fl).
3. **Locations count**: Without `--locations-override`, only L1 (roster) locations appear. Use L2 override JSON for full site list.
