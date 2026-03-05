"""
Report pipeline: Drafter → Validator + Critic (parallel) → Final Composer.
Runs Data Validator and Narrative Critic in parallel after the initial draft.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.report_writer import _build_snapshot, _build_prompt, _call_openai, _call_gemini, generate_white_paper_report

# ---------------------------------------------------------------------------
# Data Validator Prompt
# ---------------------------------------------------------------------------
DATA_VALIDATOR_PROMPT = """You are a strict data validator for a healthcare analytics report.

Your role is to verify that the narrative report is numerically consistent with the structured data outputs produced by the pipeline.

You must treat the CSV outputs and metrics.json as the source of truth.

INPUTS:
1. Draft report text (full MD)
2. CSV contents (raw text) for: locations, npis_per_location, per_npi_validation, combos, invalid_combos, ghost_billing, missed_opportunities
3. metrics.json (pipeline canonical metrics)

Your job is to RECOMPUTE all reported metrics directly from the CSV files and verify that the report values match.

Do NOT rewrite the report.
Do NOT modify wording.
You ONLY validate numbers and logic.

------------------------------------------------
STEP 1 — RECOMPUTE CORE METRICS FROM CSVs

Using the CSV files:

From locations.csv: location_count = row count

From npis_per_location.csv: total_npis = distinct servicing_npi (or NPIs in rows)

From combos.csv: total_combos = row count; ready_combos = rows where readiness_all_pass = true (if column exists)

From invalid_combos.csv: invalid_combo_count = row count; readiness_status breakdown (group by readiness_status, count); confidence_breakdown (high: confidence_score >= 70, medium: 40–69, low: <40 or null)

From per_npi_validation.csv: npis_all_checks_pass / npis_at_least_one_fail from all_checks_pass or equivalent

From ghost_billing.csv: ghost_billing_npi_count, ghost_billing_claim_count (sum claim_count), ghost_billing_total_paid (sum total_paid)

From missed_opportunities.csv: missed_opportunities_count = row count

------------------------------------------------
STEP 2 — VERIFY REPORT NUMBERS

Check that the following values in the report match the recomputed values:

- Total NPIs
- Total locations
- Total combinations
- Invalid combinations
- Ready combinations
- NPIs with issues
- NPIs fully ready
- Ghost billing metrics
- Missed opportunities (if provided)

------------------------------------------------
STEP 3 — VERIFY CATEGORY SUMS

Confirm that readiness_status counts in invalid_combos sum exactly to total invalid combinations.

------------------------------------------------
STEP 4 — VERIFY PERCENTAGES

Recompute: invalid_combos/total_combos, npis_with_issue/total_npis. Tolerance: ±0.1%

------------------------------------------------
STEP 5 — VERIFY REVENUE (metrics.json is source of truth)

Revenue cannot be recomputed from CSVs (run rates come from claims). Use metrics.json as authoritative.

**Use TOLERANCE for revenue** — rounding differences are normal. Do NOT fail validation for:
- revenue_at_risk_2024: report value vs metrics.json — tolerance ±$1 or ±0.01% (e.g. $9,159,681 vs $9,159,681.11 is PASS)
- revenue_at_risk_2024_by_status: sum of by_status can differ from total by rounding (tolerance ±$10)
- revenue_at_risk_2024_by_confidence: sum(high+medium+low) can differ by rounding
- JSON key name variations (e.g. snake_case vs camelCase) — compare values, not key strings

If the ONLY discrepancies are minor rounding or display formatting, use WARNINGS (or PASS) — NOT FAIL. FAIL only when numbers are materially wrong (e.g. wrong order of magnitude, mismatched counts).

Include in Recomputed Metrics: revenue_at_risk_2024, revenue_at_risk_2024_by_status, revenue_at_risk_2024_by_confidence (from metrics.json).
Include in Metrics Verified: Revenue totals and category sums.

------------------------------------------------
STEP 6 — VERIFY READINESS SCORE

Readiness Score = round(100 * ready_combos / total_combos). Confirm it matches.

------------------------------------------------
STEP 7 — VERIFY CONFIDENCE BREAKDOWN

Recompute from invalid_combos.csv: high (confidence_score >= 70), medium (40–69), low (<40 or null). Sum must equal invalid_combo_count.

If report includes revenue by confidence, verify report's revenue_at_risk by confidence tier matches metrics.json (revenue_at_risk_2024_by_confidence).

Include in Recomputed Metrics: confidence_breakdown (high, medium, low counts).
Include in Metrics Verified: Confidence counts and (if present) revenue by confidence.

------------------------------------------------
STEP 8 — DETECT LOGICAL CONTRADICTIONS

Flag: numbers in report not in CSV inputs; tables contradicting narrative; "Ready" rows in invalid-combo table; claims implying certainty beyond data.

------------------------------------------------
STEP 9 — CONFIDENCE-AWARE TONE

