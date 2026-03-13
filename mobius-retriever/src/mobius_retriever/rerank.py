"""Limited reranking for Path B: hierarchy sort + confidence filter."""
from __future__ import annotations

from typing import Any

from mobius_retriever.config import RerankConfig


def _hierarchy_rank(source_type: str | None, order: tuple[str, ...]) -> int:
    """Lower rank = higher in hierarchy."""
    st = (source_type or "chunk").strip().lower()
    for i, t in enumerate(order):
        if st == t or st.startswith(t):
            return i
    return len(order)


def rerank_path_b(
    chunks: list[dict[str, Any]],
    cfg: RerankConfig,
) -> list[dict[str, Any]]:
    """
    Limited reranking: optionally sort by source_type hierarchy, filter by confidence_min.
    """
    out = list(chunks)
    if cfg.apply_hierarchy_sort:
        order = cfg.source_type_order
        out = sorted(
            out,
            key=lambda c: (_hierarchy_rank(c.get("source_type"), order), -(c.get("confidence") or c.get("similarity") or 0.0)),
        )
    if cfg.confidence_min is not None:
        out = [c for c in out if (c.get("confidence") or c.get("similarity") or 0.0) >= cfg.confidence_min]
    return out
