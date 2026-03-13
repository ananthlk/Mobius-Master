# FL Medicaid NPI — 13-Step Pipeline (target state)

This doc defines the canonical sequence of steps for the FL Medicaid NPI initiative and maps current assets to it.

**Step naming is implemented and state-agnostic:** Pipeline outputs are **stepN** and **stepNa**, **stepNb**, … (no state in the name). **State (e.g. FL) is an input**; the only state-specific input is the **PML** (and TML/PPL/claims). See [FL_MEDICAID_NPI_STEP_NAMING.md](FL_MEDICAID_NPI_STEP_NAMING.md) for the full index, run order, and how to parameterize for multiple states.

---

## The 13 steps

| Step | Name | Purpose |
|------|------|---------|
| **1** | Set up organization and roster | Define org structure, billing NPIs, servicing NPIs, roster list |
| **2** | Validate locations | Ensure service locations/sites exist and are valid (e.g. geocoding, site-level checks) |
| **3** | Validate NPIs | NPI in NPPES, not deactivated, entity type consistent |
| **4** | Validate address | NPPES vs PML address alignment (ZIP+9, street, city/state); mailing vs practice |
| **5** | Validate Medicaid ID presence | NPI has Medicaid provider ID in PML; contract effective/end dates |
| **6** | Validate approved taxonomy | NPPES taxonomies vs FL TML; at least one viable for FL Medicaid |
| **7** | Validate billing codes | Billed HCPCS aligned with taxonomy / FL rules; no inappropriate codes |
| **8** | Comprehensive check | NPI + Medicaid ID + taxonomy + location all pass (combined rule) |
| **9** | Produce error report with recommendations | Actionable list of issues and recommended fixes (by org/NPI) |
| **10** | *(reserved)* | — |
| **11** | Validate billing rates | Rates vs fee schedule / contract; under/over billing flags |
| **12** | Develop missed codes and billing | “Add taxonomy/code X to unlock Y”; opportunity by provider |
| **13** | Develop revenue enhancement report | Revenue-at-risk, upside from missed codes, summary for leadership |

---

## Mapping: your steps ↔ current assets

### Step 1 — Organization and roster  
**We have:**  
- `organizations` (billing NPI, org name, address, spend)  
- `billing_servicing_pairs`, `billing_servicing_pairs_fl`  
- B0: `b0_facility_master_fl`, `b0_sub_org_address_fl`, `b0_address_propensity_fl`, `b0_sub_org_members_fl`, `b0_billing_npi_members_fl`, `b0_roster_list_fl`  

**Gap:** None; optional cleanup is to label these explicitly as “Step 1” in docs/schema.

---

### Step 2 — Validate locations  
**We have:**  
- B0 sub-org/site structure (`b0_sub_org_address_fl`, site_id in roster)  
- B1 address match (which implies “location” in the sense of address)  

**Gap:** No dedicated “location” validation (e.g. site existence, geocoding, or “location type” checks). Either:  
- Treat B1 + B0 site structure as Step 2, or  
- Add a small **step_2_location_validation_fl** that flags missing/invalid site or location type.

---

### Step 3 — Validate NPIs  
**We have:**  
- `provider_readiness`: `in_nppes`, enrollment flags  
- NPPES-based checks in B6/B1/B3/B4  

**Gap:** No single “Step 3: NPI validation” output. Option: add **step_3_npi_validation_fl** (in_nppes, not_deactivated, entity_type_ok) or surface the same from `provider_readiness` / B6 as “Step 3”.

---

### Step 4 — Validate address  
**We have:**  
- `npi_addresses_fl`, `address_validation_fl` (B1, B2, B3 address issues)  
- B1/B2 in B6  

**Gap:** None; this is B1/B2. Can rename or document as “Step 4”.

---

### Step 5 — Validate Medicaid ID presence  
**We have:**  
- `b4_medicaid_id_roster_fl`, `b4_npi_medicaid_status_fl`  
- B4 in B6: `b4_has_permissible_id`, `b4_no_medicaid_id_in_pml`  

**Gap:** None; this is B4.

---

### Step 6 — Validate approved taxonomy  
**We have:**  
- `b3_taxonomy_alignment_fl` (at_least_one_viable_in_fl, no_viable_in_fl)  
- `fl_medicaid_taxonomy`, `taxonomy_validation_fl` (C1–C4, D, F)  

**Gap:** None; this is B3 + taxonomy_validation.

---

### Step 7 — Validate billing codes  
**We have:**  
- `taxonomy_validation_fl`: issue_d (HCPCS not aligned with taxonomy), issue_c*  
- `taxonomy_hcpcs_volume_fl`, `taxonomy_hcpcs_volume_indexed_fl` (outlier detection)  
- `provider_danger_opportunities_fl` (billing codes unusual for taxonomy)  

**Gap:** No explicit “billing code vs FL fee schedule / allowed codes” check. Step 7 could be: (a) current taxonomy + HCPCS alignment + danger opportunities, and (b) optional future: **step_7_billing_code_validation_fl** (e.g. code on FL allowed list, modifier rules).

---

### Step 8 — Comprehensive check (NPI + Medicaid ID + taxonomy + location)  
**We have:**  
- B5 in B6: `b5_pass`, `b5_fail_reason` (B1 + B3 + B4)  
- B6 itself as the single read head  

