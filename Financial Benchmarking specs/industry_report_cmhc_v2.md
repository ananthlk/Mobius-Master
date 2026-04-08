# Florida Medicaid CMHC Sector Landscape -- Rate & Operational Benchmarking Report (v2)

**Sector:** Community Mental Health Centers (CMHCs) | **State:** Florida | **Period:** 2024
**Scope:** 86 CMHCs billing Medicaid fee-for-service claims through professional servicing clinicians

---

## Executive Summary

- The CMHC sector's two largest revenue streams -- Behavioral Therapy (H2019, 230K claims) and Targeted Case Management (T1017, 197K claims) -- show divergent rate positioning: H2019 collects slightly above the All FL median (+4.3%) while T1017 falls 20.3% below it, making case management the sector's single largest rate-gap exposure.
- On workforce productivity, CMHC clinicians carry median panels of 123 patients (H2019) and 275 patients (T1017), but only 26 patients for 60-minute psychotherapy (90837), suggesting heavy concentration of therapy caseloads on a small number of clinicians while case managers and PSR staff carry broad panels.
- Patient engagement (visits per patient) in the CMHC sector trails the All FL median on psychotherapy codes -- 1.67 visits per patient on 90837 vs. 2.03 statewide -- raising a question about whether patients are completing treatment episodes or disengaging after initial sessions.
- Revenue per patient on the sector's highest-volume codes ranges from $72.19 (T1015 medication management) to $1,342.29 (H2017 psychosocial rehabilitation), with PSR and ACT driving the highest per-patient yield due to session frequency, not rate.
- Where published rates exist, the gap from published to All FL paid is substantial (e.g., H0031 assessment: published $126.11 vs. All FL paid $31.59), confirming that the structural compression facing the entire market dwarfs the CMHC-specific gap on most codes.

---

## Section 1: About This Report

### What this report covers

This report benchmarks the Florida Community Mental Health Center (CMHC) sector against the broader Florida Medicaid market across 25 HCPCS codes where CMHCs have billing activity. It uses 2024 Medicaid fee-for-service claims data for all organizations billing through professional servicing clinicians.

The CMHC sector includes 86 organizations. The All FL Medicaid comparison group includes all provider types billing each code -- ranging from solo practitioners to hospital-based programs and FQHCs. This breadth is intentional: the All FL median represents the market rate a CMHC competes against, not a peer group of similar organizations.

### Four KPIs

Every code in this report is evaluated on four operational metrics:

| KPI | Field | What it measures | Operational question |
|-----|-------|-----------------|---------------------|
| **Rate per Claim** | p50_ppc | Median dollars collected per claim at the org level | Is the sector paid at market? Where are the gaps? |
| **Patients per Clinician (Panel Size)** | p50_bpc | Median unique patients per billing clinician | Is the workforce carrying enough patients? Productivity signal. |
| **Visits per Patient (Engagement)** | p50_cpb | Median claims per unique patient | Are patients staying engaged? Retention / no-show signal. |
| **Revenue per Patient** | p50_rpb | Median total revenue per unique patient | What is the yield per patient? Acquisition efficiency signal. |

### Three-layer rate context

When published fee schedule rates are available, this report frames rates in three layers:

1. **FL Medicaid Published Rate** -- What AHCA's fee schedule says Medicaid will pay. This is the ceiling. No organization routinely collects this amount.
2. **All FL Medicaid Median Paid Rate** -- What the industry actually collects at the median. This reflects compression from MCO contracts, FFS/managed care mix, modifier patterns, and billing practices. The gap from published to All FL paid is structural -- it affects everyone.
3. **CMHC Sector Median Paid Rate** -- What CMHCs specifically collect. The gap from All FL to CMHC is sector-specific and potentially addressable through contract negotiation, billing optimization, or session structure changes.

### How to read this report

This report presents market-level observations. It does not diagnose causes or recommend actions for individual organizations. Where a gap is identified, the report poses a question rather than a conclusion. For example, a rate below market may reflect structurally undervalued contracts, shorter session durations, modifier patterns, or payer mix -- the data alone cannot distinguish these causes without org-level investigation.

---

## Section 2: Sector Dashboard

Codes sorted by CMHC total claims (largest revenue streams first). Gap signal: green = at or above All FL; yellow = slightly below (-1% to -10%); red = significantly below (worse than -10%).

