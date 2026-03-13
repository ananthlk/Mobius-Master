"""
Waterfall-centric credentialing report from step outputs (1–10).
Builds report context from step_outputs, runs draft → validator → composer.
Per docs/CREDENTIALING_REPORT_PIPELINE_SPEC.md.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
from typing import Any, Callable

from app.core import TAXONOMY_CODE_LABELS
from app.report_writer import (
    AHCA_CONTEXT,
    AHCA_DOCS_REF,
    DOGE_LIMITATIONS,
    GLOSSARY,
    METHODOLOGY,
    SOURCES,
    _call_gemini,
    _call_openai,
    _load_ahca_docs,
)

logger = logging.getLogger(__name__)


def _format_exact_numbers_block(context: dict[str, Any]) -> str:
    """Return COPY-EXACTLY block with exact numbers for header/waterfall. No computation allowed."""
    wt = context.get("waterfall_totals") or {}
    pc = context.get("provider_counts") or {}
    a_count = pc.get("A")
    b_count = pc.get("B")
    c_count = pc.get("C")
    a_str = f"{a_count} providers" if a_count is not None else ""
    b_str = f"{b_count} providers" if b_count is not None else ""
    c_str = f"{c_count} providers" if c_count is not None else ""
    return f"""**COPY EXACTLY — DO NOT COMPUTE. Use these numbers verbatim in header and waterfall.**
- Section A: ${wt.get('guaranteed', 0):,.2f}{f" — {a_str}" if a_str else ""}
- Section B: ${wt.get('at_risk', 0):,.2f}{f" — {b_str}" if b_str else ""}
- Section C: ${wt.get('missing', 0):,.2f}{f" — {c_str}" if c_str else ""}
- Section D: ${wt.get('taxonomy_opt', 0):,.2f}
- Section E: ${wt.get('rate_gap', 0):,.2f} (directional only — do not add to opportunity)
- Total opportunity: B+C+D only. E excluded.

**DISAMBIGUATION:** find_associated_providers has the full roster (validated + flagged + missing). Section A = VALIDATED ONLY ({a_str or "N/A"}). Do NOT use find_associated_providers row count for Section A header or waterfall."""


def _format_canonical_tables_block(context: dict[str, Any]) -> str:
    """Return markdown block with canonical A/B/C tables for drafter, or empty if not available."""
    tt = context.get("tick_and_tie_section_sources") or {}
    a_table = tt.get("canonical_section_a_table", "").strip()
    if not a_table:
        return "Use opportunity_sizing_detail for Section A/B/C amounts. Sum of rows must equal section total."
    a_sum = tt.get("A_sum", 0)
    a_rows = tt.get("A_rows") or []
    amounts = [float(r.get("base_revenue") or 0) for r in a_rows]
    unique_amounts = len(set(round(a, 2) for a in amounts if a > 0))
    uniform_note = ""
    if unique_amounts <= 1 and amounts:
        avg_amt = sum(amounts) / len(amounts) if amounts else 0
        uniform_note = f"\nLABEL: Amounts are UNIFORM (org-level benchmark). Use 'org benchmark avg (${avg_amt:,.2f}/yr)' — NEVER 'taxonomy-differentiated' or 'for this taxonomy'."
    return f"""**SECTION A/B/C (injected automatically — for D/E narrative context only).**
{uniform_note}

Section A — {tt.get("A_count", "?")} providers, total ${a_sum:,.2f}. Section B/C: see counts below.
Use this context for Section D prerequisite checks (no provider in "not yet enrolled" who appears in Section A)."""


def _format_canonical_section_table(
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str, str]],  # (key, header, fmt)
) -> str:
    """Format rows as markdown table. fmt: 'num' for $X,XXX.XX; 'str' for text."""
    if not rows:
        return ""
    lines = []
    headers = [h for (_, h, _) in columns]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---" for _ in columns]) + "|")
    for r in rows:
        cells = []
        for key, _, fmt in columns:
            v = r.get(key) or ""
            if fmt == "num":
                try:
                    n = float(v)
                    cells.append(f"${n:,.2f}")
                except (ValueError, TypeError):
                    cells.append(str(v))
            else:
                cells.append(str(v)[:60])
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Waterfall Drafter Prompt — v3 (post-DLC rubric + data integrity audit)
# Key additions: benchmark stability, per diem comparability, materiality thresholds
# ---------------------------------------------------------------------------
WATERFALL_DRAFTER_PROMPT = """You are an expert analyst writing a Provider Roster / Credentialing report (8–12 pages)
centered on the revenue waterfall opportunity. Aim for buyer score 90+ across seven
dimensions: clarity, credibility, actionability, trust, visualization, product signal,
and completeness. Write as if presenting to a CFO and a credentialing operations director
simultaneously — the CFO needs dollar stakes and strategic framing; the operations
director needs named providers, specific actions, and correct sequencing.

**NUMBERS RULE:** You will receive a "COPY EXACTLY" block with pre-validated numbers. Use those exact numbers
for Section A/B/C counts and totals in the header and waterfall. Do NOT compute, infer, or derive counts
or amounts from other CSVs (e.g. find_associated_providers). Mismatching numbers cause validation FAIL.

This report will be reviewed by a validator and a narrative critic before being finalized.
Your job is to produce content that will pass both reviews. That means: flag your own
uncertainties. Do not dress up uncertain data as confident findings.

---

REPORT STRUCTURE (follow exactly):

## Executive Summary

- **One-line methodology**: "This outside-in analysis leverages [PML / NPPES / DOGE
  claims / TML] to identify [N] providers across [N] locations with credentialing
  and enrollment gaps."
- **Current run rate**: State the projected revenue at current run rate (A) as the
  baseline. Do not call this "guaranteed" or "confirmed" revenue.
- **Total addressable opportunity**: $[B+C+D] only. Do NOT add Section E.
  "The operational opportunity totals $[B+C+D]. Section E (rate gap) is directional
  insight from DOGE data—significant limitations apply (paid-claims only, no denials,
  small-cell suppression, facility/MCO variance). E is not a quantified opportunity."
  Give both numbers. Never present E as equivalent in confidence to B, C, or D.
- **Order opportunities by actionability** (most immediately actionable first):
  C → B → D → E. State the rationale explicitly.
- **Immediate actions** with named Mobius workflows (C, B, D, E in that order).
- **Ghost billing**: If zero, frame as positive billing integrity indicator.
- **Scope note** if NPI/location count differs from prior reports.

---

## 1. Methodology

Write 6–8 numbered steps. Include:

**Confidence bands table:**
| Band    | Score | Basis                          | Recommended action          |
|---------|-------|--------------------------------|-----------------------------|
| Perfect | 90+   | Address + billing match        | Act immediately             |
| Good    | 70+   | Billing or strong address      | Act with standard review    |
| Medium  | 50+   | Address match, no billing      | Verify before acting        |
| Low     | <50   | Weak signal only               | Internal verification first |

**Rate gap methodology note** — include this paragraph verbatim:
"Section E presents directional insights from DOGE Medicaid paid-claims data. It is
**not a quantified opportunity**. The figures compare org average paid rate per claim
to state-wide averages by HCPCS. DOGE has significant limitations: paid-claims only
(no denials), small-cell suppression, no units of service, facility vs non-facility
blending, and MCO/dual-eligible reporting variance. Per diem codes (H0040, S9485)
are not directly comparable across biller types. Use Section E for discussion and
further analysis—do not add E to the operational opportunity total (B+C+D)."

---

## 2. About the Organization

- **Location summary** with full addresses. For underserved locations (rural,
  agricultural, high-Medicaid), explicitly note patient access stakes:
  "Credentialing gaps here affect not only revenue but patients' ability to access care."
- **Readiness score** vs FL BH median 68 if available.
- **Top 10 HCPCS billing table** with claim count, total paid, avg rate/claim.
- **Benchmarking note**: Name the largest rate gap code and its gap. If H0040
  or another per diem code shows the largest gap, add: "Note: H0040 is a per diem
  bundled service — see Section E and the rate gap methodology note in Section 1."

---

## 3. Opportunity Waterfall

**Summary table:**
| Level | Description                | Amount        | Providers | Status/Confidence  |
|-------|----------------------------|---------------|-----------|---------------------|
| A     | Projected run rate         | $X            | N         | Enrolled + valid    |
| B     | At-risk (address gaps)     | $X            | N         | High — fix now      |
| C     | Enrollment gap (PML)       | $X            | N         | High — enroll now   |
| D     | Taxonomy optimization      | $X            | N         | Medium — verify     |
| E     | Rate gap (directional)     | $X            | —         | Not quantified opportunity |
| B+C+D | Operational opportunity    | $X            | —         | Actionable total    |
| Total | B+C+D                     | $X            | —         | E excluded (directional) |

Total opportunity = B+C+D only. Section E is directional insight; do not add to the total.

---

## 4. Elements of the Waterfall

Add above all tables: *"Amounts reflect benchmark methodology — see Section 1 and
the benchmark methodology note at the end of this section for details."*

**A. Projected Revenue at Current Run Rate**

Provider table. **Taxonomy-differentiated amounts are required.** Pull rates from
taxonomy_utilization_benchmarks for each provider's primary taxonomy code.
- If the benchmark produces the same rate for all taxonomies (e.g., because only
  an org-level average is available), do NOT label it taxonomy-differentiated.
  Instead label each cell: "org benchmark avg ($X/yr)" and add a table note:
  "Amounts reflect an organizational billing average. Individual rates vary by
  taxonomy and service mix — taxonomy-level benchmarks were not available for
  this run."