**Gap:** None; B5/B6 is Step 8.

---

### Step 9 — Error report with recommendations  
**We have:**  
- `provider_readiness_report` (status_flag, issue codes, status_message)  
- `provider_readiness_executive_summary`  
- B6 (detail for chat/front end)  

**Gap:** Recommendations could be more explicit (e.g. “Renew PML by date X”, “Add taxonomy Y”). Option: add **step_9_recommendations_fl** or extend `provider_readiness_report` with a recommendation text column.

---

### Step 10 — Reserved  
No asset; skip.

---

### Step 11 — Validate billing rates  
**We have:**  
- `billing_servicing_pairs`, `billing_patterns` (volume, not rates)  

**Gap:** No rate validation. Need: **step_11_billing_rate_validation_fl** (compare paid amount or units to fee schedule / contract rates; flag under/over). Depends on having rate/fee schedule data in landing.

---

### Step 12 — Missed codes and billing  
**We have:**  
- `provider_missed_opportunities_fl` (add taxonomy to unlock HCPCS)  
- `provider_danger_opportunities_fl` (review billing of code Z)  
- `provider_taxonomy_coverage_fl`, `taxonomy_hcpcs_volume_fl`  

**Gap:** None for “missed codes”; optional: single **step_12_missed_billing_opportunities_fl** that unions or summarizes missed + danger for reporting.

---

### Step 13 — Revenue enhancement report  
**We have:**  
- `provider_propensity_score_fl`  
- `provider_readiness_executive_summary`  
- No dedicated “revenue enhancement” report (upside $, at-risk $, by org)  

**Gap:** Add **step_13_revenue_enhancement_report_fl** (or similar): revenue at risk from issues, upside from missed codes, summary totals for leadership. Can build on propensity score + missed opportunities + readiness summary.

---

## Morphing plan

### Option A — Minimal (docs + one report)  
1. Keep all current model names (B0–B6, provider_readiness*, etc.).  
2. Add this doc and a one-page **step mapping** (e.g. in `FL_MEDICAID_NPI_VALIDATION_FLOW.md`) so “Step 1” = B0 + organizations, “Step 4” = B1/B2, etc.  
3. Add only the highest-value missing pieces:  
   - **Step 11:** `step_11_billing_rate_validation_fl` (stub or full when rate data exists).  
   - **Step 13:** `step_13_revenue_enhancement_report_fl` (aggregate missed opportunities + readiness into revenue-at-risk and upside).

### Option B — Full morph to Step 1–13 naming  
1. Introduce **step_N_*** models that wrap or replace current ones:  
   - Step 1: keep B0 + organizations (or add `step_1_organization_roster_fl` view over them).  
   - Steps 2–4: optional `step_2_*`, `step_3_*`; Step 4 = address_validation_fl / B1/B2.  
   - Steps 5–6: B4, B3 (or step_5_*, step_6_* views).  
   - Step 7: taxonomy_validation_fl + danger; optional step_7_*.  
   - Step 8: B6 (or `step_8_comprehensive_check_fl` = B6).  
   - Step 9: provider_readiness_report + optional step_9_recommendations.  
   - Step 11: new step_11_billing_rate_validation_fl.  
   - Step 12: missed + danger (or `step_12_missed_billing_fl`).  
   - Step 13: new step_13_revenue_enhancement_report_fl.  
2. Deprecate or alias old names over time so B6 and chat still work.

### Recommendation  
- **Short term:** Option A — document the mapping, add Step 11 (stub if no rate data) and Step 13 (revenue enhancement report).  
- **Later:** If you want a single “Step N” surface for all consumers, move to Option B and introduce step_N_* models incrementally.

---

## Summary table

| Step | Current assets | Gap / morph |
|------|----------------|-------------|
| 1 | B0, organizations, billing_servicing_pairs* | Document as Step 1 |
| 2 | B0 sites, B1 address | Optional: step_2_location_validation_fl |
| 3 | provider_readiness (in_nppes), B6 | Optional: step_3_npi_validation_fl |
| 4 | npi_addresses_fl, address_validation_fl, B1/B2 | Document as Step 4 |
| 5 | B4 (b4_*_fl) | Document as Step 5 |
| 6 | B3, fl_medicaid_taxonomy, taxonomy_validation_fl | Document as Step 6 |
| 7 | taxonomy_validation_fl (issue_d), danger_opportunities | Optional: step_7_billing_code_validation_fl; rate list if needed |
| 8 | B5, B6 | Document as Step 8 |
| 9 | provider_readiness_report, executive_summary | Optional: explicit recommendation column / step_9_* |
| 10 | — | Reserved |
| 11 | — | **New:** step_11_billing_rate_validation_fl (needs rate data) |
| 12 | provider_missed_opportunities_fl, provider_danger_opportunities_fl | Document as Step 12; optional step_12_* summary |
| 13 | propensity_score, executive_summary | **New:** step_13_revenue_enhancement_report_fl |

---

If you confirm Option A or B (or a variant), the next concrete moves are: (1) update `FL_MEDICAID_NPI_VALIDATION_FLOW.md` with the step mapping, and (2) add the two new models (Step 11 stub, Step 13 report) and any step_N_* views you want.
