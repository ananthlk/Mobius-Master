# Florida Medicaid CMHC Landscape -- Rate Benchmarking Report

**How the Community Mental Health Center sector compares to the broader Florida Medicaid market**

Data: FL Medicaid FFS 2024 | Org-level aggregation | Professional servicing NPIs

---

## Executive Summary

- The CMHC sector collects less per claim than the broader FL Medicaid market on several high-volume behavioral health codes, with gaps reaching 33% below market on 60-minute psychotherapy (90837) and 27% below market on psychiatric diagnostic evaluation (90792).
- The largest CMHC underperformance areas are 60-minute psychotherapy (90837, -32.8%), psychiatric diagnostic evaluation (90792, -27.3%), targeted case management (T1017, -20.3%), and established patient office visits at the lower levels (99212, -22.1%).
- The CMHC sector outperforms the broader market on assessment and evaluation codes: psychiatric evaluation H2000 (+16.1%), diagnostic assessment 90791 (+14.6%), and E/M level 4 established visits 99214 (+20.9%), suggesting strength in initial intake and higher-complexity visit billing.
- Published fee schedule rates sit well above what the market actually collects -- for example, the H0031 mental health assessment publishes at $126.11 per event, yet the All FL median paid rate is $31.59 and the CMHC median is $31.70, reflecting industry-wide compression of roughly 75%.
- A structural pattern emerges: the CMHC sector tends to collect at or above market on assessment, evaluation, and intake codes, but falls below market on ongoing therapy, case management, and lower-level office visits -- the recurring revenue codes that constitute the majority of claims volume.

---

## Section 1: About This Report

### Data Source and Scope

This report draws on Florida Medicaid fee-for-service claims data for calendar year 2024. All rates reflect organization-level aggregation of claims billed through professional servicing clinician NPIs. The analysis covers the full universe of CMHCs billing FL Medicaid, with participation ranging from 3 to 86 organizations depending on the service code.

### What "CMHC Sector" Means

The CMHC sector includes all organizations classified as Community Mental Health Centers in the FL Medicaid provider taxonomy. For each service code, only CMHCs with sufficient claims volume appear in the sector benchmark. The number of contributing organizations (n) is reported for every code.

### Three-Layer Rate Context

Throughout this report, rates are presented in three layers:

1. **Published Fee Schedule Rate** -- what AHCA's Medicaid fee schedule lists as the payable amount for a code. This is the statutory ceiling, not what providers typically collect.
2. **All FL Medicaid Paid (P50)** -- the median per-claim amount actually collected across all FL Medicaid providers billing a given code. This reflects industry-wide compression from MCO contracts, modifier patterns, and FFS/managed care mix.
3. **CMHC Sector Paid (P50)** -- the median per-claim amount collected across CMHC organizations specifically.

The gap between published rate and All FL paid illustrates structural compression the entire market faces. The gap between All FL paid and CMHC paid isolates CMHC-specific positioning.

### How to Read the Data

- **P25/P50/P75** refer to the 25th, 50th (median), and 75th percentile of org-level average paid per claim.
- The **"middle 50% band"** (P25 to P75) captures where most organizations fall, excluding outliers at both extremes.
- **Gap %** is calculated as CMHC P50 relative to All FL P50 -- a negative gap means the CMHC sector collects less per claim than the broader market.
- **Per-claim rates** for 15-minute unit codes (H2017, H2019, T1017, T1015) reflect the average paid per claim line, not per unit of service. A single claim may contain multiple 15-minute units, so the per-claim rate is not directly comparable to the published per-unit fee schedule rate.

---

## Section 2: Sector Dashboard

Codes are sorted by gap % (largest underperformance first). Only codes with CMHC sector data are shown.

