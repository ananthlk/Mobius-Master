"""
Generate an executive-level, white-paper-style Provider Roster / Credentialing report
using an LLM. Uses structured data + methodology + sources so the model can produce
best-in-class prose, snapshots, and insights (research-mode style).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Methodology and sources (for LLM context and report sourcing)
# ---------------------------------------------------------------------------
AHCA_DOCS_REF = "FL AHCA: ahca.myflorida.com/medicaid, Provider_Enrollment, portal.flmmis.com. Pass full AHCA docs when available."
AHCA_CONTEXT = (
    "FL AHCA Medicaid NPI Initiative: Florida Medicaid requires NPI, taxonomy, and service location (ZIP+4) for claims. "
    "AHCA publishes PML, TML, PPL. Our checks: (1) NPI in PML with Medicaid ID, (2) valid 9-digit ZIP+4, "
    "(3) taxonomy on TML/PPL, (4) NPI+taxonomy+ZIP9 combo has valid Medicaid ID. Ref: ahca.myflorida.com/medicaid, PML from portal.flmmis.com."
)
GLOSSARY = (
    "Glossary: PML = state enrolled provider list + Medicaid ID. TML/PPL = allowed taxonomy list. "
    "ZIP+4/ZIP9 = service location precision for enrollment. "
    "Combination = unique (Servicing NPI x Taxonomy x ZIP+4) row; one NPI can have multiple combos."
)
METHODOLOGY_OVERVIEW = (
    "This is an outside-in analysis using only the data sources we have (roster, state enrollment files, claims data, federal provider registry). "
    "We do not have access to the organization's internal truth; findings may include errors or misclassification. "
    "For example, NPIs flagged as 'Not enrolled' may have since enrolled, may no longer be with the organization, or may differ in the org's own records. "
    "Steps: (1) Locations and NPIs from the roster we have. (2) Four Medicaid checks against state and federal data. (3) Surfaces gaps to resolve, with recommendations. "
    "Treat results as a starting point for operational review, not as absolute truth."
)


METHODOLOGY = """
## Methodology

This report is an **outside-in** view of provider roster and credentialing readiness. We use only the data sources available to us — we do not have access to the organization's internal records or ground truth. What we show is derived from those sources; it can contain errors, timing lags, or misclassification.

**What we use:** (1) A provider roster that links organizations to locations and servicing providers, built from state enrollment data, federal provider data (NPPES), and historical billing patterns. (2) Florida Medicaid enrollment and taxonomy lists (PML, TML, PPL). (3) Claims or expenditure data for ghost billing and run rates. All of this is external or aggregated data — not the org's own HR or credentialing system.

