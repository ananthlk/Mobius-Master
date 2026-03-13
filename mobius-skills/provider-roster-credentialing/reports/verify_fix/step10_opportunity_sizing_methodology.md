# Revenue Waterfall & Opportunity Sizing — Methodology

*Include this in credentialing report runs. Last updated: 2025-02.*

---

## What We're Doing

We estimate Medicaid revenue for an organization's provider roster in five levels:

| Level | Name | Description |
|-------|------|-------------|
| **A** | Guaranteed revenue | Revenue from providers correctly enrolled and passing PML validation. |
| **B** | At-risk revenue | Revenue from providers enrolled but with PML issues (wrong taxonomy, ZIP, etc.). At risk until remediated. |
| **C** | Enrollment opportunity | Revenue from providers on the roster who are not in PML but could be enrolled. |
| **D** | Taxonomy optimization | Additional revenue if enrolled providers used their highest-paying valid taxonomy instead of their current one. |
| **E** | Rate gap opportunity | Additional revenue if the org's effective payment rate (revenue per claim) matched state benchmark instead of the org's current rate. |

Benchmarks (org → ZIP → state → national) drive revenue per member and revenue per claim. Uplifts for D and E use **revenue per claim** as the rate metric.

---

## Why This Is "Opportunity"

- **A** = baseline — what we're confident is flowing today.
- **B** = risk — what could be lost if incorrect entries are not fixed.
- **C** = new capture — revenue we could gain by enrolling missing providers.
- **D** = better coding — revenue we could gain by switching to the best valid taxonomy.
- **E** = performance gap — revenue we could gain by matching state rates.

Together, B through E form the **revenue opportunity**: the gap between current state and full potential, with each layer additive and explainable.

---

## Waterfall Structure

The steps form a waterfall:

1. **Levels 1–3 (A, B, C)** — revenue buckets: baseline, at-risk, enrollment gap.
2. **Levels 4–5 (D, E)** — optimization uplifts applied on top.

Order: secure baseline (A) → quantify at-risk (B) → quantify enrollment gap (C) → taxonomy uplift (D) → rate uplift (E).

---

## Technical Notes

- **Scope for D (taxonomy optimization):** Only **valid** and **flagged** (already enrolled). Exclude **missing** — they are not in PML yet; their opportunity is C (enroll). Exclude **entity_type=2 (organizations)** — taxonomy recommendations like "convert residential treatment center to community mental health center" don't apply to org NPIs; orgs can't change taxonomy type that way.
- **Scope for E (rate gap):** All NPIs (valid, flagged, missing) where we have a taxonomy and org benchmark.
- **Metric for uplifts:** Revenue per claim (effective rate).
- **Uplift method:** Percent difference — multiply base revenue by (1 + pct_diff).
- **Org × taxonomy benchmark:** Computed when needed for org-specific rates by taxonomy.

---

## NPI-Level Detail (Tick-and-Tie)

The opportunity sizing output includes **per-NPI detail** (`step10_opportunity_sizing_detail.csv` / `npi_detail`) so users and the critique module can validate and trace every dollar:

| Field | Purpose |
|-------|---------|
| `npi`, `provider_name`, `bucket` | Identify the provider and bucket (valid/flagged/missing). |
| `pml_source_file` | `step6_pml_validation.csv` (valid/flagged) or `step7_missing_pml_enrollment.csv` (missing). |
| `pml_row_key` | `npi=X,taxonomy_code=Y` — lookup key to find this NPI in the PML file. |
| `benchmark_file` | `step1_benchmarks.csv` |
| `benchmark_source` | Geography used: `org`, `zip5:XXXXX`, `state:FL`, or `national:US`. |
| `benchmark_geography_type`, `benchmark_geography_value` | Matches `step1_benchmarks.csv` columns for lookup. |
| `benchmark_row_key` | `taxonomy_code=X,geography_type=Y,geography_value=Z` — lookup key to find the benchmark row. |
| `base_revenue`, `taxonomy_opt_uplift`, `rate_gap_uplift` | Dollar contributions; sum to aggregates. |

When passed to the **critique module**, this file can validate: each NPI appears in the referenced PML file, each benchmark row exists in `step1_benchmarks.csv`, and dollar totals reconcile to the summary A–E amounts.