| Code | Service Line | CMHC Orgs | CMHC Claims | Rate/Claim (CMHC) | Rate/Claim (All FL) | Gap | Patients/Clinician (CMHC) | Patients/Clinician (All FL) | Visits/Patient (CMHC) | Visits/Patient (All FL) | Rev/Patient (CMHC) | Rev/Patient (All FL) |
|------|-------------|-----------|-------------|-------------------|--------------------|----|--------------------------|----------------------------|-----------------------|------------------------|--------------------|--------------------|
| H2019 | Outpatient Therapy | 86 | 230,122 | $74.53 | $71.43 | +4.3% | 123.0 | 211.0 | 2.04 | 2.51 | $137.38 | $180.81 |
| T1017 | Case Management | 34 | 196,720 | $49.58 | $62.20 | -20.3% | 275.0 | 258.0 | 4.70 | 5.57 | $240.24 | $361.14 |
| H2017 | Psychosocial Rehab | 39 | 160,030 | $123.82 | $120.93 | +2.4% | 172.5 | 242.0 | 11.80 | 11.65 | $1,342.29 | $1,376.24 |
| T1015 | Medication Mgmt | 53 | 98,946 | $65.02 | $70.18 | -7.4% | 224.0 | 227.0 | 1.13 | 1.11 | $72.19 | $76.94 |
| H0040 | ACT | 6 | 84,539 | $30.30 | $30.78 | -1.6% | 345.5 | 546.0 | 23.60 | 21.32 | $721.37 | $643.55 |
| H0031 | Assessment | 48 | 50,983 | $31.70 | $31.59 | +0.3% | 115.42 | 83.0 | 1.22 | 1.48 | $45.73 | $51.80 |
| H0032 | Assessment | 55 | 47,113 | $70.75 | $70.33 | +0.6% | 75.0 | 91.0 | 1.03 | 1.02 | $72.49 | $73.39 |
| 99214 | Medication Mgmt | 65 | 30,949 | $51.68 | $42.75 | +20.9% | 98.67 | 100.0 | 1.09 | 1.11 | $59.91 | $48.71 |
| 99213 | Medication Mgmt | 39 | 22,527 | $30.38 | $33.32 | -8.8% | 94.5 | 111.33 | 1.09 | 1.11 | $34.00 | $37.46 |
| 90833 | Medication Mgmt | 21 | 13,360 | $38.49 | $34.84 | +10.5% | 43.0 | 128.0 | 1.10 | 1.17 | $44.50 | $37.84 |
| 90837 | Outpatient Therapy | 27 | 9,799 | $57.77 | $85.97 | -32.8% | 26.0 | 95.0 | 1.67 | 2.03 | $104.89 | $161.13 |
| H2000 | Assessment | 20 | 8,502 | $225.18 | $193.95 | +16.1% | 56.67 | 58.0 | 1.04 | 1.02 | $231.46 | $206.51 |
| H2010 | Outpatient Therapy | 8 | 5,355 | $16.74 | $20.48 | -18.3% | 173.0 | 54.6 | 1.02 | 1.02 | $24.47 | $24.47 |
| H0048 | Medical BH | 6 | 3,633 | $9.57 | $9.27 | +3.2% | 102.0 | 145.0 | 1.13 | 1.12 | $12.03 | $10.46 |
| 90792 | Outpatient Therapy | 13 | 1,643 | $59.68 | $82.12 | -27.3% | 45.0 | 38.0 | 1.08 | 1.09 | $83.12 | $95.27 |
| H0036 | Case Management | 4 | 1,445 | $52.17 | $72.32 | -27.9% | 36.0 | 36.0 | 1.50 | 2.05 | $78.25 | $182.91 |
| 99215 | Medication Mgmt | 7 | 1,231 | $85.45 | $81.01 | +5.5% | 88.0 | 44.0 | 1.05 | 1.08 | $91.17 | $92.36 |
| H0004 | Outpatient Therapy | 4 | 1,047 | $0.08 | $36.89 | -99.8% | 13.0 | 96.33 | 1.33 | 1.34 | $0.10 | $54.53 |
| 99212 | Medication Mgmt | 6 | 669 | $20.67 | $26.52 | -22.1% | 40.0 | 60.0 | 1.06 | 1.07 | $25.33 | $28.85 |
| 90832 | Outpatient Therapy | 3 | 559 | $48.74 | $19.89 | +145.0% | 68.0 | 94.0 | 2.66 | 1.66 | $81.92 | $38.41 |
| T1007 | Assessment | 3 | 456 | $74.42 | $49.13 | +51.5% | 43.0 | 61.0 | 1.02 | 1.02 | $74.42 | $50.46 |
| 90834 | Outpatient Therapy | 6 | 433 | $47.74 | $53.27 | -10.4% | 18.0 | 60.0 | 1.42 | 1.50 | $68.96 | $79.50 |
| 99203 | Medication Mgmt | 4 | 372 | $65.17 | $69.17 | -5.8% | 21.0 | 39.0 | 1.02 | 1.03 | $68.85 | $74.70 |
| 90791 | Outpatient Therapy | 6 | 333 | $105.30 | $91.88 | +14.6% | 31.0 | 30.0 | 1.02 | 1.07 | $105.30 | $101.67 |
| 99204 | Medication Mgmt | 4 | 319 | $81.47 | $95.74 | -14.9% | 25.0 | 39.14 | 1.00 | 1.04 | $97.53 | $102.67 |

**Dashboard reading guide:** The gap column reflects rate per claim only. A green signal on rate does not mean the code is performing well on all dimensions -- check panel size, engagement, and revenue per patient for the full picture.

---

## Section 3: Service Line Deep Dives

### 3A. Outpatient Therapy

This is the CMHC sector's core clinical service. It spans traditional psychotherapy (CPT 90837, 90834, 90832, 90791), behavioral therapy (H2019), and specialized modalities (H2010, H0004).

---

**H2019 -- Behavioral Therapy Services** (230,122 CMHC claims | 86 orgs)
Published rate: $21.87 per 15min | Time-based code

