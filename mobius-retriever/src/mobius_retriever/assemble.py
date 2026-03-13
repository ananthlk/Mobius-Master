"""Doc assembly: confidence labels, Google fallback.

Shared by pipeline; no mobius-chat dependency.
"""
from __future__ import annotations

import json
import logging
import os
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)
_DEBUG_RAG = os.environ.get("DEBUG_RAG", "1").lower() in ("1", "true", "yes")


@dataclass
class DocAssemblyConfig:
    """Configurable thresholds for doc assembly."""
    confidence_abstain_max: float = 0.5
    confidence_process_confident_min: float = 0.85
    google_fallback_low_match_min: float = 0.5


CONFIDENCE_TIERS = {
    "abstain": "Do not send",
    "process_with_caution": "Use but reconcile across docs",
    "process_confident": "Likely correct; verify no conflicts",
}


def assign_confidence(
    doc: dict[str, Any],
    config: DocAssemblyConfig | None = None,
) -> dict[str, Any]:
    """Assign confidence_label and llm_guidance from rerank_score or match_score."""
    cfg = config or DocAssemblyConfig()
    score = doc.get("rerank_score") or doc.get("match_score") or doc.get("confidence") or 0.0
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0.0
    doc = dict(doc)
    doc["rerank_score"] = round(score, 4)
    if score < cfg.confidence_abstain_max:
        label = "abstain"
    elif score >= cfg.confidence_process_confident_min:
        label = "process_confident"
    else:
        label = "process_with_caution"
    doc["confidence_label"] = label
    doc["llm_guidance"] = CONFIDENCE_TIERS.get(label, "Use but reconcile across docs")
    return doc


def assign_confidence_batch(
    chunks: list[dict[str, Any]],
    config: DocAssemblyConfig | None = None,
) -> list[dict[str, Any]]:
    """Assign confidence to all chunks. Skips non-dict to avoid .get() on list."""
    cfg = config or DocAssemblyConfig()
    if _DEBUG_RAG and chunks:
        for i, c in enumerate(chunks[:5]):
            t = type(c).__name__
            logger.info("[DEBUG_RAG mobius-retriever assemble] assign_confidence_batch chunk[%s] type=%s", i, t)
            if t != "dict":
                logger.warning("[DEBUG_RAG] mobius-retriever assemble chunk[%s] is %s - SKIP (would cause .get on list)", i, t)
    return [assign_confidence(c, cfg) for c in chunks if isinstance(c, dict)]


