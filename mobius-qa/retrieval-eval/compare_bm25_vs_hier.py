#!/usr/bin/env python3
"""
Per-question comparison report:
  - BM25 sentence retrieval (top-1 + top-10)
  - Hierarchical vector retrieval via Vertex (top-1 + top-10)

This is the "retrieval-only" report you asked for:
for every question, show what each method retrieved and whether the *right*
evidence (gold paragraph id) appears in top 1 / top 3 / top K.

Inputs:
  - questions YAML with gold.parent_metadata_ids (paragraph ids in published_rag_metadata)
  - BM25 run dir from bm25_eval.py (contains results.csv and per_question.csv)
  - Hierarchical run dir from retrieval_eval.py (contains results.csv)

Outputs (in out dir):
  - report.md (per-question, side-by-side)
  - summary.md (aggregate hit@k and hallucination-risk counts)
  - per_question_metrics.csv
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _as_list(x) -> list[str]:
    if x is None:
        return []
    if isinstance(x, str):
        return [x]
    if isinstance(x, list):
        return [str(i) for i in x if i]
    return [str(x)]


def _hit_rank(ids: list[str], gold_ids: set[str]) -> int | None:
    """Return 1-indexed rank of first gold id in ids."""
    for i, rid in enumerate(ids, start=1):
        if str(rid) in gold_ids:
            return i
    return None


def _md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(ROOT / "questions_generated.yaml"))
    ap.add_argument("--bm25-run-dir", required=True, help="Path to reports/bm25-eval-... directory")
    ap.add_argument("--hier-run-dir", required=True, help="Path to reports/retrieval-eval-... directory")
    ap.add_argument("--out-dir", default="", help="Output directory (default: alongside bm25 run)")
    ap.add_argument("--k", type=int, default=10, help="Top-K to show/evaluate")
    ap.add_argument("--hit-k", type=int, default=3, help="What counts as 'good' (top 2-3 answers)")
    ap.add_argument("--bm25-answer-threshold", type=float, default=0.65, help="If max_norm_score >= threshold => would answer")
    ap.add_argument("--hier-answer-threshold", type=float, default=0.88, help="If top1 similarity >= threshold => would answer")
    args = ap.parse_args()

    qdata = load_yaml(Path(args.questions))
    qs = qdata.get("questions") or []
    if not isinstance(qs, list) or not qs:
        raise SystemExit("questions file missing `questions: [...]`")

    q_by_id: dict[str, dict[str, Any]] = {str(q.get("id")): q for q in qs if q.get("id")}

    import pandas as pd

    bm25_dir = Path(args.bm25_run_dir).resolve()
    hier_dir = Path(args.hier_run_dir).resolve()
    bm25_results = pd.read_csv(bm25_dir / "results.csv")
    bm25_perq = pd.read_csv(bm25_dir / "per_question.csv")
    hier_results = pd.read_csv(hier_dir / "results.csv")

    # Keep only hierarchical mode for vector side
    if "mode" in hier_results.columns:
        hier_results = hier_results[hier_results["mode"] == "hier_only"].copy()

    k = int(args.k)
    hit_k = int(args.hit_k)

    # Build grouped views
    bm25_results = bm25_results[bm25_results["rank"] <= k].copy()
    hier_results = hier_results[hier_results["rank"] <= k].copy()

    bm25_group = {qid: df.sort_values("rank") for qid, df in bm25_results.groupby("qid")}
    hier_group = {qid: df.sort_values("rank") for qid, df in hier_results.groupby("qid")}
    bm25_pq = {str(r["qid"]): r for r in bm25_perq.to_dict(orient="records")}

    out_dir = Path(args.out_dir).resolve() if args.out_dir else (bm25_dir.parent / f"compare-{bm25_dir.name}-vs-{hier_dir.name}")
    _ensure_dir(out_dir)

    per_q_rows: list[dict[str, Any]] = []

    # Per-question report
    report_md = out_dir / "report.md"
    with open(report_md, "w") as f:
        f.write("## BM25 vs Hierarchical Retrieval — Per-question Report\n\n")
        f.write(f"- **questions**: `{Path(args.questions).resolve()}`\n")
        f.write(f"- **bm25_run_dir**: `{bm25_dir}`\n")
        f.write(f"- **hier_run_dir**: `{hier_dir}`\n")
        f.write(f"- **top_k_shown**: {k}\n")
        f.write(f"- **hit_k** (\"top 2-3 answers\") : {hit_k}\n\n")

        for qid in sorted(q_by_id.keys()):
            q = q_by_id[qid]
            intent = q.get("intent")
            bucket = q.get("bucket")
            question = q.get("question") or ""
            gold = q.get("gold") or {}
            gold_parents = set(_as_list(gold.get("parent_metadata_ids")))
            expect_in_manual = bool(gold.get("expect_in_manual", bucket != "out_of_manual"))

            bdf = bm25_group.get(qid)
            hdf = hier_group.get(qid)

            bm25_ids = [str(x) for x in (bdf["parent_metadata_id"].tolist() if bdf is not None and not bdf.empty else [])]
            hier_ids = [str(x) for x in (hdf["neighbor_id"].tolist() if hdf is not None and not hdf.empty else [])]

            bm25_rank = _hit_rank(bm25_ids, gold_parents) if gold_parents else None
            hier_rank = _hit_rank(hier_ids, gold_parents) if gold_parents else None

            bm25_top1_hit = bm25_rank == 1 if bm25_rank is not None else None
            hier_top1_hit = hier_rank == 1 if hier_rank is not None else None
            bm25_hit_at_k = (bm25_rank is not None and bm25_rank <= hit_k) if bm25_rank is not None else None
            hier_hit_at_k = (hier_rank is not None and hier_rank <= hit_k) if hier_rank is not None else None

            bm25_max_norm = float(bm25_pq.get(qid, {}).get("max_norm_score")) if qid in bm25_pq else None
            hier_top1_sim = None
            if hdf is not None and not hdf.empty and "similarity" in hdf.columns:
                try:
                    hier_top1_sim = float(hdf.iloc[0]["similarity"])
                except Exception:
                    hier_top1_sim = None

            bm25_would_answer = (bm25_max_norm is not None and bm25_max_norm >= float(args.bm25_answer_threshold))
            hier_would_answer = (hier_top1_sim is not None and hier_top1_sim >= float(args.hier_answer_threshold))

            # Hallucination risk: out-of-manual but "would answer"
            bm25_fp = (not expect_in_manual) and bm25_would_answer
            hier_fp = (not expect_in_manual) and hier_would_answer

            per_q_rows.append(
                {
                    "qid": qid,
                    "intent": intent,
                    "bucket": bucket,
                    "expect_in_manual": expect_in_manual,
                    "gold_parent_ids": ";".join(sorted(gold_parents)) if gold_parents else "",
                    "bm25_gold_rank": bm25_rank,
                    "bm25_hit_top1": bm25_top1_hit,
                    "bm25_hit_topk": bm25_hit_at_k,
                    "bm25_max_norm_score": bm25_max_norm,
                    "bm25_would_answer": bm25_would_answer,
                    "bm25_false_positive_answer": bm25_fp,
                    "hier_gold_rank": hier_rank,
                    "hier_hit_top1": hier_top1_hit,
                    "hier_hit_topk": hier_hit_at_k,
                    "hier_top1_similarity": hier_top1_sim,
                    "hier_would_answer": hier_would_answer,
                    "hier_false_positive_answer": hier_fp,
                }
            )

            f.write(f"### {qid} ({intent}, {bucket})\n\n")
            f.write(f"**Q**: {_md_escape(question)}\n\n")
            f.write(f"- **gold_parent_metadata_ids**: `{', '.join(sorted(gold_parents)) if gold_parents else '(none)'}`\n")
            f.write(f"- **expect_in_manual**: `{expect_in_manual}`\n")
            f.write(f"- **BM25**: gold_rank={bm25_rank} hit@{hit_k}={bm25_hit_at_k} max_norm={bm25_max_norm}\n")
            f.write(f"- **Hier**: gold_rank={hier_rank} hit@{hit_k}={hier_hit_at_k} top1_sim={hier_top1_sim}\n\n")

            # BM25 table
            f.write("#### BM25 (sentences)\n\n")
            f.write("| rank | norm_score | parent_metadata_id | page | sentence |\n")
            f.write("|---:|---:|---|---:|---|\n")
            if bdf is None or bdf.empty:
                f.write("| - | - | - | - | - |\n\n")
            else:
                for _, r in bdf.sort_values("rank").iterrows():
                    f.write(
                        f"| {int(r['rank'])} | {float(r['norm_score']):.3f} | `{r['parent_metadata_id']}` | "
                        f"{'' if pd.isna(r.get('page_number')) else int(r.get('page_number'))} | "
                        f"{_md_escape(str(r.get('sentence_text') or ''))} |\n"
                    )
                f.write("\n")

            # Hier table
            f.write("#### Hierarchical (Vertex)\n\n")
            f.write("| rank | similarity | neighbor_id | page | snippet |\n")
            f.write("|---:|---:|---|---:|---|\n")
            if hdf is None or hdf.empty:
                f.write("| - | - | - | - | - |\n\n")
            else:
                for _, r in hdf.sort_values("rank").iterrows():
                    sim = r.get("similarity")
                    sim_s = "" if pd.isna(sim) else f"{float(sim):.3f}"
                    page = r.get("page_number")
                    page_s = "" if pd.isna(page) else str(int(page))
                    f.write(
                        f"| {int(r['rank'])} | {sim_s} | `{r['neighbor_id']}` | {page_s} | "
                        f"{_md_escape(str(r.get('text_snippet') or ''))} |\n"
                    )
                f.write("\n")

    # Summary
    dfm = pd.DataFrame(per_q_rows)
    dfm.to_csv(out_dir / "per_question_metrics.csv", index=False)

    summary_md = out_dir / "summary.md"
    with open(summary_md, "w") as f:
        f.write("## BM25 vs Hierarchical — Summary\n\n")
        f.write(f"- **out_dir**: `{out_dir}`\n")
        f.write(f"- **top_k_shown**: {k}\n")
        f.write(f"- **hit_k**: {hit_k}\n")
        f.write(f"- **bm25_answer_threshold**: {float(args.bm25_answer_threshold)}\n")
        f.write(f"- **hier_answer_threshold**: {float(args.hier_answer_threshold)}\n\n")

        def rate(mask, denom: int) -> float:
            return float(mask.sum()) / float(denom) if denom else 0.0

        # Only questions with gold ids (exclude out-of-manual probes that have no gold paragraph)
        gold_col = dfm["gold_parent_ids"]
        has_gold = gold_col.notna() & (gold_col.astype(str).str.strip() != "") & (gold_col.astype(str).str.lower() != "nan")
        df_gold = dfm[has_gold].copy()

        f.write(f"- **questions_total**: {len(dfm)}\n")
        f.write(f"- **questions_with_gold**: {len(df_gold)}\n")
        f.write(f"- **questions_without_gold** (typically out-of-manual probes): {int((~has_gold).sum())}\n\n")

        for name, prefix in [("BM25", "bm25"), ("Hierarchical", "hier")]:
            r = df_gold[f"{prefix}_gold_rank"]
            hit1 = (r == 1)
            hitk = r.notna() & (r <= hit_k)
            missed = r.isna()
            f.write(f"### {name} (evaluated on questions_with_gold)\n\n")
            f.write(f"- **Hit@1**: {rate(hit1, len(df_gold)):.3f} ({int(hit1.sum())}/{len(df_gold)})\n")
            f.write(f"- **Hit@{hit_k}**: {rate(hitk, len(df_gold)):.3f} ({int(hitk.sum())}/{len(df_gold)})\n")
            f.write(f"- **Missed (no gold in top {k})**: {int(missed.sum())}/{len(df_gold)}\n\n")

        # Hallucination risk (out-of-manual false positives)
        is_out = ~dfm["expect_in_manual"].astype(bool)
        bm25_fp = is_out & dfm["bm25_false_positive_answer"].astype(bool)
        hier_fp = is_out & dfm["hier_false_positive_answer"].astype(bool)
        f.write("### Hallucination risk (out-of-manual but would answer)\n\n")
        out_n = int(is_out.sum())
        f.write(f"- **out_of_manual_questions**: {out_n}\n")
        f.write(f"- **BM25 false positives**: {int(bm25_fp.sum())}/{out_n}\n")
        f.write(f"- **Hier false positives**: {int(hier_fp.sum())}/{out_n}\n\n")

    print("Wrote:")
    print(f"  - {report_md}")
    print(f"  - {summary_md}")
    print(f"  - {out_dir/'per_question_metrics.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

