#!/usr/bin/env python3
"""
Generate a labeled 50-question set directly from the Sunshine manual text.

This creates high-signal questions with strong gold labels:
- factual questions anchored to a specific evidence sentence (answer_contains)
- canonical questions anchored to a specific paragraph (crux_contains)
- out-of-manual questions where correct behavior is abstain

Output YAML schema matches bm25_eval.py expectations.
"""

from __future__ import annotations

import argparse
import os
import re
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


@dataclass(frozen=True)
class Cand:
    parent_id: str
    sentence: str
    page_number: int | None
    section_path: str | None
    chapter_path: str | None
    answer_contains: list[str] | None
    answer_regex: str | None
    kind: str  # phone|url|email|days|other


def _extract_answer(sentence: str) -> tuple[str, list[str] | None, str | None]:
    s = sentence or ""

    phone = re.findall(r"(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", s)
    if phone:
        return ("phone", [phone[0]], None)

    url = re.findall(r"(https?://\S+|www\.\S+)", s, flags=re.IGNORECASE)
    if url:
        return ("url", [url[0].rstrip(").,;")], None)

    email = re.findall(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", s, flags=re.IGNORECASE)
    if email:
        return ("email", [email[0]], None)

    days = re.findall(r"\b(\d{1,3}\s*(?:calendar\s*)?days?)\b", s, flags=re.IGNORECASE)
    if days:
        uniq: list[str] = []
        for d in days:
            dd = re.sub(r"\s+", " ", d.strip())
            if dd.lower() not in {u.lower() for u in uniq}:
                uniq.append(dd)
            if len(uniq) >= 1:
                break
        return ("days", uniq, None)

    # fallback: short regex anchor (first 8-10 tokens)
    toks = _tokenize(s)
    if len(toks) >= 8:
        phrase = " ".join(toks[:10])
        return ("other", None, r"(?i)" + re.escape(phrase))
    return ("other", None, None)


def _make_question_from_sentence(kind: str, sentence: str, answer: list[str] | None) -> str | None:
    s = re.sub(r"\s+", " ", (sentence or "").strip())
    if not s:
        return None

    def _context_without(ans: str) -> str:
        ctx = s.replace(ans, " ").strip()
        ctx = re.sub(r"\s+", " ", ctx)
        # drop long dot-leader runs (TOC artifacts)
        ctx = re.sub(r"\.{3,}", " ", ctx)
        ctx = ctx.strip(" -–—:;,.")
        # keep a compact slice
        if len(ctx) > 160:
            ctx = ctx[:160].rsplit(" ", 1)[0] + "…"
        return ctx

    # Context-rich templates so lexical retrieval can actually target the right line.
    if kind == "phone" and answer:
        ctx = _context_without(answer[0])
        return f'What phone number does the Sunshine provider manual list for: "{ctx}"?'
    if kind == "url" and answer:
        ctx = _context_without(answer[0])
        return f'What website/URL does the Sunshine provider manual list for: "{ctx}"?'
    if kind == "email" and answer:
        ctx = _context_without(answer[0])
        return f'What email address does the Sunshine provider manual list for: "{ctx}"?'
    if kind == "days" and answer:
        ctx = _context_without(answer[0])
        return f'How many days does the Sunshine provider manual specify for: "{ctx}"?'

    # Default: turn it into a 'what does it say' question
    lead = s
    if len(lead) > 140:
        lead = lead[:140].rsplit(" ", 1)[0] + "…"
    return f"According to the Sunshine provider manual, what does it state about: \"{lead}\"?"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--out", default=str(ROOT / "questions_generated.yaml"))
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--n_out_of_manual", type=int, default=7)
    ap.add_argument("--n_canonical", type=int, default=8)
    args = ap.parse_args()

    cfg = load_yaml(Path(args.config))
    filters = (cfg.get("filters") or {}) if isinstance(cfg.get("filters"), dict) else {}
    authority_level = filters.get("document_authority_level") or ""
    if not authority_level:
        raise SystemExit("config.filters.document_authority_level must be set")

    chat_db_url = os.getenv("CHAT_RAG_DATABASE_URL") or os.getenv("CHAT_DATABASE_URL")
    if not chat_db_url:
        raise SystemExit("Set CHAT_DATABASE_URL (or CHAT_RAG_DATABASE_URL).")

    paras = _fetch_paragraphs(chat_db_url, authority_level)
    if not paras:
        raise SystemExit("No paragraphs found for authority_level")

    # Canonical questions: pick paragraphs with section/chapter path and enough text.
    canonical: list[dict[str, Any]] = []
    for p in paras:
        txt = (p.get("text") or "").strip()
        # Skip TOC-like blocks with dot leaders; they don't make good canonical questions.
        if re.search(r"\.{6,}", txt[:250]):
            continue
        if len(txt) < 600:
            continue
        sp = p.get("section_path")
        cp = p.get("chapter_path")
        if not (sp or cp):
            continue
        sents = _split_sentences(txt)
        crux = [s for s in sents[:4] if len(s) >= 35][:3]
        if not crux:
            continue
        label = sp or cp
        canonical.append(
            {
                "id": None,
                "intent": "canonical",
                "bucket": "in_manual",
                "question": f"Summarize the key guidance in the provider manual section: \"{label}\".",
                "gold": {
                    "expect_in_manual": True,
                    "parent_metadata_ids": [str(p.get('id'))],
                    "crux_contains": crux,
                },
            }
        )
        if len(canonical) >= int(args.n_canonical):
            break

    # Factual questions: harvest sentences with stable answers.
    cands: list[Cand] = []
    for p in paras:
        pid = str(p.get("id"))
        txt = (p.get("text") or "").strip()
        if not txt:
            continue
        for s in _split_sentences(txt):
            if len(s) < 40 or len(s) > 420:
                continue
            kind, ans_contains, ans_rx = _extract_answer(s)
            # Prefer sentences that actually have an extracted concrete answer.
            if kind in ("phone", "url", "email", "days") and ans_contains:
                cands.append(
                    Cand(
                        parent_id=pid,
                        sentence=s,
                        page_number=p.get("page_number"),
                        section_path=p.get("section_path"),
                        chapter_path=p.get("chapter_path"),
                        answer_contains=ans_contains,
                        answer_regex=None,
                        kind=kind,
                    )
                )
            elif ans_rx:
                # keep a few "other" anchors so we can reach 50 if needed
                cands.append(
                    Cand(
                        parent_id=pid,
                        sentence=s,
                        page_number=p.get("page_number"),
                        section_path=p.get("section_path"),
                        chapter_path=p.get("chapter_path"),
                        answer_contains=None,
                        answer_regex=ans_rx,
                        kind=kind,
                    )
                )

    # Deduplicate by answer token / regex anchor
    picked: list[dict[str, Any]] = []
    seen_answer = set()
    # Prefer concrete kinds first
    kind_rank = {"phone": 0, "url": 1, "email": 2, "days": 3, "other": 9}
    cands.sort(key=lambda c: (kind_rank.get(c.kind, 9), len(c.sentence)))
    for c in cands:
        key = None
        if c.answer_contains:
            key = ("contains", c.answer_contains[0].lower())
        elif c.answer_regex:
            key = ("regex", c.answer_regex)
        if key and key in seen_answer:
            continue
        qtxt = _make_question_from_sentence(c.kind, c.sentence, c.answer_contains)
        if not qtxt:
            continue
        gold = {"expect_in_manual": True, "parent_metadata_ids": [c.parent_id]}
        if c.answer_contains:
            gold["answer_contains"] = c.answer_contains
        if c.answer_regex:
            gold["answer_regex"] = c.answer_regex
        picked.append(
            {
                "id": None,
                "intent": "factual",
                "bucket": "in_manual",
                "question": qtxt,
                "gold": gold,
            }
        )
        if key:
            seen_answer.add(key)
        if len(picked) >= int(args.n) - int(args.n_out_of_manual) - len(canonical):
            break

    # Out-of-manual probes (abstain expected)
    out = [
        ("factual", "What is the Medicare Part B prior authorization process in California?"),
        ("factual", "What are the Tricare behavioral health eligibility requirements in Texas?"),
        ("factual", "What is the Aetna commercial IOP authorization process in New York?"),
        ("factual", "What is the UnitedHealthcare Medicare Advantage policy for TMS in Ohio?"),
        ("factual", "What are BCBS of Florida credentialing timelines for group practices?"),
        ("canonical", "Write a summary of the latest changes to federal parity law in 2025."),
        ("canonical", "Explain how to implement a secure OAuth2 flow for a mobile app."),
    ][: int(args.n_out_of_manual)]
    out_qs = []
    for idx, (intent, q) in enumerate(out, start=1):
        out_qs.append(
            {
                "id": None,
                "intent": intent,
                "bucket": "out_of_manual",
                "question": q,
                "gold": {"expect_in_manual": False},
            }
        )

    # Assemble final set with stable ids
    all_qs = canonical + picked + out_qs
    all_qs = all_qs[: int(args.n)]
    for i, q in enumerate(all_qs, start=1):
        q["id"] = f"G{i:03d}"

    write_yaml(Path(args.out), {"questions": all_qs})
    print(f"Wrote {len(all_qs)} questions to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

