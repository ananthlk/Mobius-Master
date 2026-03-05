"""
Generate chart images for the Provider Roster Credentialing report.
Uses matplotlib + seaborn. Charts are written as PNG files for embedding in markdown.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Mobius palette (from mobius-design)
MOBIUS_COLORS = {
    "accent": "#3b82f6",
    "success": "#16a34a",
    "warning": "#f59e0b",
    "error": "#dc2626",
    "text_primary": "#1a1d21",
    "text_muted": "#64748b",
}
# Bar/pie palette
CHART_PALETTE = [
    "#3b82f6",  # accent
    "#16a34a",  # success
    "#f59e0b",  # warning
    "#dc2626",  # error
    "#8b5cf6",  # purple
    "#06b6d4",  # cyan
]


def _format_currency(val: float) -> str:
    """Format as compact currency (e.g. $5.7M, $829K)."""
    if val >= 1_000_000:
        return f"${val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"${val / 1_000:.1f}K"
    return f"${val:,.0f}"


def generate_charts(
    report: dict[str, Any],
    metrics: dict[str, Any],
    output_dir: Path,
    prefix: str,
    chart_ids: list[str] | None = None,
) -> list[dict[str, str]]:
    """
    Generate chart PNGs from report and metrics.

    Args:
        report: Full report dict (executive_summary, etc.)
        metrics: Canonical metrics (revenue_at_risk_2024_by_status, confidence_breakdown, etc.)
        output_dir: Directory to write PNG files
        prefix: Filename prefix (e.g. provider_roster_credentialing_20260304_2140)
        chart_ids: Optional list of chart ids to generate. If None, generates all applicable.

    Returns:
        List of {id, filename, title} for markdown embedding.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError as e:
        logger.warning("matplotlib/seaborn not installed; skipping chart generation: %s", e)
        return []

    ex = report.get("executive_summary") or {}
    status_breakdown = ex.get("readiness_status_breakdown") or metrics.get("readiness_status_breakdown") or {}
    revenue_by_status = ex.get("revenue_at_risk_2024_by_status") or metrics.get("revenue_at_risk_2024_by_status") or {}
    revenue_by_confidence = ex.get("revenue_at_risk_2024_by_confidence") or metrics.get("revenue_at_risk_2024_by_confidence") or {}
    confidence_breakdown = ex.get("confidence_breakdown") or metrics.get("confidence_breakdown") or {}

    revenue_total = ex.get("revenue_at_risk_2024") or metrics.get("revenue_at_risk_2024") or 0
    high_conf_revenue = 0
    if revenue_by_confidence:
        high_conf_revenue = float(revenue_by_confidence.get("high") or 0)
    invalid_count = ex.get("invalid_combo_count") or metrics.get("invalid_combo_count") or 0
    ready_count = status_breakdown.get("Ready") or metrics.get("ready_combo_count") or 0
    npis_fail = ex.get("npis_at_least_one_fail") or metrics.get("npis_at_least_one_fail") or 0
    missed = len(report.get("missed_opportunities") or [])
    if not missed:
        missed = ex.get("missed_opportunities_count") or metrics.get("missed_opportunities_count") or 0
    readiness_score = ex.get("readiness_score") or metrics.get("readiness_score")
    org_name = ex.get("org_name") or metrics.get("org_name") or "Organization"

    available: dict[str, bool] = {
        "executive_dashboard": bool(invalid_count or revenue_total or readiness_score is not None),
        "revenue_by_status": bool(revenue_by_status),
        "readiness_breakdown": bool(status_breakdown and any(k != "Ready" for k in status_breakdown)),
        "confidence_breakdown": bool(confidence_breakdown and sum(confidence_breakdown.values()) > 0),
        "revenue_by_confidence": bool(revenue_by_confidence),
    }

    to_generate = chart_ids if chart_ids else ["executive_dashboard"] + [k for k, v in available.items() if v and k != "executive_dashboard"]
    to_generate = [c for c in to_generate if available.get(c, False)]

    generated: list[dict[str, str]] = []
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sns.set_style("whitegrid")
    sns.set_palette(CHART_PALETTE)

    for chart_id in to_generate:
        try:
            if chart_id == "executive_dashboard":
                out = _chart_executive_dashboard(
                    org_name, revenue_total, high_conf_revenue,
                    invalid_count, npis_fail, missed, readiness_score,
                    output_dir, prefix,
                    ready_count=ready_count,
                )
            elif chart_id == "revenue_by_status":
                out = _chart_revenue_by_status(revenue_by_status, output_dir, prefix)
            elif chart_id == "readiness_breakdown":
                out = _chart_readiness_breakdown(status_breakdown, output_dir, prefix)
            elif chart_id == "confidence_breakdown":
                out = _chart_confidence_breakdown(confidence_breakdown, output_dir, prefix)
            elif chart_id == "revenue_by_confidence":
                out = _chart_revenue_by_confidence(revenue_by_confidence, output_dir, prefix)
            else:
                continue
            if out:
                generated.append(out)
        except Exception as e:
            logger.warning("Failed to generate chart %s: %s", chart_id, e)

    return generated