Tailor your validation report tone by confidence. For HIGH-confidence findings (we are more sure the NPI belongs at that location), treat discrepancies as critical — corrections are urgent. For LOW-confidence findings, note these may reflect roster noise or inference gaps; suggest "verify before changing" rather than treating as definitive errors. In Detected Issues and Suggested Corrections, stratify by confidence where relevant.

------------------------------------------------
OUTPUT FORMAT

DATA VALIDATION REPORT

Validation Status: PASS / WARNINGS / FAIL
(Use FAIL only for material data errors. Use WARNINGS for minor rounding/format differences. Revenue and percentages have tolerance.)

Recomputed Metrics:
- [counts from CSVs; confidence_breakdown from invalid_combos.csv; revenue/revenue_by_status/revenue_by_confidence from metrics.json]

Metrics Verified:
- [all confirmed: counts, percentages, readiness score, revenue totals and category sums, confidence breakdown]

Detected Issues:
- [each with explanation; stratify by confidence where relevant]

Data Quality Warnings:
- [anomalies]

Unverifiable Statements:
- [numbers in report not in data]

Suggested Corrections:
- [what to fix; high-confidence = immediate correction; low-confidence = verify before changing]

Do NOT rewrite the report. Only validate.
"""

# ---------------------------------------------------------------------------
# Narrative Critic Prompt
# ---------------------------------------------------------------------------
NARRATIVE_CRITIC_PROMPT = """You are a narrative critic for a healthcare analytics product report.

Your role is to review the drafted report and provide structured critique to improve clarity, insights, and executive readability.

You DO NOT modify the underlying numbers.
You DO NOT change calculations.

Your job is to evaluate:

1. **Executive clarity**: Does the report quickly answer: What is the problem? How big is it? Why it matters?

2. **Insight extraction**: Identify the 3–5 most important insights (largest revenue exposure, systemic issues, unexpected findings, data quality signals).

3. **Narrative gaps**: Missing explanations, unclear methodology, ambiguous terminology.

4. **Prioritization quality**: Do recommendations align with financial impact, effort, urgency?

5. **Product signal**: Does the report demonstrate Mobius value (detection before claims, workflows, confidence, outside-in)?

6. **Structural clarity**: Executive overview length (~120–150 words), table readability, section ordering. **Redundancy:** Flag if "Revenue Expansion" / Missed Opportunities are repeated in multiple sections. Flag if Key Recommendations and Remediation Priority Matrix are separate and overlap; they should be merged into one Action Plan. One row per metric in tables; no duplicate metrics. Top 3 problems should include % of invalid combos.

7. **Language risks**: Overclaims ("guaranteed revenue", "billing capacity"), audit-level certainty. Prefer: "can help protect" (not "can protect"); "opportunities to potentially unlock" (not "unlock X opportunities"); "highly likely to block" (not "will block"). For revenue framing, prefer "associated with credentialing gaps" and "including $X high-confidence exposure" over "revenue at risk" — executives trust the softer wording more.

8. **Tone adaptation (Friction Rule)**: Ghost billing = 0 → celebratory but cautious; Not enrolled high → urgent, revenue-focused; Florida nuances (AHCA, ZIP+4).

9. **Confidence calibration**: Does the report tailor tone to recommendation confidence? HIGH-confidence findings (we are more sure they are real gaps) should be framed with urgency and actionability. LOW-confidence findings (may be data artifacts or roster noise) should be caveated — e.g. "verify before acting," "prioritize high-confidence items first." Flag when the report overstates certainty for low-confidence recommendations or underplays urgency for high-confidence ones.

------------------------------------------------
OUTPUT FORMAT

REPORT CRITIQUE

Executive Assessment:
[2–3 sentence overall quality]

Top Insights Identified:
- [3–5 insights from report]

Narrative Strengths:
- [what works]

Narrative Weaknesses:
- [reduces clarity or impact]

Priority Improvements:
- [3–6 specific changes]

Product Signal:
[does it demonstrate Mobius intelligence?]

Risky Language or Claims:
- [statements to soften]

Confidence Calibration:
- [does tone match confidence? high-confidence = urgent/actionable; low-confidence = caveated/verify-first]

Revised Flavor (optional):
- 2–3 "Insight Callouts" to insert (e.g. "The $8.1M Risk at Naples")

Format Enhancements:
- Where a diagram or priority matrix would help

Do NOT rewrite the report. Provide critique only.
"""

# ---------------------------------------------------------------------------
# Final Composer Prompt (instructions; snapshot injected into user prompt)
# ---------------------------------------------------------------------------
FINAL_COMPOSER_SYSTEM = """You are the Final Composer for a Mobius Provider Roster / Credentialing report.

Your job is to produce the final report by:
1. Using the draft report as the base
2. Applying ALL corrections from the Data Validation Report — fix every numeric and logical discrepancy. Do not retain any incorrect numbers.
3. Incorporating insights from the Report Critique: tone adaptation, insight callouts, structural improvements, risky language fixes, and CONFIDENCE CALIBRATION (high-confidence findings = urgent/actionable; low-confidence = caveated, verify-first)
4. Apply feedback rules: (a) Reduce redundancy — merge separate Revenue Expansion and Key Recommendations if they repeat; use one unified Action Plan. (b) Risky language — use "can help protect," "opportunities to potentially unlock," "highly likely to block." (c) Ghost billing = 0 → highlight in Exec Overview as positive; state data window.