- **Rate per Claim:** CMHC median $74.53 vs. All FL $71.43 (+4.3%). The sector collects slightly above the statewide median on this code. With a published rate of $21.87 per 15-minute unit and typical sessions spanning multiple units, the per-claim rate reflects both the unit rate and session length. The All FL median itself sits well above the published single-unit rate, confirming that multi-unit billing is standard.
- **Panel Size:** CMHC median 123 patients per clinician vs. All FL 211. CMHC clinicians carry substantially smaller panels on this code. Is the CMHC workforce underutilized on behavioral therapy, or are CMHCs distributing this work across more clinicians?
- **Engagement:** CMHC median 2.04 visits per patient vs. All FL 2.51. CMHC patients complete fewer visits. Are treatment models intentionally shorter, or are patients disengaging before completing a full course?
- **Revenue per Patient:** CMHC $137.38 vs. All FL $180.81. Lower engagement drives lower per-patient yield even though the per-claim rate is competitive. The revenue gap is an engagement problem, not a rate problem.
- **Market variation:** Dense markets $69.99, moderate $73.31, sparse $68.40 (All FL). Rates are relatively stable across market types.

*Key question: H2019 is a rate success story for CMHCs, but the engagement and panel size gaps suggest the sector may not be maximizing throughput on its best-reimbursed therapy code.*

---

**90837 -- Psychotherapy 60min** (9,799 CMHC claims | 27 orgs)

- **Rate per Claim:** CMHC median $57.77 vs. All FL $85.97 (-32.8%). This is the sector's deepest rate gap on a high-profile therapy code. The $28.20 per-claim deficit across nearly 10,000 claims represents significant revenue exposure.
- **Panel Size:** CMHC median 26 patients per clinician vs. All FL 95. CMHC clinicians billing 60-minute psychotherapy carry very small panels, suggesting either part-time therapy staffing or heavy concentration of therapy caseloads on a few clinicians.
- **Engagement:** CMHC median 1.67 visits per patient vs. All FL 2.03. Patients are not returning for follow-up therapy sessions at market rates. Are CMHC patients disengaging faster, or are treatment models intentionally shorter?
- **Revenue per Patient:** CMHC $104.89 vs. All FL $161.13 (-34.9%). The combined effect of lower rates and lower engagement produces a revenue-per-patient figure that is roughly one-third below the market.
- **Size variation:** Large orgs $72.12, medium $89.80, small $94.89 (All FL). Smaller organizations actually collect more per claim on this code, suggesting that large-org MCO contracts may drive the CMHC sector's compression.

*Key question: Are CMHC contracts structurally undervalued on 60-minute psychotherapy, or is the sector billing shorter actual session times that reduce the effective per-claim collection?*

---

**90834 -- Psychotherapy 45min** (433 CMHC claims | 6 orgs)

- **Rate per Claim:** CMHC median $47.74 vs. All FL $53.27 (-10.4%). A modest gap, but the very low claim volume (433 claims from only 6 orgs) suggests this code is rarely used in the CMHC sector.
- **Panel Size:** CMHC median 18 patients per clinician vs. All FL 60. Extremely small panels reinforce that this code is a marginal part of CMHC operations.
- **Engagement:** CMHC 1.42 vs. All FL 1.50. Slightly lower engagement, consistent with the pattern on other therapy codes.
- **Revenue per Patient:** CMHC $68.96 vs. All FL $79.50. Lower across both rate and engagement dimensions.

*Key question: With only 433 claims across 6 orgs, is 45-minute psychotherapy a code the CMHC sector has intentionally moved away from, or one it should consider expanding?*

---

**90832 -- Psychotherapy 30min** (559 CMHC claims | 3 orgs)

- **Rate per Claim:** CMHC median $48.74 vs. All FL $19.89 (+145.0%). The 3 CMHC orgs billing this code collect far above the market median. However, the All FL median is depressed by a wide distribution (p25 = $3.34, p75 = $54.84), and only 3 CMHC orgs bill this code.
- **Panel Size:** CMHC 68 vs. All FL 94. Smaller panels, but only 3 orgs.
- **Engagement:** CMHC 2.66 vs. All FL 1.66. Substantially higher engagement. CMHC patients on this code return more frequently.
- **Revenue per Patient:** CMHC $81.92 vs. All FL $38.41. The combination of higher rate and higher engagement produces strong per-patient yield.

*Key question: This apparent outperformance is driven by only 3 organizations. Is there a billing pattern (e.g., consistent modifier use, specific payer contracts) that explains the divergence, or is this an artifact of small sample size?*

---

**90791 -- Diagnostic Psychiatric Evaluation** (333 CMHC claims | 6 orgs)

- **Rate per Claim:** CMHC $105.30 vs. All FL $91.88 (+14.6%). CMHCs collect above market on this intake code, though volume is very low.
- **Panel Size:** CMHC 31 vs. All FL 30. Comparable.
- **Engagement:** CMHC 1.02 vs. All FL 1.07. Near-identical -- this is typically a one-time evaluation.
- **Revenue per Patient:** CMHC $105.30 vs. All FL $101.67. Slightly above market.

*Key question: At 333 claims across 6 orgs, are CMHCs routing most intake evaluations to a different code (H2000, H0031)?*

---

**90792 -- Psychiatric Evaluation (Medical)** (1,643 CMHC claims | 13 orgs)