- NEVER label uniform amounts as "benchmark avg ($X/yr for this taxonomy)" if
  the same number appears for every taxonomy. That claim is factually false.

If Section A contains more than 30 providers, add a location summary table ABOVE
the full provider table:
| Location | Provider count | Projected revenue |
Then include the full provider table. Label it: "Full provider list — [N] providers."

**B. At-Risk Revenue**

Provider table. Required columns: Provider | Service Type | Location | At-Risk Amount
| Current ZIP | Correct ZIP. This section should be the most specific and most
immediately executable in the report.

**C. Enrollment Gap — Missing PML**

Provider table with Enrollment Action column. Note: if any rows are org-level NPIs
(not individual providers), separate them into a sub-section:
*"Org-level enrollment gaps (separate workflow from individual provider enrollment):"*
This is a different action than individual credentialing — the operations director
needs to know which is which.

**D. Taxonomy Optimization**

Org-level finding (if present): use a callout box, not a table row.

Split provider table into:
1. *Enrolled — taxonomy optimization available now*
2. *Not yet enrolled — enrollment (Section C) is prerequisite*

Prerequisite check: before placing any provider in sub-table 2, verify they are
NOT already in Section A. If a provider appears in Section A, they are enrolled
and belong in sub-table 1 or should not appear in D at all.

Caveat all D recommendations: "Directional. Verify with credentialing specialist."

**E. Rate Gap — vs. State Average**

**MANDATORY when E > $0:** Section E must be included. Do NOT omit Section E. The report will fail validation.

Code-level rate comparison table:
| HCPCS | Description | DLC avg rate | FL state avg | Gap/claim | DLC volume | Total gap |

**Mandatory flags for per diem codes:**
For H0040, S9485, or any code described as "per diem" in its HCPCS description:
> ⚠️ **Comparability flag**: [Code] is billed as a per diem bundled service at this
> organization. The state average may include billers using a different service
> model. This gap **cannot be confirmed as a rate negotiation opportunity** without
> verifying that the comparison is between like-for-like billing models. Recommended:
> exclude from actionable total pending review.

**Mandatory concentration flag:**
If any single code accounts for more than 25% of the E total, add:
> **Concentration note**: [Code] accounts for $[X] ([Y]%) of the total rate gap.
> The E total is highly sensitive to this single code. If the [Code] gap is
> determined to be structural (service model difference), the actionable E total
> would be approximately $[E minus that code].

Show negative gaps (where DLC earns above state average) — include them. Hiding
them makes the report less credible, not more.

If the visible table covers less than 50% of the E total:
- State this clearly: "[N] codes shown, covering $[X] ([Y]%) of the $[E] rate gap."
- Add: "The methodology for the remaining $[Z] gap is available on request.
  Until verified, only the $[visible total] should be treated as a confirmed
  rate gap analysis."

Close Section E with: "Mobius Rate Benchmarking can identify the specific codes
and contracts where renegotiation would have the highest return. This is a
strategic investigation. The E total should not be added to B+C+D for the purpose
of near-term revenue planning until the methodology is verified."

---

## 5. Sources

Full list with AHCA URLs.

---

## Benchmark Methodology Note

At the end of Section 4, include this note verbatim:
"Amounts in Sections A, B, and C reflect a benchmark average for each provider's
taxonomy. [If taxonomy-differentiated: Each taxonomy code is benchmarked against
the statewide average for that code.] [If org-level only: An organizational billing
average was used because taxonomy-level benchmarks were not available for this run.
Individual provider revenue potential will vary based on their specific taxonomy,
service volume, and payer mix.] Section E rate gap figures reflect the comparison
methodology described in Section 1. Per diem codes are flagged individually."

---

TONE: Honest about uncertainty. The credibility of the report comes from saying
"we don't know" where we don't know — not from filling every cell with a number.
A CFO who sees "$539K rate gap" and later discovers H0040 per diem rates aren't
comparable will not trust the next report. A CFO who sees "$539K — requires
methodology verification before treatment as actionable" will."""

# ---------------------------------------------------------------------------
# Section-specific prompts for multi-call drafting (avoids truncation)
# Token budgets per section: ~4 chars/token; keep each call under 4k tokens
# ---------------------------------------------------------------------------
_SUMMARY_SUFFIX = """ End with exactly one line: <!--SECTION_SUMMARY: Your one-line summary of what this section says (e.g. key numbers, main point) -->"""

SECTION_EXEC_SUMMARY_PROMPT = """Write the Executive Summary only (~600 tokens). Use exact numbers from the COPY EXACTLY block.
Include: one-line methodology, current run rate (A), total addressable (B+C+D only—do NOT add E), DOGE/Section E limitation note, opportunity order C→B→D→E, immediate actions, ghost billing, scope note. Output markdown starting with ## Executive Summary.""" + _SUMMARY_SUFFIX

SECTION_METHODOLOGY_PROMPT = """Write Section 1 Methodology only (~500 tokens). Include 6–8 numbered steps, the confidence bands table (copy exactly), the rate gap methodology paragraph (copy verbatim), and the DOGE limitations note: Section E is directional insight from DOGE paid-claims data—not a quantified opportunity. Output markdown starting with ## 1. Methodology.""" + _SUMMARY_SUFFIX

SECTION_ABOUT_ORG_PROMPT = """Write Section 2 About the Organization only (~600 tokens).
**MANDATORY (from MANDATORY COMPUTED FIELDS — use exactly):**
1. Readiness score: State the exact value from the context (e.g. "Readiness score: 70.41%"). Do not omit.
2. Location summary: Include ALL locations from the full list. Do not drop any (e.g. Immokalee). List every address.
3. Benchmarking note. The top-10 HCPCS billing table is pre-built and will be injected — do NOT create it.
Output markdown starting with ## 2. About the Organization. Write narrative only; the HCPCS table will be appended automatically.""" + _SUMMARY_SUFFIX

SECTION_WATERFALL_SUMMARY_PROMPT = """Write Section 3 Opportunity Waterfall summary only (~300 tokens). The summary table is pre-built and will be injected — do NOT create or modify the table.
Your job: write 1–3 sentences of intro narrative that frames the opportunity (e.g. "This analysis identifies $[B+C+D] in operational opportunity..."). Output markdown starting with ## 3. Opportunity Waterfall, then your intro only. Do not output a table.""" + _SUMMARY_SUFFIX

SECTION_4_ELEMENTS_PROMPT = """You are writing Section E narrative only. Sections A/B/C/D are PIPELINE-INJECTED — do NOT reproduce or modify them.

Your job (~400 tokens max). Output markdown starting with ### E. Rate Gap — vs. State Average:
- State that E is directional insight, NOT quantified opportunity.
- Add per diem comparability flags for H0040, S9485 if relevant.
- Add concentration note if any code > 25% of E total.
- Close with: "Mobius Rate Benchmarking can identify the specific codes and contracts where renegotiation would have the highest return. The E total should not be added to B+C+D for near-term revenue planning until the methodology is verified."

The E rate gap table is injected separately. Do NOT create A/B/C/D/E tables.""" + _SUMMARY_SUFFIX