**What we do:** For each organization and location in scope, we list servicing providers (NPIs) tied to that location in our roster. For each of those NPIs we run four checks against Medicaid and federal data: Is the NPI enrolled in Medicaid? Does the address have a valid 9-digit ZIP+4? Is the taxonomy allowed? Does the specific combination of NPI, taxonomy, and location have a valid Medicaid ID? We then flag rows where any check fails and surface missed opportunities and ghost billing (claims under the org's billing NPI where the servicing NPI is not on our roster).

**Unit of analysis:** A "combination" is one row: a specific NPI, taxonomy, and service location (ZIP+4). One provider can have multiple combinations (e.g. different locations or specialties). Counts of "Ready" and "invalid" are at this combination level.

**Confidence in roster attribution:** Each roster row has a **confidence score** (0–100) indicating how strongly we believe that this NPI belongs at this location. It is based on factors such as billing history (DOGE), address match strength, and building density. High confidence (e.g. 70–100) means we are more sure the NPI is truly with the organization at that site; medium (40–69) or low (0–39 / missing) means the link may be inferred or weak — e.g. same building but many unrelated offices, or no recent billing. The report breaks down invalid combinations by confidence so you can distinguish "what we are confident is real" from "what might be a data artifact or something we have missed." Use this to prioritize verification: high-confidence invalid combos are more likely to be true gaps; low-confidence ones may be false positives or roster noise.

**Important limitations:** Results are not guaranteed to be correct or complete. For example, many NPIs we flag as "Not enrolled" may have enrolled since our data was updated, may no longer be with the organization, or may be misattributed in our roster. Combo mismatches can reflect data lag between the state and the org. Use this report as a starting point for operational review and verification with the organization's own data — not as a definitive audit.
"""

SOURCES = """
## Sources

This report is built only from the following data sources (outside-in; we do not have the organization's internal HR or credentialing system):

- **Provider roster:** Links organizations to locations and servicing NPIs using state enrollment data (PML), federal NPPES, billing patterns, and taxonomy lists.
- **Readiness checks:** Outcomes from comparing roster rows to state and federal data (four Medicaid NPI initiative checks).
- **PML (Provider Master List):** State Medicaid provider enrollment file (e.g. FL AHCA). Used for NPI presence and NPI+taxonomy+ZIP9 combo Medicaid ID.
- **TML / PPL:** Taxonomy Master List and Pending Provider List for permitted taxonomy codes.
- **Claims / expenditure data:** Medicaid billing data (billing NPI, servicing NPI, claims, paid amounts). Used for ghost billing and run rates.
- **NPPES:** National Plan and Provider Enumeration System (practice addresses, provider names, taxonomies).
"""

DEFINITIONS = """
**Ghost billing:** In our claims data, billing under the org's billing NPI by a servicing NPI that does not appear on the roster we have for that org. May indicate roster gaps or data timing; verify with the organization.

**Missed opportunities:** (1) Locations in scope where no servicing NPI has all four checks pass in our data. (2) NPIs that appear in PML but do not have a matching NPI+taxonomy+ZIP9 combo in our check — alignment of state or NPPES data may resolve.

**Invalid combo (in our analysis):** A (location, NPI, taxonomy, ZIP+4) row where our checks against available data indicate at least one failure. The organization may have different or more current information.

**Ready:** In our data, all four checks pass for that combo; the provider is treated as credentialing-ready at that location/taxonomy/address for this report.
"""


def _load_ahca_docs(max_chars: int = 120000) -> str:
    """Load stored FL AHCA docs from data/ahca_docs/*.md. Run scripts/fetch_ahca_docs.py to refresh."""
    from pathlib import Path
    docs_dir = Path(__file__).resolve().parent.parent / "data" / "ahca_docs"
    if not docs_dir.exists():
        return "(No AHCA docs stored. Run scripts/fetch_ahca_docs.py to fetch.)"
    parts: list[str] = []
    total = 0
    for p in sorted(docs_dir.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8").strip()
            if text and total + len(text) <= max_chars:
                parts.append(text)
                total += len(text)
            elif text:
                parts.append(text[: max_chars - total])
                total = max_chars
                break
        except Exception as e:
            logger.warning("Failed to load %s: %s", p.name, e)
    return "\n\n---\n\n".join(parts) if parts else "(No AHCA docs loaded.)"


def _build_snapshot(report: dict[str, Any]) -> dict[str, Any]:
    """Build a compact, LLM-friendly snapshot of the report (no huge lists)."""
    ex = report.get("executive_summary") or {}
    locations = report.get("locations") or []
    invalid = report.get("invalid_combos") or []
    ghost = report.get("ghost_billing") or []
    missed = report.get("missed_opportunities") or []
    status_breakdown = ex.get("readiness_status_breakdown") or {}

    # Sample of invalid combos (first 5) with key fields for narrative
    invalid_sample = []
    for r in invalid[:5]:
        invalid_sample.append({
            "servicing_npi": r.get("servicing_npi"),
            "servicing_provider_name": r.get("servicing_provider_name") or "(unnamed)",
            "readiness_status": r.get("readiness_status"),
            "readiness_summary": (r.get("readiness_summary") or "")[:200],
            "pml_credentialed_combos": r.get("pml_credentialed_combos"),
            "suggested_action": r.get("suggested_action"),
            "suggested_taxonomies": r.get("suggested_taxonomies"),
        })

    # Ghost billing summary
    ghost_summary = None
    if ghost:
        total_claims = sum(g.get("claim_count") or 0 for g in ghost)
        total_paid = sum(g.get("total_paid") or 0 for g in ghost)
        ghost_sample = [{"billing_npi": g.get("billing_npi"), "servicing_npi": g.get("servicing_npi"), "claim_count": g.get("claim_count"), "total_paid": g.get("total_paid")} for g in ghost[:5]]
        ghost_summary = {"npi_count": len(ghost), "total_claims": total_claims, "total_paid": total_paid, "sample": ghost_sample}

    # Location names/addresses for context (all locations; do not truncate)
    location_summary = []
    for loc in locations:
        location_summary.append({
            "org_name": loc.get("org_name"),
            "site_city": loc.get("site_city"),
            "site_state": loc.get("site_state"),
            "site_zip": loc.get("site_zip"),
        })

    total_npis = ex.get("total_npis") or 0
    npis_fail = ex.get("npis_at_least_one_fail") or 0
    invalid_count = ex.get("invalid_combo_count") or 0
    ready_count = status_breakdown.get("Ready") or 0
    total_combos = ready_count + invalid_count
    pct_npis_with_issue = round(100 * npis_fail / total_npis, 1) if total_npis else 0
    pct_combos_invalid = round(100 * invalid_count / total_combos, 1) if total_combos else 0
    data_window_ghost_billing = "DOGE claims, last 12 months (parameterized in pipeline)"
    data_window_missed_opportunities = "As of report date (roster and readiness snapshot)"
    is_fixture = any((r.get("readiness_summary") or "").lower().startswith("fixture") for r in invalid[:3]) or not invalid

    revenue_at_risk_2024 = ex.get("revenue_at_risk_2024")
    if revenue_at_risk_2024 is None:
        revenue_at_risk_2024 = 0.0
    billing_impact_note = ex.get("billing_impact_note")
    revenue_at_risk_2024_by_status = ex.get("revenue_at_risk_2024_by_status") or {}
    revenue_at_risk_2024_by_confidence = ex.get("revenue_at_risk_2024_by_confidence") or {}
    confidence_breakdown = ex.get("confidence_breakdown") or {"high": 0, "medium": 0, "low": 0}
    readiness_score = ex.get("readiness_score")

    generated_charts = report.get("_generated_charts") or []

    # Optional benchmark (placeholder until real benchmark data)
    readiness_benchmark = report.get("_readiness_benchmark") or {
        "median": 68,
        "top_quartile": 82,
        "note": "Among comparable FL behavioral health organizations (placeholder; replace with real benchmarks when available).",
    }

    return {
        "org_name": ex.get("org_name"),
        "generated_at": datetime.now().isoformat(),
        "generated_charts": generated_charts,
        "methodology_overview": METHODOLOGY_OVERVIEW,
        "metrics": {
            "location_count": ex.get("location_count", 0),
            "total_npis": total_npis,
            "npis_all_checks_pass": ex.get("npis_all_checks_pass", 0),
            "npis_at_least_one_fail": npis_fail,
            "invalid_combo_count": invalid_count,
            "ready_combo_count": ready_count,
            "total_combo_count": total_combos,
            "pct_npis_with_issue": pct_npis_with_issue,
            "pct_combos_invalid": pct_combos_invalid,
            "ghost_billing_npi_count": ex.get("ghost_billing_npi_count", 0),
            "ghost_billing_claim_count": ex.get("ghost_billing_claim_count", 0),
            "ghost_billing_total_paid": ex.get("ghost_billing_total_paid", 0),
            "revenue_at_risk_2024": revenue_at_risk_2024,
        },
        "readiness_status_breakdown": status_breakdown,
        "next_steps_text": ex.get("next_steps", ""),
        "invalid_combo_sample": invalid_sample,
        "ghost_billing_summary": ghost_summary,
        "missed_opportunities_count": len(missed),
        "location_summary": location_summary,
        "data_window_ghost_billing": data_window_ghost_billing,
        "data_window_missed_opportunities": data_window_missed_opportunities,
        "is_fixture_or_sample_data": is_fixture,
        "billing_impact_note": billing_impact_note,
        "revenue_at_risk_2024_by_status": revenue_at_risk_2024_by_status,
        "revenue_at_risk_2024_by_confidence": revenue_at_risk_2024_by_confidence,
        "confidence_breakdown": confidence_breakdown,
        "readiness_score": readiness_score,
        "estimated_missed_opportunities_revenue_20pct": ex.get("estimated_missed_opportunities_revenue_20pct"),
        "worked_example": ex.get("worked_example"),
        "readiness_benchmark": readiness_benchmark,
    }


def _build_prompt(snapshot: dict[str, Any]) -> tuple[str, str]:
    """Build system and user prompts for the LLM."""
    system = """You are an expert analyst writing an executive-level, operator-focused report for a healthcare organization's Provider Roster and Credentialing assessment. Audience: ops leaders and credentialing operators. The report must be **resolution-focused** and frame findings as **financial risk and opportunity**. You must:

0. **CEO Summary (elevator pitch):** When revenue_at_risk_2024 is provided and greater than zero, start the report with a 3-sentence **CEO Summary** at the very top (before Executive Overview), for the reader who will not read the rest. Use **safer framing for executives:** say "$X **associated with credentialing gaps**, including $Y **high-confidence exposure**" rather than "$X revenue at risk." Example: "Mobius has identified $X in annual revenue associated with credentialing gaps across [N] providers, including $Y in high-confidence exposure. By deploying our automated Enrollment and Roster Sync workflows, [Org] can **help protect** this revenue and access opportunities to **potentially unlock** additional billing from [missed_opportunities_count] providers in state data." Use exact numbers. **Avoid overclaims:** use "can help protect"; "opportunities to potentially unlock"; "associated with credentialing gaps" (executives trust this wording more than "revenue at risk").

1. **Executive overview:** ~120–150 words, concise. Lead with org name, total NPIs, total combinations, invalid count and %. When revenue_at_risk_2024 > 0, use **safer executive framing:** "Based on historical 2024 billing run rates, Mobius estimates approximately $X in annual Medicaid revenue **associated with credentialing gaps**, including $Y in high-confidence exposure." Use exact values. Avoid "revenue at risk" — prefer "associated with credentialing gaps" and "including $Y high-confidence exposure." Then: "These combinations may be at risk for claim denial or delayed reimbursement." Include one short "So what?" paragraph on resolution. **When ghost_billing_npi_count = 0:** highlight this prominently as a positive indicator — e.g. "No ghost billing detected (checked [data_window_ghost_billing])." End with: "Mobius continuously monitors these combinations so that credentialing gaps are detected before they impact billing." Mention missed opportunities briefly if applicable.

2. **Why this matters:** Include both: (a) "Mobius converts complex Medicaid credentialing rules into a single operational view of provider readiness and **automatically generates** operational workflows to resolve issues." (b) "Mobius surfaces the exact provider combinations that **are highly likely to block** Medicaid billing before claims are submitted." (Use "highly likely to block" or "pose a significant risk of blocking" — avoid absolute "will block.")

3. **Methodology:** Use the methodology text provided. Include a **Data freshness** line: "Data current as of: [use generated_at from snapshot]. Sources: FL PML snapshot, roster, and claims data." Include the **Confidence** paragraph from the methodology (roster attribution confidence: high/medium/low; what we are sure vs what we might have missed). Include short Limitations / How to use this report. Put detailed steps in the Appendix.

4. **Mobius Readiness Score:** When readiness_score is provided (0–100), add a short section "Mobius Medicaid Readiness Score: [X] / 100" — derived from ready combinations / total combinations. When **readiness_benchmark** is provided (median, top_quartile), add context: "Among comparable FL behavioral health organizations, the median readiness score is [median]; top quartile is [top_quartile]." This makes the score narrative-worthy. Executives respond to a single score plus benchmark.

5. **Charts and visuals (REQUIRED when generated_charts present):** When **generated_charts** is provided and non-empty, you MUST include every chart as a markdown image. Use the exact filename for each image: `![title](filename.png)`. Placement: **executive_dashboard** → at the very top, immediately after the CEO Summary (or before Executive Overview if no CEO Summary); this is the single panel investors and CEOs remember. revenue_by_status and readiness_breakdown → Key Findings, after Summary Metrics table; confidence_breakdown and revenue_by_confidence → Key Findings, after the relevant tables. Add a brief caption under each chart. Do not skip or omit any chart — visuals make the report credible and executive-friendly.

6. **Key Findings:** Use "combinations that may be at risk for claim denial or delayed reimbursement" (not "invalid" only). When **estimated_missed_opportunities_revenue_20pct** is provided, quantify missed opportunities: "If even 20% of these [N] missed opportunities are activatable at similar run rates, that could represent approximately $X in new billing potential." When **worked_example** is provided, add a short "How we calculate revenue" subsection: show one example (NPI, taxonomy, location, run_rate_per_physician, annual_estimate, explanation) so a CFO can stress-test the figure. Include a single metrics table; **one row per metric** — do not duplicate the same metric as two rows (e.g. do not show both "NPIs with at least one issue" and "Percentage of NPIs with issues" as separate rows; use Count and % in one row). In the readiness status table (Top 3 problems), **add % of total invalid combinations** for each type (e.g. Not enrolled — 117 (47%); Combo mismatch — 69 (28%)). When **revenue_at_risk_2024_by_status** is provided, add Estimated Annual Revenue Impact next to each issue type. When **revenue_at_risk_2024_by_confidence** is provided, add Revenue by Confidence. When **confidence_breakdown** is provided, add a short Confidence note. When invalid_combo_sample includes **suggested_taxonomies**, include data-driven recommendations. In the readiness status table, do **not** include a row for "Ready". Define **Missed opportunities** in one sentence. **When missed_opportunities_count > 0:** integrate the Revenue Expansion narrative here (providers Medicaid-ready in state data but not fully utilized; resolving alignment unlocks billing potential) — do **not** create a separate redundant "Revenue Expansion" section that reiterates the same points.

7. **Location summary:** When multiple locations share the same or similar address/ZIP, group them under a **Standardized location** and list **Source name variations** (the different org_name values from the data). Add one line: "Multiple organizational name variants appear in external data for the same location; Mobius normalizes these for accurate roster reconstruction." This surfaces data hygiene as a Mobius value.

8. **Action Plan (unified):** Combine Key Recommendations and Insights & Mobius Actions into a **single** "Action Plan" or "Insights & Mobius Actions" section. Do **not** have separate "Key Recommendations" bullet list and "Remediation Priority Matrix" — merge them. One table: Priority (P1/P2/P3), Issue Type, Estimated Annual Revenue Impact, **Effort** (High/Medium/Low), Resolution Action. Include 4–6 concrete items with what to resolve, action, and outcome. Say "Mobius **automatically generates** operational workflows." Order by impact. **Avoid redundancy** — do not repeat the same recommendation in two places.

9. **Downloadable Files and Data Dictionary:** Add a section "Downloadable Files" that: (a) Lists the CSV and JSON outputs: locations.csv, npis_per_location.csv, per_npi_validation.csv, combos.csv, invalid_combos.csv, ghost_billing.csv, missed_opportunities.csv, metrics.json. (b) For each file, provide a brief **Data Dictionary** table (columns: File | Column | Description). Cover key columns such as: servicing_npi, provider_taxonomy_code, readiness_status, pml_credentialed_combos, suggested_action, suggested_taxonomies, claim_count, total_paid, confidence_score, zip9, org_name, location_id. Explain that these files accompany the report for operational use.

10. **Mobius Chat Upsell:** Add a short callout (e.g. before or after Key Recommendations): "**Go deeper with Mobius Chat:** Use our chat feature to develop tailored recommendations and exportable files for each opportunity. Ask for provider-specific action lists, location-by-location breakdowns, or ready-to-upload CSVs for your credentialing workflow."

11. **Appendix:** Detailed methodology steps and glossary. Do not repeat full definitions of ZIP+4, combination, etc. if already in main body; keep appendix focused on process. If is_fixture_or_sample_data, label illustrative sample "Illustrative example (fixture data)."

12. **Sources:** List data sources; cite AHCA when referencing Florida Medicaid policy.

13. **Tone:** Resolution-focused; use "in our data," "our checks indicate," "associated with" for revenue. Distinguish what we are confident is real vs what might be missed or a data artifact using the confidence breakdown.

14. **Ghost billing:** Ghost billing = servicing NPIs that bill under the org but have weak address/roster match (confidence < 40). When ghost_billing_npi_count > 0, explain these are providers billing under the org whom we cannot confidently tie to that location; recommend verification.

15. **Numeric integrity:** All numeric claims in the narrative must tie to a table or structured input. If a number appears in narrative but not in the provided data, omit it or flag it. Do not invent numbers.

16. **Urgency framing:** Include: "Claims associated with these combinations are actively billing — denial risk is present today." Add time pressure: "If nothing is done in 90–180 days, continued billing under invalid combos increases exposure to claim denial and delayed reimbursement." Executives need this to move forward."""

    data_str = json.dumps(snapshot, indent=2)
    ahca_docs = _load_ahca_docs()
    user = f"""Using the following data snapshot, methodology, definitions, and sources, produce the full operator-ready report in markdown.

FL AHCA context (use for sourcing): {AHCA_CONTEXT}

FL AHCA docs (stored from ahca.myflorida.com). When referring to Florida Medicaid policy, rules, or procedures, cite these AHCA documents and include them in the Sources section:
---
{ahca_docs}
---

Reference: {AHCA_DOCS_REF}

Glossary to include in report: {GLOSSARY}

Methodology overview (parameters): {snapshot.get("methodology_overview", METHODOLOGY_OVERVIEW)}

{METHODOLOGY}

{DEFINITIONS}

{SOURCES}

--- DATA SNAPSHOT (use these numbers only; respect is_fixture_or_sample_data for sample rows) ---

{data_str}

---

Write the complete report now. Use the organization name from the snapshot. Use resolution-focused language throughout. Include: Executive Overview (~120–150 words, concise; highlight no ghost billing when zero), Why This Matters, Methodology (concise), Key Findings (metrics; Top 3 with %; **MUST include all chart images** from generated_charts — place each after the relevant table with caption; integrate Missed Opportunities here — no separate redundant Revenue Expansion section), Ghost Billing (data window when zero), **Action Plan** (unified), **Go deeper with Mobius Chat** (upsell), **Downloadable Files** (list + Data Dictionary), Appendix, Sources. Avoid redundancy and overclaims."""
    return system, user


def _call_openai(system: str, user: str, model: str) -> str:
    import httpx
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 8192,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    choice = resp.json().get("choices", [{}])[0]
    return (choice.get("message", {}).get("content") or "").strip()


def _call_gemini(system: str, user: str, model: str) -> str:
    """Gemini via Google AI API (GEMINI_API_KEY) or Vertex (VERTEX_PROJECT_ID / CHAT_VERTEX_PROJECT_ID). Same env as mobius-chat and healthcare."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{system}\n\n{user}"}]}],
            "generationConfig": {"maxOutputTokens": 8192},
        }
        resp = httpx.post(url, json=payload, timeout=120.0)
        resp.raise_for_status()
        text = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return text.strip()
    # Vertex (prefer BQ_PROJECT / dev so report uses same project as BigQuery)
    project = (os.getenv("BQ_PROJECT") or os.getenv("VERTEX_PROJECT_ID") or os.getenv("CHAT_VERTEX_PROJECT_ID") or "").strip()
    if project:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        location = os.getenv("VERTEX_LOCATION") or os.getenv("VERTEX_REGION") or "us-central1"
        vertexai.init(project=project, location=location)
        m = GenerativeModel(model)
        response = m.generate_content(
            f"{system}\n\n{user}",
            generation_config={"max_output_tokens": 8192},
        )
        if response and response.text:
            return response.text.strip()
        raise RuntimeError("Vertex Gemini returned empty response")
    raise ValueError("Set GEMINI_API_KEY or VERTEX_PROJECT_ID (or CHAT_VERTEX_PROJECT_ID) for Gemini")


def generate_white_paper_report(
    report: dict[str, Any],
    *,
    provider: str = "openai",
    model: str | None = None,
) -> str:
    """
    Produce a white-paper-style executive report from the raw report dict using an LLM.

    Args:
        report: Full report from build_full_report().
    Kwargs:
        provider: "openai" or "gemini".
        model: Model name (e.g. gpt-4o, gemini-1.5-pro). Defaults: gpt-4o for OpenAI, gemini-1.5-pro for Gemini.

    Returns:
        Generated markdown string (full report with overview, methodology, findings, insights, sources).
    """
    if report.get("executive_summary", {}).get("error"):
        return "# Provider Roster / Credentialing Report\n\n**Error:** " + (report["executive_summary"]["error"] or "Unknown error.")

    snapshot = _build_snapshot(report)
    system, user = _build_prompt(snapshot)

    model = model or ("gpt-4o" if provider == "openai" else (os.getenv("VERTEX_MODEL") or os.getenv("CHAT_VERTEX_MODEL") or "gemini-1.5-pro"))
    if provider == "openai":
        out = _call_openai(system, user, model)
    elif provider == "gemini":
        out = _call_gemini(system, user, model)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    if not out:
        return "# Provider Roster / Credentialing Report\n\n*Report generation returned no content. Check API key and model.*"
    return out
