#!/usr/bin/env python3
"""Collect BM25 score stats from eval questions and write sigmoid config.

This is the calibration/eval layer: it runs BM25 on eval questions, collects
raw_score distributions per provision_type (paragraph, sentence), derives
sigmoid parameters (k, x0), and writes a config YAML. The retriever reads
this config when applying normalization.

Output: configs/bm25_sigmoid.yaml with bounds and sigmoid params per provision_type.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

# Add src to path
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _load_env() -> None:
    import os
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    root = Path(__file__).resolve().parent.parent.parent
    chat_env = root / "mobius-chat" / ".env"
    if chat_env.exists():
        vals = dotenv_values(chat_env)
        for k in ("CHAT_RAG_DATABASE_URL", "RAG_FILTER_AUTHORITY_LEVEL"):
            v = vals.get(k, "")
            if v:
                os.environ[k] = str(v)
        if not os.environ.get("RAG_FILTER_AUTHORITY_LEVEL"):
            os.environ["RAG_FILTER_AUTHORITY_LEVEL"] = "contract_source_of_truth"


_load_env()

import yaml
from mobius_retriever.bm25_search import bm25_search
from mobius_retriever.config import load_path_b_config
from mobius_retriever.jpd_tagger import tag_question_and_resolve_document_ids


def _n_tags_from_jpd(jpd) -> int:
    """Count distinct J/P/D tags matched. Used for score-per-tag normalization."""
    return len(jpd.p_tags or {}) + len(jpd.d_tags or {}) + len(jpd.j_tags or {})


def _quantile(sorted_values: list[float], p: float) -> float:
    """Nearest-rank quantile. p in [0, 1]."""
    if not sorted_values:
        return 0.0
    p = max(0.0, min(1.0, p))
    idx = int(round(p * (len(sorted_values) - 1)))
    return sorted_values[idx]


def _sigmoid_params_from_bounds(score_low: float, score_high: float, target_low: float = 0.1, target_high: float = 0.9) -> tuple[float, float]:
    """
    Derive sigmoid (k, x0) so that:
      sigmoid(k * (score_low - x0)) ≈ target_low
      sigmoid(k * (score_high - x0)) ≈ target_high

    Using logit: logit(p) = log(p / (1-p))
    We want: k * (score_high - x0) = logit(target_high), k * (score_low - x0) = logit(target_low)
    Solving: k = (logit(high) - logit(low)) / (score_high - score_low), x0 = score_high - logit(high)/k
    """
    if abs(score_high - score_low) < 1e-9:
        return (1.0, score_low)

    def logit(p: float) -> float:
        p = min(1 - 1e-6, max(1e-6, p))
        return math.log(p / (1 - p))

    a = logit(target_high)
    b = logit(target_low)
    k_val = (a - b) / (score_high - score_low)
    x0 = score_high - a / k_val
    return (float(k_val), float(x0))


def _histogram_bins(vals: list[float], num_bins: int = 10) -> list[tuple[float, float, int]]:
    """Return (bin_lo, bin_hi, count) for histogram."""
    if not vals or num_bins < 1:
        return []
    vmin, vmax = min(vals), max(vals)
    if vmax <= vmin:
        return [(vmin, vmax, len(vals))]
    step = (vmax - vmin) / num_bins
    bins: list[tuple[float, float, int]] = []
    for i in range(num_bins):
        lo = vmin + i * step
        hi = vmin + (i + 1) * step
        count = sum(1 for v in vals if lo <= v < hi) if i < num_bins - 1 else sum(1 for v in vals if lo <= v <= hi)
        bins.append((round(lo, 2), round(hi, 2), count))
    return bins


def collect_stats(questions_path: Path, config_path: Path, top_k_per_question: int = 50) -> dict:
    """Run BM25 on all questions, collect score-per-tag by provision_type and match_type.

    Score-per-tag: raw_bm25 / max(1, n_tags_matched). When JPD matches 0 tags, uses raw as-is.
    This normalizes by query specificity so calibration is comparable across tag counts.
    """
    config = load_path_b_config(config_path)
    auth_level = config.filters.document_authority_level or "contract_source_of_truth"
    rag_url = (config.rag_database_url or config.postgres_url or "").strip()
    postgres_url = (config.postgres_url or "").strip()

    with open(questions_path) as f:
        data = yaml.safe_load(f) or {}
    questions = data.get("questions") or []

    scores_by_type: dict[str, list[float]] = {"paragraph": [], "sentence": []}
    scores_by_match: dict[str, list[float]] = {}
    scores_by_match_and_tags: dict[tuple[str, int], list[float]] = {}
    scores_by_n_tags: dict[int, list[float]] = {}  # n_tags in query -> adjusted scores
    query_count_by_n_tags: dict[int, int] = {}  # n_tags in query -> how many questions

    for q in questions:
        question = q.get("question", "")
        if not question.strip():
            continue
        match_type = (q.get("match_type") or "unknown").strip()
        if match_type not in scores_by_match:
            scores_by_match[match_type] = []

        # JPD tagger for document_ids and n_tags (score-per-tag denominator)
        document_ids = None
        n_tags = 0
        if rag_url:
            jpd = tag_question_and_resolve_document_ids(question, rag_url, emitter=None)
            n_tags = _n_tags_from_jpd(jpd)
            if jpd.has_document_ids:
                document_ids = jpd.document_ids

        chunks = bm25_search(
            question=question,
            postgres_url=postgres_url,
            authority_level=auth_level,
            document_ids=document_ids,
            top_k=top_k_per_question,
            include_paragraphs=True,
            top_k_per_type=top_k_per_question,
            emitter=None,
        )
        divisor = max(1, n_tags)
        key_mt_tags = (match_type, n_tags)
        if key_mt_tags not in scores_by_match_and_tags:
            scores_by_match_and_tags[key_mt_tags] = []
        query_count_by_n_tags[n_tags] = query_count_by_n_tags.get(n_tags, 0) + 1
        if n_tags not in scores_by_n_tags:
            scores_by_n_tags[n_tags] = []
        for c in chunks:
            raw = c.get("raw_score")
            if raw is not None:
                adjusted = float(raw) / divisor  # normalize by n_tags in query
                pt = c.get("provision_type", "sentence")
                if pt in scores_by_type:
                    scores_by_type[pt].append(adjusted)
                scores_by_match[match_type].append(adjusted)
                scores_by_match_and_tags[key_mt_tags].append(adjusted)
                scores_by_n_tags[n_tags].append(adjusted)

    out: dict[str, dict] = {}
    for pt, vals in scores_by_type.items():
        if not vals:
            out[pt] = {"count": 0, "min": 0, "max": 0, "p5": 0, "p50": 0, "p95": 0, "k": 1.0, "x0": 0.0}
            continue
        srt = sorted(vals)
        p5 = _quantile(srt, 0.05)
        p50 = _quantile(srt, 0.50)
        p95 = _quantile(srt, 0.95)
        vmin = min(vals)
        vmax = max(vals)
        k, x0 = _sigmoid_params_from_bounds(p5, p95, target_low=0.05, target_high=0.95)
        out[pt] = {
            "count": len(vals),
            "min": round(vmin, 4),
            "max": round(vmax, 4),
            "p5": round(p5, 4),
            "p50": round(p50, 4),
            "p95": round(p95, 4),
            "k": round(k, 6),
            "x0": round(x0, 6),
        }

    # Distribution by match_type
    match_stats: dict[str, dict] = {}
    for mt, vals in scores_by_match.items():
        if vals:
            srt = sorted(vals)
            match_stats[mt] = {
                "count": len(vals),
                "min": round(min(vals), 4),
                "max": round(max(vals), 4),
                "p5": round(_quantile(srt, 0.05), 4),
                "p50": round(_quantile(srt, 0.50), 4),
                "p95": round(_quantile(srt, 0.95), 4),
            }
        else:
            match_stats[mt] = {"count": 0}

    # Good (perfect_match + conceptual) vs out_of_manual combined
    good_vals = (scores_by_match.get("perfect_match") or []) + (scores_by_match.get("conceptual") or [])
    good_combined: dict = {}
    if good_vals:
        srt = sorted(good_vals)
        good_combined = {
            "count": len(good_vals),
            "min": round(min(good_vals), 4),
            "max": round(max(good_vals), 4),
            "p5": round(_quantile(srt, 0.05), 4),
            "p50": round(_quantile(srt, 0.50), 4),
            "p95": round(_quantile(srt, 0.95), 4),
        }

    # Distribution by (match_type, n_tags)
    match_and_tags_stats: dict[str, dict] = {}
    for (mt, nt), vals in sorted(scores_by_match_and_tags.items(), key=lambda x: (x[0][0], x[0][1])):
        if vals:
            srt = sorted(vals)
            match_and_tags_stats[f"{mt}_n{nt}"] = {
                "count": len(vals),
                "min": round(min(vals), 4),
                "max": round(max(vals), 4),
                "p5": round(_quantile(srt, 0.05), 4),
                "p50": round(_quantile(srt, 0.50), 4),
                "p95": round(_quantile(srt, 0.95), 4),
            }

    # Histogram for combined scores (sentence = primary for BM25)
    all_scores = scores_by_type.get("sentence", []) or scores_by_type.get("paragraph", [])
    hist = _histogram_bins(all_scores, 10) if all_scores else []

    # Distribution by n_tags in query only (how many queries, score-per-tag stats)
    n_tags_stats: dict[int, dict] = {}
    for nt in sorted(scores_by_n_tags.keys()):
        vals = scores_by_n_tags[nt]
        if vals:
            srt = sorted(vals)
            n_tags_stats[nt] = {
                "queries": query_count_by_n_tags.get(nt, 0),
                "chunks": len(vals),
                "min": round(min(vals), 4),
                "max": round(max(vals), 4),
                "p5": round(_quantile(srt, 0.05), 4),
                "p50": round(_quantile(srt, 0.50), 4),
                "p95": round(_quantile(srt, 0.95), 4),
            }

    return {
        "provision_types": out,
        "questions_run": len(questions),
        "match_type_stats": match_stats,
        "good_combined": good_combined,
        "match_and_tags_stats": match_and_tags_stats,
        "n_tags_stats": n_tags_stats,
        "query_count_by_n_tags": query_count_by_n_tags,
        "distribution_histogram": [{"bin_lo": lo, "bin_hi": hi, "count": c} for lo, hi, c in hist],
        "raw_scores": {k: v for k, v in scores_by_type.items() if v},
    }


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def apply_normalize(raw_score: float, provision_type: str, cfg: dict) -> float:
    """Apply sigmoid normalization using config. Returns value in [0, 1]."""
    pt = cfg.get("provision_types", {}).get(provision_type, {})
    k = pt.get("k", 1.0)
    x0 = pt.get("x0", 0.0)
    return _sigmoid(k * (raw_score - x0))


def _plot_distribution_and_sigmoid(stats: dict, cfg: dict, out_path: Path) -> None:
    """Plot histogram of raw scores and sigmoid transformation curve."""
    import matplotlib.pyplot as plt
    import numpy as np

    raw_scores = stats.get("raw_scores", {})
    sentence_scores = raw_scores.get("sentence", [])
    paragraph_scores = raw_scores.get("paragraph", [])
    all_raw = sentence_scores or paragraph_scores
    if not all_raw:
        return

    pt = "sentence" if sentence_scores else "paragraph"
    params = cfg.get("provision_types", {}).get(pt, {})
    k = params.get("k", 1.0)
    x0 = params.get("x0", 0.0)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), height_ratios=[1, 1])

    # 1. Histogram of raw scores
    ax1.hist(all_raw, bins=20, edgecolor="black", alpha=0.7)
    ax1.axvline(x0, color="red", linestyle="--", label=f"x0={x0:.2f} (sigmoid center)")
    s = cfg.get("stats", {}).get(pt, {})
    if s:
        ax1.axvline(s.get("p5"), color="gray", linestyle=":", alpha=0.8, label=f"p5={s.get('p5', 0):.2f}")
        ax1.axvline(s.get("p95"), color="gray", linestyle=":", alpha=0.8, label=f"p95={s.get('p95', 0):.2f}")
    ax1.set_xlabel("BM25 raw score")
    ax1.set_ylabel("Count")
    ax1.set_title("Distribution of BM25 raw scores")
    ax1.legend()

    # 2. Sigmoid curve + scatter of (raw, norm) for each score
    x_smooth = np.linspace(min(all_raw) - 2, max(all_raw) + 2, 200)
    y_smooth = [1 / (1 + np.exp(-k * (x - x0))) for x in x_smooth]
    ax2.plot(x_smooth, y_smooth, "b-", linewidth=2, label="sigmoid(raw)")

    # Scatter: each raw score -> its sigmoid value
    norms = [_sigmoid(k * (r - x0)) for r in all_raw]
    ax2.scatter(all_raw, norms, alpha=0.3, s=10, c="green", label="data points")

    ax2.axhline(0.05, color="gray", linestyle=":", alpha=0.6)
    ax2.axhline(0.95, color="gray", linestyle=":", alpha=0.6)
    ax2.set_xlabel("BM25 raw score")
    ax2.set_ylabel("Sigmoid (normalized)")
    ax2.set_title("Sigmoid mapping: raw -> [0, 1]")
    ax2.legend()
    ax2.set_ylim(-0.05, 1.05)
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def test_config(out_path: Path) -> bool:
    """Load config and verify sigmoid maps sample scores to [0,1]. Returns True if OK."""
    import yaml as _yaml
    with open(out_path) as f:
        cfg = _yaml.safe_load(f)
    ok = True
    for pt in ("paragraph", "sentence"):
        s = cfg.get("stats", {}).get(pt, {})
        low, high = s.get("p5", 10), s.get("p95", 30)
        for raw in [low - 5, low, (low + high) / 2, high, high + 10]:
            norm = apply_normalize(raw, pt, cfg)
            if not (0 <= norm <= 1):
                print(f"  FAIL {pt} raw={raw:.2f} -> norm={norm:.4f} (expected [0,1])")
                ok = False
            else:
                print(f"  OK   {pt} raw={raw:.2f} -> norm={norm:.4f}")
    return ok


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="Test sigmoid on config (run after collect)")
    ap.add_argument(
        "--questions",
        default="",
        help="Path to eval questions YAML (default: eval_questions_calibration.yaml for calibration)",
    )
    ap.add_argument("--plot", action="store_true", help="Generate histogram + sigmoid plot")
    ap.add_argument(
        "--top-k",
        type=int,
        default=50,
        help="Docs retrieved per question (paragraph + sentence each). Default 50 for calibration.",
    )
    args = ap.parse_args()

    retriever_root = Path(__file__).resolve().parent.parent
    out_path = retriever_root / "configs" / "bm25_sigmoid.yaml"

    if args.test:
        if not out_path.exists():
            print(f"Config not found: {out_path}. Run without --test first.", file=sys.stderr)
            return 1
        print("Testing sigmoid normalization...")
        return 0 if test_config(out_path) else 1

    questions_path = Path(args.questions) if args.questions.strip() else retriever_root / "eval_questions_calibration.yaml"
    if not questions_path.is_absolute():
        questions_path = (retriever_root / questions_path).resolve()
    config_path = retriever_root / "configs" / "path_b_v1.yaml"

    if not questions_path.exists():
        print(f"Questions not found: {questions_path}", file=sys.stderr)
        return 1
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1

    top_k = max(1, min(200, getattr(args, "top_k", 50)))
    print(f"Collecting BM25 score stats from {questions_path} (top_k={top_k})...", flush=True)
    stats = collect_stats(questions_path, config_path, top_k_per_question=top_k)

    # Build config for retriever consumption
    cfg = {
        "version": "1",
        "description": "BM25 score-per-tag -> [0,1] sigmoid. raw/max(1,n_tags) before sigmoid.",
        "score_per_tag_normalization": True,
        "source_questions": str(questions_path.name),
        "questions_run": stats.get("questions_run", 0),
        "provision_types": {},
        "stats": {},
    }
    for pt, s in stats["provision_types"].items():
        cfg["provision_types"][pt] = {"k": s["k"], "x0": s["x0"], "low": s["p5"], "high": s["p95"]}
        cfg["stats"][pt] = {k: v for k, v in s.items() if k in ("count", "min", "max", "p5", "p50", "p95")}

    cfg["abstention_cutoff_normalized"] = 0.5
    oom = stats.get("match_type_stats", {}).get("out_of_manual", {})
    if oom.get("count", 0) > 0 and "p95" in oom:
        cfg["abstention_cutoff_raw"] = round(oom["p95"], 4)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

    print(f"Wrote {out_path}", flush=True)

    # Write/merge retrieval_cutoffs.yaml with bm25 section
    cutoffs_path = retriever_root / "configs" / "retrieval_cutoffs.yaml"
    cutoffs: dict = {}
    if cutoffs_path.exists():
        with open(cutoffs_path) as f:
            cutoffs = yaml.safe_load(f) or {}
    cutoffs["version"] = "1"
    cutoffs.setdefault("bm25", {})["abstention_cutoff_normalized"] = 0.5
    if oom.get("count", 0) > 0 and "p95" in oom:
        cutoffs["bm25"]["abstention_cutoff_raw"] = round(oom["p95"], 4)
    cutoffs["bm25"]["source_questions"] = str(questions_path.name)
    cutoffs["bm25"]["questions_run"] = stats.get("questions_run", 0)
    with open(cutoffs_path, "w") as f:
        yaml.dump(cutoffs, f, default_flow_style=False, sort_keys=False)
    print(f"Wrote {cutoffs_path}", flush=True)

    # Distribution summary
    print("\n--- n_tags IN QUERY (JPD tags matched per question) ---", flush=True)
    print("  Formula: adjusted_score = raw_bm25 / max(1, n_tags)  [already applied below]", flush=True)
    print("  n_tags = len(p_tags) + len(d_tags) + len(j_tags) from lexicon match", flush=True)
    qcnt = stats.get("query_count_by_n_tags", {})
    for nt in sorted(qcnt.keys()):
        print(f"  n_tags={nt}: {qcnt[nt]} questions", flush=True)

    print("\n--- Score-per-tag (raw/n_tags) by n_tags IN QUERY ---", flush=True)
    for nt in sorted(stats.get("n_tags_stats", {}).keys()):
        s = stats["n_tags_stats"][nt]
        print(f"  n_tags={nt}: {s['queries']} questions, {s['chunks']} chunks | min={s['min']} p50={s['p50']} p95={s['p95']} max={s['max']}", flush=True)

    print("\n--- GOOD vs OUT-OF-SYLLABUS ---", flush=True)
    mt_stats = stats.get("match_type_stats", {})
    good = stats.get("good_combined", {})
    oom = mt_stats.get("out_of_manual", {})
    pm = mt_stats.get("perfect_match", {})
    cc = mt_stats.get("conceptual", {})
    print("  GOOD (we want these to pass cutoff):", flush=True)
    if good.get("count", 0):
        print(f"    combined (perfect_match+conceptual): n={good['count']} | p5={good.get('p5')} p50={good.get('p50')} p95={good.get('p95')}", flush=True)
    if pm.get("count", 0):
        print(f"    perfect_match: n={pm['count']} | p5={pm.get('p5')} p50={pm.get('p50')} p95={pm.get('p95')}", flush=True)
    if cc.get("count", 0):
        print(f"    conceptual:    n={cc['count']} | p5={cc.get('p5')} p50={cc.get('p50')} p95={cc.get('p95')}", flush=True)
    print("  OUT-OF-SYLLABUS (we want these to fail / abstain):", flush=True)
    if oom.get("count", 0):
        print(f"    out_of_manual: n={oom['count']} | p5={oom.get('p5')} p50={oom.get('p50')} p95={oom.get('p95')}", flush=True)
        oom_p95 = oom.get("p95")
        good_p5 = good.get("p5")
        if oom_p95 is not None and good_p5 is not None:
            if good_p5 > oom_p95:
                print(f"  >>> SEPARABLE: cutoff in ]{oom_p95}, {good_p5}[ keeps good, drops out-of-syllabus.", flush=True)
            else:
                print(f"  >>> OVERLAP: good p5 ({good_p5}) <= out_of_manual p95 ({oom_p95}). Both occupy similar score range—tradeoff: higher cutoff drops bad but also some good.", flush=True)
    else:
        print("    (no out_of_manual in calibration)", flush=True)

    print("\n--- Distribution by match_type ---", flush=True)
    for mt, s in stats.get("match_type_stats", {}).items():
        if s.get("count", 0) > 0:
            print(f"  {mt}: n={s['count']} min={s['min']} p50={s['p50']} p95={s['p95']} max={s['max']}", flush=True)
        else:
            print(f"  {mt}: n=0", flush=True)

    print("\n--- Distribution by (match_type, n_tags) — n = chunk count ---", flush=True)
    for key in sorted(stats.get("match_and_tags_stats", {}).keys()):
        s = stats["match_and_tags_stats"][key]
        if s.get("count", 0) > 0:
            print(f"  {key}: n={s['count']} min={s['min']} p50={s['p50']} p95={s['p95']} max={s['max']}", flush=True)

    print("\n--- Histogram (sentence scores) ---", flush=True)
    for h in stats.get("distribution_histogram", [])[:12]:
        bar = "#" * min(50, h["count"]) + f" {h['count']}"
        print(f"  [{h['bin_lo']:.1f}-{h['bin_hi']:.1f}] {bar}", flush=True)

    print("\n--- Sigmoid params ---", flush=True)
    print(json.dumps({k: v for k, v in stats["provision_types"].items()}, indent=2), flush=True)

    if getattr(args, "plot", False):
        plot_path = retriever_root / "reports" / "bm25_sigmoid_distribution.png"
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        _plot_distribution_and_sigmoid(stats, cfg, plot_path)
        print(f"\nPlot saved to {plot_path}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