| Code | Description | Service Line | All FL P50 | CMHC P50 | Gap % | Published Rate | CMHC n | Signal |
|------|------------|-------------|-----------|----------|-------|---------------|--------|--------|
| H0004 | BH Counseling Services | Outpatient Therapy | $36.89 | $0.08 | -99.8% | -- | 4 | :red_circle: |
| 90837 | Psychotherapy 60min | Outpatient Therapy | $85.97 | $57.77 | -32.8% | -- | 27 | :red_circle: |
| H0036 | Community Case Mgmt | Case Management | $72.32 | $52.17 | -27.9% | -- | 4 | :red_circle: |
| 90792 | Psych Diagnostic Eval | Outpatient Therapy | $82.12 | $59.68 | -27.3% | -- | 13 | :red_circle: |
| 99212 | Office Visit L2 | Medication Mgmt | $26.52 | $20.67 | -22.1% | -- | 6 | :red_circle: |
| T1017 | Targeted Case Mgmt | Case Management | $62.20 | $49.58 | -20.3% | $14.82/15min | 34 | :red_circle: |
| H2010 | Brief Individual Therapy | Outpatient Therapy | $20.48 | $16.74 | -18.3% | -- | 8 | :red_circle: |
| 99204 | New Patient L4 | Medication Mgmt | $95.74 | $81.47 | -14.9% | -- | 4 | :red_circle: |
| 90834 | Psychotherapy 45min | Outpatient Therapy | $53.27 | $47.74 | -10.4% | -- | 6 | :red_circle: |
| 99213 | Office Visit L3 | Medication Mgmt | $33.32 | $30.38 | -8.8% | -- | 39 | :red_circle: |
| T1015 | Medication Management | Outpatient Therapy | $70.18 | $65.02 | -7.4% | $71.61/event | 53 | :red_circle: |
| 99203 | New Patient L3 | Medication Mgmt | $69.17 | $65.17 | -5.8% | -- | 4 | :red_circle: |
| H0040 | Assertive Community Tx | ACT | $30.78 | $30.30 | -1.6% | $31.55/diem | 6 | :white_circle: |
| H0031 | Mental Health Assessment | Assessment | $31.59 | $31.70 | +0.3% | $126.11/event | 48 | :white_circle: |
| H0032 | Treatment Plan Development | Assessment | $70.33 | $70.75 | +0.6% | $97.86/event | 55 | :white_circle: |
| H2017 | Psychosocial Rehab | Psychosocial Rehab | $120.93 | $123.82 | +2.4% | $9.08/15min | 39 | :white_circle: |
| H0048 | Alcohol/Drug Testing | Medical BH | $9.27 | $9.57 | +3.2% | -- | 6 | :white_circle: |
| H2019 | Behavioral Therapy Svcs | Outpatient Therapy | $71.43 | $74.53 | +4.3% | $21.87/15min | 86 | :green_circle: |
| 99215 | Office Visit L5 | Medication Mgmt | $81.01 | $85.45 | +5.5% | -- | 7 | :green_circle: |
| 90833 | Psychotherapy Add-on 30min | Medication Mgmt | $34.84 | $38.49 | +10.5% | -- | 21 | :green_circle: |
| 90791 | Psychiatric Diagnostic Interview | Outpatient Therapy | $91.88 | $105.30 | +14.6% | -- | 6 | :green_circle: |
| H2000 | Psychiatric Evaluation | Assessment | $193.95 | $225.18 | +16.1% | $250.63/eval | 20 | :green_circle: |
| 99214 | Office Visit L4 | Medication Mgmt | $42.75 | $51.68 | +20.9% | $53.43/visit | 65 | :green_circle: |
| T1007 | Treatment Plan Review | Assessment | $49.13 | $74.42 | +51.5% | -- | 3 | :green_circle: |
| 90832 | Psychotherapy 30min | Outpatient Therapy | $19.89 | $48.74 | +145.0% | -- | 3 | :green_circle: |

---

## Section 3: Service Line Deep Dives

### Outpatient Therapy

**90837 -- Psychotherapy 60min**