def filter_abstain(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only chunks that are not abstain."""
    return [c for c in chunks if isinstance(c, dict) and c.get("confidence_label") != "abstain"]


def best_score(chunks: list[dict[str, Any]]) -> float:
    """Return the highest rerank_score (or match_score) among chunks, or 0."""
    if not chunks:
        return 0.0
    best_val = 0.0
    for c in chunks:
        if not isinstance(c, dict):
            continue
        s = c.get("rerank_score") or c.get("match_score") or c.get("confidence") or 0.0
        try:
            best_val = max(best_val, float(s))
        except (TypeError, ValueError):
            pass
    return best_val


def google_search_via_url(
    query: str,
    base_url: str,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Call Google search API at base_url. Returns list of snippet dicts."""
    if not (base_url or "").strip():
        return []
    sep = "&" if "?" in base_url else "?"
    url = base_url.rstrip("/") + sep + "q=" + urllib.parse.quote(query)
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode()
        out = json.loads(data)
        if isinstance(out, list):
            results = out
        elif isinstance(out, dict):
            results = out.get("results") or out.get("items") or []
        else:
            results = []
        out_list: list[dict[str, Any]] = []
        results_slice = results[:max_results] if isinstance(results, (list, tuple)) else []
        for r in results_slice:
            if isinstance(r, dict):
                snippet = r.get("snippet") or r.get("description") or r.get("text") or ""
                title = r.get("title") or ""
                url_val = r.get("url") or r.get("link") or ""
                if snippet or title:
                    out_list.append({
                        "text": (title + "\n" + snippet).strip() if title else snippet,
                        "document_name": title or url_val or "External",
                        "source_type": "external",
                        "confidence_label": "abstain",
                        "llm_guidance": "External source; use if helpful but retain/hedge; not from authoritative corpus.",
                        "rerank_score": 0.0,
                    })
        return out_list
    except Exception as e:
        logger.warning("Google search failed: %s", e)
        return []


def apply_google_fallback(
    chunks: list[dict[str, Any]],
    question: str,
    config: DocAssemblyConfig | None = None,
    google_search_url: str | None = None,
    emitter: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Apply Google fallback: corpus only / complement / Google only based on best score."""
    def _emit(msg: str) -> None:
        if emitter and msg.strip():
            emitter(msg.strip())

    cfg = config or DocAssemblyConfig()
    google_url = (google_search_url or "").strip() or os.environ.get("CHAT_SKILLS_GOOGLE_SEARCH_URL", "").strip()
    chunks_with_conf = assign_confidence_batch(chunks, cfg)
    best = best_score(chunks_with_conf)

    # Send all chunks to LLM (no abstain filter); complement with Google when confidence is low
    if best >= cfg.confidence_process_confident_min:
        _emit("Corpus confidence sufficient; using retrieved docs only.")
        return chunks_with_conf

    if best >= cfg.google_fallback_low_match_min:
        _emit("Adding external search to complement corpus...")
        google_results = google_search_via_url(question, google_url) if google_url else []
        if google_results:
            return chunks_with_conf + google_results
        return chunks_with_conf

    _emit("Low corpus confidence; using external search.")
    google_results = google_search_via_url(question, google_url) if google_url else []
    if google_results:
        return chunks_with_conf + google_results
    return chunks_with_conf


def _deduplicate_by_content(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse chunks with identical (document_name, page_number, text); keep highest-scoring per group."""
    chunks = [c for c in chunks if isinstance(c, dict)]

    def key(c: dict[str, Any]) -> tuple[str, str | int | None, str]:
        doc = (c.get("document_name") or c.get("document_id") or "document") or "document"
        page = c.get("page_number")
        text = (c.get("text") or "").strip()
        return (str(doc), page, text)

    def score(c: dict[str, Any]) -> float:
        s = c.get("rerank_score") or c.get("match_score") or c.get("confidence") or 0.0
        try:
            return float(s)
        except (TypeError, ValueError):
            return 0.0

    by_key: dict[tuple[str, str | int | None, str], dict[str, Any]] = {}
    for c in chunks:
        k = key(c)
        if k not in by_key or score(c) > score(by_key[k]):
            by_key[k] = c
    out = list(by_key.values())
    out.sort(key=lambda c: -(score(c)))
    return out


def _is_sentence_level(chunk: dict[str, Any]) -> bool:
    """True if chunk is sentence-level (factual); else paragraph-level (hierarchical).

    Only BM25 sentence chunks are factual. Vector search uses source_type namespace to extract
    hierarchical chunks only; vector results are always paragraph-level (hierarchical).
    BM25 paragraph is also hierarchical.
    """
    src = (chunk.get("retrieval_source") or "").lower()
    if src == "vector":
        return False  # Vector namespace is hierarchical-only; never sentence-level
    if src == "bm25_sentence":
        return True
    if src == "bm25_paragraph":
        return False
    pt = (chunk.get("provision_type") or "").lower()
    return pt == "sentence"


def _apply_blend_selection(
    chunks: list[dict[str, Any]],
    n_factual: int | None,
    n_hierarchical: int | None,
    trace: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Select top n_factual sentence-level + top n_hierarchical paragraph-level chunks (by rerank_score)."""
    if n_factual is None and n_hierarchical is None:
        return chunks
    if (n_factual or 0) == 0 and (n_hierarchical or 0) == 0:
        return chunks

    sent_chunks = [c for c in chunks if _is_sentence_level(c)]
    para_chunks = [c for c in chunks if not _is_sentence_level(c)]

    def by_rerank(c: dict) -> float:
        return float(c.get("rerank_score") or c.get("match_score") or c.get("confidence") or 0.0)

    sent_chunks.sort(key=by_rerank, reverse=True)
    para_chunks.sort(key=by_rerank, reverse=True)

    top_sent = sent_chunks[: n_factual or 0]
    top_para = para_chunks[: n_hierarchical or 0]
    out = top_sent + top_para

    if trace is not None:
        chunks_by_retrieval_source: dict[str, int] = {}
        for c in chunks:
            src = c.get("retrieval_source") or "vector"
            chunks_by_retrieval_source[src] = chunks_by_retrieval_source.get(src, 0) + 1
        trace["blend_selection"] = {
            "chunks_input_n": len(chunks),
            "chunks_by_retrieval_source": chunks_by_retrieval_source,
            "n_factual": n_factual,
            "n_hierarchical": n_hierarchical,
            "n_sentence_level_pool": len(sent_chunks),
            "n_paragraph_level_pool": len(para_chunks),
            "sentence_level_chunks": [
                {"id": str(c.get("id", ""))[:24], "retrieval_source": c.get("retrieval_source"), "rerank_score": c.get("rerank_score"), "snippet": (c.get("text") or "")[:55]}
                for c in sent_chunks[:15]
            ],
            "paragraph_level_chunks": [
                {"id": str(c.get("id", ""))[:24], "retrieval_source": c.get("retrieval_source"), "rerank_score": c.get("rerank_score"), "snippet": (c.get("text") or "")[:55]}
                for c in para_chunks[:15]
            ],
            "top_sentence_selected": [
                {"id": str(c.get("id", ""))[:24], "rerank_score": c.get("rerank_score"), "snippet": (c.get("text") or "")[:55]}
                for c in top_sent
            ],
            "top_paragraph_selected": [
                {"id": str(c.get("id", ""))[:24], "rerank_score": c.get("rerank_score"), "snippet": (c.get("text") or "")[:55]}
                for c in top_para
            ],
            "n_output": len(out),
        }
    return out


def assemble_docs(
    chunks: list[dict[str, Any]],
    question: str,
    *,
    config: DocAssemblyConfig | None = None,
    apply_google: bool = True,
    google_search_url: str | None = None,
    emitter: Callable[[str], None] | None = None,
    n_factual: int | None = None,
    n_hierarchical: int | None = None,
    trace: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Assemble: blend selection (optional), content dedup, assign confidence, optionally Google fallback."""
    cfg = config or DocAssemblyConfig()
    # Defensive: filter to dicts only (avoids .get() on list)
    if _DEBUG_RAG and chunks:
        bad = [i for i, c in enumerate(chunks) if not isinstance(c, dict)]
        if bad:
            logger.warning("[DEBUG_RAG] assemble_docs input has non-dict at indices %s (types: %s)", bad[:10], [type(chunks[i]).__name__ for i in bad[:5]])
    chunks = [c for c in chunks if isinstance(c, dict)]
    chunks = _apply_blend_selection(chunks, n_factual, n_hierarchical, trace=trace)
    chunks = _deduplicate_by_content(chunks)
    chunks_with_conf = assign_confidence_batch(chunks, cfg)
    if apply_google:
        return apply_google_fallback(
            chunks_with_conf, question, cfg,
            google_search_url=google_search_url,
            emitter=emitter,
        )
    return chunks_with_conf