# ---------------------------------------------------------------------------
# Waterfall Validator Prompt — v3 (post-DLC rubric + data integrity audit)
# ---------------------------------------------------------------------------
WATERFALL_VALIDATOR_PROMPT = """You are a tick-and-tie validator for a waterfall credentialing report.
Your job is to verify numerical accuracy, internal consistency, data quality,
and appropriate caution in language. A CFO and a credentialing director will
read this report. Errors that slip through damage trust permanently.

**Status meanings:**
- **BLOCK**: Composer CANNOT fix. Do not deliver. (Truncation, cross-section NPI contradictions.)
- **COMPOSE_FIX**: Composer CAN fix from validation report. Run composer with these corrections.
- **WARN**: Minor; report can go out; note for reviewer.

VALIDATION CHECKS:

1. **NPI traceability** — Every NPI in the report must appear in step6 or step7 CSVs.

2. **Waterfall math** — B+C+D = operational total. E is informational; allow ±$1 rounding.
   Check each level against opportunity_sizing data.

3. **Section table totals and count×amount consistency** — Sum provider amounts in
   each section. Compare to section total. If mismatch: COMPOSE_FIX (never BLOCK).
   **Count×amount check**: For B, C, D (and A when amounts are uniform): if the
   waterfall states "N providers" and "section total $X," and every table row
   shows the same per-provider amount $Y, then N × Y must equal X (allow ±$1).
   Example: 41 providers, $46,522 total, but 41 × $46,522 = $1,907,402 — FAIL.
   The total equals 1 × $46,522; either the count is wrong or the total is wrong.
   If amounts are labeled "benchmark avg ($X/yr for this taxonomy)" and all X
   values are identical across different taxonomies: FAIL check 15 (uniform benchmark).

4. **Section A completeness** — Sum of Section A provider amounts vs stated A total.
   If they differ by more than $1,000: COMPOSE_FIX (never BLOCK). Composer can correct from context.
   "Section A table sums to $[X] but stated A total is $[Y]. Use COMPOSE_FIX."

5. **Section E rate table math** — If Section E contains a rate gap table:
   a. Gap/claim should equal state_avg − DLC_avg (signed correctly).
   b. **Row math**: total_gap MUST equal gap_per_claim × volume (allow ±$1).
   c. Sum of visible rows vs E total. If visible rows cover less than 50% of E: FAIL.
   **If Section E uses the disclaimer format** ("No rate gap analysis available for this run —
   HCPCS-level state benchmarks could not be computed", "0 codes shown", "do not add to
   operational total"): PASS. That is the correct format when benchmarks are unavailable.

6. **Chart vs text (reconciliation)** — Every waterfall bar label must match the
   canonical WATERFALL TOTALS above within rounding. Compare: A=guaranteed,
   B=at_risk, C=missing, D=taxonomy_opt, E=rate_gap. If the report or any chart
   caption shows C=$993.8K but canonical C=$883,392: FAIL. "Chart bar or report
   shows stale C=$[X]; canonical C=$[Y]. Regenerate chart from current totals."
   Do not deliver reports where chart values diverge from section totals.

7. **Uniform benchmark** — If all providers in Section A (or B or C) show the
   same dollar amount regardless of taxonomy:
   FAIL: "All [N] providers show identical amounts ($[X]). This is an org-level
   average, not a taxonomy-differentiated rate. The label 'benchmark avg ($X/yr
   for this taxonomy)' is factually incorrect if the same value appears for
   Clinical Social Worker, Psychiatrist, and Case Manager. Either apply
   taxonomy-specific rates or relabel as 'org benchmark avg.'"

8. **Confidence label accuracy** — "High-confidence" is only valid for Perfect
   or Good band providers. Medium-confidence providers must not be called "high-confidence."

9. **Cross-section NPI check** — BLOCK if any provider appears in:
   a. Section C (not enrolled) AND Section A (currently valid) — contradiction.
   b. Section D "not yet enrolled" AND Section A — contradiction.
   c. Section C AND Section D "enrolled" sub-table — contradiction.
   "BLOCK — [Provider] appears in [Section X] as [status] and [Section Y] as
   [contradictory status]. Resolve at source; do not compose."

10. **Raw taxonomy codes in service type column** — Flag any cell containing
    raw taxonomy codes (e.g., "363LP2300X") instead of plain-English labels.

11. **"To be defined" or placeholder text** — Flag any instance.

12. **Org NPI in provider tables** — If org NPIs (e.g., "DAVID LAWRENCE MENTAL
    HEALTH CENTER INC") appear in Section C alongside individual providers,
    flag: "Org NPIs require a different enrollment workflow than individual
    providers. Separate into a sub-section or add a workflow distinction note."

13. **"$0 unlock" or zero-value opportunity claims** — Flag any callout, table
    row, or statement claiming a finding "could unlock $0."
    "WARN — '$0 unlock' language should be removed or replaced with an
    explanation (e.g., 'no current billing volume under this taxonomy, so
    near-term revenue impact is not estimable')."

14. **Per diem comparability flag** — For any HCPCS code whose description
    contains "per diem" (commonly H0040, S9485, T1019, H0017, H0018):
    Verify that a comparability warning is present in Section E for that code.
    If not: WARN: "[Code] is a per diem code. The rate gap comparison may not
    be valid if the state average includes billers using a fee-for-service model.
    Add comparability flag per drafter instructions."
    Additionally: calculate what percentage of E total comes from per diem codes.
    If per diem codes account for more than 30% of E total:
    FAIL: "Per diem codes account for [X]% of the E total. Given the comparability
    concerns, E total should be presented as 'estimated, pending per diem
    methodology verification' rather than as a precise figure."

15. **Benchmark state average consistency** — If a prior run's Section E data
    is available for comparison, check whether any state average changed by
    more than 20% between runs for the same HCPCS code.
    FAIL: "[Code] state average changed from $[prior] to $[current] — a [X]%
    change. State Medicaid averages do not change this rapidly. One of these
    values is likely incorrect. Verify source before publication."

16. **Section E concentration risk** — If any single code accounts for more
    than 25% of E total, verify that a concentration note is present in Section E.
    If not: WARN: "[Code] accounts for $[X] ([Y]%) of E total. Add concentration
    note per drafter instructions."

17. **Operational total (E excluded)** — Verify B+C+D is the actionable total; E is
    directional only. If E is added to the opportunity total: COMPOSE_FIX. "Section E
    is not a quantified opportunity; do not add to B+C+D."

18. **HCPCS format in Section E** — The first column of the Section E rate table
    must contain HCPCS billing codes only. Valid format: starts with H, T, S, G,
    0–9, A, B, C, D, E, J, K, L, M, P, Q, R, V, or is a 5-digit CPT code.
    FAIL: Any row whose identifier matches NUCC taxonomy format (e.g. 323P00000X,
    261QM0801X — pattern: digits + letter + digits + optional letter X).
    "323P00000X is a NUCC taxonomy code, not a HCPCS billing code. Taxonomy
    codes describe provider type; they are not billed. Section E requires HCPCS
    codes (e.g. H0040, T1017, S9485). Remove or replace with the correct
    billing code for this service."

19. **Section B/C/D table row count vs waterfall count** — The number of rows in
    the Section B provider table must equal the waterfall "B providers" count
    (or be explicitly reconciled, e.g. "showing N of M"). Same for C and D.
    If waterfall says "C = 4 providers" but the C table has 3 rows: FAIL.
    "Waterfall C states 4 providers; Section C table has 3 rows. Reconcile
    count or correct the waterfall. If Weiner is enrolled (Section A), remove
    from C count."

20. **Section E completeness — no truncation** — Section E must be complete.
    a. If document ends mid-sentence or Section E is cut off: BLOCK.
    b. If waterfall E > $0 and Section E has **neither** a rate gap table **nor** the
       standard disclaimer ("No rate gap analysis available", "HCPCS-level benchmarks
       could not be computed", "0 codes shown", "do not add to operational total"):
       COMPOSE_FIX. When the disclaimer IS present, that is correct — PASS.

21. **Section D vs waterfall D consistency** — If Section D body says "No providers listed
    at this time" (or equivalent) and contains no dollar-sourced rows and no org NPI dollar
    figure, then waterfall D MUST equal $0. A waterfall D > $0 with an empty Section D body
    is a ghost number — the operational total (B+C+D) is overstated.
    FAIL: "Section D body shows no providers and no dollar amounts, but waterfall D = $[X].
    Either populate Section D with the source of the amount (e.g. org NPI estimate) or set
    D = $0 in the waterfall."

22. **Placeholder provider names** — BLOCK if any provider in Sections A/B/C/D (provider tables)
    matches: SMITH (any), DOE, "Test User", "Example Provider", "Placeholder Provider", "Generic Taxonomy",
    "UNIDENTIFIED PROVIDER", N/A, (Example) in column headers,
    "Optimal Taxonomy (Example)", or any provider name/cell containing placeholder, generic, template,
    example, test, or sample. One regex/catch-all: flag any table cell with these substrings.
    FAIL: "Report contains placeholder names or template language. Replace with real provider data."

23. **Literal format strings ($X,XXX.XX)** — BLOCK if any table cell contains unfilled template placeholders
    like $X,XXX.XX, $x,xxx.xx (capital X format strings). The total may be correct but line items must show
    actual dollar amounts. FAIL: "Report contains $X,XXX.XX in row cells. Replace with actual amounts."

24. **Taxonomy change from prior run** — If prior_run_npi_taxonomy is provided in context,
    flag any provider whose taxonomy in this run differs from the prior run (e.g. Psychiatrist
    → Behavior Analyst). These are materially different provider types (different billing
    codes, reimbursement rates, credentialing). WARN for human review: "[Provider] taxonomy
    changed from [prior] to [current]. Verify NPPES/pipeline before delivery."

**BLOCK vs COMPOSE_FIX** — Use BLOCK only for unfixable structural issues:
- **BLOCK**: Truncation; cross-section NPI contradiction (provider in A and C, or D and A);
  placeholder names or cells containing placeholder/generic/template/example/test/sample;
  literal $X,XXX.XX format strings in row cells.
- **COMPOSE_FIX**: Section A/B/C row count or sum mismatches, waterfall math,
  count×amount, Section E disclaimer, uniform benchmark, Section D ghost number,
  HCPCS/taxonomy mix-ups, labels. The composer has canonical data and can fix these.

Section A/B/C completeness (row count or sum vs stated total) → **COMPOSE_FIX**, never BLOCK.
Else if any WARN, use WARNINGS. Else PASS.

OUTPUT FORMAT:

VALIDATION REPORT
-----------------
Validation Status: PASS / WARNINGS / COMPOSE_FIX / BLOCK

[For each check, one line: CHECK N: PASS / WARN / COMPOSE_FIX / BLOCK — [detail]]

Detected Issues (BLOCK or COMPOSE_FIX items only, numbered):
1. ...

Warnings (WARN items, numbered):
1. ...

Suggested Corrections (one per issue, specific):
1. ...

Do NOT rewrite the report. Flag only."""

