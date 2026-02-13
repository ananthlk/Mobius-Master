#!/usr/bin/env python3
"""
Auto-label existing questions with "gold" evidence using Sunshine manual text.

This is a bootstrap labeling tool so we can run retrieval-only evals without
hand-annotating 50 questions. It:
  - reads questions.yaml
  - fetches Sunshine hierarchical chunks from Chat Postgres published_rag_metadata
  - uses BM25 over sentences to find best matching paragraph(s)
  - writes gold fields:
      gold.expect_in_manual (from bucket)
      gold.parent_metadata_ids (top paragraph id)
      gold.answer_contains / gold.answer_regex (factual best-effort)
      gold.crux_contains (canonical best-effort)

NOTE: This produces "weak gold" (bootstrapped from lexical match). It's useful
to get the pipeline running and to spot obvious misses/hallucination risk, but
you should refine gold labels for high-stakes scoring.
"""

from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    import yaml

    with open(path, "w") as f:
        yaml.safe_dump(
            data,
            f,
            sort_keys=False,
            allow_unicode=True,
            width=120,
            default_flow_style=False,
        )


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _split_sentences(text: str) -> list[str]:
    if not (text or "").strip():
        return []
    t = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", t)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) > 420:
            sub = re.split(r"\s*;\s*|\s+\u2022\s+|\s+\-\s+", p)
            out.extend([s.strip() for s in sub if s.strip()])
        else:
            out.append(p)
    return out


@dataclass(frozen=True)
class Sent:
    parent_id: str
    text: str
    sent_idx: int


def _fetch_paragraphs(chat_db_url: str, authority_level: str) -> list[dict[str, Any]]:
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(chat_db_url)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT id, text, page_number, section_path, chapter_path, document_display_name
            FROM published_rag_metadata
            WHERE document_authority_level = %s AND source_type = 'hierarchical'
            ORDER BY page_number NULLS LAST, paragraph_index NULLS LAST, id
            """,
            (authority_level,),
        )
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _extract_answer_hints(text: str) -> dict[str, Any]:
    """
    Try to extract stable answer substrings from an evidence sentence.
    """
    out: dict[str, Any] = {}
    if not text:
        return out

    phone = re.findall(r"(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", text)
    if phone:
        # prefer the first
        out["answer_contains"] = [phone[0]]
        return out

    url = re.findall(r"(https?://\S+|www\.\S+)", text, flags=re.IGNORECASE)
    if url:
        out["answer_contains"] = [url[0].rstrip(").,;")]
        return out

    email = re.findall(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", text, flags=re.IGNORECASE)
    if email:
        out["answer_contains"] = [email[0]]
        return out

    days = re.findall(r"\b(\d{1,3}\s*(?:calendar\s*)?days?)\b", text, flags=re.IGNORECASE)
    if days:
        # keep a couple, de-duped
        uniq: list[str] = []
        for d in days:
            dd = re.sub(r"\s+", " ", d.strip())
            if dd.lower() not in {u.lower() for u in uniq}:
                uniq.append(dd)
            if len(uniq) >= 2:
                break
        out["answer_contains"] = uniq
        return out

    # fallback: take a short distinctive phrase (first 8-12 tokens)
    toks = _tokenize(text)
    if len(toks) >= 8:
        phrase = " ".join(toks[:10])
        out["answer_regex"] = r"(?i)" + re.escape(phrase)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--questions", default=str(ROOT / "questions.yaml"))
    ap.add_argument("--out", default=str(ROOT / "questions.yaml"), help="Output YAML path (default overwrites questions.yaml)")
    ap.add_argument("--bm25-top-sents", type=int, default=25, help="How many top sentences to consider per question")
    args = ap.parse_args()

    cfg = load_yaml(Path(args.config))
    filters = (cfg.get("filters") or {}) if isinstance(cfg.get("filters"), dict) else {}
    authority_level = filters.get("document_authority_level") or ""
    if not authority_level:
        raise SystemExit("config.filters.document_authority_level must be set")

    chat_db_url = os.getenv("CHAT_RAG_DATABASE_URL") or os.getenv("CHAT_DATABASE_URL")
    if not chat_db_url:
        raise SystemExit("Set CHAT_DATABASE_URL (or CHAT_RAG_DATABASE_URL) to read published_rag_metadata.")

    qpath = Path(args.questions)
    data = load_yaml(qpath)
    qs = data.get("questions") or []
    if not isinstance(qs, list) or not qs:
        raise SystemExit("questions.yaml missing `questions: [...]`")

    paras = _fetch_paragraphs(chat_db_url, authority_level)
    if not paras:
        raise SystemExit("No paragraphs found for authority_level; did you sync to dev Chat Postgres?")

    # Build sentence corpus + reverse index to parent paragraph
    sents: list[Sent] = []
    para_text_by_id: dict[str, str] = {}
    for p in paras:
        pid = str(p.get("id"))
        txt = (p.get("text") or "").strip()
        para_text_by_id[pid] = txt
        for si, st in enumerate(_split_sentences(txt)):
            if len(st) < 30:
                continue
            sents.append(Sent(parent_id=pid, text=st, sent_idx=si))

    from rank_bm25 import BM25Okapi

    tokenized = [_tokenize(s.text) for s in sents]
    bm25 = BM25Okapi(tokenized)

    for q in qs:
        bucket = (q.get("bucket") or "").strip().lower()
        intent = (q.get("intent") or "").strip().lower()
        question = q.get("question") or ""
        expect_in_manual = bucket != "out_of_manual"

        q_tokens = _tokenize(question)
        scores = bm25.get_scores(q_tokens)
        idxs = sorted(range(len(scores)), key=lambda j: float(scores[j]), reverse=True)[: args.bm25_top_sents]

        # Pick best paragraph by aggregated score over its sentences (top-N)
        agg: dict[str, float] = defaultdict(float)
        best_sent = None
        for j in idxs:
            s = sents[j]
            sc = float(scores[j])
            agg[s.parent_id] += sc
            if best_sent is None:
                best_sent = s

        best_parent = max(agg.items(), key=lambda kv: kv[1])[0] if agg else (best_sent.parent_id if best_sent else None)

        gold: dict[str, Any] = dict(q.get("gold") or {}) if isinstance(q.get("gold"), dict) else {}
        gold["expect_in_manual"] = bool(expect_in_manual)
        if best_parent:
            gold["parent_metadata_ids"] = [str(best_parent)]

        if expect_in_manual:
            # Only attach evidence hints for in-manual; out-of-manual should abstain.
            if intent == "factual":
                if best_sent:
                    gold.update(_extract_answer_hints(best_sent.text))
            else:
                # canonical: use 2-3 crux sentences from the best paragraph based on token overlap
                para_txt = para_text_by_id.get(str(best_parent), "") if best_parent else ""
                cand_sents = _split_sentences(para_txt)[:8]  # first chunk of paragraph tends to be salient
                qset = set(_tokenize(question))
                scored = []
                for st in cand_sents:
                    stoks = set(_tokenize(st))
                    overlap = len(qset & stoks)
                    scored.append((overlap, st))
                scored.sort(key=lambda x: x[0], reverse=True)
                crux = [s for _, s in scored[:3] if s and len(s) >= 25]
                if crux:
                    gold["crux_contains"] = crux[:3]

        q["gold"] = gold

    data["questions"] = qs
    out_path = Path(args.out)
    write_yaml(out_path, data)
    print(f"Wrote labeled questions to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

