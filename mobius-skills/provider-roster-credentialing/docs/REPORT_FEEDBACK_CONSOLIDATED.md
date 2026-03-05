# Provider Roster Credentialing Report — Consolidated Feedback

Consolidated from Gemini and ChatGPT feedback on the POC report. Use this to decide what to implement in the report writer prompt and pipeline.

---

## What to keep (both reviewers)

- **Percentage-based hook** — Lead with "X% of NPIs have issues" / "Y% invalid combinations"; executives care more than raw counts.
- **Unit of analysis** — Define combination (NPI × Taxonomy × ZIP+4) once; explain why Ready count can exceed total NPIs.
- **Glossary** — PML, TML/PPL, ZIP+4, combination in business language.
- **Top 3 problems** — Not enrolled, Combo mismatch, Invalid address with brief action.
- **Mobius Actions / Next Best Actions** — Concrete workflows (enrollment tracker, roster correction, ZIP+4 validation).

**Resolution-focused language and structure (added later):**
- **Key Recommendations** — Dedicated section with 4–6 items: what to resolve, action to take, expected outcome. Avoid issue-log tone.
- **Appendix** — Detailed methodology, full glossary, illustrative sample when fixture. Keeps main body concise.
- **Tone** — Use "resolve," "remediate," "achieve readiness," "path to resolution" throughout; frame findings as opportunities to resolve, not just as a defect list.

---

## Structural and wording changes

### 1. Executive overview: shorter and more “executive”

- **Feedback:** Too long, too process-heavy; CEO should get it in ~20 seconds.
- **Target:** ~120–150 words max.
- **Ask:** Lead with what was analyzed and headline numbers, then one clear “So what?” (financial/operational impact). No methodology detail here.
- **Implementation:** Prompt: “Executive overview MUST be ~120–150 words. Lead with org name, total NPIs, total combinations, invalid count and %, NPIs with issues and %. Then one short paragraph: why it matters (claim denials, payment delays, rework). End with one line on ghost billing/missed opportunities if applicable.”

### 2. “So what?” / financial impact line

- **Feedback:** Add explicit link to revenue/operations, not just compliance.
- **Example:** “These invalid combinations create direct exposure to Medicaid claim denials and payment delays.” Optionally: “Revenue at risk” or “billing latency” when data exists.
- **Implementation:** Prompt: “Include a single ‘So what?’ or impact sentence: e.g. invalid combinations will block or delay Medicaid billing and create rework.”

### 3. Methodology: generic, not technical

- **Feedback:** Remove internal table names (bh_roster, bh_roster_readiness); use business terms.
- **Replace with:** e.g. “Master Provider Index” (or “provider roster”) for locations/NPIs; “readiness validation results” for check outcomes. Keep four checks and unit of analysis; move implementation detail to appendix or “How we calculate” if needed.
- **Implementation:** Change METHODOLOGY and METHODOLOGY_OVERVIEW (and SOURCES if shown to end users) to use generic terms; keep technical names only in a technical Sources/Appendix if desired.

### 4. Location section: show all or omit

- **Feedback:** “One representative location” feels like a placeholder. Either show all locations in a table or drop the section.
- **Option A:** Table: Location | City | State | ZIP (and if available: NPIs | NPIs with issues | Invalid combos).
- **Option B:** Remove section.
- **Implementation:** Prompt: “Location summary: list ALL locations from location_summary in a table (org_name, city, state, zip). Do not show only one ‘representative’ location.” Per-location metrics table requires snapshot support (see “Future: per-location stats” below).

### 5. Top 3 problems: add percentages

- **Feedback:** Add % of invalid combos for each type so scale is obvious.
- **Example:** Not enrolled — 117 (47%); Combo mismatch — 69 (28%); Invalid address — 53 (21%).
- **Implementation:** Prompt: “In Top 3 problems, include the percentage of total invalid combinations for each type (e.g. 47%, 28%, 21%).”

### 6. Ghost billing when zero: data freshness

- **Feedback:** When ghost billing = 0, say what was checked so it reads as “verified” not “no data.”
- **Implementation:** Already passing data_window_ghost_billing. Prompt: “When ghost billing count is zero, state the data window explicitly (e.g. ‘Checked DOGE claims from [window]. No ghost billing detected.’).”

### 7. Priority / complexity matrix

