# Report Improvements for 90+ Buyer Score

*Applied March 2026 based on DLC waterfall report evaluation (79 → 90+ target).*

## Summary of Changes

### 1. Executive Summary — Order by Actionability

**Before:** Led with total opportunity; C (enrollment) buried third.

**After:** Order opportunities by what the buyer can act on first:
- **Lead:** C (enrollment gap) — "most immediately addressable"
- **Then:** B (credentialing gaps), D (taxonomy optimization)
- **Close:** E (rate gap) — "requiring further investigation"

### 2. Taxonomy-Differentiated Amounts

**Before:** Uniform $36,808 per provider (psychiatrist = case manager).

**After:** Use `base_revenue` from `opportunity_sizing_detail` for each NPI. Amounts vary by taxonomy. Add table-header note if methodology needs clarification.

### 3. Section E — Code-Level Rate Table

**Before:** Per-provider table with identical amounts; no connection to billing data.

**After:** Code-level table: HCPCS Code | DLC avg rate | DLC claim volume | (state avg if available). Top 5–8 codes from `historic_billing_patterns`. Connects to Section 2 billing table. Softer framing: "could reflect service mix, payer contracts; Mobius can help identify codes where renegotiation would have highest impact."

### 4. Service Type Column — No Placeholders

**Before:** "To be defined upon further research" in 15+ rows.

**After:** Use `taxonomy_labels` (code → short label), `taxonomy_description`, or "Taxonomy [code]". Never use placeholder text.

### 5. Section D — Org-NPI Callout

**Before:** Org NPI mixed with individual providers in same table.

**After:** When org NPI appears (e.g. facility-level billing), put in separate **callout box**: "Important: The organization's NPI may not be registered under the Community Mental Health Center taxonomy — correcting this could unlock $X."

### 6. Section D — A + D Explanation

**Before:** Providers like JEWELL appearing in both A (valid) and D (taxonomy opt) without explanation.

**After:** Add sentence: "Providers in Section A are currently valid; Section D shows those who could increase revenue by switching taxonomy."

### 7. Section 2 — Billing Table + Scope Note

**Before:** Billing table not referenced later; scope change (4 locations vs 2) unexplained.

**After:** Top-10 HCPCS billing table in Section 2. Add scope note: "Scope may differ from prior reports because DOGE billing data surfaces additional locations."

### 8. Workflow CTAs

**Before:** Generic "deploy automated workflows."

**After:** Per-section names: "Mobius ZIP+4 Correction" (B), "Mobius Enrollment" (C), "Mobius Rate Benchmarking" (E).

## Files Modified

- `mobius-skills/provider-roster-credentialing/app/waterfall_report.py` — drafter prompt, composer prompt, taxonomy_labels in context
- `mobius-skills/provider-roster-credentialing/app/report_pipeline.py` — narrative critic item 10 (waterfall-specific)
- `mobius-chat/app/services/roster_credentialing_orchestrator.py` — step 7 output includes suggested_taxonomy_description
