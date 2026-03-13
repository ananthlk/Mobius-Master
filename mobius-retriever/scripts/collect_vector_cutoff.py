#!/usr/bin/env python3
"""Collect vector similarity stats from eval questions and derive abstention cutoff.

Runs vector search (retrieve_path_b) on calibration questions, collects max similarity
per question by match_type, and derives abstention cutoff from out_of_manual p95.

Output: Updates configs/retrieval_cutoffs.yaml with vector section.
"""
from __future__ import annotations

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
        for k in ("CHAT_RAG_DATABASE_URL", "RAG_FILTER_AUTHORITY_LEVEL", "VERTEX_PROJECT", "VERTEX_REGION",
                  "VERTEX_INDEX_ENDPOINT_ID", "VERTEX_DEPLOYED_INDEX_ID"):
            v = vals.get(k, "")
            if v:
                os.environ[k] = str(v)
        if not os.environ.get("RAG_FILTER_AUTHORITY_LEVEL"):
            os.environ["RAG_FILTER_AUTHORITY_LEVEL"] = "contract_source_of_truth"


_load_env()

import yaml
from mobius_retriever.retriever import retrieve_path_b
from mobius_retriever.config import load_path_b_config


def _quantile(sorted_values: list[float], p: float) -> float:
    """Nearest-rank quantile. p in [0, 1]."""
    if not sorted_values:
        return 0.0
    p = max(0.0, min(1.0, p))
    idx = int(round(p * (len(sorted_values) - 1)))
    return sorted_values[idx]


def collect_vector_stats(questions_path: Path, config_path: Path) -> dict:
    """Run vector search on all questions, collect max similarity per question by match_type."""
    config = load_path_b_config(config_path)

    with open(questions_path) as f:
        data = yaml.safe_load(f) or {}
    questions = data.get("questions") or []

    max_sim_by_match: dict[str, list[float]] = {}
    all_sims: list[float] = []

    for q in questions:
        question = q.get("question", "")
        if not question.strip():
            continue
        match_type = (q.get("match_type") or "unknown").strip()
        if match_type not in max_sim_by_match:
            max_sim_by_match[match_type] = []

        result = retrieve_path_b(question=question, config_path=str(config_path), emitter=None)
        sims = [c.similarity for c in result.chunks if c.similarity is not None]
        if sims:
            max_sim = max(sims)
            max_sim_by_match[match_type].append(max_sim)
            all_sims.append(max_sim)

    match_stats: dict[str, dict] = {}
    for mt, vals in max_sim_by_match.items():
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

    oom = match_stats.get("out_of_manual", {})
    abstention_cutoff = oom.get("p95", 0.5) if oom.get("count", 0) > 0 else 0.5

    return {
        "questions_run": len([q for q in questions if (q.get("question") or "").strip()]),
        "match_type_stats": match_stats,
        "abstention_cutoff": round(abstention_cutoff, 4),
        "max_sims_by_match": max_sim_by_match,
        "all_sims": all_sims,
    }


def _plot_vector_distribution(stats: dict, cutoff: float, out_path: Path) -> None:
    """Plot histogram of max similarity by match_type."""
    import matplotlib.pyplot as plt

    max_sims_by_match = stats.get("max_sims_by_match", {})
    if not max_sims_by_match:
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = {"perfect_match": "green", "conceptual": "blue", "out_of_manual": "red", "unknown": "gray"}
    for mt, vals in max_sims_by_match.items():
        if vals:
            ax.hist(vals, bins=15, alpha=0.6, label=mt, color=colors.get(mt, "gray"), edgecolor="black")
    ax.axvline(cutoff, color="red", linestyle="--", linewidth=2, label=f"cutoff={cutoff:.3f}")
    ax.set_xlabel("Max similarity per question")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of vector max similarity by match_type")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--questions",
        default="",
        help="Path to eval questions YAML (default: eval_questions_calibration.yaml)",
    )
    ap.add_argument("--plot", action="store_true", help="Generate vector similarity distribution plot")
    args = ap.parse_args()

    retriever_root = Path(__file__).resolve().parent.parent
    questions_path = Path(args.questions) if args.questions.strip() else retriever_root / "eval_questions_calibration.yaml"
    if not questions_path.is_absolute():
        questions_path = (retriever_root / questions_path).resolve()
    config_path = retriever_root / "configs" / "path_b_v1.yaml"
    cutoffs_path = retriever_root / "configs" / "retrieval_cutoffs.yaml"

    if not questions_path.exists():
        print(f"Questions not found: {questions_path}", file=sys.stderr)
        return 1
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1

    print(f"Collecting vector similarity stats from {questions_path}...", flush=True)
    stats = collect_vector_stats(questions_path, config_path)

    cutoffs: dict = {}
    if cutoffs_path.exists():
        with open(cutoffs_path) as f:
            cutoffs = yaml.safe_load(f) or {}
    cutoffs["version"] = "1"
    cutoffs["vector"] = {
        "abstention_cutoff": stats["abstention_cutoff"],
        "source_questions": str(questions_path.name),
        "questions_run": stats["questions_run"],
        "stats": {"match_type_stats": stats["match_type_stats"]},
    }

    cutoffs_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cutoffs_path, "w") as f:
        yaml.dump(cutoffs, f, default_flow_style=False, sort_keys=False)

    print(f"Wrote {cutoffs_path}", flush=True)

    print("\n--- Vector distribution by match_type ---", flush=True)
    for mt, s in stats.get("match_type_stats", {}).items():
        if s.get("count", 0) > 0:
            print(f"  {mt}: n={s['count']} min={s['min']} p50={s['p50']} p95={s['p95']} max={s['max']}", flush=True)
        else:
            print(f"  {mt}: n=0", flush=True)

    print(f"\n--- Vector abstention cutoff (from out_of_manual p95): {stats['abstention_cutoff']} ---", flush=True)

    if getattr(args, "plot", False):
        plot_path = retriever_root / "reports" / "vector_similarity_distribution.png"
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        _plot_vector_distribution(stats, stats["abstention_cutoff"], plot_path)
        print(f"\nPlot saved to {plot_path}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
