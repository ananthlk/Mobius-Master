# FL Medicaid Rate Benchmarking — Methodology & Interpretation Guide

## Purpose

This benchmarking table (`hcpcs_rate_benchmarks`) establishes FL Medicaid reimbursement benchmarks by HCPCS code, enabling organizations to understand where their rates stand relative to peers across multiple dimensions. It surfaces **questions, not conclusions** — observed differences may reflect rate variation, billing practices, unit counts, patient acuity, or payor mix.

## Data Source

- **DOGE Medicaid Provider Spending** — FL Medicaid claims (FFS + MCO), 2024 calendar year
- **NPPES** — Provider taxonomy, entity type, practice location (state/ZIP)
- **Professional servicing NPIs only** — entity_type_code = 1 in NPPES, FL practice location

## Unit of Analysis

**Organization-level aggregation.** All professional servicing NPIs are rolled up per billing organization (identified by billing_npi → org_entities). Percentiles are computed **across orgs**, not across individual NPIs.

Why org-level: For CMHCs, FQHCs, and group practices, per-NPI rates can be misleading because the payment flows to the billing org. A servicing NPI within a CMHC may show near-zero payment on individual claims while the org collects the full rate. Org-level aggregation captures the true effective rate.

## Three KPIs

Each benchmark row provides P25/P50/P75 for three complementary KPIs:

### 1. Payment per Claim (`payment_per_claim`)
- **Formula:** `SUM(total_paid) / SUM(total_claims)` per org per HCPCS
- **What it measures:** Effective rate per claim line
- **Caveat:** A single claim line can carry multiple units (e.g., 6 x 15-min units for H2019). Two orgs with the same per-unit rate but different session lengths will show different payment_per_claim. **This is not unit-adjusted.**
- **Use:** Answers "how much does a claim line pay?" — a proxy for rate, but confounded by units-per-claim.

### 2. Revenue per Beneficiary (`revenue_per_beneficiary`)
- **Formula:** `SUM(total_paid) / SUM(beneficiary_count)` per org per HCPCS
- **What it measures:** Total collected per unique patient for this service
- **Caveat:** Reflects both rate AND utilization (visit frequency x units per visit). A high revenue_per_beneficiary could mean high rates, frequent visits, long sessions, or all three.
- **Use:** Answers "how much revenue does this code generate per patient?" — the utilization-adjusted view.

### 3. Claims per Beneficiary (`claims_per_beneficiary`)
- **Formula:** `SUM(total_claims) / SUM(beneficiary_count)` per org per HCPCS
- **What it measures:** Visit/claim frequency per patient
- **Use:** Disambiguates payment_per_claim vs revenue_per_beneficiary. If org A has high $/claim but normal claims/bene, the difference is rate or unit-driven, not visit-frequency-driven.

### Interpreting the Three Together

| Scenario | $/claim | $/bene | cl/bene | Likely Explanation |
|----------|---------|--------|---------|-------------------|
| High | High | Normal | Higher rate per unit OR longer sessions (more units per claim) |
| Normal | High | High | Normal rate, more visits per patient (higher utilization) |
| High | High | High | Both rate premium AND higher utilization |
| Low | Low | Normal | Lower rate per unit OR shorter sessions |
| Normal | Low | Low | Normal rate, fewer visits (possible access issue or different patient mix) |

**Important:** These are observations, not diagnoses. The benchmarking table cannot determine WHY rates differ — only that they do. Root cause requires examining:
- Actual units per claim (not in DOGE data)
- Modifier usage (not in DOGE data)
- MCO contract terms
- Patient acuity / case mix
- Billing practices

## Dimension Axes (Parallel Cuts)

Each axis slices the full FL population independently — **no compounding**. This preserves N (sample size) for credible comparison.

| Axis | Values | What It Answers |
|------|--------|----------------|
| `all_fl` | (baseline) | Where do you stand vs all FL Medicaid orgs? |
| `by_entity` | individual / organization | Solo practitioners vs org-billed — different rate structures |
| `by_org_type` | CMHC, FQHC, BH_SPECIALTY, COMMUNITY_BH, SUD, RESIDENTIAL_BH, RHC, OTHER | Rates vary by org type due to different billing models and payor contracts |
| `by_size` | small / medium / large | Panel_per_clinician bands — larger orgs may have more negotiating leverage or different case mix |
| `by_market` | sparse / moderate / dense | Competitive density — sparse markets may have different rate dynamics than urban |
| `by_taxonomy` | billing NPI primary taxonomy code | Specific provider type (MH Counselor vs Psychiatry vs Social Worker org) |

