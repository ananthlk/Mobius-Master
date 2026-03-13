"""RAG pipeline: retrieve → rerank → assemble. Shared by Chat and retrieval-eval."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Literal

from mobius_retriever.config import (
    PathBConfig,
    apply_normalize_bm25,
    load_bm25_sigmoid_config,
    load_path_b_config,
    load_reranker_config,
    load_retrieval_cutoffs,
)
from mobius_retriever.retriever import retrieve_bm25
from mobius_retriever.vector_search import vector_search
from mobius_retriever.reranker import rerank_with_config
from mobius_retriever.assemble import assemble_docs, DocAssemblyConfig

logger = logging.getLogger(__name__)

_DEFAULT_RERANKER_CONFIG = "configs/reranker_v1.yaml"


def _bm25_to_rerank_dict(c: dict[str, Any], bm25_cfg: dict | None) -> dict[str, Any]:
    """Convert BM25 chunk to reranker input with similarity = sigmoid(raw_score)."""
    raw = c.get("raw_score")
    pt = c.get("provision_type", "sentence")
    if raw is not None and bm25_cfg:
        sim = apply_normalize_bm25(float(raw), pt, bm25_cfg)
    elif raw is not None:
        sim = min(1.0, float(raw) / 50.0)
    else:
        sim = c.get("similarity") or 0.0
    out: dict[str, Any] = {
        "id": c.get("id"),
        "text": c.get("text") or "",
        "document_id": c.get("document_id"),
        "document_name": c.get("document_name") or "document",
        "document_authority_level": c.get("document_authority_level"),
        "page_number": c.get("page_number"),
        "similarity": sim,
        "raw_score": raw,
        "provision_type": pt,
        "source_type": c.get("source_type", "hierarchical"),
    }
    return out


def _vector_to_chat_dict(c: dict[str, Any]) -> dict[str, Any]:
    """Convert vector chunk to pipeline format."""
    sim = c.get("similarity") or c.get("confidence") or 0.0
    return {
        "id": c.get("id"),
        "text": c.get("text") or "",
        "document_id": c.get("document_id"),
        "document_name": c.get("document_name") or "document",
        "page_number": c.get("page_number"),
        "source_type": c.get("source_type", "chunk"),
        "similarity": sim,
        "match_score": sim,
        "confidence": sim,
        "rerank_score": sim,
    }


def _merge_and_dedupe(
    bm25_raw: list[dict],
    vector_raw: list[dict],
    bm25_cfg: dict | None,
    trace: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Merge BM25 and vector chunks. Dedupe by id within each category (bm25_paragraph, bm25_sentence, vector), not across categories."""
    seen_by_category: dict[str, set[str]] = {
        "bm25_paragraph": set(),
        "bm25_sentence": set(),
        "vector": set(),
    }
    merged: list[dict[str, Any]] = []
    bm25_processed: list[dict[str, Any]] = []
    n_added_bm25 = 0
    n_skipped_bm25 = 0
    n_added_vector = 0
    n_skipped_vector = 0

    for c in bm25_raw:
        if not isinstance(c, dict):
            n_skipped_bm25 += 1
            continue
        cid = str(c.get("id") or "")
        pt = c.get("provision_type", "sentence")
        src = "bm25_sentence" if pt == "sentence" else "bm25_paragraph"
        seen = seen_by_category[src]
        action: str
        if cid and cid not in seen:
            seen.add(cid)
            d = _bm25_to_rerank_dict(c, bm25_cfg)
            d["retrieval_source"] = src
            merged.append(d)
            action = "added"
            n_added_bm25 += 1
        else:
            action = "skipped_duplicate_id"
            n_skipped_bm25 += 1
        if trace is not None:
            bm25_processed.append({
                "id": cid[:24] if cid else "",
                "provision_type": pt,
                "retrieval_source": src,
                "raw_score": c.get("raw_score"),
                "action": action,
            })

    for c in vector_raw:
        if not isinstance(c, dict):
            n_skipped_vector += 1
            continue
        cid = str(c.get("id") or "")
        seen = seen_by_category["vector"]
        if cid and cid not in seen:
            seen.add(cid)
            d = dict(c)
            if "similarity" not in d:
                d["similarity"] = d.get("confidence") or 0.0
            d["retrieval_source"] = "vector"
            merged.append(d)
            n_added_vector += 1
        else:
            n_skipped_vector += 1

    if trace is not None:
        merged_ids_by_source: dict[str, list[str]] = {"bm25_sentence": [], "bm25_paragraph": [], "vector": []}
        for m in merged:
            src = m.get("retrieval_source", "vector")
            if src in merged_ids_by_source:
                merged_ids_by_source[src].append(str(m.get("id", ""))[:24])
        trace["merge"] = {
            "bm25_processed": bm25_processed,
            "seen_ids_by_category": {k: list(v) for k, v in seen_by_category.items()},
            "n_added_bm25": n_added_bm25,
            "n_skipped_bm25": n_skipped_bm25,
            "n_added_vector": n_added_vector,
            "n_skipped_vector": n_skipped_vector,
            "merged_ids_by_source": merged_ids_by_source,
        }
    return merged