# ---------------------------------------------------------------------------
# Waterfall Composer Prompt — v3 (post-DLC rubric + data integrity audit)
# ---------------------------------------------------------------------------
WATERFALL_COMPOSER_PROMPT = """You are the Final Composer for a waterfall credentialing report.
Produce the definitive buyer-ready report incorporating all validation and critique
corrections. Output complete final report in markdown only. No preamble.

**Provider tables JSON (validation block)** — At the very end of the report, add this line:
<!-- PROVIDER_TABLES_JSON: {"section_a":[{"provider_name":"..."}],"section_b":[...],"section_c":[...],"section_d":[...]} -->
Replace the arrays with every provider name from your Section A, B, C, and D tables. Use the exact names as shown in the tables. section_d may be empty [] if no providers. This block enables validation; it will be stripped before delivery.

MANDATORY FIXES — apply all of these regardless of whether the critique flagged them.

**Numerical accuracy**
- Fix every numeric discrepancy from the validator.
- Ensure A, B, C, D, E, and Total match opportunity_sizing data exactly.
- **Count×amount consistency**: If validator flags that B (or C/D) provider count
  × per-provider amount ≠ section total, correct the count or total. Remove any
  provider from C count who appears in Section A (enrolled). Recalc B+C+D and
  B+C+D+E.
- **Section E row math**: If validator flags total_gap ≠ gap_per_claim × volume
  for any row, remove the row or correct the numbers. Do not leave broken math.
- If Section E contains a taxonomy code (e.g. 323P00000X) instead of HCPCS:
  remove that row. If E becomes empty, replace Section E with: "No rate gap
  analysis available — rate comparison data did not contain valid HCPCS billing
  codes." Set E = $0, recalc Total = B+C+D.
- **If Section 4.E is missing the rate table** (validator COMPOSE_FIX / Section E completeness):
  ADD a complete Section E (### E. Rate Gap) with this disclaimer. Keep E amount in waterfall:
  "No rate gap analysis available for this run — HCPCS-level state benchmarks could not be computed. The E total is from methodology (taxonomy-level org vs state comparison); treat as directional. Mobius Rate Benchmarking can provide HCPCS-level analysis once benchmarks are materialized."
  Do NOT set E = $0 — retain the E amount and add the disclaimer.
- If Section E table rows cover less than 50% of E total, reframe E in the
  waterfall summary as: "$[E] estimated — [N] codes shown, full analysis pending"
  rather than as a precise confirmed figure.

**Mandatory structure — do NOT change**
- Section 3 waterfall table Status/Confidence column: use exactly — B=High — fix now, C=High — enroll now, D=Medium — verify, E=Directional Insight. Never revert to generic High/Medium/Low.
- Section 2: Include readiness score and ALL locations. Do not drop locations.
- Sections A and C: Use Individual Providers / Organizational Enrollments (A) and Individual Provider Enrollment Gaps / Organizational Enrollment Gaps (C) sub-tables when provided in canonical tables.

**Operational / investigative split — MANDATORY**
Present two totals in the waterfall summary and exec summary:
- Operational opportunity: $[B+C+D] only — actionable now
- Section E: directional insight; do NOT add to opportunity total
Never present B+C+D+E as the "total opportunity." E has DOGE limitations.

**Placeholder / template replacement — MANDATORY**
- Replace "Placeholder Provider", "Generic Taxonomy", or any provider name/cell containing
  placeholder, generic, template, example, test, or sample with real provider data from
  opportunity_sizing_detail / step outputs. Do not deliver with template language.
- Replace any $X,XXX.XX or unfilled dollar format strings in table cells with actual
  amounts from taxonomy_opt breakdown or context. Line items must show real numbers.

**Language standards**
- Replace "guaranteed revenue" → "projected revenue at current run rate"
- Replace "high-confidence exposure" → "medium-confidence exposure" for
  medium/low band providers
- Replace "To be defined upon further research" with taxonomy code + plain label
- Replace raw taxonomy codes in service type columns with plain-English labels
- Replace "$0 unlock" → remove the entry entirely, or replace with:
  "No current billing volume — revenue impact not estimable at this time"

**Benchmark labeling — MANDATORY**
- If all providers in Section A show the same dollar amount regardless of taxonomy:
  REMOVE the label "benchmark avg ($X/yr for this taxonomy)" — this claim is false
  if the same number appears for a Psychiatrist and a Case Manager.
  REPLACE WITH: "org benchmark avg ($X/yr)" with table footnote:
  "Amounts reflect an organizational billing average. Individual rates vary by
  taxonomy, service volume, and payer mix. Taxonomy-level benchmarks were not
  available for this run."
- If taxonomy-differentiated rates ARE available: apply them per taxonomy.
  A psychiatrist's projected value must differ from a clinical social worker's.

**Per diem code treatment — MANDATORY**
For any HCPCS code in Section E whose description includes "per diem":
Replace any plain rate gap statement with this structure:
> ⚠️ **[Code] — Comparability flag**: This code is billed as a per diem bundled
> service. The state average may include billers using a fee-for-service model,
> making direct rate comparison unreliable. **This gap is not confirmed as a
> rate negotiation opportunity.** Include in rate analysis only after verifying
> the comparison methodology.

If per diem codes account for >30% of E total, add to the E section opening:
"Note: A significant portion of the estimated rate gap ([X]%) is attributable
to per diem codes where rate comparability has not been verified. The confirmed
rate gap — excluding per diem codes pending review — is approximately $[E minus
per diem codes]. The full $[E] figure should not be used for near-term revenue
planning until the per diem methodology is confirmed."

**Section E concentration**
If any code accounts for >25% of E total, add concentration note per drafter
prompt instructions.

**Section A completeness**
If Section A table does not show all providers (sum of rows ≠ A total):
Add above the table: "Showing [N shown] of [N total] providers. Full provider
list available in appendix. Total projected run rate: $[A]."

**Section D integrity**
- If Section D body says "No providers listed" (or equivalent) with no dollar amounts and
  waterfall D > $0: set D = $0 in the waterfall, recalc B+C+D and Total. Do not deliver
  a ghost number — the operational total must match the section content.
- Move any org NPI finding to a callout box.
- Split provider table into enrolled and not-yet-enrolled sub-tables.
- Before assigning any provider to the "not yet enrolled" sub-table, verify they
  do not appear in Section A. If they appear in Section A, they are enrolled —
  move them to the enrolled sub-table or remove from D if no taxonomy gap applies.
- If org NPIs appear in Section C alongside individual providers, separate them
  into a clearly labeled sub-section with a different workflow note.

**Section ordering**
Exec Summary: C → B → D → E. Show operational (B+C+D) total before E is added.

**Ghost billing**: Zero → positive framing as billing integrity indicator.

**Patient access stakes**: For any underserved location, add one sentence naming
both the revenue and the patient access implication of the credentialing gap.

**Confidence tier table**: Ensure it appears in Section 1 before any provider data.

OUTPUT: Complete final report in markdown only. Start directly with ## Executive Summary."""


