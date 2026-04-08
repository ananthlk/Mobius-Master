---
name: financial-benchmarking
description: >
  Use this skill for any Medicare claims benchmarking, provider performance analysis, or market archetping using DOGE data in BigQuery. Triggers include: benchmarking community mental health centers (CMHCs), comparing provider panel sizes, analyzing claims per beneficiary, evaluating payment rates, characterizing FL or national markets by provider density, generating peer comparisons for NPIs or organizations, building strategy decks with benchmarking data, or any request involving servicing NPI metrics, taxonomy-adjusted peer groups, or DOGE dataset analysis. Use this skill even if the user just asks to "compare" providers, "look up" a market, or "pull benchmarks" — it applies broadly to any provider performance or market intelligence workflow built on DOGE Medicare data.
---

# Financial Benchmarking — DOGE Medicare Claims

## Overview

This skill benchmarks healthcare providers (primary focus: community mental health centers in Florida) using DOGE Medicare claims data stored in BigQuery. It computes three core KPIs, supports taxonomy-adjusted peer comparison, and produces market archetype characterizations layered with public data.

---

## Data Sources

| Source | Location | Purpose |
|--------|----------|---------|
| DOGE Medicare claims | BigQuery (user's project) | Core claims data |
| NPI Registry MCP | `https://mcp.deepsense.ai/npi_registry/mcp` | Taxonomy lookups per NPI |
| CMS Coverage MCP | `https://mcp.deepsense.ai/cms_coverage/mcp` | Coverage/market context |
| ICD-10 Codes MCP | `https://mcp.deepsense.ai/icd10_codes/mcp` | Code descriptions |
| Public data (HRSA, CMS) | Web search / fetch | Physicians per 1,000 Medicaid for market archetypes |

**DOGE BigQuery schema** (per row):
- `service_month` (DATE or YYYYMM)
- `hcpcs_code`, `icd10_code`
- `servicing_npi`, `billing_npi`
- `total_claims`, `total_beneficiaries`, `total_paid`

> If the user's BQ table name or project is unknown, ask before generating queries.

---

## The Three Core KPIs

```
panel_size             = SUM(total_beneficiaries) per servicing_npi per month
claims_per_beneficiary = SUM(total_claims) / SUM(total_beneficiaries)
payment_per_claim      = SUM(total_paid) / SUM(total_claims)
```

### Interpretation Guide

| KPI | Low Signal | High Signal |
|-----|-----------|-------------|
| Panel Size | Marketing/access problem, low reach | Overscoped, capacity risk |
| Claims per Beneficiary | No-shows, underutilization | High utilization (at extremes: potential abuse) |
| Payment per Claim | Low effective reimbursement rates | Strong contract or high-acuity billing |

---

## Benchmarking Hierarchy

Always compute metrics at each level:

```
Servicing NPI + Taxonomy
        ↓
   Organization  (only when a named org is provided — use custom org logic)
        ↓
      ZIP Code
        ↓
      MSA
        ↓
     State (FL)
        ↓
    National
```

**Peer comparison** must always be **taxonomy-mix adjusted**:
- Identify the subject's taxonomy distribution (% of activity per taxonomy)
- Weight peer group metrics using that same taxonomy distribution
- This ensures like-for-like comparison across mixed-practice providers

---

## Taxonomy Handling

- Pull **all taxonomies** for each servicing NPI via NPI Registry MCP
- Do **not** pre-filter to specific taxonomies — capture full scope of service
- Apply taxonomy filters only at query/analysis time per user request
- For CMHC benchmarking, relevant taxonomy codes include (but are not limited to):
  - `101Y` (Mental Health Counselor)
  - `103T` (Psychologist)
  - `106H` (Marriage & Family Therapist)
  - `251S` (Psychiatric Residential Treatment Facility)
  - `261Q` (Clinic/Center — Mental Health)
  - Confirm full list via NPI Registry lookups when analyzing a specific market

---

## Time Windows

Support all of the following (user selects):

| Mode | Description |
|------|-------------|
| Single month | Point-in-time snapshot |
| Rolling 3-month | Smoothed trend, reduce noise |
| Full year | Annual trend, seasonality visible |

Always label the time window clearly in outputs. For trend charts, show all three KPIs over time.

---

## Benchmark Position Metrics

Support all three (configurable):

| Method | Formula | Use Case |
|--------|---------|----------|
| Percentile rank | % of peers below subject | Most intuitive for client decks |
| Z-score | (subject − peer mean) / peer std dev | Precise outlier detection |
| Above/below median flag | Binary: above or below peer median | Quick executive summary |

Default to **percentile rank** unless user specifies otherwise. Always show the underlying peer distribution (n, mean, median, p25, p75).

---

## Output Modes

### 1. Market Archetype Report
See `references/market-archetype.md` for full instructions.

Characterize FL ZIPs and MSAs by:
- Provider density (servicing NPIs per 1,000 Medicaid beneficiaries)
- Panel size distribution
- Claims per beneficiary distribution
- Payment per claim distribution
- Public data overlay: physicians per 1,000 Medicaid (from HRSA/CMS)

Produce archetype labels such as:
- **Underserved / High Demand** — low provider density, high panel sizes
- **Saturated / Competitive** — high provider density, low panel sizes
- **Underutilizing** — normal panel size, low claims per beneficiary
- **High Intensity** — high claims per beneficiary, high payment per claim

### 2. Interactive Benchmarking
See `references/benchmarking-queries.md` for BigQuery templates.

Steps:
1. Ask user: subject (NPI, org name, ZIP, or MSA), time window, benchmark level, position metric
2. Pull taxonomy profile for subject NPI(s) via NPI Registry MCP
3. Generate taxonomy-adjusted peer group BQ query
4. Compute KPIs + benchmark position for subject vs. peers
5. Present: summary table, percentile/z-score, peer distribution stats
6. Optionally drill to HCPCS code level within the subject's profile

### 3. Strategy Narrative
See `references/strategy-narrative.md` for framing guidance.

Synthesize findings into client-ready language:
- Lead with the "so what" for each KPI
- Contextualize against market archetype
- Flag outliers and their likely operational explanation
- Recommend 2–3 strategic implications per finding

---

## Org-Level Logic

Only invoke when a **named organization** is provided by the user.

- Do not attempt to derive org groupings from billing NPI alone for all providers
- The user has custom org-assembly logic — ask them to confirm the org's NPI list or trigger their existing org logic
- Once NPIs are confirmed, aggregate metrics across all servicing NPIs in the org

---

## Geographic Scope

- **Primary focus**: Florida (state + MSA + ZIP)
- **Benchmark baseline**: National (always compute national percentiles)
- **FL highlight**: Show FL distribution separately within national context
- When comparing FL markets, label MSAs clearly (e.g., Miami-Fort Lauderdale, Tampa-St. Pete, Orlando, Jacksonville)

---

## Standard Workflow

```
1. Clarify: subject, time window, benchmark level, output mode
2. Fetch taxonomy profile (NPI Registry MCP)
3. Generate + run BQ queries (see references/benchmarking-queries.md)
4. Compute KPIs at each geographic level
5. Build taxonomy-adjusted peer group
6. Compute benchmark position (percentile / z-score / median flag)
7. Layer in market archetype data if requested
8. Produce output in requested mode (report / interactive / narrative)
```

---

## Reference Files

- `references/benchmarking-queries.md` — BigQuery SQL templates for all KPIs and peer groupings
- `references/market-archetype.md` — Market archetping methodology and scoring
- `references/strategy-narrative.md` — Client-facing narrative framing and language guide
