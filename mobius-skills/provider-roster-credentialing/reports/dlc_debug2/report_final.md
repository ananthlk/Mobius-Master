## Executive Summary

This outside-in analysis leverages PML, NPPES, and DOGE claims data to identify 99 providers across 4 locations with credentialing and enrollment gaps. Our analysis projects David Lawrence Center's current annual revenue run rate at **$2,576,560.00**.

The total addressable opportunity identified for David Lawrence Center is **$3,875,742.99**. This figure includes a rate gap component (Section E) that requires methodology verification before it can be treated as actionable. The operational opportunity — enrollment, address correction, and taxonomy optimization — totals **$1,124,444.80**.

**Order of Opportunities by Actionability:**

The most immediately actionable opportunities are related to ensuring providers are properly enrolled and their information is current, as these directly impact the ability to bill for services already rendered or to be rendered.

1.  **C. Enrollment Gap ($993,816.00)**: This represents revenue from services delivered by providers who are not properly enrolled with the payer. This is a direct loss of billable revenue and is the highest priority for remediation.
2.  **B. At-Risk Revenue ($73,616.00)**: This revenue is currently being generated but is at risk due to administrative discrepancies, such as incorrect address information. These issues can lead to payment denials or delays.
3.  **D. Taxonomy Optimization ($57,012.80)**: This opportunity involves optimizing the assigned taxonomy codes for providers to ensure they are billing at the highest appropriate rates. This typically requires a review of provider credentials and service offerings.
4.  **E. Rate Gap (Investigative, $2,751,298.19)**: This is a significant potential opportunity, but it requires further analytical verification to confirm comparability between the organization's billing models and statewide averages. It is a strategic, longer-term initiative.

**Immediate Actions:**

To capture these opportunities, David Lawrence Center should prioritize the following actions:

*   **Enrollment Gap (C)**: Initiate Mobius Enrollment Workflow for the 27 identified providers (24 individual, 3 organizational) to secure $993,816.00 in potential revenue.
*   **At-Risk Revenue (B)**: Utilize Mobius Address Verification & Update workflow to correct address discrepancies for 2 providers, securing $73,616.00 in at-risk revenue.
*   **Taxonomy Optimization (D)**: Implement Mobius Taxonomy Review & Optimization for enrolled providers, starting with Lauren Jewell, to realize $30,270.05 in potential rate uplift from detailed findings. The full $57,012.80 for this category requires further investigation as detailed in Section D.
*   **Rate Gap (E)**: Engage Mobius Rate Benchmarking services for an in-depth analysis of high-volume codes to verify comparability and identify specific contracts for renegotiation, unlocking a potential $2,751,298.19.

**Ghost Billing:** No instances of ghost billing (billing for providers not legitimately associated with the organization) were identified in this analysis, indicating strong billing integrity.

**Scope Note:** This report identifies 99 providers across 4 distinct locations. This scope is consistent with our current understanding of the organization's footprint based on external data sources.

---

## 1. Methodology

This report presents an outside-in analysis of David Lawrence Center's provider roster and credentialing status, focusing on identifying opportunities to optimize revenue through improved operational efficiency and strategic rate analysis. We leverage publicly available data and advanced analytical techniques to provide a comprehensive, actionable overview.

**Methodology Steps:**

1.  **Data Ingestion**: Initial data is sourced from David Lawrence Center's publicly available provider roster, supplemented by federal (NPPES) and state (FL AHCA PML, DOGE claims) data to build a comprehensive picture of providers, locations, and services.
2.  **Location Mapping**: Identification of all associated physical locations, using provided site addresses and cross-referencing with servicing NPI practice addresses found in Florida Medicaid claims (DOGE data).
3.  **Provider Association**: Matching individual and organizational NPIs to identified locations, assessing the strength of association (e.g., direct address match, billing patterns). This step identifies all providers potentially rendering services for the organization.
4.  **Service Validation**: For each location, identifying all services provided based on associated provider taxonomies and historic billing patterns. Medicaid approval status for each taxonomy is verified against Florida's Taxonomy Master List (TML) and Provider Master List (PML).
5.  **Medicaid Readiness Checks**: Each unique NPI × taxonomy × ZIP+4 combination undergoes four critical Medicaid compliance checks:
    *   NPI presence in the Florida PML with an active Medicaid ID.
    *   Validation of the 9-digit ZIP+4 service location.
    *   Verification that the taxonomy is permitted on the TML/PPL.
    *   Confirmation of a valid Medicaid ID for the specific NPI+taxonomy+ZIP9 combination.