class TickAndTieError(Exception):
    """Raised when opportunity_sizing detail does not tick-and-tie with waterfall totals."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _build_section_e_rate_gap_table(
    historic_billing_csv: str,
    hcpcs_state_benchmarks_csv: str,
) -> tuple[list[dict[str, Any]], str]:
    """
    Build Section E rate gap table: HCPCS | Description | DLC avg | FL state avg | Gap/claim | Volume | Total gap.
    Uses historic_billing (org) + hcpcs_state_benchmarks (FL state). Only includes rows with positive gap.
    Returns (rows, markdown_table).
    """
    from app.step_output_validation import _is_valid_hcpcs

    state_by_code: dict[str, float] = {}
    if hcpcs_state_benchmarks_csv and "(no benchmarks)" not in hcpcs_state_benchmarks_csv:
        try:
            reader = csv.DictReader(io.StringIO(hcpcs_state_benchmarks_csv))
            for r in reader:
                code = str(r.get("hcpcs_code") or "").strip()
                try:
                    rpc = float(r.get("revenue_per_claim") or 0)
                except (ValueError, TypeError):
                    rpc = 0.0
                if code:
                    state_by_code[code] = rpc
        except Exception as e:
            logger.warning("Could not parse hcpcs_state_benchmarks: %s", e)

    historic_rows: list[dict[str, Any]] = []
    if historic_billing_csv:
        try:
            reader = csv.DictReader(io.StringIO(historic_billing_csv))
            historic_rows = list(reader)
        except Exception as e:
            logger.warning("Could not parse historic_billing: %s", e)

    rows: list[dict[str, Any]] = []
    for r in historic_rows or []:
        code = str(r.get("hcpcs_code") or "").strip()
        if not _is_valid_hcpcs(code):
            continue
        state_avg = state_by_code.get(code)
        if state_avg is None or state_avg <= 0:
            continue
        try:
            volume = int(r.get("claim_count") or 0)
            total_paid = float(r.get("total_paid") or 0)
        except (ValueError, TypeError):
            continue
        if volume <= 0:
            continue
        dlc_avg = total_paid / volume
        gap_per_claim = state_avg - dlc_avg
        if gap_per_claim <= 0:
            continue
        total_gap = round(gap_per_claim * volume, 2)
        desc = str(r.get("description") or "")[:80]
        rows.append({
            "hcpcs_code": code,
            "description": desc,
            "dlc_avg_rate": round(dlc_avg, 2),
            "fl_state_avg": round(state_avg, 2),
            "gap_per_claim": round(gap_per_claim, 2),
            "volume": volume,
            "total_gap": total_gap,
        })

    if not rows:
        return [], ""

    # Sort by total_gap descending
    rows = sorted(rows, key=lambda x: -x["total_gap"])

    lines = [
        "| HCPCS | Description | DLC avg rate | FL state avg | Gap/claim | DLC volume | Total gap |",
        "|-------|-------------|--------------|--------------|-----------|------------|-----------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['hcpcs_code']} | {(r['description'] or '')[:50]} | ${r['dlc_avg_rate']:,.2f} | "
            f"${r['fl_state_avg']:,.2f} | ${r['gap_per_claim']:,.2f} | {r['volume']} | ${r['total_gap']:,.2f} |"
        )
    md = "\n".join(lines)
    return rows, md


def build_report_context(step_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build report context from step_outputs.
    Runs deterministic tick-and-tie: opportunity_sizing_detail is source of truth.
    Provider counts and section totals are derived from detail; waterfall totals must match.

    Args:
        step_outputs: List of {step_id, label, csv_content, row_count}.

    Returns:
        Dict with waterfall_totals, provider_counts, tick_and_tie_section_sources, etc.

    Raises:
        TickAndTieError: If detail sums/counts do not match opportunity_sizing totals.
    """
    csv_contents: dict[str, str] = {}
    waterfall_totals: dict[str, float] = {
        "guaranteed": 0.0,
        "at_risk": 0.0,
        "missing": 0.0,
        "taxonomy_opt": 0.0,
        "rate_gap": 0.0,
        "total_opportunity": 0.0,
    }
    provider_counts: dict[str, int] = {}
    tick_and_tie_section_sources: dict[str, Any] = {}  # canonical rows for drafter

    for item in step_outputs or []:
        step_id = (item.get("step_id") or "").strip()
        csv_content = item.get("csv_content") or ""
        if step_id:
            csv_contents[step_id] = csv_content

        # Parse opportunity_sizing for waterfall totals (D, E, Total) and initial provider counts
        if step_id == "opportunity_sizing" and csv_content and "(failed)" not in csv_content:
            try:
                reader = csv.DictReader(io.StringIO(csv_content))
                for row in reader:
                    level = (row.get("level") or "").strip().upper()
                    try:
                        amt = float(row.get("amount") or 0)
                    except (ValueError, TypeError):
                        amt = 0
                    try:
                        pc = row.get("provider_count")
                        cnt = int(pc) if pc not in (None, "") else None
                    except (ValueError, TypeError):
                        cnt = None
                    if level == "A":
                        waterfall_totals["guaranteed"] = amt
                        if cnt is not None:
                            provider_counts["A"] = cnt
                    elif level == "B":
                        waterfall_totals["at_risk"] = amt
                        if cnt is not None:
                            provider_counts["B"] = cnt
                    elif level == "C":
                        waterfall_totals["missing"] = amt
                        if cnt is not None:
                            provider_counts["C"] = cnt
                    elif level == "D":
                        waterfall_totals["taxonomy_opt"] = amt
                    elif level == "E":
                        waterfall_totals["rate_gap"] = amt
                    elif level == "TOTAL" or level == "Total":
                        waterfall_totals["total_opportunity"] = amt
            except Exception as e:
                logger.warning("Could not parse opportunity_sizing CSV: %s", e)

    # Parse opportunity_sizing_detail and run deterministic tick-and-tie
    detail_csv = (
        csv_contents.get("opportunity_sizing_detail") or csv_contents.get("step10_opportunity_sizing_detail") or ""
    ).strip()
    if detail_csv and "(no detail)" not in detail_csv:
        try:
            reader = csv.DictReader(io.StringIO(detail_csv))
            npi_detail = list(reader)
        except Exception as e:
            raise TickAndTieError([f"Could not parse opportunity_sizing_detail CSV: {e}"]) from e

        valid_rows = [r for r in npi_detail if (r.get("bucket") or "").strip().lower() == "valid"]
        flagged_rows = [r for r in npi_detail if (r.get("bucket") or "").strip().lower() == "flagged"]
        missing_rows = [r for r in npi_detail if (r.get("bucket") or "").strip().lower() == "missing"]

        def _sum_base_revenue(rows: list[dict]) -> float:
            total = 0.0
            for r in rows:
                try:
                    total += float(r.get("base_revenue") or 0)
                except (ValueError, TypeError):
                    pass
            return round(total, 2)

        a_sum = _sum_base_revenue(valid_rows)
        b_sum = _sum_base_revenue(flagged_rows)
        c_sum = _sum_base_revenue(missing_rows)
        a_count = len(valid_rows)
        b_count = len(flagged_rows)
        c_count = len(missing_rows)

        tick_errors: list[str] = []
        tol = 1.0
        if abs(a_sum - waterfall_totals["guaranteed"]) > tol:
            tick_errors.append(
                f"Section A tick-and-tie FAIL: sum(valid base_revenue)={a_sum:,.2f}, "
                f"opportunity_sizing guaranteed={waterfall_totals['guaranteed']:,.2f}. "
                "Detail is source of truth; totals must match."
            )
        if abs(b_sum - waterfall_totals["at_risk"]) > tol:
            tick_errors.append(
                f"Section B tick-and-tie FAIL: sum(flagged base_revenue)={b_sum:,.2f}, "
                f"opportunity_sizing at_risk={waterfall_totals['at_risk']:,.2f}."
            )
        if abs(c_sum - waterfall_totals["missing"]) > tol:
            tick_errors.append(
                f"Section C tick-and-tie FAIL: sum(missing base_revenue)={c_sum:,.2f}, "
                f"opportunity_sizing missing={waterfall_totals['missing']:,.2f}."
            )

        if tick_errors:
            raise TickAndTieError(tick_errors)

        # Use detail-derived counts and sums as source of truth (overrides level row if different)
        provider_counts["A"] = a_count
        provider_counts["B"] = b_count
        provider_counts["C"] = c_count
        waterfall_totals["guaranteed"] = a_sum
        waterfall_totals["at_risk"] = b_sum
        waterfall_totals["missing"] = c_sum
        waterfall_totals["total_opportunity"] = round(
            b_sum + c_sum + float(waterfall_totals.get("taxonomy_opt") or 0) + float(waterfall_totals.get("rate_gap") or 0),
            2,
        )

        # Build canonical section sources for drafter — exact per-NPI amounts to use
        def _row(npi: str, name: str, base_revenue: float, taxonomy: str, zip5: str = "", **kw: Any) -> dict[str, Any]:
            return {"npi": npi, "provider_name": name, "base_revenue": round(float(base_revenue or 0), 2), "taxonomy_code": taxonomy, "zip5": zip5, **kw}

        labels = TAXONOMY_CODE_LABELS or {}

        def _parse_opt_detail(detail: str) -> tuple[str, str]:
            """Parse taxonomy_opt_detail for best_taxonomy and current. Returns (best_label, current_label)."""
            best_code = current_code = ""
            for part in (detail or "").split(";"):
                k, _, v = part.partition("=")
                if k == "best_taxonomy":
                    best_code = (v or "").strip()
                elif k == "current":
                    current_code = (v or "").strip()
            return (labels.get(best_code, best_code) if best_code else "", labels.get(current_code, current_code) if current_code else "")

        a_rows = [
            _row(r.get("npi"), r.get("provider_name"), r.get("base_revenue"), r.get("taxonomy_code"), r.get("zip5", ""))
            for r in valid_rows
        ]
        b_rows = [
            _row(r.get("npi"), r.get("provider_name"), r.get("base_revenue"), r.get("taxonomy_code"), r.get("zip5", ""))
            for r in flagged_rows
        ]
        # Dedup C by NPI (org NPI can appear multiple times across taxonomy/location)
        _by_npi: dict[str, dict[str, Any]] = {}
        for r in missing_rows:
            npi = str(r.get("npi") or "").strip().zfill(10)
            rev = float(r.get("base_revenue") or 0)
            if npi not in _by_npi:
                _by_npi[npi] = _row(r.get("npi"), r.get("provider_name"), 0, r.get("taxonomy_code"), r.get("zip5", ""))
            _by_npi[npi]["base_revenue"] = round(_by_npi[npi]["base_revenue"] + rev, 2)
        c_rows = list(_by_npi.values())
        c_count = len(c_rows)
        provider_counts["C"] = c_count
        # Pipeline validation: no blank provider_name — fail before LLM
        for rows, label in ((a_rows, "A"), (b_rows, "B"), (c_rows, "C")):
            blank = [r for r in rows if not (r.get("provider_name") or "").strip()]
            if blank:
                raise TickAndTieError([f"Pipeline FAIL: Section {label} has {len(blank)} row(s) with blank provider_name. Fix data before report generation."])

        # D rows: taxonomy optimization (taxonomy_opt_uplift > 0)
        d_amt = float(waterfall_totals.get("taxonomy_opt") or 0)
        d_rows: list[dict[str, Any]] = []
        for r in npi_detail:
            try:
                uplift = float(r.get("taxonomy_opt_uplift") or 0)
            except (ValueError, TypeError):
                uplift = 0
            if uplift < 0.01:
                continue
            name = (r.get("provider_name") or "").strip()
            if not name:
                raise TickAndTieError(["Pipeline FAIL: Section D row has blank provider_name. Fix data before report generation."])
            best_lab, cur_lab = _parse_opt_detail(r.get("taxonomy_opt_detail") or "")
            if not best_lab:
                best_lab = (r.get("taxonomy_opt_detail") or "").split("best_taxonomy=", 1)[-1].split(";")[0] or "—"
            if not cur_lab:
                cur_lab = labels.get(r.get("taxonomy_code", ""), r.get("taxonomy_code", "—"))
            d_rows.append({"provider_name": name, "current_taxonomy": cur_lab, "optimal_taxonomy": best_lab, "uplift": uplift})

        # Section D: table from pipeline or "No findings" if empty
        if d_amt < 0.01 or len(d_rows) < 1:
            canonical_section_d_table = "*No taxonomy optimization findings available for this run.*"
        else:
            canonical_section_d_table = _format_canonical_section_table(
                d_rows,
                [("provider_name", "Provider", "str"), ("current_taxonomy", "Current Taxonomy", "str"), ("optimal_taxonomy", "Optimal Taxonomy", "str"), ("uplift", "Projected Uplift", "num")],
            )

        def _service_type(row: dict) -> str:
            code = (row.get("taxonomy_code") or "").strip()
            return labels.get(code, code) if code else ""

        a_rows_with_svc = [{"provider_name": r.get("provider_name"), "service_type": _service_type(r), "base_revenue": r.get("base_revenue")} for r in a_rows]
        # Parse org NPIs from identify_org for Individual vs Organizational split
        org_npis: set[str] = set()
        id_org_csv = (csv_contents.get("identify_org") or "").strip()
        if id_org_csv:
            try:
                for r in csv.DictReader(io.StringIO(id_org_csv)):
                    npi = (r.get("npi") or "").strip()
                    if npi:
                        org_npis.add(str(npi).zfill(10))
            except Exception as e:
                logger.warning("Could not parse identify_org CSV: %s", e)
        # Split A/C into Individual vs Organizational (MANDATORY structure)
        def _split_by_org(rrows: list[dict], oset: set[str]) -> tuple[list[dict], list[dict]]:
            i, o = [], []
            for r in rrows:
                npi = str(r.get("npi") or "").strip().zfill(10)
                (o if npi in oset else i).append(r)
            return i, o
        a_indiv, a_org = _split_by_org(a_rows, org_npis) if org_npis else (a_rows, [])
        c_indiv, c_org = _split_by_org(c_rows, org_npis) if org_npis else (c_rows, [])

        def _fmt_subtable(rows: list[dict], cols: list[tuple[str, str, str]], subheader: str) -> str:
            if not rows:
                return ""
            tbl = _format_canonical_section_table(rows, cols)
            return f"**{subheader}**\n\n{tbl}\n" if tbl else ""

        a_rows_indiv_svc = [{"provider_name": r.get("provider_name"), "service_type": _service_type(r), "base_revenue": r.get("base_revenue")} for r in a_indiv]
        a_rows_org_svc = [{"provider_name": r.get("provider_name"), "service_type": _service_type(r), "base_revenue": r.get("base_revenue")} for r in a_org]
        a_table_indiv = _fmt_subtable(a_rows_indiv_svc, [("provider_name", "Provider", "str"), ("service_type", "Service Type", "str"), ("base_revenue", "Projected Revenue", "num")], "Individual Providers")
        a_table_org = _fmt_subtable(a_rows_org_svc, [("provider_name", "Provider", "str"), ("service_type", "Service Type", "str"), ("base_revenue", "Projected Revenue", "num")], "Organizational Enrollments")
        c_table_indiv = _fmt_subtable(c_indiv, [("provider_name", "Provider", "str"), ("base_revenue", "Enrollment Gap Amount", "num")], "Individual Provider Enrollment Gaps")
        c_table_org = _fmt_subtable(c_org, [("provider_name", "Provider", "str"), ("base_revenue", "Enrollment Gap Amount", "num")], "Organizational Enrollment Gaps")
        a_combined = (a_table_indiv + "\n\n" + a_table_org).strip() if (a_table_indiv or a_table_org) else _format_canonical_section_table(a_rows_with_svc, [("provider_name", "Provider", "str"), ("service_type", "Service Type", "str"), ("base_revenue", "Projected Revenue", "num")])
        c_combined = (c_table_indiv + "\n\n" + c_table_org).strip() if (c_table_indiv or c_table_org) else _format_canonical_section_table(c_rows, [("provider_name", "Provider", "str"), ("base_revenue", "Enrollment Gap Amount", "num")])

        tick_and_tie_section_sources = {
            "A_rows": a_rows,
            "B_rows": b_rows,
            "C_rows": c_rows,
            "D_rows": d_rows,
            "A_sum": a_sum,
            "B_sum": b_sum,
            "C_sum": c_sum,
            "A_count": a_count,
            "B_count": b_count,
            "C_count": c_count,
            "D_count": len(d_rows),
            "canonical_section_a_table": a_combined,
            "canonical_section_b_table": _format_canonical_section_table(
                b_rows,
                [("provider_name", "Provider", "str"), ("zip5", "Current ZIP", "str"), ("base_revenue", "At-Risk Amount", "num")],
            ),
            "canonical_section_c_table": c_combined,
            "canonical_section_d_table": canonical_section_d_table,
        }

    # Parse locations from find_locations (MANDATORY — include all, no silent drops)
    locations_mandatory: list[dict[str, str]] = []
    loc_csv = (csv_contents.get("find_locations") or "").strip()
    if loc_csv:
        try:
            for row in csv.DictReader(io.StringIO(loc_csv)):
                addr = (row.get("site_address_line_1") or row.get("site_address") or "").strip()
                city = (row.get("site_city") or "").strip()
                state = (row.get("site_state") or "").strip()
                zip5 = (row.get("site_zip5") or row.get("site_zip") or "").strip()
                if addr or city:
                    locations_mandatory.append({
                        "address": addr, "city": city, "state": state, "zip5": zip5,
                        "full": f"{addr}, {city}, {state} {zip5}".strip(", "),
                    })
        except Exception as e:
            logger.warning("Could not parse find_locations CSV: %s", e)

    # Readiness score: 100 × A / (A+B+C) provider count. LOCKED — provider-count-based, not revenue/combo-based.
    a_cnt = provider_counts.get("A") or 0
    b_cnt = provider_counts.get("B") or 0
    c_cnt = provider_counts.get("C") or 0
    total_abc = a_cnt + b_cnt + c_cnt
    readiness_score = round(100.0 * a_cnt / total_abc, 2) if total_abc else 0.0

    ahca_docs = _load_ahca_docs(max_chars=80000)
    methodology = (
        "Revenue Waterfall: A=Projected revenue at current run rate (valid PML combos), B=At-risk (flagged), "
        "C=Enrollment gap (missing PML, deduped by NPI), D=Taxonomy optimization, E=Org vs state rate gap. "
        "Uses taxonomy_utilization_benchmarks and org benchmark. Outside-in analysis; we do not have internal org records. "
        "Readiness score (locked): 100 × A provider count / (A+B+C provider count); provider-count-based, not revenue-based."
    )

    # Build Section E rate gap table when E > 0 (HCPCS-level: DLC avg vs FL state avg)
    section_e_rows: list[dict[str, Any]] = []
    section_e_md = ""
    if float(waterfall_totals.get("rate_gap") or 0) > 0.01:
        hb_csv = csv_contents.get("historic_billing_patterns") or ""
        hcpcs_csv = (
            csv_contents.get("hcpcs_state_benchmarks")
            or csv_contents.get("step5b_hcpcs_state_benchmarks")
            or ""
        )
        section_e_rows, section_e_md = _build_section_e_rate_gap_table(hb_csv, hcpcs_csv)

    # Mandatory computed fields — LLM fills numbers only, never omits or changes structure
    mandatory_computed = {
        "readiness_score": readiness_score,
        "readiness_score_vs_median": f"Readiness score: {readiness_score}% (FL BH median 68)",
        "location_count": len(locations_mandatory),
        "locations_full_list": [loc["full"] for loc in locations_mandatory],
        "confidence_tier_verbs": "B=High — fix now | C=High — enroll now | D=Medium — verify | E=Directional Insight",
    }

    return {
        "waterfall_totals": waterfall_totals,
        "provider_counts": provider_counts,
        "tick_and_tie_section_sources": tick_and_tie_section_sources,
        "csv_contents": csv_contents,
        "methodology": methodology,
        "fl_static_docs_ref": f"{AHCA_DOCS_REF}\n{AHCA_CONTEXT}",
        "ahca_docs": ahca_docs,
        "glossary": GLOSSARY,
        "methodology_full": METHODOLOGY,
        "doge_limitations": DOGE_LIMITATIONS,
        "sources": SOURCES,
        "taxonomy_labels": TAXONOMY_CODE_LABELS,
        "section_e_rate_gap_rows": section_e_rows,
        "section_e_rate_gap_table": section_e_md,
        "readiness_score": readiness_score,
        "locations_mandatory": locations_mandatory,
        "mandatory_computed_fields": mandatory_computed,
    }


