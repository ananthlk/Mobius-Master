## Executive Summary

This outside-in analysis leverages PML, NPPES, DOGE claims, and TML to identify 99 providers across 4 locations with credentialing and enrollment gaps.

The projected revenue at the current run rate stands at **$2,576,560.00**. This figure represents the baseline for the organization's current fully credentialed and enrolled provider base.

The total addressable opportunity, encompassing enrollment gaps, address corrections, taxonomy optimization, and potential rate improvements, is **$3,875,742.99**. This figure includes a rate gap component (Section E) that requires methodology verification before it can be treated as actionable for near-term revenue planning. The operational opportunity — enrollment, address correction, and taxonomy optimization — totals **$1,124,444.80**. This operational total represents direct revenue uplifts achievable through immediate credentialing and roster management actions, carrying a high degree of confidence.

**Opportunities are ordered by actionability:**

1.  **Enrollment Gap (C: $993,816.00):** This is the most substantial and immediately actionable opportunity. It represents a significant amount of uncaptured revenue from 27 providers (individuals and organizations) already identified and associated with the organization but currently lacking proper Medicaid enrollment.
2.  **At-Risk Revenue (B: $73,616.00):** This opportunity requires immediate attention to prevent future revenue loss due to minor address discrepancies that can lead to claim denials or audits.
3.  **Taxonomy Optimization (D: $57,012.80):** A strategic uplift opportunity that can enhance reimbursement rates by ensuring providers are enrolled with the most advantageous and accurate taxonomies for the services they deliver. This is a medium-confidence exposure requiring verification.
4.  **Rate Gap (E: $2,751,298.19):** This is an investigative opportunity. While significant, the methodology for this rate gap requires further verification and detailed analysis before it can be confirmed as actionable for revenue planning. The E total is from a taxonomy-level comparison and should be treated as directional.

**Immediate Actions:**

*   **For Enrollment Gaps (C):** Initiate Mobius Credentialing Workflow for Medicaid Enrollment for the 27 identified providers (individuals and organizations) lacking PML enrollment. This will unlock $993,816.00 in potential annual revenue.
*   **For At-Risk Revenue (B):** Initiate Mobius Roster Management Workflow to correct address discrepancies for 2 providers, securing $73,616.00 in revenue currently at risk.
*   **For Taxonomy Optimization (D):** Review identified taxonomy optimization opportunities for 2 providers with credentialing specialists. This can potentially yield $57,012.80 in additional revenue. This is a directional opportunity requiring verification.
*   **For Rate Gap (E):** Engage Mobius Rate Benchmarking specialists to conduct an in-depth analysis of the rate gap, focusing on service models and contract terms to verify the actionable portion of the $2,751,298.19 potential.

No indications of ghost billing were identified in the claims data reviewed, suggesting strong billing integrity for David Lawrence Center.

**Scope Note:** This is the first Mobius revenue waterfall analysis for David Lawrence Center, based on external data sources. Therefore, a comparison to prior internal reports is not applicable. This report identifies 99 unique providers and 4 distinct operational locations.

## 1. Methodology

This report employs a rigorous, outside-in analytical framework to identify and quantify revenue opportunities related to provider credentialing and roster accuracy. We do not have internal organizational records from David Lawrence Center.

1.  **Organizational Identification**: We began by identifying all NPIs and names associated with David Lawrence Center using NPPES data.
2.  **Location Mapping**: Primary and secondary service locations were identified by leveraging site_source/site_reason data from NPI records, with the organization's main address serving as a base and additional servicing NPI practice addresses from DOGE (Data on Growth and Expenditures) augmenting this.
3.  **Provider Association**: Individual providers were associated with these locations based on strong address matches from NPPES and their roster status.
4.  **Service Type Identification**: For each location, potential billable services were identified through associated taxonomies, indicating the types of care that could be delivered.
5.  **Historic Billing Analysis**: Medicaid claims data was analyzed to understand historic billing patterns by HCPCS code, entity type, claim count, and total paid amounts. This informs current run rates and identifies key service areas.
6.  **Medicaid Eligibility Checks (PML Validation)**: For each NPI × taxonomy × ZIP+4 combination (a "combo"), four critical Medicaid checks were performed: (1) NPI presence in the Provider Master List (PML) with a Medicaid ID, (2) validation of a 9-digit ZIP+4, (3) confirmation of taxonomy on the Taxonomy Master List (TML) or Pending Provider List (PPL), and (4) verification that the NPI+taxonomy+ZIP9 combo has a valid Medicaid ID. These checks are crucial for determining a provider's eligibility to bill Medicaid.
7.  **Opportunity Identification**: Based on the PML validation and associated data, providers were categorized into different revenue waterfall buckets (Projected Run Rate, At-Risk, Enrollment Gap, Taxonomy Optimization, Rate Gap).
8.  **Opportunity Sizing**: Revenue impact for each opportunity was quantified using benchmark rates (either taxonomy-specific or organizational average where specific benchmarks were unavailable) and projected service volumes.

