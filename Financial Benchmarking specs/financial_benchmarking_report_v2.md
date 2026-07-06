# Financial Rate Benchmarking Report

## 1. About This Report

### What Data

This report draws on Florida Medicaid claims data -- both fee-for-service (FFS) and managed care organization (MCO) payments -- spanning calendar years 2019 through 2024. The source is the DOGE Medicaid Provider Spending dataset, limited to professional servicing providers with a Florida practice location. All metrics are aggregated at the organization level, not the individual clinician level, to reflect the true effective rate your organization collects.

### What We Measured

We benchmark your organization on four key performance indicators (KPIs):

1. **Rate per claim** -- "Are you paid at market?" The average dollar amount your organization receives each time it submits a claim for a given service.
2. **Patients per clinician** -- "Is your team's caseload growing or shrinking?" The number of unique patients each clinician on your team serves in a year.
3. **Visits per patient** -- "Are patients showing up and staying engaged?" The average number of claim submissions per patient, a proxy for treatment frequency and retention.
4. **Revenue per patient** -- "How much revenue does each patient generate?" Total payments collected divided by unique patients -- the combined effect of your rate, visit frequency, and session intensity.

### Who We Compared Against

Your organization is benchmarked against five peer groups, each offering a different lens:

- **All FL Medicaid Orgs** -- Every organization billing these codes in Florida Medicaid, providing the broadest possible market context.
- **Organization-Billed** -- Limited to organization-billed entities (excluding solo practitioners), since organizational billing structures differ from individual providers.
- **Similar CMHCs** -- Community mental health centers across Florida, the most direct peer group for your organization's billing model and service mix.
- **Similar Size Orgs** -- Organizations with comparable caseloads (medium panel size, 100-499 patients per clinician), controlling for scale.
- **Similar Market** -- Organizations operating in sparse-density markets like yours, where competitive dynamics and patient access differ from urban settings.

### How to Read the Charts

In each chart, the **diamond** marks your organization's actual value. The **blue line** marks the peer group median (the 50th percentile -- half of peers are above, half below). The **gray band** spans the middle 50% of peers (25th to 75th percentile). If your diamond sits inside the gray band, you are in the typical range. If it sits above or below, that is a signal worth investigating.

### Key Limitation

**Payment per claim is not the same as payment per session.** A single claim can carry multiple units of service. For example, a 90-minute therapy session billed as six 15-minute units will show a higher payment per claim than a 30-minute session billed as two units -- even if both organizations are paid the same per-unit rate. This report measures what your organization is paid per claim submission, not per 15-minute increment. Organizations that bill longer sessions will naturally show higher per-claim amounts. Where this limitation is especially relevant (notably behavioral therapy and case management codes), we flag it in the service line sections below.

---

## 2. Executive Dashboard

The table below assigns a badge to each code across four KPIs, using the Similar CMHCs peer group (n varies by code) as the primary comparison. Scan for red and yellow -- those are the areas that warrant investigation first.

| Service Line | Code | Rate Position | Productivity | Utilization | Revenue | Key Question |
|---|---|---|---|---|---|---|
| Outpatient Therapy | H2019 | 🟢 Strong | 🟢 Strong | 🟢 Strong | 🟢 Strong | ⚠️ Why is your per-claim rate nearly double the CMHC median while visit frequency is normal -- longer sessions, more units, or a different billing structure? |
| Outpatient Therapy | T1015 | 🟢 Strong | ⚪ At Market | ⚪ At Market | 🟢 Strong | Is the above-median rate sustainable under current MCO contracts? |
| Case Management | T1017 | ⚪ At Market | 🔴 Concern | ⚪ At Market | ⚪ At Market | Why has caseload per clinician dropped from 528 (2019) to 179.5 (2024) -- staffing increase, volume loss, or panel redistribution? |
| Assessment | H0031 | 🟢 Strong | 🔴 Concern | ⚪ At Market | 🟢 Strong | 📊 With only 91 claims, is the above-market rate a true signal or small-sample noise? |
| Assessment | H0032 | ⚪ At Market | 🔴 Concern | ⚪ At Market | ⚪ At Market | 📊 With only 68 claims, why has the caseload dropped from 208 (2019) to 33 (2024) per clinician? |
| E&M Office Visits | 99214 | 🔴 Concern | 🔴 Concern | ⚪ At Market | 🔴 Concern | 📊 At $15.77 per claim vs. a $51.68 CMHC median and only 45 claims -- is this code being billed correctly? |

