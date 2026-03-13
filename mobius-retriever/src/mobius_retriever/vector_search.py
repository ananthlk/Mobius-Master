"""Vector search: embed query -> Vertex find_neighbors -> Postgres fetch metadata."""
from __future__ import annotations

import logging
from typing import Any, Callable

from mobius_retriever.config import PathBConfig

logger = logging.getLogger(__name__)

VERTEX_SOURCE_TYPE_NAMESPACE = "source_type"


def _emit(emitter: Callable[[str], None] | None, msg: str) -> None:
    if emitter and msg.strip():
        emitter(msg.strip())


def _embed_query(text: str, cfg: PathBConfig) -> list[float]:
    """Produce embedding for query using Vertex AI."""
    import vertexai
    from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

    vertexai.init(project=cfg.vector.project, location=cfg.vector.region)
    model = TextEmbeddingModel.from_pretrained(cfg.embedding.model)
    inputs = [TextEmbeddingInput(text, task_type=cfg.embedding.task_type)]
    resp = model.get_embeddings(inputs, output_dimensionality=cfg.embedding.output_dimensionality)
    if not resp or not resp[0].values:
        raise ValueError("Empty embedding returned from Vertex")
    return list(resp[0].values)


def _build_namespaces(cfg: PathBConfig, source_type_allow: list[str] | None) -> list[Any]:
    """Build Vertex filter namespaces from config."""
    ns: list[Any] = []
    try:
        from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import Namespace
    except ImportError as e:
        logger.warning("Vertex Namespace not available: %s", e)
        return ns
    def _valid(val: str) -> bool:
        v = (val or "").strip()
        return bool(v) and "${" not in v

    f = cfg.filters
    if _valid(f.document_payer):
        ns.append(Namespace(name="document_payer", allow_tokens=[f.document_payer], deny_tokens=[]))
    if _valid(f.document_state):
        ns.append(Namespace(name="document_state", allow_tokens=[f.document_state], deny_tokens=[]))
    if _valid(f.document_program):
        ns.append(Namespace(name="document_program", allow_tokens=[f.document_program], deny_tokens=[]))
    if _valid(f.document_authority_level):
        ns.append(Namespace(name="document_authority_level", allow_tokens=[f.document_authority_level], deny_tokens=[]))
    if source_type_allow:
        ns.append(Namespace(name=VERTEX_SOURCE_TYPE_NAMESPACE, allow_tokens=source_type_allow, deny_tokens=[]))
    return ns


def _vertex_find_neighbors(
    cfg: PathBConfig,
    query_embedding: list[float],
    k: int,
    namespaces: list[Any],
    emitter: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Query Vertex, return list of {id, distance}."""
    from google.cloud import aiplatform

    aiplatform.init(project=cfg.vector.project, location=cfg.vector.region)
    endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=cfg.vector.index_endpoint_id)
    _emit(emitter, "Searching Vertex...")
    resp = endpoint.find_neighbors(
        deployed_index_id=cfg.vector.deployed_index_id,
        queries=[query_embedding],
        num_neighbors=k,
        filter=namespaces if namespaces else None,
    )
    neighbors = resp[0] if resp else []
    out: list[dict[str, Any]] = []
    for n in neighbors:
        nid = getattr(n, "id", None)
        if not nid:
            continue
        dist = getattr(n, "distance", None)
        out.append({"id": str(nid), "distance": float(dist) if dist is not None else None})
    _emit(emitter, f"Vertex returned {len(out)} neighbor(s)")
    return out


def _fetch_metadata(ids: list[str], postgres_url: str) -> dict[str, dict[str, Any]]:
    """Fetch rows from published_rag_metadata by id."""
    if not ids or not postgres_url:
        return {}
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        return {}
    try:
        conn = psycopg2.connect(postgres_url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT id, document_id, source_type, text, page_number, document_display_name, document_filename, document_authority_level
               FROM published_rag_metadata WHERE id::text = ANY(%s)""",
            (ids,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {str(r["id"]): dict(r) for r in rows}
    except Exception as e:
        logger.exception("Postgres fetch failed: %s", e)
        return {}


def distance_to_similarity(distance: float | None) -> float | None:
    """Cosine distance [0,2] -> similarity [0,1]. Same as chat."""
    if distance is None:
        return None
    try:
        d = float(distance)
        return max(0.0, min(1.0, 1.0 - d / 2.0))
    except (TypeError, ValueError):
        return None


def vector_search(
    question: str,
    cfg: PathBConfig,
    source_type_allow: list[str] | None = None,
    emitter: Callable[[str], None] | None = None,
    min_results_for_namespace: int | None = None,
) -> list[dict[str, Any]]:
    """
    Run vector search: embed -> Vertex -> Postgres.

    Uses namespaces: document_authority_level, document_payer, document_state, document_program, source_type.
    If namespaced query returns fewer than min_results_for_namespace (default: top_k), retries without namespace.

    Returns list of dicts with id, text, document_id, page_number, source_type, similarity, confidence.
    """
    _emit(emitter, "Embedding question...")
    query_embedding = _embed_query(question, cfg)
    namespaces = _build_namespaces(cfg, source_type_allow)
    min_results = min_results_for_namespace if min_results_for_namespace is not None else max(1, cfg.top_k)

    _emit(emitter, f"Filters: authority_level={cfg.filters.document_authority_level or '(none)'} payer={cfg.filters.document_payer or '(none)'} source_type_allow={source_type_allow}")
    neighbors = _vertex_find_neighbors(cfg, query_embedding, cfg.top_k, namespaces, emitter)

    if neighbors and len(neighbors) >= min_results:
        pass  # Use namespaced results
    elif neighbors and len(neighbors) < min_results and namespaces:
        _emit(emitter, f"Namespaced query returned {len(neighbors)} < {min_results}; retrying without namespace")
        neighbors_fallback = _vertex_find_neighbors(cfg, query_embedding, cfg.top_k, [], emitter)
        if neighbors_fallback:
            neighbors = neighbors_fallback
    elif not neighbors and namespaces:
        _emit(emitter, "Namespaced query returned 0; retrying without namespace")
        neighbors = _vertex_find_neighbors(cfg, query_embedding, cfg.top_k, [], emitter)

    if not neighbors:
        _emit(emitter, "No neighbors from Vertex; check index has data.")
        return []
    ids = [n["id"] for n in neighbors]
    _emit(emitter, f"Fetching {len(ids)} metadata rows from Postgres...")
    meta_by_id = _fetch_metadata(ids, cfg.postgres_url)
    ordered: list[dict[str, Any]] = []
    id_to_distance = {n["id"]: n.get("distance") for n in neighbors}
    _emit(emitter, f"Postgres returned {len(meta_by_id)} row(s) for {len(ids)} id(s)")
    for n in neighbors:
        nid = n["id"]
        meta = meta_by_id.get(nid)
        if not meta:
            continue
        dist = id_to_distance.get(nid)
        sim = distance_to_similarity(dist)
        doc_name = meta.get("document_display_name") or meta.get("document_filename") or "document"
        ordered.append({
            "id": meta.get("id"),
            "text": meta.get("text") or "",
            "document_id": meta.get("document_id"),
            "document_name": doc_name,
            "document_authority_level": (meta.get("document_authority_level") or "").strip() or None,
            "page_number": meta.get("page_number"),
            "source_type": meta.get("source_type") or "chunk",
            "distance": dist,
            "similarity": sim,
            "confidence": sim,
        })
    return ordered
