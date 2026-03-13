"""BM25 sentence-level retrieval from published_rag_metadata. No reranking."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _emit(emitter: Callable[[str], None] | None, msg: str) -> None:
    if emitter and msg.strip():
        emitter(msg.strip())


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


@dataclass
class SentenceDoc:
    sid: str
    parent_metadata_id: str
    sentence_text: str
    page_number: int | None
    section_path: str | None
    chapter_path: str | None
    document_display_name: str | None
    document_id: str | None = None
    document_authority_level: str | None = None


def _fetch_paragraphs(
    postgres_url: str,
    authority_level: str | None,
    source_types: list[str] | None = None,
    tag_filters: dict[str, str] | None = None,
    document_ids: list[str] | None = None,
    emitter: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Fetch paragraphs from published_rag_metadata. source_types: None or ['hierarchical'] = hierarchical only; [] or ['hierarchical','fact'] = all."""
    if not postgres_url:
        _emit(emitter, "No postgres_url; skipping BM25 corpus fetch.")
        return []
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        _emit(emitter, "psycopg2 not available; skipping BM25.")
        return []
    # Default: hierarchical only. source_types=[] or ["hierarchical","fact"] = all (no filter)
    if source_types is None or (source_types and "fact" not in source_types and set(source_types) <= {"hierarchical"}):
        where = ["source_type = 'hierarchical'"]
        scope = "hierarchical"
    else:
        where = ["1=1"]
        scope = "all"
    params: list[Any] = []
    if authority_level:
        where.append("document_authority_level = %s")
        params.append(authority_level)
    _ALLOWED_TAG_COLS = {"document_payer", "document_state", "document_program", "document_authority_level"}
    for col, val in (tag_filters or {}).items():
        if col in _ALLOWED_TAG_COLS and (val or "").strip():
            where.append(f"{col} = %s")
            params.append(val.strip())
    if document_ids:
        where.append("document_id::text = ANY(%s)")
        params.append(document_ids)
        _emit(emitter, f"BM25 corpus: document_ids filter ON ({len(document_ids)} doc(s))")
    if not where:
        where = ["1=1"]
    if authority_level:
        _emit(emitter, f"BM25 corpus: authority_level={authority_level!r}")
    if tag_filters:
        _emit(emitter, f"BM25 corpus: tag_filters={tag_filters}")
    sql = f"""
      SELECT id, document_id, text, page_number, section_path, chapter_path, document_display_name, document_authority_level
      FROM published_rag_metadata
      WHERE {' AND '.join(where)}
      ORDER BY page_number NULLS LAST, paragraph_index NULLS LAST, id
    """
    try:
        conn = psycopg2.connect(postgres_url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        filter_desc = []
        if authority_level:
            filter_desc.append(f"authority_level={authority_level!r}")
        if document_ids:
            filter_desc.append(f"document_id IN ({len(document_ids)} ids)")
        if tag_filters:
            filter_desc.append(f"tag_filters={list(tag_filters.keys())}")
        suffix = " [" + ", ".join(filter_desc) + "]" if filter_desc else ""
        _emit(emitter, f"BM25 corpus: fetched {len(rows)} paragraph(s) ({scope}){suffix}")
        return [dict(r) for r in rows]
    except Exception as e:
        logger.exception("BM25 corpus fetch failed: %s", e)
        _emit(emitter, f"BM25 corpus fetch failed: {e}")
        return []


def _build_sentence_corpus(paragraph_rows: list[dict[str, Any]]) -> list[SentenceDoc]:
    corpus: list[SentenceDoc] = []
    for r in paragraph_rows:
        pid = str(r.get("id"))
        txt = (r.get("text") or "").strip()
        if not txt:
            continue
        doc_id = r.get("document_id")
        doc_id_str = str(doc_id) if doc_id is not None else None
        for i, s in enumerate(_split_sentences(txt)):
            corpus.append(
                SentenceDoc(
                    sid=f"{pid}#s{i}",
                    parent_metadata_id=pid,
                    sentence_text=s,
                    page_number=r.get("page_number"),
                    section_path=r.get("section_path"),
                    chapter_path=r.get("chapter_path"),
                    document_display_name=r.get("document_display_name"),
                    document_id=doc_id_str,
                    document_authority_level=(r.get("document_authority_level") or "").strip() or None,
                )
            )
    return corpus


def bm25_search(
    question: str,
    postgres_url: str,
    authority_level: str | None = None,
    source_types: list[str] | None = None,
    tag_filters: dict[str, str] | None = None,
    document_ids: list[str] | None = None,
    top_k: int = 10,
    include_paragraphs: bool = True,
    top_k_per_type: int | None = None,
    corpus_cache: tuple[list[SentenceDoc], Any] | None = None,
    emitter: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """
    BM25 retrieval on paragraph and/or sentence corpus. Returns list of dicts compatible with ChunkResult.
    When include_paragraphs=True, runs BM25 on both full paragraphs and sentences; each result has provision_type.
    """
    from rank_bm25 import BM25Okapi

    k_per = top_k_per_type if top_k_per_type is not None else top_k

    if corpus_cache is not None:
        corpus, _ = corpus_cache
        rows = []
        include_paragraphs = False
    else:
        scope_parts = [f"source_type={source_types or 'hierarchical'}"]
        if authority_level:
            scope_parts.append(f"authority_level={authority_level!r}")
        if document_ids:
            scope_parts.append(f"document_id IN ({len(document_ids)} ids)")
        if tag_filters:
            scope_parts.append(f"tag_filters={list(tag_filters.keys())}")
        _emit(emitter, f"Building BM25 corpus: published_rag_metadata WHERE {' AND '.join(scope_parts)}")
        rows = _fetch_paragraphs(
            postgres_url, authority_level,
            source_types=source_types,
            tag_filters=tag_filters,
            document_ids=document_ids,
            emitter=emitter,
        )
        if not rows:
            return []
        corpus = _build_sentence_corpus(rows)
        _emit(emitter, f"BM25 corpus: {len(rows)} paragraph(s), {len(corpus)} sentence(s)")

    q_tokens = _tokenize(question)
    out: list[dict[str, Any]] = []

    if include_paragraphs and rows:
        para_texts = [(str(r.get("id")), (r.get("text") or "").strip()) for r in rows]
        para_texts = [(pid, t) for pid, t in para_texts if t]
        if para_texts:
            pids, texts = zip(*para_texts)
            tokenized_para = [_tokenize(t) for t in texts]
            bm25_para = BM25Okapi(tokenized_para)
            raw_para = bm25_para.get_scores(q_tokens)
            idxs_para = sorted(range(len(raw_para)), key=lambda j: float(raw_para[j]), reverse=True)[:k_per]
            r_by_id = {str(r.get("id")): r for r in rows}
            for rank, j in enumerate(idxs_para, 1):
                pid = pids[j]
                r = r_by_id.get(pid, {})
                raw_score = float(raw_para[j])
                out.append({
                    "id": pid,
                    "text": texts[j],
                    "document_id": r.get("document_id"),
                    "document_name": r.get("document_display_name") or "document",
                    "document_authority_level": (r.get("document_authority_level") or "").strip() or None,
                    "page_number": r.get("page_number"),
                    "source_type": "hierarchical",
                    "distance": None,
                    "similarity": None,
                    "confidence": None,
                    "raw_score": raw_score,
                    "rank": rank,
                    "provision_type": "paragraph",
                })
            _emit(emitter, f"BM25 paragraph matches: {len(idxs_para)} (top raw_score={raw_para[idxs_para[0]]:.4f})" if idxs_para else "BM25 paragraph matches: 0")

    if corpus:
        tokenized = [_tokenize(d.sentence_text) for d in corpus]
        bm25 = BM25Okapi(tokenized)
        raw = bm25.get_scores(q_tokens)
        idxs = sorted(range(len(raw)), key=lambda j: float(raw[j]), reverse=True)[:k_per]
        for rank, j in enumerate(idxs, 1):
            d = corpus[j]
            raw_score = float(raw[j])
            out.append({
                "id": d.parent_metadata_id,
                "text": d.sentence_text,
                "document_id": d.document_id,
                "document_name": d.document_display_name or "document",
                "document_authority_level": d.document_authority_level,
                "page_number": d.page_number,
                "source_type": "hierarchical",
                "distance": None,
                "similarity": None,
                "confidence": None,
                "raw_score": raw_score,
                "rank": rank,
                "provision_type": "sentence",
            })
        _emit(emitter, f"BM25 sentence matches: {len(idxs)} (top raw_score={raw[idxs[0]]:.4f})" if idxs else "BM25 sentence matches: 0")

    _emit(emitter, f"BM25 returned {len(out)} provision(s) total (paragraph + sentence)")
    return out


def fetch_seed_chunks_for_document_ids(
    postgres_url: str,
    document_ids: list[str],
    authority_level: str | None = None,
    tag_filters: dict[str, str] | None = None,
    emitter: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Fetch one paragraph per document_id for continuity (include previous turn sources).
    Returns chunks in same format as bm25_search output."""
    if not document_ids or not postgres_url:
        return []
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        return []
    where = ["document_id::text = ANY(%s)"]
    params: list[Any] = [document_ids]
    if authority_level:
        where.append("document_authority_level = %s")
        params.append(authority_level)
    _ALLOWED = {"document_payer", "document_state", "document_program", "document_authority_level"}
    for col, val in (tag_filters or {}).items():
        if col in _ALLOWED and (val or "").strip():
            where.append(f"{col} = %s")
            params.append(val.strip())
    sql = f"""
      SELECT id, document_id, text, page_number, document_display_name, document_authority_level
      FROM published_rag_metadata
      WHERE source_type = 'hierarchical' AND {' AND '.join(where)}
      ORDER BY document_id, page_number NULLS LAST, paragraph_index NULLS LAST
    """
    try:
        conn = psycopg2.connect(postgres_url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        _emit(emitter, f"Seed chunks fetch failed: {e}")
        return []
    seen_doc: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        doc_id = str(r.get("document_id") or "")
        if not doc_id or doc_id in seen_doc:
            continue
        seen_doc.add(doc_id)
        txt = (r.get("text") or "").strip()
        if not txt:
            continue
        pid = str(r.get("id") or "")
        out.append({
            "id": pid,
            "text": txt,
            "document_id": doc_id,
            "document_name": (r.get("document_display_name") or "document") or "document",
            "document_authority_level": (r.get("document_authority_level") or "").strip() or None,
            "page_number": r.get("page_number"),
            "source_type": "hierarchical",
            "distance": None,
            "similarity": None,
            "confidence": None,
            "raw_score": 0.5,
            "rank": 0,
            "provision_type": "paragraph",
        })
    if emitter and out:
        _emit(emitter, f"Included {len(out)} seed chunk(s) from previous turn(s)")
    return out
