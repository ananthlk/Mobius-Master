"""Corpus search — vector search over the published RAG corpus.

This is the "heavyweight" retrieval skill: embed the query, query a
vector store (Chroma local or Vertex AI cloud) with metadata filters,
then hydrate hit-ids with document metadata from Postgres. Returns
ranked chunks with match scores, ready for downstream assembly /
reranking / LLM synthesis.

Scope boundary (2026-04-20 Day 4)
----------------------------------
What THIS function does:

  1. Accepts an ``embed_query`` callback — consumers pass their own
     embedding provider. This package does not ship an embedder.
  2. Vector search:
       - Chroma (local default): cosine similarity against a persisted
         collection. ``chroma_persist_dir`` + ``chroma_collection`` in
         the backend config.
       - Vertex AI (prod): ``find_neighbors`` against a deployed Matching
         Engine index. ``vertex_index_endpoint_id`` +
         ``vertex_deployed_index_id``.
  3. Postgres metadata fetch: queries ``published_rag_metadata`` (via
     the db_agent ``db_query`` client if available; direct psycopg2
     otherwise) to hydrate chunk text + document metadata by id.
  4. Score conversion: cosine distance → similarity in [0, 1].
  5. Emits SkillEvent at boundaries + in the middle when chunks are
     found.

What this function DOES NOT do (stays in consumer):

  * **Confidence filter** — requires chat-specific label taxonomy.
  * **Doc assembly (neighbor expansion, tag-match rerank)** — chat
    owns the assembly pipeline for now; will migrate in a follow-up.
  * **LLM synthesis** — chat's ModelRouter / llm_calls analytics /
    stage routing is chat-specific.
  * **Google fallback** — that's a composition of corpus + google
    skills; composed at the consumer layer.
  * **Retrieval persistence** — writes to chat's ``retrieval_runs``
    table.

Consumers
---------
* mobius-chat's builtin ``search_corpus`` skill wraps this + adds
  assembly + LLM synthesis for the chat's ReAct loop.
* mobius-skills-mcp will expose ``corpus_search`` for external
  consumers that want raw retrieval hits.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from mobius_skills_core._types import (
    ChunkRef,
    Emitter,
    SkillEvent,
    SkillResult,
    SourceRef,
    _safe_emit,
)

logger = logging.getLogger(__name__)

_STEP_ID = "corpus_search"


# ── Backend configs (caller passes these — no env reads here) ──


@dataclass
class ChromaConfig:
    """Chroma local backend configuration.

    ``persist_dir`` is the filesystem path where the persisted client
    stores its index. ``collection`` is the collection name (matches
    how the sync job writes — default ``published_rag`` in mobius-chat).
    """
    persist_dir: str
    collection: str = "published_rag"


@dataclass
class VertexConfig:
    """Vertex AI Matching Engine backend configuration."""
    project_id: str
    location: str = "us-central1"
    index_endpoint_id: str = ""
    deployed_index_id: str = ""
    # Namespace name for source_type filtering (matches mobius-chat's
    # VERTEX_SOURCE_TYPE_NAMESPACE).
    source_type_namespace: str = "source_type"


@dataclass
class CorpusFilters:
    """Metadata filters applied at vector-store query time.

    All fields are AND-ed. Empty / None means no filter on that field.
    Matches the ``document_payer`` / ``document_state`` / etc. metadata
    written by the dbt ingest job.
    """
    payer: str = ""
    state: str = ""
    program: str = ""
    authority_level: str = ""
    # Restrict to a subset of source types (e.g. ["policy", "summary"]).
    # None = all source types.
    source_type_allow: list[str] | None = None


# Module-level cache for Chroma clients (keyed by persist_dir).
# Matches mobius-chat's pattern — reinstantiating the client on every
# call is expensive (loads the HNSW index from disk).
_CHROMA_CACHE: dict[str, Any] = {}


def _reset_chroma_cache() -> None:
    """Testing hook — clear the Chroma collection cache.

    Production callers never need this. Tests that mock ``chromadb.PersistentClient``
    call this between test methods so a stale mock from a previous
    test doesn't leak across assertions.
    """
    _CHROMA_CACHE.clear()


# ── Chroma backend ──


def _get_chroma_collection(cfg: ChromaConfig):
    key = f"{cfg.persist_dir}::{cfg.collection}"
    if key in _CHROMA_CACHE:
        return _CHROMA_CACHE[key]
    import chromadb  # type: ignore[import-untyped]
    client = chromadb.PersistentClient(path=cfg.persist_dir)
    collection = client.get_or_create_collection(
        name=cfg.collection,
        metadata={"hnsw:space": "cosine"},
    )
    _CHROMA_CACHE[key] = collection
    return collection


def _search_chroma(
    query_embedding: list[float],
    k: int,
    chroma: ChromaConfig,
    filters: CorpusFilters,
) -> tuple[list[str], dict[str, float]]:
    """Chroma query with AND-ed metadata filters. Returns (ids, id→distance)."""
    collection = _get_chroma_collection(chroma)

    conditions: list[dict] = []
    if filters.payer:
        conditions.append({"document_payer": filters.payer})
    if filters.state:
        conditions.append({"document_state": filters.state})
    if filters.program:
        conditions.append({"document_program": filters.program})
    if filters.authority_level:
        conditions.append({"document_authority_level": filters.authority_level})
    if filters.source_type_allow:
        conditions.append({"source_type": {"$in": list(filters.source_type_allow)}})

    where = None
    if len(conditions) == 1:
        where = conditions[0]
    elif len(conditions) > 1:
        where = {"$and": conditions}

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=where,
        include=["distances"],
    )
    if not result or not result.get("ids") or not result["ids"][0]:
        return [], {}

    ids = result["ids"][0]
    id_to_distance: dict[str, float] = {}
    distances = result.get("distances") or [[]]
    if distances and distances[0]:
        for i, _id in enumerate(ids):
            try:
                id_to_distance[str(_id)] = float(distances[0][i])
            except (TypeError, ValueError, IndexError):
                pass
    return ids, id_to_distance


# ── Vertex backend ──


def _search_vertex(
    query_embedding: list[float],
    k: int,
    vertex: VertexConfig,
    filters: CorpusFilters,
) -> tuple[list[str], dict[str, float]]:
    """Vertex AI Matching Engine query. Returns (ids, id→distance)."""
    namespaces: list[Any] = []
    try:
        from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import (  # type: ignore[import-untyped]
            Namespace,
        )
        if filters.payer:
            namespaces.append(Namespace(
                name="document_payer",
                allow_tokens=[filters.payer], deny_tokens=[],
            ))
        if filters.state:
            namespaces.append(Namespace(
                name="document_state",
                allow_tokens=[filters.state], deny_tokens=[],
            ))
        if filters.program:
            namespaces.append(Namespace(
                name="document_program",
                allow_tokens=[filters.program], deny_tokens=[],
            ))
        if filters.authority_level:
            namespaces.append(Namespace(
                name="document_authority_level",
                allow_tokens=[filters.authority_level], deny_tokens=[],
            ))
        if filters.source_type_allow:
            namespaces.append(Namespace(
                name=vertex.source_type_namespace,
                allow_tokens=list(filters.source_type_allow),
                deny_tokens=[],
            ))
    except ImportError as exc:
        logger.warning("Vertex Namespace import failed: %s", exc)

    try:
        from google.cloud import aiplatform  # type: ignore[import-untyped]
        aiplatform.init(project=vertex.project_id, location=vertex.location)
        endpoint = aiplatform.MatchingEngineIndexEndpoint(
            index_endpoint_name=vertex.index_endpoint_id,
        )
        response = endpoint.find_neighbors(
            deployed_index_id=vertex.deployed_index_id,
            queries=[query_embedding],
            num_neighbors=k,
            filter=namespaces if namespaces else None,
        )
        neighbors = response[0] if response else []
        ids = [n.id for n in neighbors if getattr(n, "id", None)]
        id_to_distance: dict[str, float] = {}
        for n in neighbors:
            nid = getattr(n, "id", None)
            if nid is not None:
                dist = getattr(n, "distance", None)
                if dist is not None:
                    try:
                        id_to_distance[str(nid)] = float(dist)
                    except (TypeError, ValueError):
                        pass
        return ids, id_to_distance
    except Exception as exc:
        logger.exception("Vertex find_neighbors failed: %s", exc)
        return [], {}


# ── Postgres metadata hydration ──


_METADATA_SQL = (
    "SELECT id, document_id, source_type, text, page_number, paragraph_index, "
    "document_display_name, document_filename "
    "FROM published_rag_metadata "
    "WHERE id::text = ANY(CAST(:ids AS text[]))"
)


def _hydrate_via_db_agent(
    ids: list[str],
    database: str,
    db_query_fn: Callable | None,
) -> list[dict[str, Any]]:
    """Fetch metadata rows via the db-agent client.

    Returns list of row dicts in the order Postgres returned them
    (caller will reorder by vector-store ranking). Empty list on error.
    """
    if db_query_fn is None:
        return []
    result = db_query_fn(
        _METADATA_SQL,
        database,
        params={"ids": [str(i) for i in ids]},
        max_rows=max(len(ids) * 2, 50),
    )
    err = result.get("error") if isinstance(result, dict) else None
    if err:
        msg = err.get("message", "") if isinstance(err, dict) else str(err)
        logger.warning("db_agent metadata fetch failed: %s", msg)
        return []
    cols = result.get("columns") or []
    return [dict(zip(cols, r)) for r in (result.get("rows") or [])]


def _hydrate_via_psycopg2(
    ids: list[str],
    database_url: str,
) -> list[dict[str, Any]]:
    """Direct psycopg2 fallback when the db-agent isn't available.

    Mirrors the db_agent shape so callers get the same row dicts.
    """
    import psycopg2  # type: ignore[import-untyped]
    import psycopg2.extras  # type: ignore[import-untyped]
    conn = psycopg2.connect(database_url, connect_timeout=10)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                _METADATA_SQL.replace(":ids", "%(ids)s")
                             .replace("CAST(%(ids)s AS text[])", "%(ids)s::text[]"),
                {"ids": [str(i) for i in ids]},
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Main entry point ──


def run_corpus_search(
    query: str,
    *,
    embed_query: Callable[[str], list[float]],
    k: int = 10,
    filters: CorpusFilters | None = None,
    chroma: ChromaConfig | None = None,
    vertex: VertexConfig | None = None,
    database: str = "chat",
    db_query_fn: Callable | None = None,
    database_url: str | None = None,
    emitter: Emitter | None = None,
) -> SkillResult:
    """Search the published RAG corpus and return ranked chunks.

    Args:
        query: The natural-language query. Empty → tool_error.
        embed_query: Callable(str) → list[float] that produces the query
            embedding. The package is embedder-agnostic — mobius-chat
            passes ``get_query_embedding``; other consumers pass their
            own.
        k: Number of neighbors to request from the vector store. Default 10.
        filters: CorpusFilters for metadata filtering (payer, state,
            program, authority_level, source_type_allow). None → no
            filters (search the entire corpus).
        chroma: ChromaConfig for Chroma-backed search. Supply exactly
            one of ``chroma`` or ``vertex``; if both, ``chroma`` wins.
        vertex: VertexConfig for Vertex Matching Engine search.
        database: Name of the database the db_query_fn should address
            (mobius-chat convention: "chat"). Ignored when ``db_query_fn``
            is None.
        db_query_fn: Optional db-agent query function (e.g. ``app.db_client.db_query``).
            When supplied, metadata is fetched through the agent; this
            is the preferred path in production for connection-pool
            reuse and audit.
        database_url: Postgres connection string. Used only when
            ``db_query_fn`` is None (direct psycopg2 fallback). When
            both are None, the function returns an empty result set
            with signal="tool_error".
        emitter: Optional SkillEvent callback.

    Returns:
        SkillResult with:
          * text: human-readable summary ("Found N chunk(s)" or the
            failure message)
          * chunks: ChunkRef[] — the ranked hits with text + metadata
          * sources: SourceRef[] — citation-ready form of each chunk
          * signal: "ok" when hits returned; "no_sources" when the
            vector store returned zero; "tool_error" on config/backend
            failure.
    """
    if not query or not str(query).strip():
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note="empty query rejected",
            data={"reason": "empty_query"},
            task_type="failure", task_severity="low",
        ))
        return SkillResult(text="Error: query is required.", signal="tool_error")

    if chroma is None and vertex is None:
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note="no vector-store backend configured",
            data={"reason": "no_backend"},
            task_type="blocker", task_severity="high",
        ))
        return SkillResult(
            text="Error: neither chroma nor vertex backend configured.",
            signal="tool_error",
        )

    if db_query_fn is None and not database_url:
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note="no Postgres path (agent or URL) configured",
            data={"reason": "no_db_path"},
            task_type="blocker", task_severity="high",
        ))
        return SkillResult(
            text="Error: no metadata path configured (pass db_query_fn or database_url).",
            signal="tool_error",
        )

    clean_query = str(query).strip()
    effective_filters = filters or CorpusFilters()

    _safe_emit(emitter, SkillEvent(
        signal="tool_invoked", step_id=_STEP_ID,
        note=f"Searching the corpus for: {clean_query[:80]}",
        data={
            "query": clean_query, "k": k,
            "backend": "chroma" if chroma else "vertex",
            "filters": {
                "payer": effective_filters.payer,
                "state": effective_filters.state,
                "program": effective_filters.program,
                "authority_level": effective_filters.authority_level,
                "source_type_allow": effective_filters.source_type_allow,
            },
        },
        task_type="info", task_severity="low",
    ))

    # 1. Embed
    try:
        embedding = embed_query(clean_query)
    except Exception as exc:
        logger.exception("embed_query failed")
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note=f"Embedding failed ({exc})",
            data={"error_type": "embed", "message": str(exc)},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text=f"Corpus search failed (embedding: {exc}).",
            signal="tool_error",
        )

    # 2. Vector search
    try:
        if chroma is not None:
            ids, id_to_distance = _search_chroma(
                embedding, k, chroma, effective_filters,
            )
        else:
            assert vertex is not None
            ids, id_to_distance = _search_vertex(
                embedding, k, vertex, effective_filters,
            )
    except Exception as exc:
        logger.exception("vector search failed")
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note=f"Vector search failed ({exc})",
            data={"error_type": "vector", "message": str(exc)},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text=f"Corpus search failed (vector store: {exc}).",
            signal="tool_error",
        )

    if not ids:
        _safe_emit(emitter, SkillEvent(
            signal="no_sources", step_id=_STEP_ID,
            note="Vector store returned 0 neighbors",
            data={"query": clean_query, "k": k},
            task_type="info", task_severity="low",
        ))
        return SkillResult(
            text="No corpus chunks found for this query.",
            signal="no_sources",
            extra={"ids": [], "distances": {}},
        )

    # 3. Hydrate metadata from Postgres
    try:
        if db_query_fn is not None:
            rows = _hydrate_via_db_agent(ids, database, db_query_fn)
        else:
            assert database_url is not None
            rows = _hydrate_via_psycopg2(ids, database_url)
    except Exception as exc:
        logger.exception("metadata hydration failed")
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note=f"Metadata hydration failed ({exc})",
            data={"error_type": "db", "message": str(exc)},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text=f"Corpus search failed (db: {exc}).",
            signal="tool_error",
        )

    # 4. Reorder by vector-store ranking + convert distance to similarity
    id_to_row: dict[str, dict[str, Any]] = {str(r.get("id")): r for r in rows}
    chunks: list[ChunkRef] = []
    sources: list[SourceRef] = []
    for rank_idx, _id in enumerate(ids, 1):
        r = id_to_row.get(str(_id))
        if not r:
            continue  # vector store id with no Postgres row — skip
        text = r.get("text") or ""
        doc_id = str(r["document_id"]) if r.get("document_id") else ""
        doc_name = (
            r.get("document_display_name")
            or r.get("document_filename")
            or "document"
        )
        distance = id_to_distance.get(str(_id))
        # cosine distance in [0, 2] → similarity in [0, 1]
        score = 0.0
        if distance is not None:
            try:
                score = round(max(0.0, min(1.0, 1.0 - float(distance) / 2.0)), 4)
            except (TypeError, ValueError):
                pass
        chunks.append(ChunkRef(
            text=text,
            score=score,
            document_id=doc_id,
            document_name=doc_name,
            page_number=r.get("page_number"),
            chunk_id=str(r.get("id") or ""),
            metadata={
                "source_type": r.get("source_type") or "chunk",
                "paragraph_index": r.get("paragraph_index"),
                "distance": distance,
            },
        ))
        sources.append(SourceRef(
            document_name=doc_name,
            document_id=doc_id or None,
            source_type=r.get("source_type") or "chunk",
            page_number=r.get("page_number"),
            index=rank_idx,
            text=(text[:300] + "…") if len(text) > 300 else text,
            authority="corpus",
        ))

    if not chunks:
        # Vector store returned ids but Postgres had nothing — sync lag
        _safe_emit(emitter, SkillEvent(
            signal="no_sources", step_id=_STEP_ID,
            note=f"{len(ids)} vector hit(s) but no metadata rows (sync lag?)",
            data={"vector_hit_count": len(ids), "metadata_rows": 0},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text="No corpus chunks resolved (vector store and Postgres out of sync).",
            signal="no_sources",
            extra={"vector_hit_count": len(ids)},
        )

    _safe_emit(emitter, SkillEvent(
        signal="tool_completed", step_id=_STEP_ID,
        note=f"Found {len(chunks)} corpus chunk(s)",
        data={
            "chunk_count": len(chunks),
            "vector_hit_count": len(ids),
            "metadata_gap": len(ids) - len(chunks),
        },
        task_type="info", task_severity="low",
    ))

    # Summary text for consumers that want a quick "what was found" string
    summary_lines = [f"Found {len(chunks)} corpus chunk(s):"]
    for s in sources[:8]:
        page = f" p{s.page_number}" if s.page_number is not None else ""
        summary_lines.append(f"  [{s.index}] {s.document_name}{page}")

    return SkillResult(
        text="\n".join(summary_lines),
        sources=sources,
        chunks=chunks,
        signal="ok",
        extra={
            "query": clean_query,
            "k": k,
            "vector_hit_count": len(ids),
            "distances": id_to_distance,
        },
    )