- **Rate per Claim:** CMHC $59.68 vs. All FL $82.12 (-27.3%). A significant gap on the physician-level psychiatric evaluation. The All FL distribution is wide (p25 = $19.56, p75 = $144.58), but the CMHC median falls well below the market center.
- **Panel Size:** CMHC 45 vs. All FL 38. CMHC psychiatrists evaluating more patients than market median.
- **Engagement:** CMHC 1.08 vs. All FL 1.09. Essentially identical -- this is a one-time or infrequent code.
- **Revenue per Patient:** CMHC $83.12 vs. All FL $95.27. The rate gap flows directly to revenue per patient since engagement is comparable.

*Key question: Are CMHC psychiatric evaluations being reimbursed at a lower contracted rate, or are modifiers or place-of-service codes reducing the effective payment?*

---

**H2010 -- Brief Individual Psychotherapy** (5,355 CMHC claims | 8 orgs)

- **Rate per Claim:** CMHC $16.74 vs. All FL $20.48 (-18.3%). A meaningful gap on a CMHC-relevant therapy code.
- **Panel Size:** CMHC 173 vs. All FL 54.6. CMHC clinicians carry dramatically larger panels on this code, more than 3x the market. This is a high-volume, brief-contact model.
- **Engagement:** CMHC 1.02 vs. All FL 1.02. Identical -- this is primarily a single-visit service.
- **Revenue per Patient:** CMHC $24.47 vs. All FL $24.47. Identical revenue per patient despite the rate gap, because engagement is the same.

*Key question: The rate gap on H2010 does not translate to a revenue-per-patient gap because engagement is identical. Is the lower per-claim rate offset by the much larger panel size (173 vs. 55), producing equivalent or greater total clinician-level revenue?*

---

**H0004 -- Behavioral Health Counseling** (1,047 CMHC claims | 4 orgs)

- **Rate per Claim:** CMHC $0.08 vs. All FL $36.89 (-99.8%). This is an extreme outlier. A $0.08 median rate per claim effectively means this code is being billed at zero reimbursement for most CMHC claims. This almost certainly reflects a data or billing anomaly rather than a true rate.
- **Panel Size:** CMHC 13 vs. All FL 96.33. Very small panels.
- **Engagement:** CMHC 1.33 vs. All FL 1.34. Comparable.
- **Revenue per Patient:** CMHC $0.10 vs. All FL $54.53. Effectively zero.

*Key question: The $0.08 median rate strongly suggests denied claims, bundled billing, or a coding error. Organizations billing H0004 should audit claim-level payment data before drawing any reimbursement conclusions.*

---

### 3B. Case Management

---

**T1017 -- Targeted Case Management** (196,720 CMHC claims | 34 orgs)
Published rate: $14.82 per 15min | Time-based code

- **Rate per Claim:** CMHC $49.58 vs. All FL $62.20 (-20.3%). This is the sector's largest revenue-gap exposure by volume. With nearly 200,000 claims, even a modest per-claim gap produces substantial aggregate revenue impact. The published rate of $14.82 per 15-minute unit means the typical claim spans multiple units; the All FL median of $62.20 per claim implies roughly 4 units per claim at the market level.
- **Panel Size:** CMHC 275 vs. All FL 258. CMHC case managers carry slightly larger panels than the market, suggesting the workforce is not underutilized.
- **Engagement:** CMHC 4.70 vs. All FL 5.57. CMHC patients receive fewer case management contacts per patient. Are CMHC patients disengaging from case management, or are treatment models intentionally delivering fewer but longer contacts?
- **Revenue per Patient:** CMHC $240.24 vs. All FL $361.14 (-33.5%). The combination of lower rate and lower engagement produces a per-patient yield that is one-third below market. This is the sector's most consequential revenue gap.
- **Size variation:** Large orgs $66.98, medium $57.14, small $62.20 (All FL). Larger organizations collect more per claim, suggesting scale-dependent contract leverage.

*Key question: T1017 is a time-based code. The 20.3% per-claim gap may reflect shorter session durations (fewer 15-minute units per encounter) rather than a lower per-unit rate. Both explanations are operationally significant but require different interventions -- contract negotiation vs. service delivery restructuring.*

---

**H0036 -- Community-Based Case Management** (1,445 CMHC claims | 4 orgs)

- **Rate per Claim:** CMHC $52.17 vs. All FL $72.32 (-27.9%). A significant gap, though only 4 CMHC orgs bill this code.
- **Panel Size:** CMHC 36 vs. All FL 36. Identical.
- **Engagement:** CMHC 1.50 vs. All FL 2.05. Notably lower engagement. CMHC patients receive fewer contacts.
- **Revenue per Patient:** CMHC $78.25 vs. All FL $182.91 (-57.2%). The combined rate and engagement gap produces a dramatic per-patient revenue deficit.

*Key question: With only 4 CMHC orgs billing 1,445 claims, is this a niche code for the sector? The engagement gap (1.50 vs. 2.05) suggests patients may be transitioning out of this service more quickly in CMHC settings.*

---

### 3C. Psychosocial Rehabilitation

---

**H2017 -- Psychosocial Rehabilitation** (160,030 CMHC claims | 39 orgs)
Published rate: $9.08 per 15min | Time-based code