The CMHC sector collects a median of $57.77 per claim on 60-minute psychotherapy, compared to $85.97 for All FL Medicaid -- a gap of -32.8% (n=27 CMHCs). Across the broader market, large organizations collect $72.12, medium organizations $89.80, and small organizations $94.89. By market density, the All FL P50 is relatively stable ($79.39 to $89.80 across sparse, moderate, and dense markets). This is the highest-volume traditional psychotherapy code and the gap here represents a substantial revenue shortfall for the CMHC sector. The question for the sector: does the gap reflect contract rate differences, coding practices, or a different payer mix within FFS claims?

**90792 -- Psychiatric Diagnostic Evaluation**

CMHCs collect $59.68 per claim vs. $82.12 market-wide, a gap of -27.3% (n=13 CMHCs). In the broader market, dense-market organizations collect $95.27 while moderate-market organizations collect $57.75, showing substantial geographic variation. The CMHC median aligns more closely with moderate/sparse-market providers than dense-market providers. This raises a question about whether CMHC geographic distribution -- or the complexity of evaluations billed -- drives the gap.

**90834 -- Psychotherapy 45min**

The CMHC sector collects $47.74 vs. $53.27 market-wide, a gap of -10.4% (n=6 CMHCs). In the broader market, smaller organizations actually collect more ($69.36) than larger ones ($50.32), an unusual pattern. The gap is narrower here than on 90837, but follows the same directional pattern.

**H2019 -- Behavioral Therapy Services**

This is the highest-participation CMHC code (n=86 organizations, 230,122 claims). The CMHC sector collects $74.53 per claim vs. $71.43 market-wide, a modest +4.3% advantage. The published rate is $21.87 per 15-minute unit; the per-claim figures reflect multiple units per claim. Across the broader market, rates are stable across size tiers ($68.41 to $72.91) and market densities ($68.40 to $73.31). The near-parity here is notable given the CMHC sector's underperformance on other therapy codes.

**H2010 -- Brief Individual Psychotherapy**

CMHCs collect $16.74 per claim vs. $20.48 market-wide, a gap of -18.3% (n=8 CMHCs). In the broader market, large organizations collect $22.15 while medium organizations collect $15.41, suggesting size matters. The CMHC median falls between these tiers.

**T1015 -- Medication Management**

The CMHC sector collects $65.02 per claim vs. $70.18 market-wide, a gap of -7.4% (n=53 CMHCs). The published rate is $71.61 per event. The All FL market median is already 2% below the published rate, and CMHCs sit a further 7% below that. By size, large organizations collect $73.63 (above published), while medium organizations collect $60.04. By market density, sparse-market organizations collect $87.12, substantially above dense-market organizations at $68.48. This code carries high claims volume (98,946 CMHC claims) and even a modest per-claim gap represents significant aggregate revenue.

**90791 -- Psychiatric Diagnostic Interview**

CMHCs collect $105.30 vs. $91.88 market-wide, a gap of +14.6% (n=6 CMHCs). Notably, sparse-market organizations in the broader market also collect $105.30, while dense-market organizations collect $90.39. The CMHC advantage here aligns with assessment-code outperformance seen elsewhere.

### Medication Management / E&M Codes

**99214 -- Office Visit Level 4 (Established)**

This is the second-highest CMHC participation code (n=65 organizations, 30,949 claims). The CMHC sector collects $51.68 per claim vs. $42.75 market-wide, an advantage of +20.9%. The published rate is $53.43 per visit (FSI; facility rate: $50.77). The CMHC median is within $1.75 of the published rate, while the broader market median sits $10.68 below it. By size in the broader market, large organizations collect $47.98, medium $42.68, and small $24.29. The CMHC sector outperforms all size tiers. This is one of the clearest areas of CMHC strength.

**99213 -- Office Visit Level 3 (Established)**