6.  **Revenue Modeling**: Calculation of projected annual revenue (current run rate) for fully compliant NPI-taxonomy-location combinations using an organizational billing average (as taxonomy-specific benchmarks were not available for this run). This forms the baseline (Section A).
7.  **Opportunity Identification**: Analysis of compliance check failures and rate discrepancies to categorize revenue into specific opportunity buckets: At-Risk (B), Enrollment Gap (C), Taxonomy Optimization (D), and Rate Gap (E).
8.  **Quantification and Prioritization**: Quantification of each opportunity based on estimated annual revenue potential and prioritization by actionability, considering the directness and immediacy of potential revenue realization.

**Confidence Bands Table:**

Our findings are categorized into confidence bands to guide operational decisions.

| Band    | Score | Basis                          | Recommended action          |
|---------|-------|--------------------------------|-----------------------------|
| Perfect | 90+   | Address + billing match        | Act immediately             |
| Good    | 70+   | Billing or strong address      | Act with standard review    |
| Medium  | 50+   | Address match, no billing      | Verify before acting        |
| Low     | <50   | Weak signal only               | Internal verification first |

**Limitations:**

This analysis provides an indicative, outside-in view; we do not have direct access to David Lawrence Center's internal HR or credentialing records. Therefore, data lag, recent enrollment timing, or roster noise may affect the precision of results. This report is intended for operational review and strategic planning, not as an audit.

**Rate Gap Methodology Note (Section E):**

Section E rate gap figures are calculated by comparing each organization's average paid rate per claim against state-wide average paid rates for the same HCPCS code. This comparison has important limitations:

*   **Per Diem Codes**: Codes such as H0040 (Assertive Community Treatment) and S9485 (Crisis Intervention) are billed as per diem bundled services. The state average may include billers using a fee-for-service model, making direct rate comparison unreliable.
    *   ⚠️ **H0040 — Comparability flag**: This code is billed as a per diem bundled service. The state average may include billers using a fee-for-service model, making direct rate comparison unreliable. **This gap is not confirmed as a rate negotiation opportunity.** Include in rate analysis only after verifying the comparison methodology.
    *   ⚠️ **S9485 — Comparability flag**: This code is billed as a per diem bundled service. The state average may include billers using a fee-for-service model, making direct rate comparison unreliable. **This gap is not confirmed as a rate negotiation opportunity.** Include in rate analysis only after verifying the comparison methodology.
*   **Service Model Differences**: State averages include all biller types; if an organization uses a different service model than the state average, the gap may reflect model differences rather than rate negotiation opportunities.

For these reasons, per diem code gaps are shown for informational purposes, and the overall Section E total should be verified before inclusion in any near-term revenue projection.

---

## 2. About the Organization

David Lawrence Center is a critical behavioral health provider in Collier County, Florida, serving a diverse patient population. This section provides an overview of the organization's operational footprint and key billing patterns.

**Location Summary:**

David Lawrence Center operates from multiple sites, ensuring access to care across the region.

*   **6075 BATHEY LN, NAPLES, FL 34116**
*   **2806 HORSESHOE DR S, NAPLES, FL 34104**
*   **5266 GOLDEN GATE PKWY, NAPLES, FL 34116**
*   **425 N 1ST ST, IMMOKALEE, FL 34142**
    *   **Patient Access Stakes:** The Immokalee location (425 N 1ST ST, IMMOKALEE, FL 34142) serves a predominantly agricultural and underserved rural community. Credentialing gaps or administrative issues in this area affect not only the organization's revenue but critically impact patients' ability to access essential behavioral health services.

**Readiness Score:**

A specific readiness score for David Lawrence Center was not available in this analysis. For context, the Florida Behavioral Health (FL BH) median readiness score is typically around 68, indicating the average level of compliance and operational efficiency across similar organizations in the state. A detailed readiness score for David Lawrence Center would provide a valuable benchmark for internal improvement initiatives.