def _extract_section_summary(text: str) -> tuple[str, str]:
    """Extract <!--SECTION_SUMMARY: ... --> from section output. Returns (content_without_summary, summary)."""
    import re
    match = re.search(r"<!--SECTION_SUMMARY:\s*(.+?)\s*-->", text, re.DOTALL)
    if match:
        summary = match.group(1).strip()
        content = text[: match.start()].rstrip() + text[match.end() :].lstrip()
        return content, summary
    return text, ""


# Section IDs for per-section draft generation
DRAFT_SECTIONS = ("exec_summary", "methodology", "about_org", "waterfall_summary", "elements")
SECTION_LABELS = {
    "exec_summary": "Executive Summary",
    "methodology": "Methodology",
    "about_org": "About the Organization",
    "waterfall_summary": "Opportunity Waterfall summary",
    "elements": "Section 4 Elements (D/E narrative)",
}


def _build_shared_context(context: dict[str, Any], org_name: str) -> str:
    """Shared context string for all section prompts."""
    wt = context.get("waterfall_totals") or {}
    csv_str = json.dumps(context.get("csv_contents") or {}, indent=2)
    mcf = context.get("mandatory_computed_fields") or {}
    section_e_block = ""
    if float(wt.get("rate_gap") or 0) > 0.01 and context.get("section_e_rate_gap_table"):
        section_e_block = f"""**SECTION E RATE GAP TABLE (pre-built, inject verbatim):**
{context.get("section_e_rate_gap_table")}"""
    elif float(wt.get("rate_gap") or 0) > 0.01:
        section_e_block = '''**SECTION E disclaimer (use when no rate gap table):**
"No rate gap analysis available for this run — HCPCS-level state benchmarks could not be computed. The E total is from methodology (taxonomy-level org vs state comparison); treat as directional. Mobius Rate Benchmarking can provide HCPCS-level analysis once benchmarks are materialized."'''
    mandatory_block = f"""
**MANDATORY COMPUTED FIELDS — use verbatim. Do NOT omit or change structure.**
- Readiness score: {mcf.get('readiness_score', 0)}% (FL BH median 68). State: "Readiness score: {mcf.get('readiness_score', 0)}%"
- Location count: {mcf.get('location_count', 0)}. Include ALL {mcf.get('location_count', 0)} locations — do not silently drop any.
- Locations (full list): {chr(10).join('- ' + a for a in (mcf.get('locations_full_list') or []))}
- Confidence tier (Section 3 waterfall): {mcf.get('confidence_tier_verbs', 'B=High — fix now | C=High — enroll now | D=Medium — verify | E=Directional Insight')}
"""
    return f"""Organization: {org_name}

{_format_exact_numbers_block(context)}
{mandatory_block}

Methodology: {context.get('methodology', '')}
Full methodology: {context.get('methodology_full', '')}
DOGE limitations (Section E): {context.get('doge_limitations', '')}
FL Medicaid NPI docs: {context.get('fl_static_docs_ref', '')}
Sources: {context.get('sources', '')}
AHCA docs (abbreviated): {str(context.get('ahca_docs', ''))[:15000]}
CSV contents: {csv_str}
Taxonomy labels: {json.dumps(context.get("taxonomy_labels") or {}, indent=2)}

{section_e_block}"""