Follow Mobius Brand Voice: professional, urgent, action-oriented.

Ensure every numeric claim in the narrative ties to a table or structured input. Do not invent numbers.

If validation status is FAIL, explicitly correct every flagged discrepancy before producing output.

Prioritize Revenue-at-Risk narrative and Data Hygiene insights for location summaries.

Output the complete final report in markdown. Same structure as the draft.
"""


def run_data_validator(
    draft_md: str,
    csv_contents: dict[str, str],
    metrics: dict[str, Any],
    *,
    provider: str = "openai",
    model: str | None = None,
) -> str:
    """Run the Data Validator LLM. Returns validation report text."""
    model = model or ("gpt-4o" if provider == "openai" else (os.getenv("VERTEX_MODEL") or os.getenv("CHAT_VERTEX_MODEL") or "gemini-1.5-pro"))
    user = f"""DRAFT REPORT:
---
{draft_md}
---

CSV CONTENTS (raw text per file):
{json.dumps(csv_contents, indent=2)}

METRICS.JSON:
{json.dumps(metrics, indent=2)}

Verify the draft report against these inputs. Follow the output format exactly."""
    if provider == "openai":
        return _call_openai(DATA_VALIDATOR_PROMPT, user, model)
    if provider == "gemini":
        return _call_gemini(DATA_VALIDATOR_PROMPT, user, model)
    raise ValueError(f"Unknown provider: {provider}")


def run_narrative_critic(
    draft_md: str,
    *,
    provider: str = "openai",
    model: str | None = None,
) -> str:
    """Run the Narrative Critic LLM. Returns critique report text."""
    model = model or ("gpt-4o" if provider == "openai" else (os.getenv("VERTEX_MODEL") or os.getenv("CHAT_VERTEX_MODEL") or "gemini-1.5-pro"))
    user = f"""DRAFT REPORT:
---
{draft_md}
---

Review this draft and produce the structured REPORT CRITIQUE. Follow the output format exactly."""
    if provider == "openai":
        return _call_openai(NARRATIVE_CRITIC_PROMPT, user, model)
    if provider == "gemini":
        return _call_gemini(NARRATIVE_CRITIC_PROMPT, user, model)
    raise ValueError(f"Unknown provider: {provider}")


def run_final_composer(
    draft_md: str,
    validation_report: str,
    critique_report: str,
    report: dict[str, Any],
    *,
    provider: str = "openai",
    model: str | None = None,
) -> str:
    """Run the Final Composer LLM. Returns final report MD."""
    model = model or ("gpt-4o" if provider == "openai" else (os.getenv("VERTEX_MODEL") or os.getenv("CHAT_VERTEX_MODEL") or "gemini-1.5-pro"))
    snapshot = _build_snapshot(report)
    user = f"""DRAFT REPORT (base):
---
{draft_md}
---

DATA VALIDATION REPORT:
---
{validation_report}
---

REPORT CRITIQUE:
---
{critique_report}
---

DATA SNAPSHOT (for methodology, metrics, definitions):
{json.dumps(snapshot, indent=2)}

Produce the final report. Apply all validator corrections. Incorporate critic insights. Output complete markdown only."""
    if provider == "openai":
        return _call_openai(FINAL_COMPOSER_SYSTEM, user, model)
    if provider == "gemini":
        return _call_gemini(FINAL_COMPOSER_SYSTEM, user, model)
    raise ValueError(f"Unknown provider: {provider}")


def generate_with_pipeline(
    report: dict[str, Any],
    csv_contents: dict[str, str],
    metrics: dict[str, Any],
    *,
    provider: str = "openai",
    model: str | None = None,
) -> tuple[str, str, str, str]:
    """
    Full pipeline: Drafter → Validator + Critic (parallel) → Composer.

    Returns:
        (final_md, validation_report, critique_report, draft_md)
    """
    if report.get("executive_summary", {}).get("error"):
        err = report["executive_summary"]["error"] or "Unknown error."
        return (
            f"# Provider Roster / Credentialing Report\n\n**Error:** {err}",
            "",
            "",
            "",
        )

    # 1. Drafter
    draft_md = generate_white_paper_report(report, provider=provider, model=model)

    # 2. Validator and Critic in parallel
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_validator = ex.submit(run_data_validator, draft_md, csv_contents, metrics, provider=provider, model=model)
        fut_critic = ex.submit(run_narrative_critic, draft_md, provider=provider, model=model)
        validation_report = fut_validator.result()
        critique_report = fut_critic.result()

    # 3. Composer
    final_md = run_final_composer(
        draft_md, validation_report, critique_report, report,
        provider=provider, model=model,
    )

    return final_md, validation_report, critique_report, draft_md
