"""Path B: vector search + limited reranking. Configurable and versioned."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from pathlib import Path

from mobius_retriever.bm25_search import bm25_search, fetch_seed_chunks_for_document_ids
from mobius_retriever.config import (
    PathBConfig,
    apply_normalize_bm25,
    load_bm25_sigmoid_config,
    load_path_b_config,
    load_reranker_config,
    load_retrieval_cutoffs,
)
from mobius_retriever.rerank import rerank_path_b
from mobius_retriever.reranker import rerank_with_config
from mobius_retriever.vector_search import vector_search

logger = logging.getLogger(__name__)


@dataclass
class ChunkResult:
    """Single retrieved chunk."""
    id: Any
    text: str
    document_id: Any
    document_name: str
    page_number: int | None
    source_type: str
    similarity: float | None
    confidence: float | None
    distance: float | None
    raw_score: float | None = None
    rank: int = 0
    provision_type: str = "sentence"  # "paragraph" | "sentence"

    @classmethod
    def from_dict(cls, d: dict[str, Any], rank: int = 0) -> ChunkResult:
        return cls(
            id=d.get("id"),
            text=d.get("text") or "",
            document_id=d.get("document_id"),
            document_name=d.get("document_name") or "document",
            page_number=d.get("page_number"),
            source_type=d.get("source_type") or "chunk",
            similarity=d.get("similarity"),
            confidence=d.get("confidence"),
            distance=d.get("distance"),
            raw_score=d.get("raw_score"),
            rank=rank,
            provision_type=d.get("provision_type", "sentence"),
        )

    @property
    def score_display(self) -> str:
        """Score for display (similarity, raw_score, or —)."""
        if self.similarity is not None:
            return f"{self.similarity:.3f}"
        if self.raw_score is not None:
            return f"{self.raw_score:.3f}"
        return "—"


@dataclass
class RetrievalResult:
    """Result of Path B retrieval."""
    chunks: list[ChunkResult] = field(default_factory=list)
    config_version: str = ""
    config_name: str = ""
    path: str = "path_b"
    raw: list[dict[str, Any]] = field(default_factory=list)


def retrieve_path_b(
    question: str,
    config: PathBConfig | None = None,
    config_path: str | None = None,
    source_type_allow: list[str] | None = None,
    emitter: Callable[[str], None] | None = None,
) -> RetrievalResult:
    """
    Path B: vector search + limited reranking (no tags).
    Used as A/B arm or standalone vector-only retrieval.

    Args:
        question: Search-ready question text
        config: PathBConfig (if provided, config_path ignored)
        config_path: Path to YAML config (used if config is None)
        source_type_allow: Optional filter for source_type (e.g. ["hierarchical"])
        emitter: Optional callback for progress/logging

    Returns:
        RetrievalResult with chunks
    """
    if config is None:
        if not config_path:
            raise ValueError("Either config or config_path must be provided")
        config = load_path_b_config(Path(config_path))
    # Use param if provided, else config's source_type_allow
    st = source_type_allow if source_type_allow is not None else getattr(config.filters, "source_type_allow", None)
    chunks = vector_search(question, config, source_type_allow=st, emitter=emitter)
    if config.rerank.reranker_config_path:
        reranker_cfg = load_reranker_config(config.rerank.reranker_config_path)
        question_tags = None
        doc_tags_by_id = {}
        rag_url = config.rag_database_url or config.postgres_url
        line_tags_by_key: dict = {}
        if rag_url and "tag_match" in reranker_cfg.signals:
            from mobius_retriever.jpd_tagger import (
                tag_question_and_resolve_document_ids,
                fetch_document_tags_by_ids,
                fetch_line_tags_for_chunks,
            )
            jpd = tag_question_and_resolve_document_ids(question, rag_url, emitter=None)
            if jpd.has_tags:
                question_tags = jpd
                doc_ids = list({str(c.get("document_id", "")) for c in chunks if c.get("document_id")})
                if doc_ids:
                    doc_tags_by_id = fetch_document_tags_by_ids(rag_url, doc_ids)
                line_tags_by_key = fetch_line_tags_for_chunks(rag_url, chunks) if chunks else {}
        chunks = rerank_with_config(
            chunks,
            reranker_cfg,
            question_tags=question_tags,
            doc_tags_by_id=doc_tags_by_id,
            line_tags_by_key=line_tags_by_key,
        )
    else:
        chunks = rerank_path_b(chunks, config.rerank)
    # Apply vector cutoff: keep only chunks with similarity >= cutoff
    cutoffs = load_retrieval_cutoffs()
    chunks = [c for c in chunks if (c.get("similarity") or 0.0) >= cutoffs.vector_abstention_cutoff]
    results = [ChunkResult.from_dict(c, rank=i + 1) for i, c in enumerate(chunks)]
    return RetrievalResult(
        chunks=results,
        config_version=config.version,
        config_name=config.name,
        path="path_b",
        raw=chunks,
    )


def retrieve_bm25(
    question: str,
    postgres_url: str = "",
    authority_level: str | None = None,
    source_types: list[str] | None = None,
    tag_filters: dict[str, str] | None = None,
    use_question_tags: bool = False,
    use_jpd_tagger: bool = False,
    rag_database_url: str | None = None,
    top_k: int = 10,
    top_k_override: int | None = None,
    config: PathBConfig | None = None,
    config_path: str | None = None,
    emitter: Callable[[str], None] | None = None,
    include_document_ids: list[str] | None = None,
) -> RetrievalResult:
    """
    BM25 retrieval on hierarchical sentence corpus. No reranking.
    Uses PathBConfig for postgres_url, authority_level, top_k when provided.
    use_jpd_tagger: tag question with J/P/D lexicon, resolve document_ids, scope BM25 corpus.
    rag_database_url: RAG DB for lexicon + document_tags (required when use_jpd_tagger=True).
    include_document_ids: document_ids from previous turns; one paragraph per doc prepended when not in BM25 results.
    """
    if config_path and not config:
        config = load_path_b_config(Path(config_path))
    if config is not None:
        postgres_url = config.postgres_url or postgres_url
        al = config.filters.document_authority_level
        if al and "${" not in al:
            authority_level = authority_level or al
        top_k = top_k_override if top_k_override is not None else config.top_k
        if rag_database_url is None:
            rag_database_url = config.rag_database_url or ""
    else:
        rag_database_url = rag_database_url or ""

    filters = dict(tag_filters or {})
    if use_question_tags:
        from mobius_retriever.tagger import tag_question
        qt = tag_question(question)
        filters.update(qt.as_filters())

    document_ids: list[str] | None = None
    n_tags: int = 0
    if use_jpd_tagger and rag_database_url:
        def _e(m: str) -> None:
            if emitter and m.strip():
                emitter(m.strip())
        _e("BM25: J/P/D tagger ON; resolving document_ids from lexicon + document_tags")
        from mobius_retriever.jpd_tagger import tag_question_and_resolve_document_ids
        jpd = tag_question_and_resolve_document_ids(question, rag_database_url, emitter=emitter)
        if jpd.error:
            logger.debug("J/P/D tagger: %s", jpd.error)
            _e(f"J/P/D tagger error: {jpd.error}")
        elif jpd.has_document_ids:
            document_ids = jpd.document_ids
            _e(f"BM25: corpus scoped to {len(document_ids)} document(s) (document_tags match)")
        elif jpd.has_tags:
            _e("BM25: J/P/D matched tags but 0 document_ids in document_tags -> full corpus")
        else:
            _e("BM25: J/P/D no tags matched question -> full corpus")
        n_tags = len(jpd.p_tags or {}) + len(jpd.d_tags or {}) + len(jpd.j_tags or {})

    if not postgres_url:
        return RetrievalResult(chunks=[], config_name="bm25", path="bm25")
    chunks = bm25_search(
        question=question,
        postgres_url=postgres_url,
        authority_level=authority_level,
        source_types=source_types,
        tag_filters=filters if filters else None,
        document_ids=document_ids,
        top_k=top_k,
        include_paragraphs=True,
        top_k_per_type=top_k,
        emitter=emitter,
    )
    # Prepend seed chunks for previous turn documents not already in BM25 results
    if include_document_ids:
        present_doc_ids = {str(c.get("document_id", "")) for c in chunks if c.get("document_id")}
        missing = [d for d in include_document_ids if d and str(d).strip() and str(d).strip() not in present_doc_ids]
        if missing:
            seed_chunks = fetch_seed_chunks_for_document_ids(
                postgres_url=postgres_url,
                document_ids=missing,
                authority_level=authority_level,
                tag_filters=filters if filters else None,
                emitter=emitter,
            )
            chunks = seed_chunks + chunks
    # Use raw BM25 score as-is (no per-tag normalization). Let reranker handle tag-based boost.
    cutoffs = load_retrieval_cutoffs()
    bm25_cfg = load_bm25_sigmoid_config()
    if bm25_cfg:
        cutoff = cutoffs.bm25_abstention_cutoff_normalized
        filtered: list[dict[str, Any]] = []
        for c in chunks:
            raw = c.get("raw_score")
            if raw is None:
                continue
            pt = c.get("provision_type", "sentence")
            norm = apply_normalize_bm25(float(raw), pt, bm25_cfg)
            if norm >= cutoff:
                filtered.append(c)
        chunks = filtered
    results = [ChunkResult.from_dict(c, rank=i + 1) for i, c in enumerate(chunks)]
    return RetrievalResult(
        chunks=results,
        config_version="",
        config_name="bm25",
        path="bm25",
        raw=chunks,
    )