**Top 10 HCPCS Billing Table:**

Understanding the top billed services provides insight into the organization's core activities and potential areas for revenue optimization.

| HCPCS | Description                                     | Claim Count | Total Paid ($) | Average Rate/Claim ($) |
|-------|-------------------------------------------------|-------------|----------------|------------------------|
| H0040 | Assertive community treatment program, per diem | 11008       | 318844.30      | 28.96                  |
| H2019 | Therapeutic behavioral services, per 15 minutes | 2904        | 361422.97      | 124.46                 |
| T1017 | Targeted case management, each 15 minutes       | 1689        | 83933.25       | 49.69                  |
| T1015 | Clinic visit/encounter, all-inclusive           | 1676        | 118227.58      | 70.54                  |
| S9485 | Crisis intervention mental health services, per diem | 484         | 281712.25      | 582.05                 |
| H0046 | Mental health services, not otherwise specified | 358         | 7378.19        | 20.61                  |
| H0032 | Mental health service plan development by non-physician | 274         | 23775.30       | 86.77                  |
| H0031 | Mental health assessment, by non-physician      | 106         | 5676.89        | 53.56                  |
| H0035 | Mental health partial hospitalization, treatment, less than 24 hours | 93          | 18200.00       | 195.70                 |
| 99214 | (description not available)                     | 62          | 1253.85        | 20.22                  |

**Benchmarking Note:**

Due to current limitations in available state benchmark data for individual HCPCS codes, a specific "largest rate gap code" cannot be identified in this section. The overall rate gap (Section E) is calculated at the taxonomy level, not the HCPCS code level. Once HCPCS-level state benchmarks are materialized, a more granular analysis can pinpoint specific codes and associated rate gaps. The current E total from taxonomy-level comparison is $2,751,298.19.

---

## 3. Opportunity Waterfall

The following table summarizes the identified revenue opportunities, categorized by their actionability and current status.

| Level | Description                      | Amount          | Providers | Status/Confidence   |
|-------|----------------------------------|-----------------|-----------|---------------------|
| A     | Projected run rate               | $2,576,560.00   | 70        | Enrolled + valid    |
| B     | At-risk (address gaps)           | $73,616.00      | 2         | High — fix now      |
| C     | Enrollment gap (PML)             | $993,816.00     | 27        | High — enroll now   |
| D     | Taxonomy optimization            | $57,012.80      | —         | Medium — verify     |
| E     | Rate gap (investigative)         | $2,751,298.19   | —         | Requires analysis   |
| **B+C+D** | **Operational opportunity**      | **$1,124,444.80** | —         | **Actionable total**|
| **Total** | **B+C+D+E**                      | **$3,875,742.99** | —         | **Includes E (verify)** |

---

## 4. Elements of the Waterfall

Amounts reflect benchmark methodology — see Section 1 and the benchmark methodology note at the end of this section for details.

### A. Projected Revenue at Current Run Rate

This section highlights the revenue currently being generated by David Lawrence Center's enrolled and validated providers. This is the baseline from which all opportunities are measured.

**Location Summary Table:**

| Location                               | Provider Count | Projected Revenue |
|----------------------------------------|----------------|-------------------|
| 6075 BATHEY LN, NAPLES, FL 34116       | 55             | $2,024,440.00     |
| 2806 HORSESHOE DR S, NAPLES, FL 34104  | 12             | $441,696.00       |
| 425 N 1ST ST, IMMOKALEE, FL 34142      | 3              | $110,424.00       |
| **Total**                              | **70**         | **$2,576,560.00** |

**Full provider list — 70 providers.**

