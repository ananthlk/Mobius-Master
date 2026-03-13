"""Versioned, configurable retrieval config. Loads from YAML with env var resolution."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _resolve_env(val: str) -> str:
    """Replace ${VAR} or $VAR with os.environ."""
    if not isinstance(val, str):
        return val

    def repl(m: re.Match) -> str:
        key = m.group(1) or m.group(2)
        return os.environ.get(key, m.group(0)) if key else m.group(0)

    return re.sub(r"\$\{([^}]+)\}|\$(\w+)", repl, val)


def _deep_resolve(data: Any) -> Any:
    """Recursively resolve ${VAR} in strings."""
    if isinstance(data, str):
        return _resolve_env(data)
    if isinstance(data, dict):
        return {k: _deep_resolve(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_deep_resolve(x) for x in data]
    return data


@dataclass
class VectorConfig:
    """Vertex AI Vector Search config."""
    project: str
    region: str
    index_endpoint_id: str
    deployed_index_id: str


@dataclass
class EmbeddingConfig:
    """Query embedding config."""
    model: str
    output_dimensionality: int
    task_type: str


@dataclass
class FiltersConfig:
    """Jurisdiction / filter config."""
    document_authority_level: str = ""
    document_payer: str = ""
    document_state: str = ""
    document_program: str = ""
    source_type_allow: list[str] | None = None  # e.g. ["hierarchical"] for hierarchical chunks only


@dataclass
class RerankConfig:
    """Limited reranking config for Path B."""
    source_type_order: tuple[str, ...] = ("policy", "section", "chunk", "hierarchical", "fact")
    apply_hierarchy_sort: bool = False  # sort by source_type hierarchy
    confidence_min: float | None = None
    reranker_config_path: str | None = None  # path to reranker YAML; if set, use config-driven reranker


@dataclass
class RerankerSignalConfig:
    """Single signal in reranker config."""
    weight: float
    formula: str
    params: dict = field(default_factory=dict)
    normalize: bool = True  # if False, use raw directly (e.g. score already calibrated via sigmoid)


@dataclass
class RerankerConfig:
    """Config-driven reranker: additive weighted scoring."""
    version: str
    name: str
    combination_method: str  # additive | multiplicative
    signals: dict[str, RerankerSignalConfig]
    post_rerank_decay_threshold: float | None = None  # legacy: global decay; used as fallback
    post_rerank_decay_by_category: dict[str, float] | None = None  # per retrieval_source threshold


@dataclass
class PathBConfig:
    """Path B: vector search + limited reranking."""
    version: str
    name: str
    vector: VectorConfig
    embedding: EmbeddingConfig
    filters: FiltersConfig
    postgres_url: str
    rag_database_url: str = ""  # RAG DB for lexicon + document_tags (J/P/D); defaults to postgres_url
    top_k: int = 10
    rerank: RerankConfig = field(default_factory=RerankConfig)
    raw: dict = field(default_factory=dict)


def load_path_b_config(path: Path) -> PathBConfig:
    """Load Path B config from YAML. Version must be present."""
    with open(path, "r") as f:
        raw = yaml.safe_load(f) or {}
    raw = _deep_resolve(raw)
    v = raw.get("version")
    if not v:
        raise ValueError("Config must have 'version' field")
    name = raw.get("name", "path_b")
    vertex = raw.get("vertex") or {}
    embedding = raw.get("embedding") or {}
    filters = raw.get("filters") or {}
    rerank_raw = raw.get("rerank") or {}
    postgres_url = (raw.get("postgres_url") or "").strip()
    if not postgres_url or "${" in str(postgres_url):
        postgres_url = os.environ.get("CHAT_RAG_DATABASE_URL", "") or os.environ.get("CHAT_DATABASE_URL", "")
    rag_database_url = (raw.get("rag_database_url") or "").strip()
    if not rag_database_url:
        rag_database_url = os.environ.get("RAG_DATABASE_URL", "") or postgres_url
    def _normalize_deployed_id(v: str) -> str:
        """Resolve display names to actual deployed index ID (matches chat_config behavior)."""
        v = (v or "").strip()
        if not v or v.startswith("endpoint_mobius_chat_publi_"):
            return v
        if v in ("Endpoint_mobius_chat_published_rag", "mobius_chat_published_rag") or "published_rag" in v.lower():
            return os.environ.get("VERTEX_DEPLOYED_INDEX_ACTUAL", "endpoint_mobius_chat_publi_1769989702095")
        return v

    def _fallback(key: str, env_keys: list[str], default: str = "") -> str:
        v = vertex.get(key) or ""
        v = (v if isinstance(v, str) else str(v)).strip()
        if not v or "${" in v:
            for ek in env_keys:
                v = os.environ.get(ek, "")
                if v:
                    return v.strip()
        return v or default

    vector = VectorConfig(
        project=_fallback("project", ["VERTEX_PROJECT", "VERTEX_PROJECT_ID"]),
        region=_fallback("region", ["VERTEX_REGION", "VERTEX_LOCATION"], "us-central1"),
        index_endpoint_id=_fallback("index_endpoint_id", ["VERTEX_INDEX_ENDPOINT_ID", "CHAT_VERTEX_INDEX_ENDPOINT_ID"]),
        deployed_index_id=_normalize_deployed_id(
            _fallback("deployed_index_id", ["VERTEX_DEPLOYED_INDEX_ID", "CHAT_VERTEX_DEPLOYED_INDEX_ID"])
        ),
    )
    emb = EmbeddingConfig(
        model=(embedding.get("model") or "gemini-embedding-001").strip(),
        output_dimensionality=int(embedding.get("output_dimensionality", 1536)),
        task_type=(embedding.get("task_type") or "RETRIEVAL_DOCUMENT").strip(),
    )
    st_allow = filters.get("source_type_allow")
    if isinstance(st_allow, list):
        source_type_allow = [str(x).strip() for x in st_allow if str(x).strip()]
    else:
        source_type_allow = None
    filt = FiltersConfig(
        document_authority_level=(filters.get("document_authority_level") or "").strip(),
        document_payer=(filters.get("document_payer") or "").strip(),
        document_state=(filters.get("document_state") or "").strip(),
        document_program=(filters.get("document_program") or "").strip(),
        source_type_allow=source_type_allow or None,
    )
    st_order = rerank_raw.get("source_type_order")
    reranker_path = (rerank_raw.get("reranker_config") or "").strip() or None
    rerank = RerankConfig(
        source_type_order=tuple(st_order) if isinstance(st_order, list) else ("policy", "section", "chunk", "hierarchical", "fact"),
        apply_hierarchy_sort=bool(rerank_raw.get("apply_hierarchy_sort", False)),
        confidence_min=rerank_raw.get("confidence_min"),
        reranker_config_path=reranker_path,
    )
    return PathBConfig(
        version=str(v),
        name=name,
        vector=vector,
        embedding=emb,
        filters=filt,
        postgres_url=postgres_url,
        rag_database_url=rag_database_url or postgres_url,
        top_k=int(raw.get("top_k", 10)),
        rerank=rerank,
        raw=raw,
    )


@dataclass
class RetrievalCutoffs:
    """Retrieval abstention cutoffs from calibration (bm25_sigmoid + vector)."""

    bm25_abstention_cutoff_normalized: float
    bm25_abstention_cutoff_raw: float | None
    vector_abstention_cutoff: float
    raw: dict


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    import math
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def load_bm25_sigmoid_config(path: Path | None = None) -> dict | None:
    """Load bm25_sigmoid.yaml for normalization. Returns None if file missing."""
    if path is None:
        _pkg = Path(__file__).resolve().parent
        path = _pkg.parent.parent / "configs" / "bm25_sigmoid.yaml"
    if not path.exists():
        return None
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def apply_normalize_bm25(raw_score: float, provision_type: str, bm25_cfg: dict) -> float:
    """Apply sigmoid normalization using bm25_sigmoid config. Returns value in [0, 1]."""
    pt = bm25_cfg.get("provision_types", {}).get(provision_type, {})
    k = pt.get("k", 1.0)
    x0 = pt.get("x0", 0.0)
    return _sigmoid(k * (raw_score - x0))


def load_reranker_config(path: Path | str) -> RerankerConfig:
    """Load reranker YAML. Path may be relative to retriever root (e.g. configs/reranker_v1.yaml) or absolute."""
    p = Path(path)
    if not p.is_absolute():
        _pkg = Path(__file__).resolve().parent
        root = _pkg.parent.parent
        p = root / p
    if not p.exists():
        raise FileNotFoundError(f"Reranker config not found: {p}")
    with open(p, "r") as f:
        raw = yaml.safe_load(f) or {}
    v = raw.get("version", "1")
    name = raw.get("name", "reranker")
    comb = (raw.get("combination") or {}).get("method", "additive")
    signals_raw = raw.get("signals") or {}
    signals: dict[str, RerankerSignalConfig] = {}
    if not isinstance(signals_raw, dict):
        signals_raw = {}
    for k, s in signals_raw.items():
        if isinstance(s, dict):
            norm_val = s.get("normalize")
            normalize = bool(norm_val) if norm_val is not None else True
            signals[k] = RerankerSignalConfig(
                weight=float(s.get("weight", 0.0)),
                formula=(s.get("formula") or "direct").strip(),
                params=dict(s.get("params") or {}),
                normalize=normalize,
            )
    post = raw.get("post_rerank") or {}
    decay_thresh = post.get("decay_threshold")
    post_rerank_decay_threshold = float(decay_thresh) if decay_thresh is not None else None
    decay_by_cat = post.get("decay_by_category")
    post_rerank_decay_by_category = None
    if isinstance(decay_by_cat, dict):
        post_rerank_decay_by_category = {str(k): float(v) for k, v in decay_by_cat.items()}
    return RerankerConfig(
        version=str(v),
        name=name,
        combination_method=str(comb),
        signals=signals,
        post_rerank_decay_threshold=post_rerank_decay_threshold,
        post_rerank_decay_by_category=post_rerank_decay_by_category,
    )


def load_retrieval_cutoffs(path: Path | None = None) -> RetrievalCutoffs:
    """Load retrieval_cutoffs.yaml. Exposes bm25 and vector abstention thresholds."""
    if path is None:
        # Default: configs/retrieval_cutoffs.yaml relative to this package
        _pkg = Path(__file__).resolve().parent
        path = _pkg.parent.parent / "configs" / "retrieval_cutoffs.yaml"
    raw: dict = {}
    if path.exists():
        with open(path, "r") as f:
            raw = yaml.safe_load(f) or {}

    bm25 = raw.get("bm25") or {}
    vector = raw.get("vector") or {}

    return RetrievalCutoffs(
        bm25_abstention_cutoff_normalized=float(bm25.get("abstention_cutoff_normalized", 0.5)),
        bm25_abstention_cutoff_raw=bm25.get("abstention_cutoff_raw"),
        vector_abstention_cutoff=float(vector.get("abstention_cutoff", 0.5)),
        raw=raw,
    )