- **Rate per Claim:** CMHC $123.82 vs. All FL $120.93 (+2.4%). The sector is at market on its third-largest revenue stream. The published rate of $9.08 per 15-minute unit, combined with a median per-claim rate above $120, implies typical sessions of 13+ units (over 3 hours).
- **Panel Size:** CMHC 172.5 vs. All FL 242. CMHC clinicians carry smaller PSR panels. Is the CMHC workforce at capacity, or are programs serving fewer patients per staff member than the market?
- **Engagement:** CMHC 11.80 vs. All FL 11.65. Essentially identical. PSR patients in the CMHC sector attend at market frequency.
- **Revenue per Patient:** CMHC $1,342.29 vs. All FL $1,376.24. Nearly identical. This is the sector's highest per-patient yield code, driven by the high visit frequency inherent in PSR programming.
- **Market variation:** Dense $126.65, moderate $110.45, sparse $94.02 (All FL). Dense markets collect more, likely reflecting longer program days or more units per session.

*Key question: H2017 is operationally healthy on rate, engagement, and revenue per patient. The panel size gap (172.5 vs. 242) is the one area worth investigating -- is it a staffing constraint, a program design choice, or a reporting artifact?*

---

### 3D. Assertive Community Treatment

---

**H0040 -- Assertive Community Treatment (FACT)** (84,539 CMHC claims | 6 orgs)
Published rate: $31.55 per diem

- **Rate per Claim:** CMHC $30.30 vs. All FL $30.78 (-1.6%). Essentially at market. The published rate of $31.55 per diem means the All FL median collects 97.6% of the published rate -- ACT is one of the least-compressed codes in the dataset.
- **Panel Size:** CMHC 345.5 vs. All FL 546. CMHC ACT teams serve smaller caseloads. Given that ACT is a team-based model with mandated staff-to-patient ratios, this may reflect smaller team sizes rather than underutilization.
- **Engagement:** CMHC 23.60 vs. All FL 21.32. CMHC patients receive slightly more contacts per patient, consistent with intensive wraparound models.
- **Revenue per Patient:** CMHC $721.37 vs. All FL $643.55 (+12.1%). Higher engagement at a comparable rate produces above-market per-patient revenue.

*Key question: H0040 is a strong performer for CMHCs on rate, engagement, and revenue per patient. The smaller panel size (345.5 vs. 546) is the operational question -- is it a function of team size, program maturity, or catchment area constraints?*

---

### 3E. Assessment & Intake

---

**H0031 -- Mental Health Assessment** (50,983 CMHC claims | 48 orgs)
Published rate: $126.11 per event (in-depth, HO modifier) | Limited assessment: $17.90

- **Rate per Claim:** CMHC $31.70 vs. All FL $31.59 (+0.3%). At market. However, the published in-depth rate of $126.11 means the entire market collects only 25% of the fee schedule rate. This massive structural compression affects everyone equally.
- **Panel Size:** CMHC 115.42 vs. All FL 83. CMHC assessors evaluate more patients per clinician than the market. Higher throughput on an assessment code may reflect the sector's role as a community entry point.
- **Engagement:** CMHC 1.22 vs. All FL 1.48. Fewer repeat assessments. This may be operationally appropriate -- fewer re-assessments could indicate efficient intake processes.
- **Revenue per Patient:** CMHC $45.73 vs. All FL $51.80. Slightly lower, driven by the engagement difference.

*Key question: The gap between published rate ($126.11) and actual paid ($31.70) is extraordinary. Is the market predominantly billing the limited assessment ($17.90 published) rather than the in-depth assessment, or are MCO contracts compressing the in-depth rate to this level?*

---

**H0032 -- Treatment Plan Development** (47,113 CMHC claims | 55 orgs)
Published rate: $97.86 per event | Review: $48.93

- **Rate per Claim:** CMHC $70.75 vs. All FL $70.33 (+0.6%). At market. The published rate of $97.86 means the market collects approximately 72% of the fee schedule -- moderate structural compression.
- **Panel Size:** CMHC 75 vs. All FL 91. Slightly smaller panels.
- **Engagement:** CMHC 1.03 vs. All FL 1.02. Nearly identical -- treatment plans are typically developed once per episode.
- **Revenue per Patient:** CMHC $72.49 vs. All FL $73.39. Essentially identical.

*Key question: H0032 is one of the sector's healthiest codes across all four KPIs. The 28% gap to published rate ($97.86) is structural and industry-wide. Is the mix of initial plans vs. reviews ($48.93) driving the compression?*

---

**H2000 -- Psychiatric Evaluation** (8,502 CMHC claims | 20 orgs)
Published rate: $250.63 per eval (physician) | Non-physician: $179.02

- **Rate per Claim:** CMHC $225.18 vs. All FL $193.95 (+16.1%). CMHCs collect well above the statewide median on psychiatric evaluations. The published physician rate of $250.63 means CMHCs collect 89.8% of the fee schedule -- far less compression than on most codes.
- **Panel Size:** CMHC 56.67 vs. All FL 58. Comparable.
- **Engagement:** CMHC 1.04 vs. All FL 1.02. Nearly identical -- this is a one-time evaluation.
- **Revenue per Patient:** CMHC $231.46 vs. All FL $206.51 (+12.1%). Above market.