CMHCs collect $30.38 per claim vs. $33.32 market-wide, a gap of -8.8% (n=39 CMHCs). Across the broader market, rates range from $24.97 (small orgs) to $34.81 (large orgs). By market density, the range is tight ($30.78 to $34.29). The CMHC sector's position below the large-org median but above the small-org median suggests a mid-tier billing profile on this code.

**99212 -- Office Visit Level 2 (Established)**

CMHCs collect $20.67 per claim vs. $26.52 market-wide, a gap of -22.1% (n=6 CMHCs). Large organizations in the broader market collect $26.67, medium $29.25, and small $19.35. The CMHC median sits near the small-org tier despite CMHCs generally being medium-to-large organizations. This gap warrants examination.

**99204 -- New Patient Level 4**

CMHCs collect $81.47 vs. $95.74 market-wide, a gap of -14.9% (n=4 CMHCs). The broader market shows relatively little variation by size ($91.56 to $97.63) or density ($88.99 to $95.87). The small CMHC sample (4 organizations) limits the strength of this observation, but the gap is consistent with underperformance on E/M established-visit codes at the lower levels.

**90833 -- Psychotherapy Add-on (30min)**

CMHCs collect $38.49 per claim vs. $34.84 market-wide, an advantage of +10.5% (n=21 CMHCs). This add-on code is billed alongside an E/M visit when psychotherapy is provided during the same encounter. The CMHC advantage here, combined with the 99214 advantage, suggests that when CMHCs bill combined medication-management-plus-therapy visits, they capture relatively strong reimbursement.

### Assessment and Evaluation

**H2000 -- Psychiatric Evaluation**

The CMHC sector collects $225.18 per claim vs. $193.95 market-wide, an advantage of +16.1% (n=20 CMHCs). The published rate is $250.63 for physician/HP-level evaluations ($179.02 for non-physician). The CMHC median sits 10% below the published physician rate but 16% above the market median. In the broader market, small organizations collect $276.76, medium $210.00, and large $191.53. By density, sparse-market organizations collect $211.09 while dense-market collect $186.94. The CMHC sector's above-market position may reflect a higher proportion of physician-level evaluations.

**H0031 -- Mental Health Assessment**

The CMHC sector collects $31.70 per claim vs. $31.59 market-wide, essentially at parity (+0.3%, n=48 CMHCs). The published rate is $126.11 for in-depth assessment (HO modifier) and $17.90 for limited assessment. The market collects roughly 25% of the in-depth published rate, illustrating the modifier mix and compression dynamics at play. By size, the broader market shows minimal variation ($29.81 to $32.10). By density, variation is also modest ($30.38 to $32.39). This is a high-volume CMHC code (50,983 claims) where the sector is aligned with market norms.

**H0032 -- Treatment Plan Development**

CMHCs collect $70.75 per claim vs. $70.33 market-wide, at parity (+0.6%, n=55 CMHCs). The published rate is $97.86 per event ($48.93 for review). The market collects approximately 72% of the development published rate. By density, dense-market organizations collect $74.40 while moderate collect $68.20. The CMHC sector matches the market closely on this high-volume code (47,113 claims).

**T1007 -- Treatment Plan Review**

CMHCs collect $74.42 per claim vs. $49.13 market-wide, an advantage of +51.5% (n=3 CMHCs). In the broader market, large organizations collect $53.96 and sparse-market organizations collect $70.43. The small CMHC sample limits confidence, but the gap is large.

### Case Management

**T1017 -- Targeted Case Management**

The CMHC sector collects $49.58 per claim vs. $62.20 market-wide, a gap of -20.3% (n=34 CMHCs). The published rate is $14.82 per 15-minute unit; per-claim figures reflect multiple units. This is a high-volume code (196,720 CMHC claims). In the broader market, large organizations collect $66.98, medium $57.14, and small $62.20. By density, dense-market organizations collect $67.13 while sparse-market collect $49.69. The CMHC sector's median aligns closely with the sparse-market tier. Given that targeted case management is a core CMHC service and represents substantial claims volume, the 20% gap below market is a significant sector-level finding.

