#!/usr/bin/env python3
"""
BM25 sentence-candidate retrieval eval (retrieval-only, pre-rerank).

Goal:
- Build a sentence-level candidate set from the Sunshine manual (published_rag_metadata)
- Retrieve top-K with BM25 for each question
- Normalize scores with a sigmoid (confidence proxy)
- Evaluate whether the gold evidence/answer is in top-K (and where)
- Penalize "confident retrieval" on out-of-manual questions (hallucination risk)

Gold labeling strategy (questions.yaml):
- Factual: provide gold.answer_contains[] and/or gold.answer_regex
- Canonical: provide gold.crux_contains[] (2-3 lines/phrases) and/or gold.parent_metadata_ids[]
- Out-of-manual: set bucket=out_of_manual (or gold.expect_in_manual=false) so correct behavior is abstain
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def load_questions(path: Path) -> list[dict[str, Any]]:
    data = load_yaml(path)
    qs = data.get("questions") or []
    if not isinstance(qs, list):
        raise ValueError("questions.yaml must have top-level `questions: [...]`")
    return qs


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _tokenize(text: str) -> list[str]:
    # Keep digits for phone numbers; drop punctuation.
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _split_sentences(text: str) -> list[str]:
    """
    Lightweight sentence splitter.
    We bias towards splitting enough to make 'atomics' without heavy NLP deps.
    """
    if not (text or "").strip():
        return []
    t = re.sub(r"\s+", " ", text.strip())
    # Split on punctuation with whitespace after, but keep abbreviations moderately intact.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", t)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Further split long "sentences" on semicolons / bullets.
        if len(p) > 420:
            sub = re.split(r"\s*;\s*|\s+\u2022\s+|\s+\-\s+", p)
            out.extend([s.strip() for s in sub if s.strip()])
        else:
            out.append(p)
    return out


@dataclass(frozen=True)
class SentenceDoc:
    # Stable sentence id for output (not used for joining to DB)
    sid: str
    parent_metadata_id: str
    sentence_text: str
    page_number: int | None
    section_path: str | None
    chapter_path: str | None
    document_display_name: str | None


def _fetch_sunshine_paragraphs(
    chat_db_url: str,
    authority_level: str,
    generator_id: str | None,
) -> list[dict[str, Any]]:
    import psycopg2
    import psycopg2.extras

    where = ["document_authority_level = %s", "source_type = 'hierarchical'"]
    params: list[Any] = [authority_level]
    if generator_id:
        # Back-compat: many rows may have generator_id NULL. If caller requests a generator_id,
        # include NULL rows too (so we don't silently return an empty corpus).
        where.append("(generator_id = %s OR generator_id IS NULL)")
        params.append(generator_id)

    sql = f"""
      SELECT
        id,
        text,
        page_number,
        section_path,
        chapter_path,
        document_display_name
      FROM published_rag_metadata
      WHERE {' AND '.join(where)}
      ORDER BY page_number NULLS LAST, paragraph_index NULLS LAST, id
    """

    conn = psycopg2.connect(chat_db_url)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _build_sentence_corpus(paragraph_rows: list[dict[str, Any]]) -> list[SentenceDoc]:
    corpus: list[SentenceDoc] = []
    for r in paragraph_rows:
        pid = str(r.get("id"))
        txt = (r.get("text") or "").strip()
        if not txt:
            continue
        sents = _split_sentences(txt)
        for i, s in enumerate(sents):
            sid = f"{pid}#s{i}"
            corpus.append(
                SentenceDoc(
                    sid=sid,
                    parent_metadata_id=pid,
                    sentence_text=s,
                    page_number=r.get("page_number"),
                    section_path=r.get("section_path"),
                    chapter_path=r.get("chapter_path"),
                    document_display_name=r.get("document_display_name"),
                )
            )
    return corpus


def _sigmoid(x: float) -> float:
    # numerically stable sigmoid
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _sigmoid_normalize(scores: list[float], k: float, x0: float) -> list[float]:
    return [_sigmoid(k * (float(s) - x0)) for s in scores]


def _sigmoid_params_from_topk(raw_scores: list[float], target_top: float = 0.95, target_k: float = 0.50) -> tuple[float, float]:
    """
    Auto-calibrate sigmoid per-query to make:
      - top score map to ~target_top
      - kth score (last in list) map to ~target_k
    This is monotonic and yields comparable [0,1] "confidence" across queries.
    """
    if not raw_scores:
        return (1.0, 0.0)
    s_hi = float(raw_scores[0])
    s_lo = float(raw_scores[-1])
    if abs(s_hi - s_lo) < 1e-9:
        return (1.0, s_hi)

    # Solve:
    #   sigmoid(k*(s_hi-x0)) = target_top
    #   sigmoid(k*(s_lo-x0)) = target_k
    # Let a = logit(target_top), b = logit(target_k)
    def logit(p: float) -> float:
        p = min(1 - 1e-6, max(1e-6, p))
        return math.log(p / (1 - p))

    a = logit(target_top)
    b = logit(target_k)
    k_val = (a - b) / (s_hi - s_lo)
    x0 = s_hi - a / k_val
    return (k_val, x0)


def _sigmoid_params_from_max_raw(max_raw_scores: list[float]) -> tuple[float, float]:
    """
    Compute a *global* sigmoid (k, x0) from the distribution of per-question max BM25 scores.

    We map:
      - Q25(max_raw) -> ~0.25
      - Q75(max_raw) -> ~0.75

    This produces meaningful cross-question normalized scores for thresholding/abstention.
    """
    if not max_raw_scores:
        return (1.0, 0.0)
    xs = sorted(float(x) for x in max_raw_scores)
    if len(xs) < 4:
        # fallback: center at median, mild slope
        mid = xs[len(xs) // 2]
        return (1.0, mid)

    def q(p: float) -> float:
        # simple nearest-rank quantile
        p = max(0.0, min(1.0, p))
        idx = int(round(p * (len(xs) - 1)))
        return xs[idx]

    q25 = q(0.25)
    q75 = q(0.75)
    if abs(q75 - q25) < 1e-9:
        return (1.0, q(0.50))

    # Want sigmoid(k*(q75-x0))=0.75 and sigmoid(k*(q25-x0))=0.25
    # => k*(q75-x0)=logit(0.75)=a and k*(q25-x0)=logit(0.25)=-a
    a = math.log(0.75 / 0.25)
    x0 = (q25 + q75) / 2.0
    k_val = (2.0 * a) / (q75 - q25)
    return (k_val, x0)


def _gold_expect_in_manual(q: dict[str, Any]) -> bool:
    b = (q.get("bucket") or "").strip().lower()
    g = q.get("gold") or {}
    if isinstance(g, dict) and "expect_in_manual" in g:
        return bool(g.get("expect_in_manual"))
    return b != "out_of_manual"


def _gold_match_candidate(q: dict[str, Any], cand: SentenceDoc) -> dict[str, Any]:
    """
    Returns match info dict:
      { matched: bool, why: str | None }
    """
    g = q.get("gold") or {}
    if not isinstance(g, dict):
        return {"matched": False, "why": None}

    # 1) Parent paragraph id(s) (strongest)
    parent_ids = g.get("parent_metadata_ids") or []
    if isinstance(parent_ids, str):
        parent_ids = [parent_ids]
    if isinstance(parent_ids, list) and parent_ids:
        if cand.parent_metadata_id in {str(x) for x in parent_ids if x}:
            return {"matched": True, "why": "parent_metadata_id"}

    # 2) Substring evidence (answer/crux lines)
    hay = (cand.sentence_text or "").lower()
    contains = []
    for key in ("answer_contains", "crux_contains"):
        v = g.get(key)
        if isinstance(v, str) and v.strip():
            contains.append(v.strip())
        elif isinstance(v, list):
            contains.extend([str(x).strip() for x in v if str(x).strip()])
    for needle in contains:
        if needle.lower() in hay:
            return {"matched": True, "why": f"contains:{needle[:48]}"}

    # 3) Regex evidence
    rx = g.get("answer_regex")
    if isinstance(rx, str) and rx.strip():
        try:
            if re.search(rx, cand.sentence_text or "", flags=re.IGNORECASE):
                return {"matched": True, "why": "answer_regex"}
        except re.error:
            pass

    return {"matched": False, "why": None}


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _plot(df, out_dir: Path) -> list[Path]:
    import matplotlib.pyplot as plt

    written: list[Path] = []
    if df.empty:
        return written

    # Max normalized score distributions by bucket
    if "max_norm_score" in df.columns and "bucket" in df.columns:
        fig = plt.figure(figsize=(10, 6))
        for bucket in sorted(df["bucket"].dropna().unique().tolist()):
            sub = df[(df["bucket"] == bucket) & df["max_norm_score"].notna()]
            if sub.empty:
                continue
            x = sub["max_norm_score"].astype(float).tolist()
            if not x:
                continue
            xmin, xmax = min(x), max(x)
            bins = 30 if xmax > xmin else 1
            plt.hist(x, bins=bins, alpha=0.5, label=bucket)
        plt.title("BM25 sigmoid-normalized max score distribution")
        plt.xlabel("max_norm_score")
        plt.ylabel("count")
        plt.legend()
        p = out_dir / "bm25_max_norm_score_hist_by_bucket.png"
        fig.tight_layout()
        fig.savefig(p, dpi=150)
        plt.close(fig)
        written.append(p)

    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--questions", default=str(ROOT / "questions.yaml"))
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument(
        "--generator-id",
        default="",
        help="Optional: filter corpus by generator_id (also includes NULL rows for back-compat)",
    )
    ap.add_argument("--abstain-threshold", type=float, default=0.65, help="If max_norm_score < threshold => abstain")
    ap.add_argument(
        "--sigmoid-mode",
        choices=["global_max_raw", "auto_topk", "fixed"],
        default="global_max_raw",
        help="How to map BM25 raw scores -> [0,1] confidence",
    )
    ap.add_argument("--sigmoid-k", type=float, default=1.0, help="fixed mode: k")
    ap.add_argument("--sigmoid-x0", type=float, default=0.0, help="fixed mode: x0")
    ap.add_argument(
        "--authority-level",
        default="",
        help="Override config: filter corpus by this document_authority_level (e.g. contract_source_of_truth)",
    )
    args = ap.parse_args()

    cfg = load_yaml(Path(args.config))
    filters = (cfg.get("filters") or {}) if isinstance(cfg.get("filters"), dict) else {}
    authority_level = (args.authority_level or "").strip() or filters.get("document_authority_level") or ""
    if not authority_level:
        raise SystemExit("config.filters.document_authority_level or --authority-level must be set")

    chat_db_url = os.getenv("CHAT_RAG_DATABASE_URL") or os.getenv("CHAT_DATABASE_URL")
    if not chat_db_url:
        raise SystemExit("Set CHAT_DATABASE_URL (or CHAT_RAG_DATABASE_URL) to read published_rag_metadata.")

    qs = load_questions(Path(args.questions))

    run_dir = ROOT / "reports" / f"bm25-eval-{_utc_ts()}"
    run_dir = run_dir.resolve()
    _ensure_dir(run_dir)

    print(f"BM25 eval: questions={len(qs)} top_k={args.top_k} authority_level={authority_level} generator_id={args.generator_id}")

    # Build corpus
    paras = _fetch_sunshine_paragraphs(chat_db_url, authority_level, args.generator_id or None)
    corpus = _build_sentence_corpus(paras)
    if not corpus:
        raise SystemExit("No corpus sentences found. Check authority_level/generator_id filter.")

    # BM25 index
    from rank_bm25 import BM25Okapi

    tokenized = [_tokenize(d.sentence_text) for d in corpus]
    bm25 = BM25Okapi(tokenized)

    # Global sigmoid (k, x0) (if requested)
    global_k = None
    global_x0 = None
    if args.sigmoid_mode == "global_max_raw":
        max_raw_scores: list[float] = []
        for q in qs:
            q_tokens = _tokenize(q.get("question") or "")
            raw = bm25.get_scores(q_tokens)
            try:
                max_raw_scores.append(float(max(raw)) if len(raw) else 0.0)
            except Exception:
                max_raw_scores.append(0.0)
        global_k, global_x0 = _sigmoid_params_from_max_raw(max_raw_scores)

    rows: list[dict[str, Any]] = []
    per_q: list[dict[str, Any]] = []
    started = time.monotonic()

    for i, q in enumerate(qs, start=1):
        qid = q.get("id")
        question = q.get("question") or ""
        intent = (q.get("intent") or "").strip().lower()
        bucket = (q.get("bucket") or "").strip().lower()

        q_tokens = _tokenize(question)
        raw = bm25.get_scores(q_tokens)
        # Top-k by raw score
        idxs = sorted(range(len(raw)), key=lambda j: float(raw[j]), reverse=True)[: args.top_k]
        raw_top = [float(raw[j]) for j in idxs]
        docs_top = [corpus[j] for j in idxs]

        if args.sigmoid_mode == "auto_topk":
            k_val, x0 = _sigmoid_params_from_topk(raw_top)
        elif args.sigmoid_mode == "global_max_raw":
            k_val, x0 = float(global_k or 1.0), float(global_x0 or 0.0)
        else:
            k_val, x0 = float(args.sigmoid_k), float(args.sigmoid_x0)

        norm_top = _sigmoid_normalize(raw_top, k=k_val, x0=x0)
        max_norm = float(norm_top[0]) if norm_top else None

        expect_in_manual = _gold_expect_in_manual(q)
        predicted_answer = bool(max_norm is not None and max_norm >= float(args.abstain_threshold))

        # Gold match rank (if any gold provided)
        best_match_rank = None
        best_match_why = None
        for rank, d in enumerate(docs_top, start=1):
            m = _gold_match_candidate(q, d)
            if m["matched"]:
                best_match_rank = rank
                best_match_why = m["why"]
                break

        per_q.append(
            {
                "qid": qid,
                "intent": intent,
                "bucket": bucket,
                "question": question,
                "expect_in_manual": expect_in_manual,
                "sigmoid_mode": args.sigmoid_mode,
                "sigmoid_k": k_val,
                "sigmoid_x0": x0,
                "abstain_threshold": float(args.abstain_threshold),
                "max_raw_score": float(raw_top[0]) if raw_top else None,
                "max_norm_score": max_norm,
                "predicted_answer": predicted_answer,
                "gold_best_rank": best_match_rank,
                "gold_match_why": best_match_why,
            }
        )

        # Candidate rows
        for rank, (d, s_raw, s_norm) in enumerate(zip(docs_top, raw_top, norm_top), start=1):
            m = _gold_match_candidate(q, d)
            rows.append(
                {
                    "qid": qid,
                    "intent": intent,
                    "bucket": bucket,
                    "question": question,
                    "rank": rank,
                    "sentence_id": d.sid,
                    "parent_metadata_id": d.parent_metadata_id,
                    "raw_score": float(s_raw),
                    "norm_score": float(s_norm),
                    "page_number": d.page_number,
                    "section_path": d.section_path,
                    "chapter_path": d.chapter_path,
                    "document_display_name": d.document_display_name,
                    "sentence_text": d.sentence_text[:360] + ("…" if len(d.sentence_text) > 360 else ""),
                    "gold_matched": bool(m["matched"]),
                    "gold_match_why": m["why"],
                }
            )

        if i % 5 == 0:
            print(f"  progress: {i}/{len(qs)} | {time.monotonic() - started:.1f}s")

    # Write outputs
    results_jsonl = run_dir / "results.jsonl"
    per_question_jsonl = run_dir / "per_question.jsonl"
    _write_jsonl(results_jsonl, rows)
    _write_jsonl(per_question_jsonl, per_q)

    import pandas as pd

    dfq = pd.DataFrame(per_q)
    df = pd.DataFrame(rows)
    dfq.to_csv(run_dir / "per_question.csv", index=False)
    df.to_csv(run_dir / "results.csv", index=False)

    # Summary
    summary_md = run_dir / "summary.md"
    with open(summary_md, "w") as f:
        f.write("## BM25 Sentence Candidate Eval (pre-rerank)\n\n")
        f.write(f"- **run_dir**: `{run_dir}`\n")
        f.write(f"- **questions**: {len(qs)}\n")
        f.write(f"- **top_k**: {args.top_k}\n")
        f.write(f"- **authority_level**: `{authority_level}`\n")
        f.write(f"- **generator_id**: `{args.generator_id}`\n")
        f.write(f"- **abstain_threshold**: {float(args.abstain_threshold)}\n")
        f.write(f"- **sigmoid_mode**: `{args.sigmoid_mode}`\n\n")

        # Hallucination penalty view: out_of_manual predicted_answer
        if not dfq.empty:
            # Define correctness on action
            dfq["is_out_of_manual"] = ~dfq["expect_in_manual"].astype(bool)
            dfq["false_positive_answer"] = dfq["is_out_of_manual"] & dfq["predicted_answer"].astype(bool)
            dfq["false_negative_abstain"] = (~dfq["is_out_of_manual"]) & (~dfq["predicted_answer"].astype(bool))
            dfq["gold_found_topk"] = dfq["gold_best_rank"].notna()

            fp = int(dfq["false_positive_answer"].sum())
            fn = int(dfq["false_negative_abstain"].sum())
            f.write("### Action quality (hallucination risk)\n\n")
            f.write(f"- **false_positive_answer (should abstain, but would answer)**: {fp}\n")
            f.write(f"- **false_negative_abstain (should answer, but would abstain)**: {fn}\n\n")

            # Retrieval quality (only where gold is present/usable)
            labeled = dfq[dfq["gold_best_rank"].notna()].copy()
            f.write("### Retrieval quality (only questions with usable gold match)\n\n")
            if labeled.empty:
                f.write("- No gold matches were configured in `questions.yaml` yet.\n\n")
            else:
                recall_at_1 = float((labeled["gold_best_rank"] <= 1).mean())
                recall_at_5 = float((labeled["gold_best_rank"] <= 5).mean())
                recall_at_k = float((labeled["gold_best_rank"] <= args.top_k).mean())
                f.write(f"- **Recall@1**: {recall_at_1:.3f}\n")
                f.write(f"- **Recall@5**: {recall_at_5:.3f}\n")
                f.write(f"- **Recall@{args.top_k}**: {recall_at_k:.3f}\n\n")

    # Plots
    plots = _plot(dfq, run_dir)
    if plots:
        print("Wrote plots:")
        for p in plots:
            print(f"  - {p}")

    print("Done. Outputs:")
    print(f"  - {run_dir/'per_question.csv'}")
    print(f"  - {run_dir/'results.csv'}")
    print(f"  - {summary_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