**Flag Legend:**
- ⚠️ **Anomaly** -- H2019 shows a per-claim rate well above market ($143.65 vs. $74.53 CMHC median) while visit frequency is at the CMHC median. This pattern typically indicates longer sessions (more units per claim) rather than a higher per-unit rate. Investigate units per claim.
- 📊 **Volume Caution** -- 99214 (45 claims), H0031 (91 claims), and H0032 (68 claims) each have fewer than 100 claims in 2024. Benchmarks for these codes should be interpreted with caution.

---

## 3. Service Line Deep Dives

### Outpatient Therapy

Outpatient therapy is your organization's largest revenue-generating service line, with H2019 (behavioral therapy) alone accounting for $180,133 in 2024 payments across 1,254 claims. Combined with T1015 (medication management, $39,790), this service line represents the core of clinical operations.

---

**H2019 -- Behavioral Therapy Services**

- **Rate Position:** 🟢 Strong -- Your average payment per claim of $143.65 is nearly double the CMHC median of $74.53, placing you well above 86 similar community mental health centers.
- **Productivity:** 🟢 Strong -- At 166.7 patients per clinician, your caseload exceeds the CMHC median of 123.0, indicating your clinical team is carrying a healthy panel relative to peers.
- **Utilization:** 🟢 Strong -- At 2.51 visits per patient, treatment frequency is well above the CMHC median of 2.04, suggesting patients are staying engaged across multiple visits.
- **Revenue Intensity:** 🟢 Strong -- Revenue per patient of $360.27 is well above the CMHC median of $137.38 -- the combined effect of a higher per-claim rate and above-average visit frequency.
- **Key Question:** The per-claim rate has risen steadily from $96.94 (2019) to $143.65 (2024) while the CMHC trend signal shows the gap widening. Is this driven by longer session lengths (more 15-minute units per claim), a favorable MCO contract, or a different billing structure than peers?
- **Caveat:** H2019 is a per-15-minute code. The payment-per-claim figure reflects both the per-unit rate and the number of units billed per session. Two organizations paid the identical per-unit rate will show different per-claim amounts if their average session lengths differ.

*[Charts would be inserted here]*

---

**T1015 -- Medication Management**

- **Rate Position:** 🟢 Strong -- Your average payment per claim of $68.84 is above the CMHC median of $65.02 among 53 similar centers, with the trend diverging upward.
- **Productivity:** ⚪ At Market -- At 230.0 patients per clinician, your caseload is near the CMHC median of 224.0, though down from 491.4 in 2019.
- **Utilization:** ⚪ At Market -- At 1.26 visits per patient, frequency is slightly above the CMHC median of 1.13, consistent with a code that is typically billed once or twice per patient per year.
- **Revenue Intensity:** 🟢 Strong -- Revenue per patient of $86.50 exceeds the CMHC median of $72.19, driven by a combination of slightly higher rates and slightly higher visit frequency.
- **Key Question:** The per-claim rate has fluctuated ($55.98 in 2019, a spike to $79.90 in 2021, then $68.84 in 2024) -- is this volatility driven by changes in session length, modifier usage, or MCO contract renegotiation?
- **Caveat:** T1015 is also a per-15-minute code, so payment per claim reflects both rate and units billed. The wide P25-P75 spread in the All FL group ($49.92-$166.48) suggests significant variation in how organizations bill this service.

*[Charts would be inserted here]*

---

### Case Management

Targeted case management (T1017) generated $83,933 across 1,689 claims in 2024. This is a high-touch, high-frequency service -- your patients averaged 4.7 visits each -- making it a meaningful contributor to both revenue and clinical workload.

---

**T1017 -- Targeted Case Management**