def _chart_executive_dashboard(
    org_name: str,
    revenue_total: float,
    high_conf_revenue: float,
    invalid_count: int,
    npis_fail: int,
    missed: int,
    readiness_score: int | None,
    output_dir: Path,
    prefix: str,
    ready_count: int = 0,
) -> dict[str, str] | None:
    """Single-panel Mobius Executive Dashboard — the slide CEOs remember. Includes Ready/Invalid/Missed donut."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axis("off")

    # Panel background
    panel = FancyBboxPatch((0.02, 0.02), 0.96, 0.96, boxstyle="round,pad=0.02",
                           facecolor="#f8fafc", edgecolor=MOBIUS_COLORS["accent"], linewidth=2)
    ax.add_patch(panel)

    # Title
    ax.text(0.5, 0.92, "Mobius Executive Dashboard", fontsize=18, fontweight="bold",
            ha="center", va="top", color=MOBIUS_COLORS["text_primary"])
    ax.text(0.5, 0.86, org_name, fontsize=12, ha="center", va="top", color=MOBIUS_COLORS["text_muted"])

    # At-a-glance donut: Ready | Invalid | Missed (right side)
    if ready_count > 0 or invalid_count > 0 or missed > 0:
        donut_ax = fig.add_axes([0.68, 0.15, 0.28, 0.55])
        vals = [ready_count, invalid_count, missed]
        labels = ["Ready", "Invalid", "Missed Opps"]
        colors = [CHART_PALETTE[1], CHART_PALETTE[2], CHART_PALETTE[0]]
        vals = [max(v, 0.5) for v in vals]
        wedges, texts, autotexts = donut_ax.pie(vals, labels=labels, colors=colors[:3], autopct="%1.0f%%",
                                                startangle=90, pctdistance=0.75)
        donut_ax.add_patch(plt.Circle((0, 0), 0.5, fc="#f8fafc"))
        donut_ax.set_title("At a glance", fontsize=10, color=MOBIUS_COLORS["text_muted"])
        for t in texts:
            t.set_fontsize(9)

    # Metrics (left side, 2 rows x 2 cols)
    metrics = []
    if revenue_total and revenue_total > 0:
        metrics.append((_format_currency(revenue_total), "associated with\ncredentialing gaps"))
    if high_conf_revenue and high_conf_revenue > 0:
        metrics.append((_format_currency(high_conf_revenue), "high-confidence\nexposure"))
    if invalid_count > 0:
        metrics.append((f"{invalid_count:,}", "credentialing\ngaps"))
    if npis_fail > 0:
        metrics.append((f"{npis_fail:,}", "providers\naffected"))
    if missed > 0:
        metrics.append((f"{missed:,}", "missed\nopportunities"))
    if readiness_score is not None:
        metrics.append((f"{readiness_score}", "readiness\nscore"))

    n = len(metrics)
    if n == 0:
        plt.close()
        return None

    cols = 2
    for i, (val, label) in enumerate(metrics):
        row, col = i // cols, i % cols
        x = 0.15 + col * 0.25
        y = 0.62 - row * 0.22
        ax.text(x, y + 0.06, val, fontsize=14, fontweight="bold", color=MOBIUS_COLORS["accent"])
        ax.text(x, y - 0.02, label, fontsize=9, color=MOBIUS_COLORS["text_muted"], ha="center")

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    path = output_dir / f"{prefix}_executive_dashboard.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    return {"id": "executive_dashboard", "filename": path.name, "title": "Mobius Executive Dashboard"}


def _chart_revenue_by_status(
    revenue_by_status: dict[str, float],
    output_dir: Path,
    prefix: str,
) -> dict[str, str] | None:
    """Horizontal bar: revenue at risk by readiness status."""
    if not revenue_by_status:
        return None
    import matplotlib.pyplot as plt
    import seaborn as sns

    labels = list(revenue_by_status.keys())
    values = [float(revenue_by_status.get(k) or 0) for k in labels]
    labels = [l.replace(" ", "\n") if len(l) > 12 else l for l in labels]

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(labels, [v / 1_000_000 for v in values], color=CHART_PALETTE[: len(labels)])
    ax.set_xlabel("Revenue at Risk ($M)")
    ax.set_title("Revenue at Risk by Issue Type")
    ax.set_xlim(0, max(values) / 1_000_000 * 1.15 if values else 6)
    for i, (bar, val) in enumerate(zip(bars, values)):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                _format_currency(val), va="center", fontsize=9, color=MOBIUS_COLORS["text_primary"])
    fig.tight_layout()
    path = output_dir / f"{prefix}_revenue_by_status.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    return {"id": "revenue_by_status", "filename": path.name, "title": "Revenue at Risk by Issue Type"}


def _chart_readiness_breakdown(
    status_breakdown: dict[str, int],
    output_dir: Path,
    prefix: str,
) -> dict[str, str] | None:
    """Bar: invalid combinations by readiness status (exclude Ready)."""
    filtered = {k: v for k, v in status_breakdown.items() if k != "Ready" and v > 0}
    if not filtered:
        return None
    import matplotlib.pyplot as plt

    labels = list(filtered.keys())
    values = list(filtered.values())
    labels = [l.replace(" ", "\n") if len(l) > 14 else l for l in labels]

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(labels, values, color=CHART_PALETTE[: len(labels)])
    ax.set_ylabel("Invalid Combinations")
    ax.set_title("Invalid Combinations by Readiness Status")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                str(val), ha="center", fontsize=9, color=MOBIUS_COLORS["text_primary"])
    plt.xticks(rotation=15, ha="right")
    fig.tight_layout()
    path = output_dir / f"{prefix}_readiness_breakdown.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    return {"id": "readiness_breakdown", "filename": path.name, "title": "Invalid Combinations by Readiness Status"}


def _chart_confidence_breakdown(
    confidence_breakdown: dict[str, int],
    output_dir: Path,
    prefix: str,
) -> dict[str, str] | None:
    """Pie or bar: invalid combos by confidence level."""
    filtered = {k: v for k, v in confidence_breakdown.items() if v > 0}
    if not filtered:
        return None
    import matplotlib.pyplot as plt

    labels = [k.capitalize() for k in filtered.keys()]
    values = list(filtered.values())
    colors = [CHART_PALETTE[0], CHART_PALETTE[1], CHART_PALETTE[2]][: len(labels)]

    fig, ax = plt.subplots(figsize=(5, 5))
    wedges, texts, autotexts = ax.pie(values, labels=labels, autopct="%1.0f%%", colors=colors, startangle=90)
    for t in texts:
        t.set_fontsize(10)
    for t in autotexts:
        t.set_fontsize(9)
    ax.set_title("Invalid Combinations by Confidence Level")
    fig.tight_layout()
    path = output_dir / f"{prefix}_confidence_breakdown.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    return {"id": "confidence_breakdown", "filename": path.name, "title": "Invalid Combinations by Confidence Level"}


def _chart_revenue_by_confidence(
    revenue_by_confidence: dict[str, float],
    output_dir: Path,
    prefix: str,
) -> dict[str, str] | None:
    """Bar: revenue at risk by confidence level."""
    if not revenue_by_confidence:
        return None
    import matplotlib.pyplot as plt

    labels = [k.capitalize() for k in revenue_by_confidence.keys()]
    values = [float(revenue_by_confidence.get(k) or 0) for k in revenue_by_confidence]

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(labels, [v / 1_000_000 for v in values], color=CHART_PALETTE[: len(labels)])
    ax.set_ylabel("Revenue at Risk ($M)")
    ax.set_title("Revenue at Risk by Confidence Level")
    for bar, val in zip(bars, values):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                    _format_currency(val), ha="center", fontsize=9, color=MOBIUS_COLORS["text_primary"])
    fig.tight_layout()
    path = output_dir / f"{prefix}_revenue_by_confidence.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    return {"id": "revenue_by_confidence", "filename": path.name, "title": "Revenue at Risk by Confidence Level"}


# ---------------------------------------------------------------------------
# LLM Chart Spec: suggest which charts to include
# ---------------------------------------------------------------------------
CHART_SPEC_PROMPT = """You are a report designer. Given a provider roster credentialing report snapshot, suggest which charts to include to maximize executive impact and credibility.