def run_rag_pipeline(
    question: str,
    path: Literal["mobius", "lazy"],
    config: PathBConfig | None = None,
    config_path: str | None = None,
    top_k: int = 10,
    apply_google_fallback: bool = True,
    google_search_url: str | None = None,
    emitter: Callable[[str], None] | None = None,
    n_factual: int | None = None,
    n_hierarchical: int | None = None,
    trace: dict[str, Any] | None = None,
    filter_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve → Rerank → Assemble. Returns assembled docs.

    - path="mobius": BM25 sentence + BM25 paragraph + Vector → merge → rerank → assemble
    - path="lazy": Vector only, top-k, return docs (no rerank, no assemble)
    """
    def _emit(msg: str) -> None:
        if emitter and msg.strip():
            emitter(msg.strip())

    if trace is not None:
        trace["path"] = path

    if config is None:
        cfg_path = config_path or "configs/path_b_v1.yaml"
        p = Path(cfg_path)
        if not p.is_absolute():
            pkg = Path(__file__).resolve().parent
            p = pkg.parent.parent / cfg_path
        config = load_path_b_config(p)

    rag_url = config.rag_database_url or config.postgres_url
    overrides = filter_overrides or {}
    # Apply overrides to config.filters (used by vector_search) and build tag_filters (for BM25)
    if overrides.get("filter_payer"):
        config.filters.document_payer = (overrides["filter_payer"] or "").strip()
    if overrides.get("filter_state"):
        config.filters.document_state = (overrides["filter_state"] or "").strip()
    if overrides.get("filter_program"):
        config.filters.document_program = (overrides["filter_program"] or "").strip()
    if overrides.get("filter_authority_level"):
        config.filters.document_authority_level = (overrides["filter_authority_level"] or "").strip()

    tag_filters: dict[str, str] = {}
    # Skip unresolved env vars (e.g. ${RAG_FILTER_STATE}) — they match no rows and zero the corpus.
    def _resolved(v: str) -> str:
        v = (v or "").strip()
        return v if v and "${" not in v else ""

    if _resolved(config.filters.document_payer):
        tag_filters["document_payer"] = config.filters.document_payer.strip()
    if _resolved(config.filters.document_state):
        tag_filters["document_state"] = config.filters.document_state.strip()
    if _resolved(config.filters.document_program):
        tag_filters["document_program"] = config.filters.document_program.strip()
    auth_level = config.filters.document_authority_level or None
    if auth_level and "${" in str(auth_level):
        auth_level = None

    if path == "lazy":
        _emit("Lazy path: top-k vector search only.")
        vec = vector_search(
            question,
            config,
            source_type_allow=getattr(config.filters, "source_type_allow", None),
            emitter=emitter,
        )
        return [_vector_to_chat_dict(c) for c in vec[:top_k]]

    # Mobius path
    _emit("Mobius path: BM25 + Vector → rerank → assemble.")
    t0_extract = time.perf_counter()
    bm25_emits: list[str] = []

    def _bm25_emit(m: str) -> None:
        if m.strip():
            bm25_emits.append(m.strip())
            if emitter:
                emitter(m.strip())

    bm25_result = retrieve_bm25(
        question=question,
        config=config,
        top_k=top_k,
        use_jpd_tagger=True,
        tag_filters=tag_filters if tag_filters else None,
        emitter=_bm25_emit,
    )
    vec_raw = vector_search(
        question,
        config,
        source_type_allow=getattr(config.filters, "source_type_allow", None),
        emitter=emitter,
    )
    cutoffs = load_retrieval_cutoffs()
    vec_filtered = [c for c in vec_raw if (c.get("similarity") or 0.0) >= cutoffs.vector_abstention_cutoff]

    bm25_cfg = load_bm25_sigmoid_config()
    t0_merge = time.perf_counter()
    merged = _merge_and_dedupe(bm25_result.raw, vec_filtered, bm25_cfg, trace=trace)
    extract_ms = int((time.perf_counter() - t0_extract) * 1000)
    merge_ms = int((time.perf_counter() - t0_merge) * 1000)

    if trace is not None:
        def _snip(c: dict, n: int = 55) -> str:
            return ((c.get("text") or "")[:n] + ("..." if len(c.get("text") or "") > n else "")).replace("\n", " ")
        postgres_set = bool((config.postgres_url or "").strip())
        trace["extract"] = {
            "bm25_raw_n": len(bm25_result.raw),
            "bm25_postgres_url_set": postgres_set,
            "bm25_emits": bm25_emits,
            "vector_raw_n": len(vec_raw),
            "vector_abstention_cutoff": cutoffs.vector_abstention_cutoff,
            "vector_filtered_n": len(vec_filtered),
            "merged_n": len(merged),
            "extract_ms": extract_ms,
            "merge_ms": merge_ms,
            "bm25_sigmoid_snapshot": (bm25_cfg or {}).get("provision_types"),
            "bm25_chunks": [
                {"provision_type": c.get("provision_type"), "raw_score": c.get("raw_score"), "snippet": _snip(c)}
                for c in bm25_result.raw[:10]
            ],
            "vector_chunks": [
                {"similarity": c.get("similarity"), "snippet": _snip(c)}
                for c in vec_filtered[:8]
            ],
        }

    # Rerank
    t0_rerank = time.perf_counter()
    try:
        reranker_cfg = load_reranker_config(
            config.rerank.reranker_config_path or _DEFAULT_RERANKER_CONFIG
        )
        if reranker_cfg.signals and merged and rag_url:
            from mobius_retriever.jpd_tagger import (
                tag_question_and_resolve_document_ids,
                fetch_document_tags_by_ids,
                fetch_line_tags_for_chunks,
            )
            doc_ids = list({str(d.get("document_id", "")) for d in merged if d.get("document_id")})
            doc_tags = fetch_document_tags_by_ids(rag_url, doc_ids) if doc_ids else {}
            line_tags = fetch_line_tags_for_chunks(rag_url, merged) if merged else {}
            jpd = tag_question_and_resolve_document_ids(question, rag_url, emitter=emitter)
            qtags = jpd if ("tag_match" in (reranker_cfg.signals or {})) and jpd.has_tags else None
            merged = rerank_with_config(
                merged, reranker_cfg,
                question_tags=qtags,
                doc_tags_by_id=doc_tags,
                line_tags_by_key=line_tags,
                trace=trace,
            )
    except Exception as e:
        logger.warning("Reranker failed: %s; using pre-rerank order.", e)
    rerank_ms = int((time.perf_counter() - t0_rerank) * 1000)
    if trace is not None and "rerank" in trace:
        trace["rerank"]["rerank_ms"] = rerank_ms

    # Convert to chat format (preserve retrieval_source, provision_type for blend selection)
    _debug = os.environ.get("DEBUG_RAG", "1").lower() in ("1", "true", "yes")
    if _debug and merged:
        bad = [(i, type(c).__name__) for i, c in enumerate(merged) if not isinstance(c, dict)]
        if bad:
            logger.warning("[DEBUG_RAG pipeline] merged has non-dict at %s", bad[:10])
    chunks_for_assembly: list[dict[str, Any]] = []
    merged = [c for c in merged if isinstance(c, dict)]
    for c in merged:
        raw = c.get("raw_score")
        src = c.get("retrieval_source", "")
        pt = c.get("provision_type")
        if pt is None and src == "vector":
            pt = "paragraph"  # Vector returns hierarchical only; treat as paragraph
        pt = pt or "sentence"
        if raw is not None and bm25_cfg:
            match = apply_normalize_bm25(float(raw), pt, bm25_cfg)
        else:
            match = c.get("similarity") or c.get("rerank_score") or 0.0
        chunks_for_assembly.append({
            "id": c.get("id"),
            "text": c.get("text") or "",
            "document_id": c.get("document_id"),
            "document_name": c.get("document_name") or "document",
            "page_number": c.get("page_number"),
            "source_type": c.get("source_type", "chunk"),
            "match_score": match,
            "confidence": match,
            "rerank_score": c.get("rerank_score") or match,
            "retrieval_source": c.get("retrieval_source", "vector"),
            "provision_type": pt,
        })

    # Assemble (blend selection by n_factual/n_hierarchical when provided)
    t0_assemble = time.perf_counter()
    assembled = assemble_docs(
        chunks_for_assembly,
        question,
        apply_google=apply_google_fallback,
        google_search_url=google_search_url,
        emitter=emitter,
        n_factual=n_factual,
        n_hierarchical=n_hierarchical,
        trace=trace,
    )
    assemble_ms = int((time.perf_counter() - t0_assemble) * 1000)
    if trace is not None:
        trace["assemble_ms"] = assemble_ms
        trace["n_assembled"] = len(assembled)
        n_corpus = sum(1 for c in assembled if isinstance(c, dict) and (c.get("rerank_score") or 0) > 0)
        trace["n_corpus"] = n_corpus
        trace["n_google"] = len(assembled) - n_corpus
    return assembled