| Provider                                 | Service Type                        | Projected Revenue         |
|------------------------------------------|-------------------------------------|---------------------------|
| PEREZ, MARIANA                           | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| MILLER, LAVERNE                          | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| DARIEN, JANE                             | Clinical Neuropsychologist          | org benchmark avg ($36,808.00/yr) |
| PITTS, ABIGAIL                          | Counselor                           | org benchmark avg ($36,808.00/yr) |
| BRITNELL, PRISCILLA                      | Counselor                           | org benchmark avg ($36,808.00/yr) |
| JEWELL, LAUREN                           | Counselor                           | org benchmark avg ($36,808.00/yr) |
| SCHLICHTING, BONNIE                      | Counselor                           | org benchmark avg ($36,808.00/yr) |
| CHATTERTON, KELLY                        | Addiction (Substance Use Disorder) Counselor | org benchmark avg ($36,808.00/yr) |
| HALL, CHRISTOPHER                        | Addiction (Substance Use Disorder) Counselor | org benchmark avg ($36,808.00/yr) |
| ANDREWS-JONES, SUSAN                     | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| RODRIGUEZ, DAVID                         | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| SWEET, JOSEPH                            | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| CARRINGTON, NATHANIEL                    | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| MISCAVAGE, KAREN                         | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| MESSANO, ANNA                            | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| RAND, MARY                               | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| MCDOWELL, MICHAEL                        | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| DAUPHINAIS, NANCY                        | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| BREAULT, JOHN                            | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| HOLMES, CHRISTINE                        | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| ARREDONDO, MONICA                        | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| TUTTON, DAVID                            | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| MATEIKA, MATTHEW                         | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| KIRGAN, SUSAN                            | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| GEORGE, NATALIE                          | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| SAGANOWICH, JAMES                        | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| MENA, JESUS                              | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| STRUNK, LAUREN                           | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| WIREMAN, JENNIFER                        | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| MODZELEWSKI, MOLLY                       | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| BREWER, ERIN                             | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| LONG, KRISTIN                            | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| SANTORA, MICHELE                         | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| HIRCHAK, JESSICA                         | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| ODOR, LAUREN                             | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| MATTSON, KEITH                           | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| ARROYAVE, MARIA                          | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| DE POL, GREGORY                          | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| DAVIS, CYNTHIA                           | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| WEILAND, ASHLEY                          | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| ALFONSO, DAIRY                           | Clinical Social Worker              | org benchmark avg ($36,808.00/yr) |
| FUENTES, DAVID                           | Clinical Child & Adolescent Psychologist | org benchmark avg ($36,808.00/yr) |
| DRUMMOND, BIANCA                         | Social Worker                       | org benchmark avg ($36,808.00/yr) |
| BOWDEN, GAYLA                            | Social Worker                       | org benchmark avg ($36,808.00/yr) |
| MACGEORGE, TIMOTHY                       | Clinical Neuropsychologist          | org benchmark avg ($36,808.00/yr) |
| PHIMMASONE, JACQUELINE                   | Clinical Neuropsychologist          | org benchmark avg ($36,808.00/yr) |
| GALLO, CYNTHIA                           | Clinical Neuropsychologist          | org benchmark avg ($36,808.00/yr) |
| PATAK, JENNIFER                          | Clinical Neuropsychologist          | org benchmark avg ($36,808.00/yr) |
| BABIN, ERIN                              | Clinical Neuropsychologist          | org benchmark avg ($36,808.00/yr) |
| SLOCUM, ANGELA                           | Clinical Neuropsychologist          | org benchmark avg ($36,808.00/yr) |
| SWEET, SUSAN                             | Clinical Neuropsychologist          | org benchmark avg ($36,808.00/yr) |
| VANHARA, ARIELLA                         | Clinical Neuropsychologist          | org benchmark avg ($36,808.00/yr) |
| MILLER, KERI                             | Clinical Neuropsychologist          | org benchmark avg ($36,808.00/yr) |
| LOPEZ, ANGELA                            | Clinical Neuropsychologist          | org benchmark avg ($36,808.00/yr) |
| LYRISTAKIS, ERIN                         | Clinical Neuropsychologist          | org benchmark avg ($36,808.00/yr) |
| PIERRE, YVES                             | Case Manager/Care Coordinator       | org benchmark avg ($36,808.00/yr) |
| REA, JOSEPH                              | Case Manager/Care Coordinator       | org benchmark avg ($36,808.00/yr) |
| VALENZUELA, RONNY                        | Psychiatrist (2084P0800X)           | org benchmark avg ($36,808.00/yr) |
| VILLAVERDE, OSCAR                        | Psychiatrist (2084P0800X)           | org benchmark avg ($36,808.00/yr) |
| PIECZALSKA, MARTA                        | Psychiatrist (2084P0800X)           | org benchmark avg ($36,808.00/yr) |
| BENOIT, EDDY                             | Psychiatrist (2084P0800X)           | org benchmark avg ($36,808.00/yr) |
| DAVID LAAWRENCE CENTER                   | Community/Behavioral Health Agency  | org benchmark avg ($36,808.00/yr) |
| DAVID LAWRENCE MENTAL HEALTH CENTER INC  | Clinic/Center (261Q00000X)          | org benchmark avg ($36,808.00/yr) |
| DAVID LAWRENCE MENTAL HEALTH CENTER, INC | Clinic/Center (261QM0801X)          | org benchmark avg ($36,808.00/yr) |
| DAVID LAWRENCE CENTER                    | Residential Treatment Facility (322D00000X) | org benchmark avg ($36,808.00/yr) |
| DAVID LAWRENCE CENTER                    | Residential Treatment Facility (323P00000X) | org benchmark avg ($36,808.00/yr) |
| GERRITY, MAUREEN                         | Physician Assistant                 | org benchmark avg ($36,808.00/yr) |
| EDWARDS, JEFFREY                         | Psych/Mental Health Nurse Practitioner (363LP0808X) | org benchmark avg ($36,808.00/yr) |
| NERVINA, LORI                            | Psych/Mental Health Nurse Practitioner (363LP0808X) | org benchmark avg ($36,808.00/yr) |
| EBAUGH, DEBRA                            | Psych/Mental Health Nurse Practitioner (363LP0808X) | org benchmark avg ($36,808.00/yr) |