- **Feedback:** Add a remediation priority matrix: Priority (P1/P2/P3), Issue type, Complexity (High/Medium/Low), Next action.
- **Example:** P1 CRITICAL — Not Enrolled — High — Submit enrollment via AHCA; P2 HIGH — Combo Mismatch — Medium — Reconcile roster vs PML; P3 QUICK WIN — Invalid Address — Low — Update ZIP+4.
- **Implementation:** Prompt: “Include a Remediation Priority Matrix table: Priority (P1–P3), Issue Type, Complexity (High/Medium/Low), Next Best Action. Map: Not enrolled = High, Combo mismatch = Medium, Invalid address = Low.”

### 8. Reduce repetition

- **Feedback:** Define “combination” once; avoid long methodology in body if it’s in appendix.
- **Implementation:** Prompt: “Define the unit of analysis (combination) once—either in Methodology or in Glossary, not in both in full. Keep Methodology concise; put detailed step logic in an Appendix if needed.”

### 9. Single “Insights + Actions” section

- **Feedback:** “Insights & Recommendations” and “Mobius Actions” overlap; merge.
- **Implementation:** Prompt: “Use one combined section: ‘Insights & Mobius Actions.’ Short interpretation (2–3 sentences), then Remediation Priority Matrix, then 3–5 concrete workflows. Do not repeat the same actions in a separate Recommendations section.”

### 10. Summary table: no duplicate metrics

- **Feedback:** Don’t show both “NPIs with at least one issue” and “Percentage of NPIs with issues” as separate rows.
- **Implementation:** Prompt: “In the main metrics table, one row per metric; use a single Count column and a % column where relevant; do not duplicate the same metric as two rows.”

### 11. Mobius differentiation

- **Feedback:** Make it clear Mobius turns credentialing rules into an operational view and generates workflows.
- **Examples:** “Mobius converts complex Medicaid credentialing rules into a single operational view of provider readiness.” “Mobius surfaces the exact combinations that will block Medicaid billing before claims are submitted.”
- **Implementation:** Prompt: “Include one short ‘Why this matters’ or product line: e.g. Mobius converts Medicaid credentialing rules into a single operational view and generates workflows to resolve issues; or that Mobius surfaces combinations that will block billing before claims are submitted.”

### 12. Optional: Florida / AHCA future-proofing

- **Feedback:** Note AHCA enrollment modernization (e.g. 2026) and that Mobius will track changes.
- **Implementation:** Optional one-line in prompt: “If relevant, add a short ‘Future-proofing’ note: AHCA enrollment changes; Mobius monitors so Not Enrolled NPIs can be migrated or re-submitted.”

---

## Implementation checklist

| # | Change | Where | Status |
|---|--------|--------|--------|
| 1 | Executive overview ~120–150 words, lead with numbers + So what | Prompt | |
| 2 | So what / financial impact sentence | Prompt | |
| 3 | Methodology generic (no bh_roster, bh_roster_readiness) | Constants | |
| 4 | Location: all locations in table, or omit | Prompt | |
| 5 | Top 3 problems: add % of invalid combos | Prompt | |
| 6 | Ghost billing zero: state data window | Prompt | |
| 7 | Remediation Priority Matrix (P1/P2/P3, Complexity, Action) | Prompt | |
| 8 | Define combination once; methodology concise, detail in appendix | Prompt | |
| 9 | Merge Insights + Mobius Actions into one section | Prompt | |
| 10 | Metrics table: no duplicate rows | Prompt | |
| 11 | “Why this matters” / Mobius differentiation line | Prompt | |
| 12 | Optional AHCA future-proofing line | Prompt | |
| — | Increase max_output_tokens (e.g. 8192) to avoid truncation | report_writer.py | |

---

## Future: per-location stats (location leaderboard)

- **Idea:** Table: Location | City | NPIs | NPIs with issues | Invalid combos (so “which site is most at risk” is obvious).
- **Requires:** Core or snapshot to expose per-location counts (e.g. from readiness_rows/invalid_combos by location_id or site). Not in current snapshot; add to `_build_snapshot` and optionally to `build_executive_summary`/report payload when available.

---

## References

- Report writer: `mobius-skills/provider-roster-credentialing/app/report_writer.py`
- Snapshot shape: `_build_snapshot()` in same file; report payload from `core.build_full_report` / `build_executive_summary`.