*Key question: This is a strong-performing code. Are CMHCs billing a higher share of physician-level (HP modifier) evaluations, which would explain the above-market rate?*

---

**T1007 -- Assessment/Treatment Plan** (456 CMHC claims | 3 orgs)

- **Rate per Claim:** CMHC $74.42 vs. All FL $49.13 (+51.5%). Well above market, but only 3 CMHC orgs.
- **Panel Size:** CMHC 43 vs. All FL 61. Smaller panels.
- **Engagement:** CMHC 1.02 vs. All FL 1.02. Identical.
- **Revenue per Patient:** CMHC $74.42 vs. All FL $50.46. Above market.

*Key question: With only 3 CMHC orgs and 456 claims, this is a low-volume code. The above-market rate may reflect specific organizational billing practices rather than a sector-wide pattern.*

---

### 3F. Medication Management (E/M Codes)

---

**99214 -- Office Visit Level 4** (30,949 CMHC claims | 65 orgs)
Published rate: $53.43 per visit (FSI) | Facility: $50.77

- **Rate per Claim:** CMHC $51.68 vs. All FL $42.75 (+20.9%). CMHCs collect well above the market median. With the published FSI rate at $53.43, CMHCs collect 96.7% of the fee schedule -- nearly no compression. The All FL median of $42.75 suggests the broader market is more compressed, possibly due to facility-rate billing or payer mix.
- **Panel Size:** CMHC 98.67 vs. All FL 100. Essentially identical.
- **Engagement:** CMHC 1.09 vs. All FL 1.11. Essentially identical.
- **Revenue per Patient:** CMHC $59.91 vs. All FL $48.71 (+23.0%). Above market on per-patient yield, driven entirely by the rate advantage.

*Key question: This is the sector's strongest E/M code. Are CMHCs consistently billing FSI (professional) rates rather than facility rates, giving them an edge over hospital-based competitors?*

---

**99213 -- Office Visit Level 3** (22,527 CMHC claims | 39 orgs)

- **Rate per Claim:** CMHC $30.38 vs. All FL $33.32 (-8.8%). A moderate gap on the most commonly billed E/M code in the market (2.4M All FL claims).
- **Panel Size:** CMHC 94.5 vs. All FL 111.33. Slightly smaller panels.
- **Engagement:** CMHC 1.09 vs. All FL 1.11. Comparable.
- **Revenue per Patient:** CMHC $34.00 vs. All FL $37.46 (-9.2%). The gap flows primarily from rate.

*Key question: Are CMHC prescribers downgrading visits that could be billed as 99214 to 99213? The 99214 rate is above market while 99213 is below, suggesting potential upcoding opportunity or documentation improvement.*

---

**90833 -- Psychotherapy Add-On (with E/M)** (13,360 CMHC claims | 21 orgs)

- **Rate per Claim:** CMHC $38.49 vs. All FL $34.84 (+10.5%). Above market. This add-on code is billed alongside an E/M visit and reflects the psychotherapy component of a medication management appointment.
- **Panel Size:** CMHC 43 vs. All FL 128. CMHC clinicians carry dramatically smaller panels on this code. Are fewer CMHC prescribers billing the psychotherapy add-on, concentrating this billing among a small number of clinicians?
- **Engagement:** CMHC 1.10 vs. All FL 1.17. Slightly lower.
- **Revenue per Patient:** CMHC $44.50 vs. All FL $37.84 (+17.6%). Above market per-patient yield despite smaller panels.

*Key question: The panel size gap (43 vs. 128) is striking. Are most CMHC prescribers not billing 90833 at all, leaving revenue on the table by not documenting the psychotherapy component of medication management visits?*

---

**99215 -- Office Visit Level 5** (1,231 CMHC claims | 7 orgs)

- **Rate per Claim:** CMHC $85.45 vs. All FL $81.01 (+5.5%). Above market.
- **Panel Size:** CMHC 88 vs. All FL 44. CMHC clinicians carry double the market panel size on this high-complexity code.
- **Engagement:** CMHC 1.05 vs. All FL 1.08. Comparable.
- **Revenue per Patient:** CMHC $91.17 vs. All FL $92.36. At market.

*Key question: The large panel size (88 vs. 44) on a high-complexity visit code is unusual. Are CMHC prescribers serving a disproportionately complex patient population that warrants Level 5 billing?*

---

**99212 -- Office Visit Level 2** (669 CMHC claims | 6 orgs)

- **Rate per Claim:** CMHC $20.67 vs. All FL $26.52 (-22.1%). A significant gap, though volume is low.
- **Panel Size:** CMHC 40 vs. All FL 60. Smaller panels.
- **Engagement:** CMHC 1.06 vs. All FL 1.07. Identical.
- **Revenue per Patient:** CMHC $25.33 vs. All FL $28.85. Below market.

*Key question: At only 669 claims, this is a low-volume code for CMHCs. The 22.1% rate gap may reflect payer mix or site-of-service coding rather than a systemic contract issue.*

---

**99203 -- New Patient Visit Level 3** (372 CMHC claims | 4 orgs)