- **Rate Position:** ⚪ At Market -- Your average payment per claim of $49.69 matches the CMHC median of $49.58 almost exactly among 34 similar centers. However, this is well below the broader FL market median of $62.20 (288 orgs).
- **Productivity:** 🔴 Concern -- At 179.5 patients per clinician, your caseload is well below the CMHC median of 275.0. This has fallen sharply from 528.0 in 2019, with an especially steep drop from 270.5 (2022) to 179.5 (2024).
- **Utilization:** ⚪ At Market -- At 4.7 visits per patient, treatment frequency matches the CMHC median of 4.7 exactly. Patients are engaging at typical frequency.
- **Revenue Intensity:** ⚪ At Market -- Revenue per patient of $233.80 is near the CMHC median of $240.24. Normal visit frequency and a market-rate per-claim payment produce market-level revenue per patient.
- **Key Question:** The combination of a falling caseload (528 to 179.5 patients per clinician over five years) and a rate trend that is diverging downward versus peers warrants investigation -- has the organization added case management staff faster than the patient panel has grown, or is the panel itself shrinking?
- **Caveat:** T1017 is a per-15-minute code. The per-claim rate of $49.69 reflects both the rate per unit and the number of units per encounter. The CMHC-specific median is substantially lower than the all-FL median, which is typical because CMHCs often bill shorter case management encounters than specialty case management organizations.

*[Charts would be inserted here]*

---

### Assessment

Assessment services (H0031 and H0032) generated a combined $10,488 across 159 claims in 2024. These are low-frequency, typically once-per-patient services that serve as the clinical front door for treatment engagement.

---

**H0031 -- Mental Health Assessment**

- **Rate Position:** 🟢 Strong -- Your average payment per claim of $57.85 is well above the CMHC median of $31.70 among 48 similar centers -- 83% above the peer midpoint.
- **Productivity:** 🔴 Concern -- At 76.0 patients per clinician (single clinician), caseload is well below the CMHC median of 115.42. This has dropped from 177.7 (2019), with a particularly sharp decline from 248.0 (2022) to 76.0 (2024).
- **Utilization:** ⚪ At Market -- At 1.2 visits per patient, assessment frequency is near the CMHC median of 1.22, consistent with a code that is typically billed once per patient.
- **Revenue Intensity:** 🟢 Strong -- Revenue per patient of $69.27 is well above the CMHC median of $45.73, driven almost entirely by the above-market per-claim rate since visit frequency is typical.
- **Key Question:** The per-claim rate is 83% above the CMHC median -- is this because your organization bills the in-depth assessment version (HO modifier, fee schedule $126.11) while most peers bill the limited version (fee schedule $17.90)?
- **Caveat:** 📊 With only 91 claims and a single servicing clinician, this sample is too small for confident benchmarking. Additionally, H0031 blends two distinct billing variations (in-depth assessment vs. limited assessment) that carry very different fee schedule rates; the data cannot distinguish between them.

*[Charts would be inserted here]*

---

**H0032 -- Treatment Plan Development**

- **Rate Position:** ⚪ At Market -- Your average payment per claim of $76.81 is above the CMHC median of $70.75 among 55 similar centers, placing you between the median and the 75th percentile ($82.31).
- **Productivity:** 🔴 Concern -- At 33.0 patients per clinician, caseload is well below the CMHC median of 75.0. This has dropped precipitously from 207.6 (2019) to 33.0 (2024).
- **Utilization:** ⚪ At Market -- At 1.03 visits per patient, treatment plan development frequency matches the CMHC median of 1.03 exactly. This is expected -- treatment plans are typically developed once per patient.
- **Revenue Intensity:** ⚪ At Market -- Revenue per patient of $79.14 is above the CMHC median of $72.49, consistent with the slightly above-market rate and typical utilization.
- **Key Question:** The trend signals show convergence (previously well above market, now closer to the median) -- is the declining per-claim rate ($92.19 in 2019 to $76.81 in 2024) a concern, or is it normalizing toward the peer range? And why has the caseload per clinician dropped by 84% over five years?
- **Caveat:** 📊 With only 68 claims, this sample is below the threshold for confident benchmarking. H0032 also blends multiple billing variations (plan development vs. plan review) with different fee schedule rates ($97.86 vs. $48.93); the data combines all variations.

*[Charts would be inserted here]*

---

### E&M Office Visits

Office-based evaluation and management (99214) generated only $710 across 45 claims in 2024. This is the smallest service line by volume and revenue, but the patterns here are notable enough to warrant attention.

---

**99214 -- Office Visit (Level 4)**