def _generate_section(
    system_prompt: str,
    user_content: str,
    provider: str,
    model: str,
    max_tokens: int = 4096,
) -> str:
    """Call LLM for one section. Returns section markdown."""
    if provider == "openai":
        return _call_openai(system_prompt, user_content, model, max_output_tokens=max_tokens)
    if provider == "gemini":
        return _call_gemini(system_prompt, user_content, model, max_output_tokens=max_tokens)
    raise ValueError(f"Unknown provider: {provider}")


def _build_section_3_summary_table(context: dict[str, Any]) -> str:
    """Build Section 3 waterfall summary table deterministically. No LLM involvement."""
    wt = context.get("waterfall_totals") or {}
    pc = context.get("provider_counts") or {}
    a = float(wt.get("guaranteed") or 0)
    b = float(wt.get("at_risk") or 0)
    c = float(wt.get("missing") or 0)
    d = float(wt.get("taxonomy_opt") or 0)
    e = float(wt.get("rate_gap") or 0)
    total = float(wt.get("total_opportunity") or 0)
    op_total = b + c + d
    na = pc.get("A") or "—"
    nb = pc.get("B") or "—"
    nc = pc.get("C") or "—"
    return f"""| Level | Description | Amount | Providers | Status/Confidence |
|-------|-------------|--------|-----------|-------------------|
| A | Projected run rate | ${a:,.2f} | {na} | Enrolled + valid |
| B | At-risk (address gaps) | ${b:,.2f} | {nb} | High — fix now |
| C | Enrollment gap (PML) | ${c:,.2f} | {nc} | High — enroll now |
| D | Taxonomy optimization | ${d:,.2f} | — | Medium — verify |
| E | Rate gap (directional only) | ${e:,.2f} | — | Not quantified opportunity |
| B+C+D | Operational opportunity | ${op_total:,.2f} | — | Actionable total |
| Total | B+C+D | ${op_total:,.2f} | — | E excluded (directional insight only) |"""


def _build_section_2_hcpcs_table(context: dict[str, Any]) -> str:
    """Build top-10 HCPCS billing table deterministically from historic_billing. Returns empty string if no data."""
    csv_contents = context.get("csv_contents") or {}
    hb_csv = csv_contents.get("historic_billing_patterns") or ""
    if not hb_csv or "(failed)" in hb_csv:
        return ""
    try:
        reader = csv.DictReader(io.StringIO(hb_csv))
        rows = []
        for r in reader:
            try:
                claims = int(r.get("claim_count") or 0)
                total = float(r.get("total_paid") or 0)
                rate = total / claims if claims else 0
            except (ValueError, TypeError):
                continue
            code = (r.get("hcpcs_code") or "").strip()
            desc = (r.get("description") or "")[:60]
            if code:
                rows.append({"code": code, "description": desc, "claim_count": claims, "total_paid": total, "rate": rate})
        rows = sorted(rows, key=lambda x: -x["total_paid"])[:10]
    except Exception:
        return ""
    if not rows:
        return ""
    lines = ["| HCPCS | Description | Claims | Total paid | Avg rate/claim |", "|-------|-------------|--------|------------|----------------|"]
    for r in rows:
        lines.append(f"| {r['code']} | {r['description']} | {r['claim_count']:,} | ${r['total_paid']:,.2f} | ${r['rate']:,.2f} |")
    return "\n".join(lines)


def _build_section_4_deterministic(context: dict[str, Any]) -> str:
    """Build Section 4 deterministically: intro + canonical A/B/C/D tables (pipeline-owned, LLM must not change)."""
    tt = context.get("tick_and_tie_section_sources") or {}
    wt = context.get("waterfall_totals") or {}
    a_sum = tt.get("A_sum", 0)
    b_sum = tt.get("B_sum", 0)
    c_sum = tt.get("C_sum", 0)
    d_sum = float(wt.get("taxonomy_opt") or 0)
    a_count = tt.get("A_count", 0)
    b_count = tt.get("B_count", 0)
    c_count = tt.get("C_count", 0)
    d_count = tt.get("D_count", 0)
    d_table = (tt.get("canonical_section_d_table") or "").strip()
    if not d_table:
        d_table = "*No taxonomy optimization findings available for this run.*" if d_sum < 0.01 else "(no data)"
    parts = [
        "## 4. Elements of the Waterfall\n",
        "*Amounts reflect benchmark methodology — see Section 1 and the benchmark methodology note at the end of this section for details.*\n",
        f"### A. Projected Revenue at Current Run Rate\n\n**{a_count} providers | Total: ${a_sum:,.2f}**\n",
        (tt.get("canonical_section_a_table") or "(no data)").strip(),
        f"\n### B. At-Risk Revenue\n\n**{b_count} providers | Total: ${b_sum:,.2f}**\n",
        (tt.get("canonical_section_b_table") or "(no rows)").strip(),
        f"\n### C. Enrollment Gap — Missing PML\n\n**{c_count} providers | Total: ${c_sum:,.2f}**\n",
        (tt.get("canonical_section_c_table") or "(no rows)").strip(),
        f"\n### D. Taxonomy Optimization\n\n**{d_count} providers | Total: ${d_sum:,.2f}**\n",
        d_table,
        "\n*Directional. Verify with credentialing specialist.*",
    ]
    return "\n".join(parts)


def _generate_section_with_summary(
    prompt: str,
    user_content: str,
    provider: str,
    model: str,
    max_tokens: int = 2048,
) -> tuple[str, str]:
    """Generate one section and extract <!--SECTION_SUMMARY-->. Returns (content, summary)."""
    raw = _generate_section(prompt, user_content, provider, model, max_tokens=max_tokens)
    content, summary = _extract_section_summary(raw)
    return content, summary