*Note: Amounts reflect an organizational billing average. Individual rates vary by taxonomy, service volume, and payer mix. Taxonomy-level benchmarks were not available for this run.*

### B. At-Risk Revenue

This section identifies revenue that is currently being billed but is at risk of denial or delay due to administrative inconsistencies, primarily incorrect address information in payer systems compared to actual service locations. Addressing these promptly is crucial to prevent revenue loss.

**Note on Concentration:** The two providers listed below account for 100% of the identified at-risk revenue, highlighting the focused impact of resolving these specific address discrepancies.

| Provider            | Service Type          | Location                               | At-Risk Amount | Current ZIP | Correct ZIP |
|---------------------|-----------------------|----------------------------------------|----------------|-------------|-------------|
| BIRMINGHAM, CHELSEA | Clinical Social Worker | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00     | 33908       | 34116       |
| STABILE, KATIE      | Clinical Social Worker | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00     | 33931       | 34116       |

**Action:** Initiate Mobius Address Verification & Update workflow for these 2 providers to reconcile their practice addresses with state records and prevent potential claim denials.

### C. Enrollment Gap — Missing PML

This represents a significant opportunity for David Lawrence Center to capture revenue from services already delivered by providers who are not properly enrolled with Medicaid (as indicated by missing PML entries). This is a direct loss of billable services that can be rectified with immediate enrollment efforts.

| Provider                                 | Service Type                        | Location                               | Enrollment Gap Amount | Enrollment Action                       |
|------------------------------------------|-------------------------------------|----------------------------------------|-----------------------|-----------------------------------------|
| DROUIN, HOLLY                            | Clinical Social Worker              | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| WEINER, CASEY                            | Clinical Neuropsychologist          | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| GONZALEZ SAVOURNIN, SEPTIMIO             | Nurse Practitioner                  | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| DEMPSEY, ZACHARY                         | Clinical Social Worker              | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| CHASANOV, MAXIM                          | Psychiatrist                        | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| SLETTA, TONYA                            | Clinical Social Worker              | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| GALANTI, GABRIELLE                       | Case Manager/Care Coordinator       | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| GIBBONS, MARY                            | Social Worker                       | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| DENNISTON, TAYLOR                        | Clinical Neuropsychologist          | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| JENKINS, CARRIE                          | Clinical Social Worker              | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| PAUL, PRESTON                            | Clinical Neuropsychologist          | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| BIRNIE, LAURA                            | Hospice and Palliative Care         | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| GRAYDEN, BRITTEN                         | Counselor                           | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| HERMANN-BARROS, SUZANNE                  | Clinical Social Worker              | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| KOROLEVICH, EMILY                        | Hospice and Palliative Care         | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| COOPER, KENDEL                           | Clinical Social Worker              | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| THOME, COLETTE                           | Counselor                           | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| LUBIN, CLAIRE                            | Registered Nurse                    | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| CALIXTE, JULIENNE                        | Psych/Mental Health Nurse Practitioner | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| SCALIA, JENNIFER                         | Clinical Neuropsychologist          | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| CAMARDA, PETRA                           | Clinical Neuropsychologist          | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| NEALON, KATHLEEN                         | Clinical Neuropsychologist          | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| CAYWOOD, APRIL                           | Psych/Mental Health Nurse Practitioner | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |
| DION, MICHELLE                           | Psych/Mental Health Nurse Practitioner | 6075 BATHEY LN, NAPLES, FL 34116       | $36,808.00            | Initiate Mobius Enrollment Workflow     |