- **Rate Position:** 🔴 Concern -- Your average payment per claim of $15.77 is well below the CMHC median of $51.68 among 65 similar centers -- 69% below the peer midpoint.
- **Productivity:** 🔴 Concern -- At 37.0 patients per clinician (single clinician), caseload is well below the CMHC median of 98.67.
- **Utilization:** ⚪ At Market -- At 1.22 visits per patient, frequency is above the CMHC median of 1.09, suggesting patients who do receive this service tend to return.
- **Revenue Intensity:** 🔴 Concern -- Revenue per patient of $19.18 is well below the CMHC median of $59.91, the direct consequence of a per-claim rate that is less than a third of the market midpoint.
- **Key Question:** A Level 4 office visit at $15.77 per claim is far below what any standard fee schedule would pay for 99214. Is this code being billed without the expected components (e.g., as a secondary code on a claim where another service captures the primary payment), or is there a systematic billing issue?
- **Caveat:** 📊 With only 45 claims and a single servicing clinician, this is a very small sample. The trend data shows $0 payments in 2019 and 2020 and only $3.31 in 2021, suggesting this code may have been recently adopted or its billing context may have changed. COVID-era disruption (2020-2021) may also have affected the early data points.

*[Charts would be inserted here]*

---

## 4. Caveats & Methodology

### Per-Metric Caveats

**Rate per claim** measures the average payment per claim submission, not per unit of service. For codes billed in 15-minute increments (H2019, T1015, T1017), a single claim can contain multiple units. An organization billing six units per claim will show three times the per-claim rate of an organization billing two units per claim, even if both are paid the same per-unit amount. This metric answers "what does a typical claim pay?" -- not "what is our per-unit reimbursement rate?"

**Patients per clinician** measures the number of unique patients attributed to each servicing provider. It reflects both panel assignment practices and staffing levels. An organization that adds clinicians without growing its patient base will show declining patients per clinician, even if overall volume is healthy. This metric cannot distinguish between healthy panel management and a shrinking patient base.

**Visits per patient** measures claim frequency, not clinical engagement. A patient who no-shows three appointments and completes one visit looks the same as a patient who was only scheduled for one visit. This metric also cannot account for patients who disengage entirely (they simply disappear from the denominator in subsequent periods). It answers "how many times are we billing per patient?" -- not "are patients completing their treatment plans?"

**Revenue per patient** is the combined effect of rate, visit frequency, and units per visit. A high value can reflect premium rates, high utilization, long sessions, or all three. This metric is useful for identifying service lines where revenue concentration is high or low, but it cannot diagnose why.

### Data Source

All benchmarks are derived from the DOGE Medicaid Provider Spending dataset for the state of Florida, covering calendar years 2019 through 2024. The data includes both fee-for-service and managed care organization claims. Only professional servicing NPIs (entity type code 1 in NPPES) with a Florida practice location are included. MCO negotiated rates are typically below published fee schedules; the median values in this report reflect market-effective rates, not published maximums.

### Peer Group Construction

Each peer group is a parallel, single-dimension cut of the full Florida Medicaid population. Peer groups are not compounded (e.g., "CMHCs in sparse markets" is not a group -- CMHC and sparse market are separate lenses). This preserves sample size for statistical credibility. All cells require a minimum of 3 distinct organizations to prevent individual identification.

The five peer groups used in this report:

| Peer Group | What It Controls For | Sample Size (varies by code) |
|---|---|---|
| All FL Medicaid Orgs | Nothing -- broadest context | 288-4,211 orgs |
| Organization-Billed | Excludes solo practitioners | 280-3,733 orgs |
| Similar CMHCs | Organization type (community mental health center) | 34-86 orgs |
| Similar Size Orgs | Panel size (medium: 100-499 patients per clinician) | 126-1,643 orgs |
| Similar Market | Competitive density (sparse: fewer than 3 peers in ZIP) | 77-543 orgs |

### What "Payment Per Claim" Means vs. "Payment Per Session"

This is the most important methodological nuance in this report. The underlying data provides total payments and total claims, but not the number of units per claim. For time-based codes like H2019 (behavioral therapy, billed per 15 minutes), a single claim submission can represent anywhere from one unit (15 minutes) to eight or more units (2+ hours).

This means: if Organization A bills a 90-minute therapy session as one claim with six units, and Organization B bills a 30-minute session as one claim with two units, Organization A will show three times the "payment per claim" -- even if both organizations are paid the exact same per-unit rate. The data cannot separate rate differences from session-length differences.

Where this matters most in this report: **H2019**, where your organization's per-claim rate of $143.65 is nearly double the CMHC median. This could mean your organization is paid more per unit, or it could mean your therapists conduct longer sessions. Both are operationally meaningful, but they have different implications. The former suggests a rate advantage; the latter suggests a clinical model choice. Investigating units per claim in your billing system is the recommended next step.