**H0036 -- Community Case Management**

CMHCs collect $52.17 per claim vs. $72.32 market-wide, a gap of -27.9% (n=4 CMHCs). The broader market sample is also small (9 organizations total). Medium-sized organizations in the broader market collect $72.32. The small CMHC sample limits interpretation, but the gap is directionally consistent with T1017 underperformance.

### Assertive Community Treatment

**H0040 -- FACT Program**

The CMHC sector collects $30.30 per claim vs. $30.78 market-wide, a gap of -1.6% (n=6 CMHCs). The published rate is $31.55 per diem. All three figures are tightly clustered: the published diem is $31.55, the market pays $30.78, and CMHCs pay $30.30. The tight IQR in the broader market (P25: $30.18 to P75: $31.38) confirms this is a price-administered code with minimal negotiation range. By size and density, variation is negligible. The CMHC sector is essentially at market on this code.

### Psychosocial Rehabilitation

**H2017 -- Psychosocial Rehabilitation**

The CMHC sector collects $123.82 per claim vs. $120.93 market-wide, a modest advantage of +2.4% (n=39 CMHCs). The published rate is $9.08 per 15-minute unit; per-claim figures reflect high unit counts (the P50 claims-per-beneficiary of 11.8 units suggests sessions of roughly 3 hours). By size in the broader market, large organizations collect $115.81, medium $124.70, and small $123.82. By density, dense-market organizations collect $126.65, moderate $110.45, and sparse $94.02. The CMHC sector sits at the medium-org tier and is near parity with the broader market.

### Medical Behavioral Health

**H0048 -- Alcohol/Drug Testing**

CMHCs collect $9.57 per claim vs. $9.27 market-wide, a modest advantage of +3.2% (n=6 CMHCs). The broader market is tightly clustered (P25: $8.52 to P75: $9.90). Variation by size and density is minimal. This is a price-administered code where the CMHC sector is at market.

---

## Section 4: Cross-Cutting Patterns

### Systematic CMHC Underperformance

The CMHC sector falls below the broader FL Medicaid market on a cluster of codes that share a common profile: ongoing, recurring service delivery.

- **Psychotherapy codes** (90837 at -32.8%, 90792 at -27.3%, 90834 at -10.4%, H2010 at -18.3%) -- the core therapy service line shows consistent underperformance.
- **Case management** (T1017 at -20.3%, H0036 at -27.9%) -- another high-volume recurring service where CMHCs collect substantially less per claim.
- **Lower-level E/M visits** (99212 at -22.1%, 99213 at -8.8%) -- routine follow-up visits where the sector trails the market.
- **Medication management** (T1015 at -7.4%, 99204 at -14.9%) -- the gap is narrower here but still present.

### Systematic CMHC Advantage

The CMHC sector collects at or above market on a different cluster: initial evaluations, assessments, and higher-complexity visits.

- **Assessment codes** (H2000 at +16.1%, H0031 at +0.3%, H0032 at +0.6%, T1007 at +51.5%) -- the intake/assessment service line shows parity or advantage.
- **Higher-level E/M** (99214 at +20.9%, 99215 at +5.5%) -- more complex visits where CMHCs outperform.
- **Initial diagnostic interviews** (90791 at +14.6%) -- another intake-oriented code.
- **Psychotherapy add-on** (90833 at +10.5%) -- suggests combined visits capture strong rates.

### The Structural Pattern

The data suggests a bifurcation in CMHC rate positioning:

**Front-door strength:** The CMHC sector performs well on the codes associated with getting clients into care -- psychiatric evaluations, assessments, treatment planning, higher-complexity initial visits. These tend to be one-time or low-frequency services.

**Ongoing-care gap:** The sector underperforms on the codes associated with keeping clients in care -- weekly therapy, monthly case management, routine follow-up visits. These are the recurring revenue codes that drive the majority of claims volume and total reimbursement.