Available chart types (generate only these ids):
- executive_dashboard: SINGLE PANEL at top — key metrics (revenue associated with gaps, high-confidence exposure, credentialing gaps, providers affected, missed opportunities, readiness score). ALWAYS include first when data exists.
- revenue_by_status: Bar chart of revenue by issue type.
- readiness_breakdown: Bar chart of invalid combinations by readiness status.
- confidence_breakdown: Pie chart of invalid combos by confidence.
- revenue_by_confidence: Bar chart of revenue by confidence level.

Return a JSON array with executive_dashboard FIRST when metrics exist, e.g. ["executive_dashboard", "revenue_by_status", "readiness_breakdown", "confidence_breakdown", "revenue_by_confidence"].
Include 2-4 charts. Only include charts for which the snapshot has the required data.
Output ONLY the JSON array, no other text."""


def get_chart_spec_from_llm(
    report: dict[str, Any],
    metrics: dict[str, Any],
    *,
    provider: str = "openai",
    model: str | None = None,
) -> list[str]:
    """
    Use LLM to suggest which charts to generate based on report and metrics.
    Returns list of chart ids (e.g. ["revenue_by_status", "readiness_breakdown"]).
    """
    try:
        from app.report_writer import _call_openai, _call_gemini
    except ImportError:
        return []

    import os
    ex = report.get("executive_summary") or {}
    model = model or ("gpt-4o-mini" if provider == "openai" else (os.getenv("VERTEX_MODEL") or "gemini-1.5-flash"))
    subset = {
        "revenue_at_risk_2024_by_status": ex.get("revenue_at_risk_2024_by_status") or metrics.get("revenue_at_risk_2024_by_status"),
        "readiness_status_breakdown": ex.get("readiness_status_breakdown") or metrics.get("readiness_status_breakdown"),
        "confidence_breakdown": ex.get("confidence_breakdown") or metrics.get("confidence_breakdown"),
        "revenue_at_risk_2024_by_confidence": ex.get("revenue_at_risk_2024_by_confidence") or metrics.get("revenue_at_risk_2024_by_confidence"),
    }
    data_str = json.dumps(subset, indent=2)
    user = f"Report snapshot (relevant fields):\n{data_str}\n\nWhich charts should we include? Return JSON array only."
    try:
        if provider == "openai":
            raw = _call_openai(CHART_SPEC_PROMPT, user, model)
        else:
            raw = _call_gemini(CHART_SPEC_PROMPT, user, model)
        # Parse JSON array from response (handle markdown code blocks)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        ids = json.loads(raw)
        if isinstance(ids, list) and all(isinstance(x, str) for x in ids):
            return ids
    except Exception as e:
        logger.warning("Chart spec LLM failed, using defaults: %s", e)
    return []  # Fallback: generate all applicable in generate_charts