<div style="background-color: #f0f8ff; border-left: 6px solid #2196F3; padding: 10px; margin: 10px 0;">
    **Org-level NPIs require a distinct enrollment process compared to individual providers.**
    <br>
    **Action:** Initiate Mobius Org Enrollment Workflow for these organizational entities.
</div>

| Organization                             | Service Type                        | Location                               | Enrollment Gap Amount |
|------------------------------------------|-------------------------------------|----------------------------------------|-----------------------|
| DAVID LAWRENCE MENTAL HEALTH CENTER INC (NPI: 1871163600) | Community/Behavioral Health Agency  | 2806 HORSESHOE DR S, NAPLES, FL 34104  | $36,808.00            |
| DAVID LAWRENCE CENTER (NPI: 1033883731)  | Clinic/Center                       | 5266 GOLDEN GATE PKWY, NAPLES, FL 34116 | $36,808.00            |
| DAVID LAWRENCE MENTAL HEALTH CENTER INC (NPI: 1962072793) | Community/Behavioral Health Agency  | 425 N 1ST ST, IMMOKALEE, FL 34142      | $36,808.00            |

### D. Taxonomy Optimization

This opportunity focuses on ensuring that providers are credentialed and billing under the most advantageous taxonomy codes that accurately reflect their qualifications and the services they render. Optimizing taxonomies can lead to higher reimbursement rates for existing services.

**Enrolled — taxonomy optimization available now:**

| Provider       | Current Service Type | Potential Optimal Service Type                     | Estimated Annual Uplift | Recommendation                                             |
|----------------|----------------------|----------------------------------------------------|-------------------------|------------------------------------------------------------|
| JEWELL, LAUREN | Counselor            | Addiction (Substance Use Disorder) Counselor (101YA0400X) | $30,270.05              | Review credentials for 101YA0400X; update taxonomy. |

**Uncertainty Flag:** The total taxonomy optimization opportunity is stated as $57,012.80. However, only Lauren Jewell's estimated uplift of $30,270.05 was explicitly detailed in our deep dive based on available data. The remaining $26,742.75 for this category represents potential uplift from other providers or other service code optimizations for whom specific optimal taxonomy recommendations were not available or fully quantified in the current data run. This portion of the opportunity is directional and requires further, more granular investigation and internal verification before it can be treated as a precise, confirmed figure.

**Not yet enrolled — enrollment (Section C) is prerequisite:**

For the following organizations, taxonomy optimization is possible but depends on successful completion of their enrollment (refer to Section C for enrollment actions):

<div style="background-color: #f0f8ff; border-left: 6px solid #2196F3; padding: 10px; margin: 10px 0;">
    **Org-level Taxonomy Optimization (Pending Enrollment)**

    **DAVID LAWRENCE MENTAL HEALTH CENTER INC (NPI: 1871163600)**
    *   **Current Taxonomy**: Community/Behavioral Health Agency (251S00000X)
    *   **Potential Optimization**: The NPI is also associated with Clinic/Center (261QC1500X). If this taxonomy aligns with services and is higher-reimbursing, it could represent an optimization opportunity post-enrollment.
    *   **DAVID LAWRENCE CENTER (NPI: 1033883731)**
    *   **Current Taxonomy**: Clinic/Center (261QM0801X)
    *   **Potential Optimization**: No clear alternative higher-paying taxonomy identified in available data, but further review of service scope is recommended post-enrollment.
    *   **DAVID LAWRENCE MENTAL HEALTH CENTER INC (NPI: 1962072793)**
    *   **Current Taxonomy**: Community/Behavioral Health Agency (251S00000X)
    *   **Potential Optimization**: Similar to NPI 1871163600, this NPI is associated with Clinic/Center (261QC1500X). An optimization opportunity may exist after enrollment.