### Published Rate Context

Where published rates are available, the data reveals consistent compression:

- **H0031**: Published $126.11, market collects $31.59 (25% of published), CMHCs collect $31.70
- **H0032**: Published $97.86, market collects $70.33 (72% of published), CMHCs collect $70.75
- **H2000**: Published $250.63, market collects $193.95 (77% of published), CMHCs collect $225.18
- **99214**: Published $53.43, market collects $42.75 (80% of published), CMHCs collect $51.68
- **H0040**: Published $31.55, market collects $30.78 (98% of published), CMHCs collect $30.30
- **T1015**: Published $71.61, market collects $70.18 (98% of published), CMHCs collect $65.02
- **T1017**: Published $14.82/15min, market collects $62.20/claim, CMHCs collect $49.58/claim (unit-based; per-claim not directly comparable to published per-unit rate)

The compression varies dramatically by code. Some codes (H0040, T1015) see the market collecting near-published rates, while others (H0031) show 75% compression from published to actual. The CMHC sector's position relative to the market is independent of the absolute compression level -- the sector can outperform the market even when the market itself is heavily compressed (as with H2000).

### Questions for the Sector

- What explains the consistent gap between CMHC and market on therapy codes? Is this a contract rate issue, a coding/modifier pattern, or a function of which MCO contracts CMHCs hold?
- Does the front-door strength / ongoing-care gap pattern reflect intentional rate strategy, or an unexamined artifact of historical contracting?
- CMHCs that bill 99214 at near-published rates while billing 90837 at 33% below market may have different contracting dynamics for E/M vs. psychotherapy codes -- is this visible in MCO contract terms?
- T1017 (targeted case management) represents 196,720 CMHC claims at a 20% gap to market. At the sector level, what would closing even half that gap represent in aggregate revenue?
- The CMHC sector participation varies widely -- 86 organizations bill H2019 but only 3-6 bill many therapy codes. Does this reflect genuine service mix differences or undercoding of billable services?

---

## Section 5: Methodology

### Data Source

Florida Medicaid fee-for-service claims, calendar year 2024. Claims are aggregated at the organization level using professional servicing NPI linkage. Published fee schedule rates are drawn from the AHCA Medicaid fee schedule where available.

### Peer Construction

The "All FL Medicaid" benchmark includes all organizations billing each code through FL Medicaid FFS, regardless of provider type. This means the CMHC sector is being compared to a market that includes FQHCs (which may receive PPS rates), hospital-based providers, private practices, and other organizational types. PPS-eligible organizations may have structurally different rate floors that elevate the All FL median on certain codes.

### Size and Market Density Segmentation

Organizations are segmented into size tiers (large, medium, small) based on total Medicaid claims volume, and into market density tiers (dense, moderate, sparse) based on the geographic concentration of Medicaid providers in their service area. Not all segmentation tiers have sufficient data for every code.

### Limitations

- **FFS only.** This analysis covers fee-for-service Medicaid claims. Managed care Medicaid (which represents the majority of FL Medicaid enrollment) is not reflected. Rate dynamics under MCO contracts may differ.
- **Per-claim, not per-unit.** For 15-minute unit codes, rates are per claim line. A claim with more units will show a higher per-claim rate even if the per-unit rate is identical. Cross-code comparisons should account for this.
- **Modifier rollup.** Codes like H0031 and H0032 include all modifier variants in a single code-level benchmark. Published rates vary by modifier (e.g., H0031 with HO modifier vs. without), and the blended benchmark may obscure modifier-specific patterns.
- **Snapshot, not trend.** This is a single-period analysis. Rate positioning may shift year over year.
- **No causal inference.** Gaps between CMHC and market rates may reflect contract terms, coding patterns, service complexity, payer mix within FFS, geographic distribution, or other factors not observable in claims data alone.