- **Rate per Claim:** CMHC $65.17 vs. All FL $69.17 (-5.8%). Slightly below market.
- **Panel Size:** CMHC 21 vs. All FL 39. Smaller panels on new patient visits.
- **Engagement:** CMHC 1.02 vs. All FL 1.03. Identical -- new patient visits are by definition single-encounter.
- **Revenue per Patient:** CMHC $68.85 vs. All FL $74.70. Slightly below.

*Key question: With only 4 CMHC orgs billing 372 claims, new patient E/M visits are a marginal part of CMHC billing. Are most new patients routed through H0031/H0032/H2000 assessment codes instead?*

---

**99204 -- New Patient Visit Level 4** (319 CMHC claims | 4 orgs)

- **Rate per Claim:** CMHC $81.47 vs. All FL $95.74 (-14.9%). Below market on the more complex new patient visit.
- **Panel Size:** CMHC 25 vs. All FL 39.14. Smaller panels.
- **Engagement:** CMHC 1.00 vs. All FL 1.04. Identical.
- **Revenue per Patient:** CMHC $97.53 vs. All FL $102.67. Slightly below.

*Key question: The 14.9% rate gap on 99204 across only 4 orgs may reflect contracted rates with specific MCOs rather than a sector-wide pattern.*

---

### 3G. Medication Management (HCPCS)

---

**T1015 -- Medication Management** (98,946 CMHC claims | 53 orgs)
Published rate: $71.61 per event

- **Rate per Claim:** CMHC $65.02 vs. All FL $70.18 (-7.4%). A moderate gap on a high-volume code. The published rate of $71.61 means the All FL median collects 98% of the fee schedule -- very little structural compression. The CMHC sector collects 90.8% of published.
- **Panel Size:** CMHC 224 vs. All FL 227. Essentially identical. The workforce is carrying comparable caseloads.
- **Engagement:** CMHC 1.13 vs. All FL 1.11. Essentially identical.
- **Revenue per Patient:** CMHC $72.19 vs. All FL $76.94 (-6.2%). The modest rate gap flows through to a proportional revenue-per-patient gap.
- **Market variation:** Dense $68.48, moderate $59.59, sparse $87.12 (All FL). Sparse markets collect substantially more, possibly reflecting different MCO contract structures in rural areas.

*Key question: T1015 has minimal structural compression (published $71.61 vs. All FL $70.18), so the CMHC gap of $5.16 per claim is almost entirely sector-specific. Is this addressable through contract renegotiation?*

---

### 3H. Medical Behavioral Health

---

**H0048 -- Alcohol/Drug Screening** (3,633 CMHC claims | 6 orgs)

- **Rate per Claim:** CMHC $9.57 vs. All FL $9.27 (+3.2%). At market.
- **Panel Size:** CMHC 102 vs. All FL 145. Smaller panels.
- **Engagement:** CMHC 1.13 vs. All FL 1.12. Identical.
- **Revenue per Patient:** CMHC $12.03 vs. All FL $10.46 (+15.0%). Above market.

*Key question: This code is operationally healthy. The smaller panel (102 vs. 145) may simply reflect that fewer CMHC clinicians are designated for screening compared to the broader market.*

---

## Section 4: Cross-Cutting Patterns

### 4A. Rate Patterns

The CMHC sector shows a clear pattern: **strong on HCPCS behavioral health codes, weak on CPT psychotherapy codes.**

Codes where CMHCs collect at or above market:
- H2019 Behavioral Therapy (+4.3%), H2017 PSR (+2.4%), H0040 ACT (-1.6%), H0031 Assessment (+0.3%), H0032 Treatment Plan (+0.6%), H2000 Psych Eval (+16.1%), 99214 Office Visit L4 (+20.9%), 90833 Therapy Add-On (+10.5%), 99215 Office Visit L5 (+5.5%), H0048 Screening (+3.2%)

Codes where CMHCs collect below market:
- 90837 Psychotherapy 60min (-32.8%), 90792 Psych Eval Medical (-27.3%), T1017 Case Management (-20.3%), H2010 Brief Therapy (-18.3%), 99204 New Patient L4 (-14.9%), 90834 Psychotherapy 45min (-10.4%), 99213 Office Visit L3 (-8.8%), T1015 Med Mgmt (-7.4%)

The pattern suggests that CMHC-specific HCPCS codes (H-codes, T-codes) -- which are primarily used by community behavioral health providers -- are competitively reimbursed, while CPT codes shared with the broader medical market (90837, 90834, 99213) tend to be lower. This may reflect that CMHC MCO contracts are negotiated primarily around H-code rates, with CPT codes defaulting to lower fee schedules.

### 4B. Productivity Patterns (Panel Size)

CMHC clinicians consistently carry smaller panels than the market on therapy codes (H2019: 123 vs. 211, 90837: 26 vs. 95, 90834: 18 vs. 60) but comparable or larger panels on assessment and case management codes (H0031: 115 vs. 83, T1017: 275 vs. 258).

This suggests a workforce model where case managers and PSR staff carry broad caseloads while therapists serve smaller, more intensive panels. Whether this is an intentional clinical model or a reflection of therapist retention challenges is an org-level question.

### 4C. Engagement Patterns (Visits per Patient)