</div>

**Caveat all D recommendations:** Directional. Verify with credentialing specialist. Mobius can assist in this detailed review.

### E. Rate Gap

No rate gap analysis available for this run — HCPCS-level state benchmarks could not be computed. The E total is from methodology (taxonomy-level org vs state comparison); treat as directional. Mobius Rate Benchmarking can provide HCPCS-level analysis once benchmarks are materialized.

Section E represents a significant potential revenue opportunity totaling **$2,751,298.19**, identified by comparing David Lawrence Center's average paid rates per claim against statewide averages for similar services at a taxonomy level. However, a detailed breakdown at the HCPCS code level could not be provided for this report due to the current absence of robust, comparable state benchmarks for individual CPT/HCPCS codes in our dataset. The overall figure is derived from taxonomy-level comparisons and is thus directional.

This area warrants strategic investigation. The primary objective would be to identify specific high-volume services or contracts where David Lawrence Center's reimbursement rates significantly lag behind the state average. This could inform payer negotiations or service delivery model adjustments.

**Mobius Rate Benchmarking can identify the specific codes and contracts where renegotiation would have the highest return. This is a strategic investigation. The E total should not be added to B+C+D for the purpose of near-term revenue planning until the methodology is verified.**

---

## 5. Sources

This report is built only from the following data sources (outside-in; we do not have the organization's internal HR or credentialing system):

*   **Provider roster**: Links organizations to locations and servicing NPIs using state enrollment data (PML), federal NPPES, billing patterns, and taxonomy lists.
*   **Readiness checks**: Outcomes from comparing roster rows to state and federal data (four Medicaid NPI initiative checks).
*   **PML (Provider Master List)**: State Medicaid provider enrollment file (e.g., FL AHCA). Used for NPI presence and NPI+taxonomy+ZIP9 combo Medicaid ID.
    *   **URL**: [https://ahca.myflorida.com/medicaid](https://ahca.myflorida.com/medicaid), portal.flmmis.com
*   **TML / PPL**: Taxonomy Master List and Pending Provider List for permitted taxonomy codes.
    *   **URL**: [https://ahca.myflorida.com/medicaid](https://ahca.myflorida.com/medicaid)
*   **Claims / expenditure data**: Medicaid billing data (billing NPI, servicing NPI, claims, paid amounts). Used for ghost billing and run rates.
*   **NPPES**: National Plan and Provider Enumeration System (practice addresses, provider names, taxonomies).
    *   **URL**: [https://npiregistry.cms.hhs.gov/](https://npiregistry.cms.hhs.gov/) (implied public access)
*   **Florida Agency for Health Care Administration (AHCA) Medicaid Rules**: Provides context for state-specific requirements.
    *   **URL**: [https://ahca.myflorida.com/medicaid/rules](https://ahca.myflorida.com/medicaid/rules)
*   **Florida Agency for Health Care Administration (AHCA) Provider Reimbursement Schedules and Billing Codes**: Source for fee schedules and billing codes.
    *   **URL**: [https://ahca.myflorida.com/medicaid/rules/rule-59g-4.002-provider-reimbursement-schedules-and-billing-codes](https://ahca.myflorida.com/medicaid/rules/rule-59g-4.002-provider-reimbursement-schedules-and-billing-codes)
*   **Florida Agency for Health Care Administration (AHCA) Medicaid Policy, Quality and Operations**: General Medicaid policy information.
    *   **URL**: [https://ahca.myflorida.com/medicaid/medicaid-policy-quality-and-operations](https://ahca.myflorida.com/medicaid/medicaid-policy-quality-and-operations)

---

## Benchmark Methodology Note

Amounts in Sections A, B, and C reflect a benchmark average for each provider's taxonomy. An organizational billing average was used because taxonomy-level benchmarks were not available for this run. Individual provider revenue potential will vary based on their specific taxonomy, service volume, and payer mix. Section E rate gap figures reflect the comparison methodology described in Section 1. Per diem codes are flagged individually due to their unique billing structure impacting direct comparability.