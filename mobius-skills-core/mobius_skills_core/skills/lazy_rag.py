"""Lazy RAG — vector-only retrieval with caller-supplied filter.

This is the "light" retrieval algorithm: embed the query, vector-search
Chroma filtered by whatever the caller passes, return chunks directly
from Chroma's metadata (no Postgres hydration, no rerank, no
confidence labeling, no LLM synthesis).

Two consumers wrap this with different filters:

* ``thread_corpus_search`` — scopes to one user-uploaded document
  (``instant_rag=true`` + ``document_id=X``). Fast lookup of "what
  does this doc I just uploaded say about Y?"

* ``lazy_corpus_search`` — scopes to the approved corpus
  (``instant_rag != true`` + optional payer/state/program filters).
  The 3rd retrieval skill: capture-oriented search of the published
  corpus without the heavy pipeline (no rerank, no confidence
  filter, no sibling-paragraph assembly). Default ``k`` higher than
  the heavy path because the goal is recall, not precision.

Contrast with ``corpus_search``
-------------------------------
``corpus_search`` (Day 4):
  embed → vector search → Postgres metadata hydration → caller does
  confidence filter + assembly + synthesis. Used when citations with
  full document metadata matter.

``lazy_rag`` (Day 5, this module):
  embed → vector search → return Chroma metadata directly. Used when
  speed + capture matter; citations are best-effort (whatever ended
  up in Chroma's metadata at ingest time).

Both use the same Chroma backend; they differ in post-vector
processing. See the 2×2 in docs/skill-architecture.md (heavy/light ×
approved-corpus/thread-uploads).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from mobius_skills_core._types import (
    ChunkRef,
    Emitter,
    SkillEvent,
    SkillResult,
    SourceRef,
    _safe_emit,
)
from mobius_skills_core.skills.corpus_search import (
    ChromaConfig,
    _get_chroma_collection,
)

logger = logging.getLogger(__name__)

_STEP_ID = "lazy_rag"


def run_lazy_rag(
    query: str,
    *,
    embed_query: Callable[[str], list[float]],
    chroma: ChromaConfig,
    k: int = 8,
    where: dict[str, Any] | None = None,
    default_document_name: str = "document",
    step_id: str = _STEP_ID,
    emitter: Emitter | None = None,
) -> SkillResult:
    """Vector-only retrieval from Chroma with caller-supplied filter.

    Args:
        query: Natural-language query. Empty → tool_error.
        embed_query: Callable(str) → list[float]. Consumer provides its
            own embedder — this package is embedder-neutral.
        chroma: Chroma backend configuration.
        k: Number of chunks to return. Default 8 (matches the legacy
            instant_rag_search default). ``lazy_corpus_search`` passes
            a larger k for capture-oriented retrieval.
        where: Chroma ``where`` filter expression. Passed straight
            through; caller owns semantics. Common shapes:
              * ``{"document_id": "doc-abc"}`` — single-doc scope.
              * ``{"$and": [{"instant_rag": "true"}, {"document_id": "X"}]}``
                — thread_corpus_search's full scope.
              * ``{"instant_rag": {"$ne": "true"}}`` — exclude user uploads.
        default_document_name: Fallback name when Chroma metadata has
            no ``display_name`` / ``filename``. The thread-scoped
            wrapper passes "Uploaded document"; the corpus wrapper
            passes "document".
        step_id: Emit ``step_id`` override. Wrappers pass their own
            (e.g. ``"thread_corpus_search"``) so dashboards can group
            per-skill even though the shared impl fires the events.
        emitter: Optional SkillEvent callback.

    Returns:
        SkillResult with:
          * text: "--- " separated chunk bodies joined for LLM context.
          * chunks: ChunkRef[] with text + score + metadata.
          * sources: SourceRef[] one per chunk, with index for citation.
          * signal: "ok" when chunks returned, "no_sources" when empty,
            "tool_error" on backend failure.
          * extra: ``vector_count_hint`` when empty (for diagnostics —
            tells consumers whether Chroma has nothing matching the
            filter vs. has things that didn't pass similarity).
    """
    if not query or not str(query).strip():
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=step_id,
            note="empty query rejected",
            data={"reason": "empty_query"},
            task_type="failure", task_severity="low",
        ))
        return SkillResult(text="Error: query is required.", signal="tool_error")

    clean_query = str(query).strip()
    _safe_emit(emitter, SkillEvent(
        signal="tool_invoked", step_id=step_id,
        note=f"Lazy retrieval for: {clean_query[:80]}",
        data={"query": clean_query, "k": k, "where": where},
        task_type="info", task_severity="low",
    ))

    try:
        embedding = embed_query(clean_query)
    except Exception as exc:
        logger.exception("lazy_rag embed_query failed")
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=step_id,
            note=f"Embedding failed ({exc})",
            data={"error_type": "embed", "message": str(exc)},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text=f"Lazy retrieval failed (embedding: {exc}).",
            signal="tool_error",
        )

    try:
        collection = _get_chroma_collection(chroma)
    except Exception as exc:
        logger.exception("lazy_rag chroma open failed")
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=step_id,
            note=f"Chroma open failed ({exc})",
            data={"error_type": "chroma_open", "message": str(exc)},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text=f"Lazy retrieval failed (chroma: {exc}).",
            signal="tool_error",
        )

    try:
        result = collection.query(
            query_embeddings=[embedding],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.exception("lazy_rag chroma query failed")
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=step_id,
            note=f"Chroma query failed ({exc})",
            data={"error_type": "chroma_query", "message": str(exc)},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text=f"Lazy retrieval failed (query: {exc}).",
            signal="tool_error",
        )

    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    if not ids:
        # Diagnostic probe — distinguishes "no vectors match filter" from
        # "vectors exist but similarity too low". Same pattern lazy_rag_search
        # used in 2026-04-17 diagnostics.
        vector_count_hint = -1
        try:
            probe = collection.get(where=where, limit=1)
            vector_count_hint = len(probe.get("ids") or [])
        except Exception:
            pass
        logger.info(
            "[lazy_rag] empty result for step=%s where=%r. "
            "vector_count_probe=%s "
            "(0 = nothing indexed matches filter — ingest gap? "
            ">0 = query embedding missed all indexed vectors).",
            step_id, where, vector_count_hint if vector_count_hint >= 0 else "probe_failed",
        )
        _safe_emit(emitter, SkillEvent(
            signal="no_sources", step_id=step_id,
            note="Lazy retrieval returned no matches",
            data={"query": clean_query, "where": where,
                  "vector_count_hint": vector_count_hint},
            task_type="info", task_severity="low",
        ))
        return SkillResult(
            text="",
            signal="no_sources",
            extra={"vector_count_hint": vector_count_hint, "where": where},
        )

    chunks: list[ChunkRef] = []
    sources: list[SourceRef] = []
    for idx, (cid, text, meta, dist) in enumerate(zip(ids, docs, metas, distances), 1):
        if not text or not str(text).strip():
            continue
        m = meta or {}
        # Cosine distance [0, 2] → similarity [0, 1]
        try:
            score = round(max(0.0, min(1.0, 1.0 - float(dist or 0.0) / 2.0)), 4)
        except (TypeError, ValueError):
            score = 0.0

        doc_id = str(m.get("document_id") or "")
        doc_name = str(
            m.get("display_name")
            or m.get("document_display_name")
            or m.get("filename")
            or m.get("document_filename")
            or default_document_name
        )
        page_number = m.get("page_number")
        source_type = str(m.get("source_type") or "chunk")

        # Metadata dict for ChunkRef — include anything useful for
        # downstream scoring (instant_rag flag, etc).
        chunk_metadata = {
            "source_type": source_type,
            "distance": dist,
            # Keep the raw Chroma metadata accessible for consumers that
            # want domain-specific fields without enumerating them here.
            "_raw": dict(m),
        }
        if "instant_rag" in m:
            chunk_metadata["instant_rag"] = m["instant_rag"]
        if "paragraph_index" in m:
            chunk_metadata["paragraph_index"] = m["paragraph_index"]

        chunks.append(ChunkRef(
            text=str(text),
            score=score,
            document_id=doc_id,
            document_name=doc_name,
            page_number=page_number,
            chunk_id=str(cid),
            metadata=chunk_metadata,
        ))
        sources.append(SourceRef(
            document_name=doc_name,
            document_id=doc_id or None,
            source_type=source_type,
            page_number=page_number,
            index=idx,
            text=(str(text)[:300] + "…") if len(str(text)) > 300 else str(text),
            authority="user-asserted" if str(m.get("instant_rag", "")).lower() == "true" else "corpus",
        ))

    if not chunks:
        # All returned ids had empty text — unusual but possible.
        _safe_emit(emitter, SkillEvent(
            signal="no_sources", step_id=step_id,
            note="All returned chunks had empty text",
            data={"ids_returned": len(ids)},
            task_type="failure", task_severity="low",
        ))
        return SkillResult(
            text="",
            signal="no_sources",
            extra={"ids_returned": len(ids), "where": where},
        )

    _safe_emit(emitter, SkillEvent(
        signal="tool_completed", step_id=step_id,
        note=f"Found {len(chunks)} passage(s)",
        data={"chunk_count": len(chunks), "query": clean_query},
        task_type="info", task_severity="low",
    ))

    # Join raw chunk text with section-break markers — the integrator at
    # the end of the turn does LLM synthesis, so we never LLM-synth here.
    # Matches the legacy instant_rag_search.lazy_rag_search pattern.
    answer = "\n\n---\n\n".join(c.text for c in chunks)

    return SkillResult(
        text=answer,
        sources=sources,
        chunks=chunks,
        signal="ok",
        extra={
            "query": clean_query,
            "k": k,
            "where": where,
            "chunk_count": len(chunks),
        },
    )