Patient engagement in the CMHC sector trails the All FL median on most therapy and case management codes:
- 90837: 1.67 vs. 2.03 (-17.7%)
- H2019: 2.04 vs. 2.51 (-18.7%)
- T1017: 4.70 vs. 5.57 (-15.6%)
- H0036: 1.50 vs. 2.05 (-26.8%)

The exception is high-intensity services where engagement is at or above market:
- H0040 ACT: 23.60 vs. 21.32 (+10.7%)
- H2017 PSR: 11.80 vs. 11.65 (+1.3%)

This pattern raises a systemic question: are CMHC patients disengaging from outpatient and case management services at higher rates than the broader market? If so, the revenue impact compounds the per-claim rate gap -- the sector loses on both rate and volume per patient.

### 4D. Revenue Yield Patterns (Revenue per Patient)

The revenue-per-patient KPI combines rate and engagement into a single measure of per-patient yield. The largest absolute gaps are:

| Code | CMHC Rev/Patient | All FL Rev/Patient | Gap |
|------|------------------|--------------------|-----|
| T1017 | $240.24 | $361.14 | -$120.90 |
| H0036 | $78.25 | $182.91 | -$104.66 |
| 90837 | $104.89 | $161.13 | -$56.24 |
| H2019 | $137.38 | $180.81 | -$43.43 |

On T1017, a $120.90 per-patient gap across a caseload of 275 patients per clinician represents significant revenue exposure at the clinician level. On H2019, the $43.43 gap across 123 patients per clinician is smaller per-patient but still meaningful in aggregate.

Codes where revenue per patient exceeds the market (H0040 at $721.37 vs. $643.55, 99214 at $59.91 vs. $48.71, H2000 at $231.46 vs. $206.51) demonstrate that the sector can outperform when rate and engagement align.

---

## Section 5: Methodology & Caveats

### Data Source
Florida Medicaid fee-for-service claims for 2024, filtered to professional servicing clinician-level billing. Managed care encounter data is included where reported through the FFS claims system. The CMHC sector is defined as organizations classified as Community Mental Health Centers in the Florida Medicaid provider enrollment file. The All FL comparison group includes all provider types billing each code.

### KPI Definitions
- **Rate per Claim (p50_ppc):** Median of each organization's average paid amount per claim. This is an org-level median, not a claim-level median -- it gives equal weight to each organization regardless of volume.
- **Patients per Clinician (p50_bpc):** Median of each organization's average unique patients per billing clinician (NPI). Reflects caseload breadth.
- **Visits per Patient (p50_cpb):** Median of each organization's average claims per unique patient. Reflects service intensity and patient retention.
- **Revenue per Patient (p50_rpb):** Median of each organization's average total paid amount per unique patient. Combines rate and engagement into a single yield metric.

### Percentile Benchmarks
All FL benchmarks include p25, p50, and p75. CMHC benchmarks report the sector median (p50) only. The sector gap percentage is calculated as (CMHC p50 - All FL p50) / All FL p50.

### Published Rate Context
Published rates are drawn from the Florida AHCA Medicaid fee schedule where available. Not all codes have published rates in the dataset. Where available, published rates represent the maximum allowable Medicaid FFS reimbursement. Actual collections are lower due to MCO contract discounts, modifier-driven rate adjustments, and billing pattern variation.

### Time-Based Code Caveat
For codes billed in 15-minute units (H2019, H2017, T1017, H0031 limited, and others), per-claim rates reflect both the per-unit rate AND session duration. If the CMHC sector averages fewer units per claim than the broader market, the per-claim gap may partly reflect shorter sessions rather than lower per-unit reimbursement. Both are operationally meaningful -- shorter sessions may indicate efficiency or may indicate compressed service delivery. Distinguishing between per-unit rate compression and session-length compression requires unit-level claims data not included in this report.

### Modifier Rollup
H0031 and H0032 rates in this dataset roll up across modifiers (e.g., HO for in-depth, no modifier for limited). The published rate for H0031 ranges from $17.90 (limited) to $126.11 (in-depth with HO modifier). The observed median of $31.70 likely reflects a mix of limited and in-depth assessments.

### FQHC/RHC PPS Exception
The All FL comparison group includes Federally Qualified Health Centers (FQHCs) and Rural Health Clinics (RHCs), which may bill under Prospective Payment System (PPS) rates that differ from fee-for-service schedules. This means the All FL median on some codes may be influenced by PPS-rate billers whose effective per-claim payment follows a different structure.

### Org Count Thresholds
Codes with very low CMHC org counts (3-4 organizations) should be interpreted with caution. Small samples are more sensitive to individual organizational billing patterns and may not represent sector-wide trends. Codes flagged in the dashboard with fewer than 5 CMHC orgs are: H0004 (4), H0036 (4), 90832 (3), T1007 (3), 99203 (4), 99204 (4).

### What This Report Does Not Do
This report does not diagnose the cause of any gap, recommend specific actions, or evaluate individual organizations. It presents market-level observations and frames questions for further investigation. Gap closure may require contract renegotiation, billing practice changes, clinical workflow adjustments, or a combination -- the appropriate response depends on org-level analysis.

---

*Report generated from 2024 Florida Medicaid claims data. CMHC sector: 86 organizations. All metrics are org-level medians unless otherwise noted.*