### Org Type Definitions

| Org Type | Taxonomy Basis | Typical Billing Pattern |
|----------|---------------|----------------------|
| **CMHC** | 261QM0801X | CBH fee schedule H-codes, bundled encounter billing |
| **FQHC** | 261QF0400X | PPS encounter rate — per-CPT rates often $0 (paid as encounter) |
| **RHC** | 261QR1300X | All-inclusive rate — similar to FQHC |
| **SUD** | 101YA0400X, 261QR0405X, etc. | Substance use-specific codes |
| **RESIDENTIAL_BH** | 322D, 323P, 3244U | Per-diem billing |
| **COMMUNITY_BH** | 251S, 261QC, 261Q, etc. | Mix of CBH + outpatient |
| **BH_SPECIALTY** | 101Y, 103T, 1041C, 106H, 2084P, 363L | Individual/group therapy practices — closest to fee schedule rates |
| **OTHER** | All others | Non-BH Medicaid orgs |

### Size Band Definitions

| Size | Panel per Clinician | Typical Profile |
|------|-------------------|----------------|
| small | < 100 | Solo/small group, limited capacity |
| medium | 100–499 | Mid-size practice or CMHC |
| large | ≥ 500 | Large CMHC, FQHC, or multi-site org |

### Market Tier Definitions

| Tier | Orgs in ZIP+State | Typical Setting |
|------|------------------|----------------|
| sparse | < 3 peers | Rural, frontier, underserved |
| moderate | 3–9 peers | Suburban, mid-size market |
| dense | ≥ 10 peers | Urban, competitive |

## Minimum Sample Size

All cells require **≥ 3 distinct organizations**. Cells with fewer orgs are excluded to prevent individual org identification and ensure statistical credibility.

## Known Limitations

1. **No unit-of-service adjustment.** DOGE provides total_claims and total_paid but NOT units per claim. For per-15-min codes (H2019, H2017, T1017), payment_per_claim reflects (per_unit_rate x units_per_claim). We cannot separate rate from session length.

2. **No modifier data.** DOGE does not include billing modifiers. H0031 blends HO (in-depth assessment, $126.11) with unmodified (limited assessment, $17.90). H0032 blends development ($97.86) with TS review ($48.93).

3. **FQHC/RHC PPS contamination.** FQHCs and RHCs receive all-inclusive encounter rates. When they bill T1015 or CPT codes, the per-claim payment reflects the PPS rate, not the fee schedule rate. Their benchmarks are NOT comparable to non-FQHC/RHC orgs on per-claim metrics.

4. **Multi-site orgs split across ZIPs.** An org with sites in multiple ZIPs appears as separate org_entity_ids. Their claims are not combined unless billing under a shared NPI.

5. **Beneficiary overlap.** `beneficiary_count` from DOGE is per (billing_npi, servicing_npi, HCPCS, month) cell. When aggregated to the org level, the same beneficiary may be counted in multiple months. Revenue_per_beneficiary is therefore an annualized measure, not a per-unique-patient measure.

6. **MCO negotiated rates.** DOGE includes both FFS and MCO claims. MCO rates are typically below the published fee schedule. The P50 reflects the market-effective rate, not the published maximum.

## Refresh Cadence

Table is periodic — not rebuilt on every dbt run. Refresh with:
```
dbt run --select hcpcs_rate_benchmarks --vars '{run_periodic: true}'
```

## Radar Chart Usage

For a given org, the radar chart plots the org's actual KPI against each dimension's P25/P75 band:

1. Look up the org's characteristics: org_type, size_band, market_tier, billing_entity, billing_taxonomy
2. For each HCPCS code, query the matching `dimension_value` on each axis
3. Plot P25–P75 as the band, P50 as the reference line, org's actual as the data point
4. If the org is **below P25 on multiple axes** → systemic rate/utilization concern
5. If the org is **above P75 on one axis** → investigate that specific dimension (is it billing practice? patient acuity? rate premium?)
6. If $/claim is high but claims/bene is normal → rate or units-per-claim difference
7. If $/claim is normal but $/bene is high → utilization/frequency difference

The benchmark surfaces the question. The org's billing team, contract terms, and clinical documentation answer it.