def generate_waterfall_draft(
    context: dict[str, Any],
    org_name: str,
    *,
    provider: str = "openai",
    model: str | None = None,
    emitter: Callable[[str], None] | None = None,
) -> str:
    """Generate first-draft markdown via multi-section LLM calls (avoids truncation).
    If emitter is provided, emits 'Generating X…' before each section and a one-line summary after."""
    model = model or ("gpt-4o" if provider == "openai" else (os.getenv("VERTEX_MODEL") or os.getenv("CHAT_VERTEX_MODEL") or "gemini-2.5-flash"))
    shared = _build_shared_context(context, org_name)
    wt = context.get("waterfall_totals") or {}

    def _emit(msg: str) -> None:
        if emitter and msg and str(msg).strip():
            try:
                emitter(str(msg).strip())
            except Exception:
                pass

    # 1. Executive Summary
    _emit("Generating Executive Summary…")
    s1, sum1 = _generate_section_with_summary(SECTION_EXEC_SUMMARY_PROMPT, shared, provider, model, max_tokens=2048)
    if sum1:
        _emit(f"Executive Summary: {sum1}")
    # 2. Methodology
    _emit("Generating Methodology…")
    s2, sum2 = _generate_section_with_summary(SECTION_METHODOLOGY_PROMPT, shared, provider, model, max_tokens=2048)
    if sum2:
        _emit(f"Methodology: {sum2}")
    # 3. About the Organization — LLM narrative + deterministic HCPCS table
    _emit("Generating About the Organization…")
    s3_narrative, sum3 = _generate_section_with_summary(SECTION_ABOUT_ORG_PROMPT, shared, provider, model, max_tokens=2048)
    if sum3:
        _emit(f"About the Organization: {sum3}")
    hcpcs_table = _build_section_2_hcpcs_table(context)
    s3 = s3_narrative.strip() + ("\n\n**Top HCPCS billing (by total paid)**\n\n" + hcpcs_table if hcpcs_table else "")
    # 4. Opportunity Waterfall — LLM intro + deterministic summary table
    _emit("Generating Opportunity Waterfall summary…")
    s4_intro, sum4 = _generate_section_with_summary(SECTION_WATERFALL_SUMMARY_PROMPT, shared, provider, model, max_tokens=1024)
    if sum4:
        _emit(f"Waterfall summary: {sum4}")
    s4_summary = s4_intro.strip() + "\n\n" + _build_section_3_summary_table(context)
    # 5. Section 4 Elements — deterministic A/B/C + LLM for D/E narrative + inject E table
    _emit("Generating Section 4 Elements (D/E narrative)…")
    s4_base = _build_section_4_deterministic(context)
    s4_user = shared + "\n\n" + _format_canonical_tables_block(context)
    s4_narrative_raw, sum5 = _generate_section_with_summary(SECTION_4_ELEMENTS_PROMPT, s4_user, provider, model, max_tokens=2048)
    e_table_block = ""
    if float(wt.get("rate_gap") or 0) > 0.01:
        if context.get("section_e_rate_gap_table"):
            e_table_block = context.get("section_e_rate_gap_table", "") + "\n\n"
        else:
            e_table_block = '"No rate gap analysis available for this run — HCPCS-level state benchmarks could not be computed. The E total is from methodology (taxonomy-level org vs state comparison); treat as directional. Mobius Rate Benchmarking can provide HCPCS-level analysis once benchmarks are materialized."\n\n'
    if sum5:
        _emit(f"Section 4 Elements: {sum5}")
    e_header = "\n### E. Rate Gap — vs. State Average\n\n"
    e_content = s4_narrative_raw.strip()
    if "### E." in e_content:
        _, after = e_content.split("### E.", 1)
        idx = after.find("\n") + 1 if "\n" in after else len(after)
        e_content = after[idx:].strip()
    s4_narrative = e_header + e_table_block + (e_content + "\n" if e_content else "")
    s4_full = s4_base + "\n\n" + s4_narrative.strip()
    s4_full += '\n\n**Benchmark Methodology Note:**\n"Amounts in Sections A, B, and C reflect a benchmark average for each provider\'s taxonomy. Section E presents directional insights from DOGE paid-claims data—it is not a quantified opportunity. Significant DOGE limitations apply (paid-claims only, small-cell suppression, facility/MCO variance). Do not add E to the operational total. Per diem codes are flagged individually."\n'
    # 6. Section 5 Sources (include DOGE limitations for user visibility)
    s5 = f"\n## 5. Sources\n\n{context.get('sources', '')}\n\n{DOGE_LIMITATIONS.strip()}\n"

    title = f"# Provider Roster and Credentialing Report: {org_name}\n## Maximizing Revenue through Operational and Strategic Optimization\n\n**Date:** (current)\n**Prepared for:** CFO & Credentialing Operations Director, {org_name}\n\n---\n\n"
    return title + s1.strip() + "\n\n---\n\n" + s2.strip() + "\n\n---\n\n" + s3.strip() + "\n\n---\n\n" + s4_summary.strip() + "\n\n---\n\n" + s4_full + s5


def run_waterfall_validator(
    draft_md: str,
    context: dict[str, Any],
    *,
    provider: str = "openai",
    model: str | None = None,
) -> str:
    """Run validator. Returns validation_report text. Runs deterministic D/E checks first."""
    from app.step_output_validation import validate_report_structure_d_and_e

    wt = context.get("waterfall_totals") or {}
    structural_errors = validate_report_structure_d_and_e(draft_md, wt)
    if structural_errors:
        # Truncation, placeholder names, $X,XXX.XX = BLOCK (retry draft). Section E disclaimer, D ghost = COMPOSE_FIX.
        block_keywords = ("truncation", "placeholder", "literal format")
        is_block = any(
            kw in (e or "").lower() for e in structural_errors for kw in block_keywords
        )
        status = "BLOCK" if is_block else "COMPOSE_FIX"
        report = f"VALIDATION REPORT\n-----------------\nValidation Status: {status}\n\n"
        report += "Pre-validation (structural):\n"
        for i, err in enumerate(structural_errors, 1):
            report += f"{i}. {err}\n"
        report += "\n" + ("Do not compose — regenerate draft." if is_block else "Composer can apply these fixes.")
        return report

    model = model or ("gpt-4o" if provider == "openai" else (os.getenv("VERTEX_MODEL") or os.getenv("CHAT_VERTEX_MODEL") or "gemini-1.5-pro"))
    csv_str = json.dumps(context.get("csv_contents") or {}, indent=2)
    prior_tax = context.get("prior_run_npi_taxonomy") or {}
    prior_str = json.dumps(prior_tax, indent=2) if prior_tax else "Not provided."
    user = f"""DRAFT REPORT:
---
{draft_md}
---

WATERFALL TOTALS (reconciled source of truth — use these, not raw CSV):
- A: ${wt.get('guaranteed', 0):,.2f}
- B: ${wt.get('at_risk', 0):,.2f}
- C: ${wt.get('missing', 0):,.2f}
- D: ${wt.get('taxonomy_opt', 0):,.2f}
- E: ${wt.get('rate_gap', 0):,.2f}
- Total: ${wt.get('total_opportunity', 0):,.2f}

CSV CONTENTS (step6=step_6 or pml_validation, step7=step_7 or missing, step10_detail=opportunity_sizing_detail):
{csv_str}

PRIOR RUN NPI→TAXONOMY (for check 23 — taxonomy change detection; empty if none):
{prior_str}

Validate the draft. Output the validation report only."""

    if provider == "openai":
        return _call_openai(WATERFALL_VALIDATOR_PROMPT, user, model)
    if provider == "gemini":
        return _call_gemini(WATERFALL_VALIDATOR_PROMPT, user, model)
    raise ValueError(f"Unknown provider: {provider}")


def run_waterfall_composer(
    draft_md: str,
    validation_report: str,
    context: dict[str, Any],
    org_name: str,
    *,
    critique_report: str = "",
    additional_fixes: list[str] | None = None,
    provider: str = "openai",
    model: str | None = None,
) -> str:
    """Run composer to produce final markdown incorporating number validation + narrative critique."""
    model = model or ("gpt-4o" if provider == "openai" else (os.getenv("VERTEX_MODEL") or os.getenv("CHAT_VERTEX_MODEL") or "gemini-1.5-pro"))
    wt = context.get("waterfall_totals") or {}
    critique_section = ""
    if critique_report and critique_report.strip():
        critique_section = f"""

REPORT CRITIQUE (narrative / storyline — incorporate tone, clarity, risky language fixes):
---
{critique_report.strip()}
---

"""
    additional_section = ""
    if additional_fixes:
        fixes_str = "\n".join(f"- {f}" for f in additional_fixes)
        additional_section = f"""

ADDITIONAL DETERMINISTIC FIXES (must fix — from post-compose checks):
---
{fixes_str}
---

"""
    user = f"""DRAFT REPORT:
---
{draft_md}
---

DATA VALIDATION REPORT (numbers — fix all discrepancies):
---
{validation_report}
---
{critique_section}{additional_section}
Source totals (use exactly): A=${wt.get('guaranteed', 0):,.2f}, B=${wt.get('at_risk', 0):,.2f}, C=${wt.get('missing', 0):,.2f}, D=${wt.get('taxonomy_opt', 0):,.2f}, E=${wt.get('rate_gap', 0):,.2f}, Total=${wt.get('total_opportunity', 0):,.2f}

Org: {org_name}

Produce the final report: apply ALL corrections from the data validation report; incorporate insights from the report critique (tone, clarity, risky language). If ADDITIONAL DETERMINISTIC FIXES are present, apply those corrections as well (e.g. chart/section value mismatch, Section E disclaimer). Output markdown only."""

    _max_tokens = 65536  # gemini-2.5-flash supports 65536; avoid truncation of full report
    if provider == "openai":
        return _call_openai(WATERFALL_COMPOSER_PROMPT, user, model, max_output_tokens=_max_tokens)
    if provider == "gemini":
        return _call_gemini(WATERFALL_COMPOSER_PROMPT, user, model, max_output_tokens=_max_tokens)
    raise ValueError(f"Unknown provider: {provider}")