**Confidence Bands Table:**

| Band    | Score | Basis                          | Recommended action          |
| :------ | :---- | :----------------------------- | :-------------------------- |
| Perfect | 90+   | Address + billing match        | Act immediately             |
| Good    | 70+   | Billing or strong address      | Act with standard review    |
| Medium  | 50+   | Address match, no billing      | Verify before acting        |
| Low     | <50   | Weak signal only               | Internal verification first |

**Rate Gap Methodology Note:**
Section E rate gap figures are calculated by comparing each organization's average paid rate per claim against state-wide average paid rates for the same HCPCS code. This comparison has important limitations: (1) Per diem codes (e.g., H0040 Assertive Community Treatment, S9485 Crisis Intervention) bundle multiple contacts into a single daily charge — their per-claim rates are not directly comparable to fee-for-service encounter rates that other billers may use for the same code. (2) State averages include all biller types; if an organization uses a different service model than the state average, the gap may reflect model differences rather than rate negotiation opportunities. For these reasons, per diem code gaps are shown for informational purposes and should be verified before inclusion in any revenue projection.

## 2. About the Organization

David Lawrence Center is a prominent behavioral healthcare provider in Collier County, Florida, operating across multiple locations to serve its community.

**Location Summary:**

*   **6075 BATHEY LN, NAPLES, FL 34116** (Primary administrative and service delivery hub)
*   **2806 HORSESHOE DR S, NAPLES, FL 34104** (Another key service delivery location in Naples)
*   **5266 GOLDEN GATE PKWY, NAPLES, FL 34116** (Additional Naples service location)
*   **425 N 1ST ST, IMMOKALEE, FL 34142** (Crucial location in Immokalee, a rural and agricultural community in Collier County. Credentialing gaps here affect not only the organization's revenue potential but critically impede patient access to care in a historically underserved, high-Medicaid area.)

**Readiness Score:**
A specific "readiness score" relative to the FL BH median of 68 is not available in this analysis.

**Top 10 HCPCS Billing Table:**
This table highlights the organization's most frequently billed services and their associated revenue, offering insight into core service delivery areas.

| HCPCS | Description                                     | Claim Count | Total Paid ($) | Avg Rate/Claim ($) |
| :---- | :---------------------------------------------- | :---------- | :------------- | :----------------- |
| H0040 | Assertive community treatment program, per diem | 11008       | 318,844.30     | 28.96              |
| H2019 | Therapeutic behavioral services, per 15 minutes | 2904        | 361,422.97     | 124.46             |
| T1017 | Targeted case management, each 15 minutes       | 1689        | 83,933.25      | 49.69              |
| T1015 | Clinic visit/encounter, all-inclusive           | 1676        | 118,227.58     | 70.54              |
| S9485 | Crisis intervention mental health services, per diem | 484         | 281,712.25     | 582.05             |
| H0046 | Mental health services, not otherwise specified | 358         | 7,378.19       | 20.61              |
| H0032 | Mental health service plan development by non-physician | 274         | 23,775.30      | 86.77              |
| H0031 | Mental health assessment, by non-physician      | 106         | 5,676.89       | 53.56              |
| H0035 | Mental health partial hospitalization, treatment, less than 24 hours | 93          | 18,200.00      | 195.70             |
| 99214 | (description not available)                     | 62          | 1,253.85       | 20.22             |

**Benchmarking Note:**
Based on the `historic_billing_patterns`, the highest average paid rate per claim is for S9485 ($582.05). H0040, a significant volume code, has an average rate of $28.96. Note: H0040 and S9485 are per diem bundled services — see Section E and the rate gap methodology note in Section 1 for important considerations regarding their comparability in rate gap analysis. Due to the lack of HCPCS-level state benchmarks for this analysis, we cannot identify the largest rate gap code for comparison at this time.

## 3. Opportunity Waterfall

This waterfall illustrates the potential revenue streams available to David Lawrence Center through optimized credentialing and billing practices.

**Summary Table:**

| Level       | Description                           | Amount         | Providers | Status/Confidence                |
| :---------- | :------------------------------------ | :------------- | :-------- | :------------------------------- |
| A           | Projected revenue at current run rate | $2,576,560.00  | 70        | Enrolled + valid                 |
| B           | At-risk (address gaps)                | $73,616.00     | 2         | High — fix now                   |
| C           | Enrollment gap (PML)                  | $993,816.00    | 27        | High — enroll now                |
| D           | Taxonomy optimization                 | $57,012.80     | 2         | Medium — verify                  |
| E           | Rate gap (investigative)              | $2,751,298.19  | —         | Requires analysis, directional   |
| **B+C+D**   | **Operational opportunity**           | **$1,124,444.80** | —         | **High confidence, actionable now** |
| **Total**   | **B+C+D+E**                           | **$3,875,742.99** | —         | **Includes E which requires rate methodology verification** |

## 4. Elements of the Waterfall

Amounts reflect benchmark methodology — see Section 1 and the benchmark methodology note at the end of this section for details.

### A. Projected Revenue at Current Run Rate

This section details the expected annual revenue generated by David Lawrence Center's currently enrolled and validated providers. It serves as the baseline against which all opportunities are measured.

**Location Summary:**

| Location                        | Provider Count | Projected Revenue |
| :------------------------------ | :------------- | :---------------- |
| 6075 BATHEY LN, NAPLES, FL 34116 | 57             | $2,098,056.00     |
| 2806 HORSESHOE DR S, NAPLES, FL 34104 | 10             | $368,080.00       |
| 425 N 1ST ST, IMMOKALEE, FL 34142 | 3              | $110,424.00       |
| **Total**                       | **70**         | **$2,576,560.00** |

**Full provider list — 70 providers.**

| Provider                                    | Service Type                                | Projected Revenue          |
| :------------------------------------------ | :------------------------------------------ | :------------------------- |
| PEREZ, MARIANA                              | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| MILLER, LAVERNE                             | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| DARIEN, JANE                                | Clinical Neuropsychologist                  | org benchmark avg ($36,808.00/yr) |
| PITTS, ABIGAIL                              | Counselor                                   | org benchmark avg ($36,808.00/yr) |
| BRITNELL, PRISCILLA                         | Counselor                                   | org benchmark avg ($36,808.00/yr) |
| JEWELL, LAUREN                              | Counselor                                   | org benchmark avg ($36,808.00/yr) |
| SCHLICHTING, BONNIE                         | Counselor                                   | org benchmark avg ($36,808.00/yr) |
| CHATTERTON, KELLY                           | Addiction (Substance Use Disorder) Counselor | org benchmark avg ($36,808.00/yr) |
| HALL, CHRISTOPHER                           | Addiction (Substance Use Disorder) Counselor | org benchmark avg ($36,808.00/yr) |
| ANDREWS-JONES, SUSAN                        | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| RODRIGUEZ, DAVID                            | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| SWEET, JOSEPH                               | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| CARRINGTON, NATHANIEL                       | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| MISCAVAGE, KAREN                            | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| MESSANO, ANNA                               | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| RAND, MARY                                  | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| MCDOWELL, MICHAEL                           | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| DAUPHINAIS, NANCY                           | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| BREAULT, JOHN                               | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| HOLMES, CHRISTINE                           | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| ARREDONDO, MONICA                           | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| TUTTON, DAVID                               | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| MATEIKA, MATTHEW                            | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| KIRGAN, SUSAN                               | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| GEORGE, NATALIE                             | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| SAGANOWICH, JAMES                           | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| MENA, JESUS                                 | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| STRUNK, LAUREN                              | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| WIREMAN, JENNIFER                           | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| MODZELEWSKI, MOLLY                          | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| BREWER, ERIN                                | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| LONG, KRISTIN                               | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| SANTORA, MICHELE                            | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| HIRCHAK, JESSICA                            | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| ODOR, LAUREN                                | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| MATTSON, KEITH                              | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| ARROYAVE, MARIA                             | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| DE POL, GREGORY                             | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| DAVIS, CYNTHIA                              | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| WEILAND, ASHLEY                             | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| ALFONSO, DAIRY                              | Clinical Social Worker                      | org benchmark avg ($36,808.00/yr) |
| FUENTES, DAVID                              | Clinical Child & Adolescent Psychologist    | org benchmark avg ($36,808.00/yr) |
| DRUMMOND, BIANCA                            | Social Worker                               | org benchmark avg ($36,808.00/yr) |
| BOWDEN, GAYLA                               | Social Worker                               | org benchmark avg ($36,808.00/yr) |
| MACGEORGE, TIMOTHY                          | Clinical Neuropsychologist                  | org benchmark avg ($36,808.00/yr) |
| PHIMMASONE, JACQUELINE                      | Clinical Neuropsychologist                  | org benchmark avg ($36,808.00/yr) |
| GALLO, CYNTHIA                              | Clinical Neuropsychologist                  | org benchmark avg ($36,808.00/yr) |
| PATAK, JENNIFER                             | Clinical Neuropsychologist                  | org benchmark avg ($36,808.00/yr) |
| BABIN, ERIN                                 | Clinical Neuropsychologist                  | org benchmark avg ($36,808.00/yr) |
| SLOCUM, ANGELA                              | Clinical Neuropsychologist                  | org benchmark avg ($36,808.00/yr) |
| SWEET, SUSAN                                | Clinical Neuropsychologist                  | org benchmark avg ($36,808.00/yr) |
| VANHARA, ARIELLA                            | Clinical Neuropsychologist                  | org benchmark avg ($36,808.00/yr) |
| MILLER, KERI                                | Clinical Neuropsychologist                  | org benchmark avg ($36,808.00/yr) |
| LOPEZ, ANGELA                               | Clinical Neuropsychologist                  | org benchmark avg ($36,808.00/yr) |
| LYRISTAKIS, ERIN                            | Clinical Neuropsychologist                  | org benchmark avg ($36,808.00/yr) |
| PIERRE, YVES                                | Case Manager/Care Coordinator               | org benchmark avg ($36,808.00/yr) |
| REA, JOSEPH                                 | Case Manager/Care Coordinator               | org benchmark avg ($36,808.00/yr) |
| VALENZUELA, RONNY                           | Psychiatrist                                | org benchmark avg ($36,808.00/yr) |
| VILLAVERDE, OSCAR                           | Psychiatrist                                | org benchmark avg ($36,808.00/yr) |
| PIECZALSKA, MARTA                           | Psychiatrist                                | org benchmark avg ($36,808.00/yr) |
| BENOIT, EDDY                                | Psychiatrist                                | org benchmark avg ($36,808.00/yr) |
| DAVID LAAWRENCE CENTER                      | Community/Behavioral Health Agency          | org benchmark avg ($36,808.00/yr) |
| DAVID LAWRENCE MENTAL HEALTH CENTER INC     | Clinic/Center (Unspecified Type)            | org benchmark avg ($36,808.00/yr) |
| DAVID LAWRENCE MENTAL HEALTH CENTER, INC    | Behavioral Health Clinic/Center             | org benchmark avg ($36,808.00/yr) |
| DAVID LAWRENCE CENTER                       | Residential Facility, Mentally Ill Children | org benchmark avg ($36,808.00/yr) |
| DAVID LAWRENCE CENTER                       | Psychiatric Residential Treatment Facility, Children/Adolescents | org benchmark avg ($36,808.00/yr) |
| GERRITY, MAUREEN                            | Physician Assistant                         | org benchmark avg ($36,808.00/yr) |
| EDWARDS, JEFFREY                            | Nurse Practitioner, Psychiatric/Mental Health | org benchmark avg ($36,808.00/yr) |
| NERVINA, LORI                               | Nurse Practitioner, Psychiatric/Mental Health | org benchmark avg ($36,808.00/yr) |
| EBAUGH, DEBRA                               | Nurse Practitioner, Psychiatric/Mental Health | org benchmark avg ($36,808.00/yr) |

*Note: Amounts reflect an organizational billing average. Individual rates vary by taxonomy, service volume, and payer mix. Taxonomy-level benchmarks were not available for this run.*

### B. At-Risk Revenue

This section highlights revenue that is currently being billed but is at risk of denial or clawback due to discrepancies, primarily incorrect location data. Addressing these issues immediately is critical to securing this revenue.

| Provider            | Service Type         | Location                   | At-Risk Amount | Current ZIP | Correct ZIP |
| :------------------ | :------------------- | :------------------------- | :------------- | :---------- | :---------- |
| BIRMINGHAM, CHELSEA | Clinical Social Worker | 6075 BATHEY LN, NAPLES, FL 34116 | $36,808.00     | 33908       | 34116       |
| STABILE, KATIE      | Clinical Social Worker | 6075 BATHEY LN, NAPLES, FL 34116 | $36,808.00     | 33931       | 34116       |

**Action for Operations Director:** For BIRMINGHAM, CHELSEA and STABILE, KATIE, initiate Mobius Roster Management Workflow to update their current servicing ZIP codes in all relevant systems to align with the primary location at 6075 Bathey Ln, Naples, FL 34116 (341167536). Verify all payer enrollments reflect the accurate service address.

### C. Enrollment Gap — Missing PML

This represents revenue opportunities from providers who are associated with David Lawrence Center but are not currently enrolled in the Medicaid Provider Master List (PML). Enrolling these providers will unlock significant revenue.

**Individual Provider Enrollment Gaps:**

| Provider                                    | Service Type                                | Enrollment Gap Amount | Location                   | Enrollment Action                            |
| :------------------------------------------ | :------------------------------------------ | :-------------------- | :------------------------- | :------------------------------------------- |
| DROUIN, HOLLY                               | Clinical Social Worker                      | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| WEINER, CASEY                               | Clinical Neuropsychologist                  | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| GONZALEZ SAVOURNIN, SEPTIMIO                | Nurse Practitioner, Gerontological          | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| DEMPSEY, ZACHARY                            | Clinical Social Worker                      | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| CHASANOV, MAXIM                             | Psychiatrist                                | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| SLETTA, TONYA                               | Clinical Social Worker                      | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| GALANTI, GABRIELLE                          | Case Manager/Care Coordinator               | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| GIBBONS, MARY                               | Social Worker                               | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| DENNISTON, TAYLOR                           | Clinical Neuropsychologist                  | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| JENKINS, CARRIE                             | Clinical Social Worker                      | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| PAUL, PRESTON                               | Clinical Neuropsychologist                  | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| BIRNIE, LAURA                               | Hospice and Palliative Care                 | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| GRAYDEN, BRITTEN                            | Counselor                                   | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| HERMANN-BARROS, SUZANNE                     | Clinical Social Worker                      | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| KOROLEVICH, EMILY                           | Hospice and Palliative Care                 | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| COOPER, KENDEL                              | Clinical Social Worker                      | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| THOME, COLETTE                              | Counselor                                   | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| LUBIN, CLAIRE                               | Registered Nurse                            | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| CALIXTE, JULIENNE                           | Nurse Practitioner, Psychiatric/Mental Health | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| SCALIA, JENNIFER                            | Clinical Neuropsychologist                  | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| CAMARDA, PETRA                              | Clinical Neuropsychologist                  | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| NEALON, KATHLEEN                            | Clinical Neuropsychologist                  | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| CAYWOOD, APRIL                              | Nurse Practitioner, Psychiatric/Mental Health | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |
| DION, MICHELLE                              | Nurse Practitioner, Psychiatric/Mental Health | $36,808.00            | 6075 BATHEY LN, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Medicaid Enrollment |

**Organizational Provider Enrollment Gaps:**
These organizational NPIs are missing from the Provider Master List and represent additional enrollment opportunities.

| Provider                                | Service Type                      | Enrollment Gap Amount | Location                       | Enrollment Action                            |
| :-------------------------------------- | :-------------------------------- | :-------------------- | :----------------------------- | :------------------------------------------- |
| DAVID LAWRENCE MENTAL HEALTH CENTER INC | Community/Behavioral Health Agency | $36,808.00            | 2806 HORSESHOE DR S, NAPLES, FL 34104 | Initiate Mobius Credentialing Workflow for Organizational Medicaid Enrollment |
| DAVID LAWRENCE CENTER                   | Behavioral Health Clinic/Center   | $36,808.00            | 5266 GOLDEN GATE PKWY, NAPLES, FL 34116 | Initiate Mobius Credentialing Workflow for Organizational Medicaid Enrollment |
| DAVID LAWRENCE MENTAL HEALTH CENTER INC | Community/Behavioral Health Agency | $36,808.00            | 425 N 1ST ST, IMMOKALEE, FL 34142 | Initiate Mobius Credentialing Workflow for Organizational Medicaid Enrollment |

### D. Taxonomy Optimization

This section identifies opportunities to optimize revenue by ensuring enrolled providers are associated with the most appropriate and highest-reimbursing taxonomy codes for their services, where a more advantageous taxonomy is available for billing. This is a medium-confidence exposure requiring verification.

| Provider          | Current Service Type               | Suggested Service Type                  | Optimization Opportunity | Location                   |
| :---------------- | :--------------------------------- | :-------------------------------------- | :----------------------- | :------------------------- |
| JEWELL, LAUREN    | Counselor                          | Addiction (Substance Use Disorder) Counselor | $30,270.05               | 6075 BATHEY LN, NAPLES, FL 34116 |
| HOLMES, CHRISTINE | Clinical Social Worker             | Case Manager/Care Coordinator           | $26,742.75               | 6075 BATHEY LN, NAPLES, FL 34116 |

**Action for Operations Director:** For JEWELL, LAUREN and HOLMES, CHRISTINE, review the suggested taxonomy optimizations. Verify with credentialing specialists if these providers perform services aligned with the suggested taxonomies and initiate the process to update their taxonomy with Medicaid and other relevant payers. This is a directional opportunity. Verify with credentialing specialist.

### E. Rate Gap — vs. State Average

No rate gap analysis available for this run — HCPCS-level state benchmarks could not be computed. The E total is from methodology (taxonomy-level org vs state comparison); treat as directional. Mobius Rate Benchmarking can provide HCPCS-level analysis once benchmarks are materialized.

## 5. Sources

This report is built only from the following data sources (outside-in; we do not have the organization's internal HR or credentialing system):

*   **Provider roster:** Links organizations to locations and servicing NPIs using state enrollment data (PML), federal NPPES, billing patterns, and taxonomy lists.
*   **Readiness checks:** Outcomes from comparing roster rows to state and federal data (four Medicaid NPI initiative checks).
*   **PML (Provider Master List):** State Medicaid provider enrollment file (e.g. FL AHCA - ahca.myflorida.com/medicaid). Used for NPI presence and NPI+taxonomy+ZIP9 combo Medicaid ID.
*   **TML / PPL:** Taxonomy Master List and Pending Provider List for permitted taxonomy codes.
*   **Claims / expenditure data:** Medicaid billing data (billing NPI, servicing NPI, claims, paid amounts). Used for ghost billing and run rates.
*   **NPPES:** National Plan and Provider Enumeration System (practice addresses, provider names, taxonomies).
*   **FL AHCA Medicaid NPI Initiative:** Florida Medicaid requires NPI, taxonomy, and service location (ZIP+4) for claims. AHCA publishes PML, TML, PPL. Our checks: (1) NPI in PML with Medicaid ID, (2) valid 9-digit ZIP+4, (3) taxonomy on TML/PPL, (4) NPI+taxonomy+ZIP9 combo has valid Medicaid ID. Ref: ahca.myflorida.com/medicaid, PML from portal.flmmis.com.
*   **FL AHCA Fee Schedules**: ahca.myflorida.com/medicaid/rules/rule-59g-4.002-provider-reimbursement-schedules-and-billing-codes
*   **FL AHCA Medicaid Main Page**: ahca.myflorida.com/medicaid/
*   **FL AHCA Medicaid Policy, Quality and Operations**: ahca.myflorida.com/medicaid/medicaid-policy-quality-and-operations
*   **FL AHCA Medicaid Rules**: ahca.myflorida.com/medicaid/rules

---

### Benchmark Methodology Note

Amounts in Sections A, B, and C reflect an organizational billing average. Individual rates vary by taxonomy, service volume, and payer mix. Taxonomy-level benchmarks were not available for this run. Section E rate gap figures reflect the comparison methodology described in Section 1, which has important limitations, particularly concerning per diem codes.