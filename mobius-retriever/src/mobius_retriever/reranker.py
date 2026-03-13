"""Config-driven reranker: additive weighted scoring of retrieval chunks."""
from __future__ import annotations

from typing import Any

from mobius_retriever.config import RerankerConfig, RerankerSignalConfig


def _get_score(chunk: dict[str, Any]) -> float:
    """Extract retrieval score (similarity or confidence) from chunk."""
    return float(chunk.get("similarity") or chunk.get("confidence") or 0.0)


def _authority_level_score(authority_level: str | None) -> float:
    """Map document_authority_level to score. Higher = more authoritative."""
    al = (authority_level or "").strip().lower()
    if al == "contract_source_of_truth":
        return 1.0
    if al == "operational_suggested":
        return 0.65
    if al == "fyi_not_citable":
        return 0.35
    return 0.0  # unknown / empty


def _doc_set_or_dict(val: Any) -> tuple[set[str], dict[str, float]]:
    """Parse doc tag dict to (codes set, weights dict)."""
    if val is None:
        return set(), {}
    if isinstance(val, dict):
        codes = set(str(k) for k in val.keys() if k)
        weights = {str(k): float(v) if isinstance(v, (int, float)) else 1.0
                   for k, v in val.items() if k}
        return codes, weights
    return set(), {}


def _compute_tag_match(
    chunk: dict,
    question_tags: Any,
    doc_tags_by_id: dict[str, dict[str, Any]],
    params: dict,
    line_tags_by_key: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> float:
    """Tag overlap: count and intensity of J/D/P matches. Uses line-level tags when available."""
    score, _ = _compute_tag_match_with_breakdown(chunk, question_tags, doc_tags_by_id, params, line_tags_by_key)
    return score


def _norm_text(t: str) -> str:
    """Normalize text for line match (same as jpd_tagger._normalize_text_for_match)."""
    if not t or not isinstance(t, str):
        return ""
    return " ".join((t or "").split()).strip().lower()


def _get_chunk_tags(
    chunk: dict,
    doc_tags_by_id: dict[str, dict[str, Any]],
    line_tags_by_key: dict[tuple[str, str], dict[str, Any]] | None,
) -> dict[str, Any]:
    """Use line-level tags when available, else document-level tags.
    Always returns a dict (guards against list/other types from DB)."""
    if not isinstance(chunk, dict):
        return {}
    doc_id = str(chunk.get("document_id") or "")
    doc_tags = doc_tags_by_id.get(doc_id) if isinstance(doc_tags_by_id, dict) and doc_tags_by_id else {}
    if not isinstance(doc_tags, dict):
        doc_tags = {}
    if line_tags_by_key:
        line_key = (doc_id, _norm_text(chunk.get("text") or ""))
        if line_key in line_tags_by_key:
            val = line_tags_by_key[line_key]
            return val if isinstance(val, dict) else {}
    return doc_tags


def _compute_tag_match_with_breakdown(
    chunk: dict,
    question_tags: Any,
    doc_tags_by_id: dict[str, dict[str, Any]],
    params: dict,
    line_tags_by_key: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> tuple[float, dict[str, Any]]:
    """Compute tag_match score and return a per-tag breakdown for reporting.
    Uses line-level tags from policy_lines when available (line_tags_by_key); else document_tags.
    Returns (raw_score, breakdown) where breakdown includes:
      question_tags: {p_tags, d_tags, j_tags} (tag -> score from lexicon match)
      doc_tags: {p_tags, d_tags, j_tags} (tag -> doc/line weight)
      overlap: {p_tags, d_tags, j_tags} list of (tag, q_score, doc_score, doc_decayed, contrib)
      by_type: {p, d, j} -> count_norm, intensity_norm
      tag_source: "line" | "document"
    """
    doc_id = str(chunk.get("document_id") or "")
    doc_tags = _get_chunk_tags(chunk, doc_tags_by_id, line_tags_by_key)
    doc_decay = float(params.get("doc_decay_factor", 0.7))

    doc_p_codes, doc_p_weights = _doc_set_or_dict(doc_tags.get("p_tags"))
    doc_d_codes, doc_d_weights = _doc_set_or_dict(doc_tags.get("d_tags"))
    doc_j_codes, doc_j_weights = _doc_set_or_dict(doc_tags.get("j_tags"))

    q_p = getattr(question_tags, "p_tags", None) or {}
    q_d = getattr(question_tags, "d_tags", None) or {}
    q_j = getattr(question_tags, "j_tags", None) or {}

    j_weight = float(params.get("j_weight", 0.4))
    d_weight = float(params.get("d_weight", 0.4))
    p_weight = float(params.get("p_weight", 0.2))
    p_count_weight = float(params.get("p_count_weight", 0.4))  # %p matched weight
    d_count_weight = float(params.get("d_count_weight", 0.6))  # %d matched weight; J filter later
    count_scale = float(params.get("count_scale", 0.5))
    intensity_scale = float(params.get("intensity_scale", 0.5))

    def _q_to_float(d: dict) -> dict[str, float]:
        return {str(k): float(v) if isinstance(v, (int, float)) else 1.0 for k, v in (d or {}).items() if k}

    q_p_f = _q_to_float(q_p)
    q_d_f = _q_to_float(q_d)
    q_j_f = _q_to_float(q_j)

    breakdown: dict[str, Any] = {
        "question_tags": {"p_tags": q_p_f, "d_tags": q_d_f, "j_tags": q_j_f},
        "doc_tags": {
            "p_tags": dict(doc_p_weights),
            "d_tags": dict(doc_d_weights),
            "j_tags": dict(doc_j_weights),
        },
        "overlap": {"p_tags": [], "d_tags": [], "j_tags": []},
        "by_type": {},
    }

    def _overlap_score_and_breakdown(
        kind: str,
        q_tags: dict[str, float],
        doc_codes: set[str],
        doc_weights: dict[str, float],
    ) -> tuple[float, float, list[tuple[str, float, float, float, float]]]:
        """Returns (count_norm, intensity_norm, overlap_details)."""
        q_codes = set(q_tags.keys())
        overlap = q_codes & doc_codes
        count = len(overlap) / max(1, len(q_codes)) if q_codes else 0.0
        intensity_sum = 0.0
        overlap_list: list[tuple[str, float, float, float, float]] = []
        for c in overlap:
            q_val = q_tags.get(c, 1.0)
            doc_val = doc_weights.get(c, 1.0)
            doc_decayed = doc_val * doc_decay
            contrib = (q_val + doc_decayed) / 2.0
            intensity_sum += contrib
            overlap_list.append((c, q_val, doc_val, doc_decayed, contrib))
        intensity = intensity_sum / max(1, len(q_codes)) if q_codes else 0.0
        return count, intensity, overlap_list

    cp, ip, overlap_p = _overlap_score_and_breakdown("p", q_p_f, doc_p_codes, doc_p_weights)
    cd, id_, overlap_d = _overlap_score_and_breakdown("d", q_d_f, doc_d_codes, doc_d_weights)
    cj, ij, overlap_j = _overlap_score_and_breakdown("j", q_j_f, doc_j_codes, doc_j_weights)

    breakdown["overlap"]["p_tags"] = [
        {"tag": t, "q_score": round(qs, 4), "doc_score": round(ds, 4), "doc_decayed": round(dd, 4), "contrib": round(c, 4)}
        for t, qs, ds, dd, c in overlap_p
    ]
    breakdown["overlap"]["d_tags"] = [
        {"tag": t, "q_score": round(qs, 4), "doc_score": round(ds, 4), "doc_decayed": round(dd, 4), "contrib": round(c, 4)}
        for t, qs, ds, dd, c in overlap_d
    ]
    breakdown["overlap"]["j_tags"] = [
        {"tag": t, "q_score": round(qs, 4), "doc_score": round(ds, 4), "doc_decayed": round(dd, 4), "contrib": round(c, 4)}
        for t, qs, ds, dd, c in overlap_j
    ]
    breakdown["by_type"] = {
        "p": {"count_norm": round(cp, 4), "intensity_norm": round(ip, 4)},
        "d": {"count_norm": round(cd, 4), "intensity_norm": round(id_, 4)},
        "j": {"count_norm": round(cj, 4), "intensity_norm": round(ij, 4)},
    }

    # count_norm: %p × p_weight + %d × d_weight (J as separate filter later)
    count_norm = cp * p_count_weight + cd * d_count_weight
    intensity_norm = ip * p_count_weight + id_ * d_count_weight
    # homogeneity: J/D pollution - matched/total (focused chunk = high)
    doc_jd = doc_j_codes | doc_d_codes
    q_jd = set(q_j_f.keys()) | set(q_d_f.keys())
    overlap_jd = q_jd & doc_jd
    homogeneity = len(overlap_jd) / max(1, len(doc_jd)) if doc_jd else 1.0
    homogeneity_scale = float(params.get("homogeneity_scale", 0.3))
    # direct = completeness + intensity + homogeneity
    direct_score = count_scale * count_norm + intensity_scale * intensity_norm + homogeneity_scale * homogeneity

    # context: incremental boost from doc-level tags when we have line-level (propagation from neighbors)
    tag_source = "line" if line_tags_by_key and (doc_id, _norm_text(chunk.get("text") or "")) in line_tags_by_key else "document"
    context_score = 0.0
    context_weight = float(params.get("context_weight", 0.2))
    if tag_source == "line":
        doc_level = doc_tags_by_id.get(doc_id) or {}
        d_p, _ = _doc_set_or_dict(doc_level.get("p_tags"))
        d_d, _ = _doc_set_or_dict(doc_level.get("d_tags"))
        d_j, _ = _doc_set_or_dict(doc_level.get("j_tags"))
        doc_jd_level = d_p | d_d | d_j
        q_all = set(q_p_f.keys()) | set(q_d_f.keys()) | set(q_j_f.keys())
        if doc_jd_level and q_all:
            ctx_overlap = q_all & doc_jd_level
            context_score = len(ctx_overlap) / max(1, len(doc_jd_level))

    raw_score = direct_score + context_weight * context_score
    breakdown["params"] = {
        "count_scale": count_scale,
        "intensity_scale": intensity_scale,
        "homogeneity_scale": homogeneity_scale,
        "context_weight": context_weight,
        "doc_decay_factor": doc_decay,
        "p_count_weight": p_count_weight,
        "d_count_weight": d_count_weight,
    }
    breakdown["count_norm"] = round(count_norm, 4)
    breakdown["intensity_norm"] = round(intensity_norm, 4)
    breakdown["homogeneity"] = round(homogeneity, 4)
    breakdown["context_score"] = round(context_score, 4)
    breakdown["tag_source"] = tag_source
    return raw_score, breakdown


def _compute_signal_raw(
    name: str,
    chunk: dict,
    all_chunks: list[dict],
    cfg: RerankerSignalConfig,
    context: dict[str, Any] | None = None,
) -> float:
    """Compute raw signal value for one chunk."""
    if name == "score":
        return _get_score(chunk)

    if name == "decay_from_top":
        # Penalize chunks further from top: higher score when closer to top.
        # cur/top = 1 for top chunk, <1 for others. Chunks far from top get low score.
        top = max(_get_score(c) for c in all_chunks) if all_chunks else 0.0
        cur = _get_score(chunk)
        if top <= 0:
            return 1.0
        return cur / top

    if name == "authority_level":
        return _authority_level_score(chunk.get("document_authority_level"))

    if name == "length":
        # Floor-only: penalize fragments; no penalty for long chunks.
        text = (chunk.get("text") or "").strip()
        n = len(text)
        min_c = float(cfg.params.get("min_chars", 50))
        return 0.0 if n < min_c else 1.0

    if name == "tag_match":
        ctx = context or {}
        qt = ctx.get("question_tags")
        doc_tags = ctx.get("doc_tags_by_id") or {}
        line_tags = ctx.get("line_tags_by_key")
        if qt is None or not doc_tags:
            return 0.0
        return _compute_tag_match(chunk, qt, doc_tags, cfg.params, line_tags)

    return 0.0


def _compute_signal_raw_with_breakdown(
    name: str,
    chunk: dict,
    all_chunks: list[dict],
    cfg: RerankerSignalConfig,
    context: dict[str, Any] | None = None,
) -> tuple[float, dict[str, Any] | None]:
    """Compute raw signal and optional breakdown (for tag_match). Returns (raw_value, breakdown_or_none)."""
    if name == "tag_match":
        ctx = context or {}
        qt = ctx.get("question_tags")
        doc_tags = ctx.get("doc_tags_by_id") or {}
        line_tags = ctx.get("line_tags_by_key")
        if qt is None or not doc_tags:
            return 0.0, None
        raw, breakdown = _compute_tag_match_with_breakdown(chunk, qt, doc_tags, cfg.params, line_tags)
        return raw, breakdown
    raw = _compute_signal_raw(name, chunk, all_chunks, cfg, context)
    return raw, None


def _minmax_normalize(values: list[float]) -> list[float]:
    """Normalize to [0, 1]. If all same, return 1.0 for all."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [1.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _apply_decay_per_category(
    scored_chunks: list[dict[str, Any]],
    cfg: RerankerConfig,
    trace: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Apply decay within each retrieval_source category. Returns filtered chunks."""
    decay_by_cat = cfg.post_rerank_decay_by_category or {}
    fallback = cfg.post_rerank_decay_threshold
    if fallback is None and not decay_by_cat:
        return scored_chunks

    by_category: dict[str, list[dict[str, Any]]] = {}
    for c in scored_chunks:
        src = (c.get("retrieval_source") or "vector").lower()
        by_category.setdefault(src, []).append(c)

    out: list[dict[str, Any]] = []
    trace_decay: list[dict[str, Any]] = []

    for cat, cat_chunks in by_category.items():
        if not cat_chunks:
            continue
        cat_chunks_sorted = sorted(cat_chunks, key=lambda x: -(x.get("rerank_score") or 0))
        top_score = cat_chunks_sorted[0].get("rerank_score") or 0.0
        threshold = decay_by_cat.get(cat) if decay_by_cat.get(cat) is not None else fallback
        if threshold is None or top_score <= 0:
            kept = cat_chunks_sorted
        else:
            kept = [c for c in cat_chunks_sorted if (c.get("rerank_score") or 0) / top_score >= threshold]
        out.extend(kept)

        if trace is not None:
            trace_decay.append({
                "category": cat,
                "n_before": len(cat_chunks_sorted),
                "top_score_in_category": top_score,
                "threshold": threshold,
                "n_after": len(kept),
                "chunks_before": [
                    {"id": str(c.get("id", ""))[:20], "rerank_score": c.get("rerank_score"), "snippet": (c.get("text") or "")[:50]}
                    for c in cat_chunks_sorted
                ],
                "chunks_kept": [
                    {"id": str(c.get("id", ""))[:20], "rerank_score": c.get("rerank_score"), "decay_ratio": (c.get("rerank_score") or 0) / top_score if top_score > 0 else 0}
                    for c in kept
                ],
            })

    if trace is not None and trace_decay:
        trace["decay_per_category"] = trace_decay

    # Sort by rerank descending for consistency
    out.sort(key=lambda x: -(x.get("rerank_score") or 0))
    return out


def rerank_with_config(
    chunks: list[dict[str, Any]],
    cfg: RerankerConfig,
    *,
    question_tags: Any = None,
    doc_tags_by_id: dict[str, dict[str, set[str]]] | None = None,
    line_tags_by_key: dict[tuple[str, str], dict[str, Any]] | None = None,
    trace: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Rerank chunks using additive weighted scoring.
    Applies per-category decay (within bm25_sentence, bm25_paragraph, vector).
    question_tags: JPDTagResult (for tag_match).
    trace: optional dict to capture rerank + decay variables for debugging.
    Returns sorted list (best first), with rerank_score attached to each chunk.
    """
    if not chunks or not cfg.signals:
        return chunks
    chunks = [c for c in chunks if isinstance(c, dict)]
    if not chunks:
        return []

    context: dict[str, Any] = {}
    if question_tags is not None:
        context["question_tags"] = question_tags
    if doc_tags_by_id:
        context["doc_tags_by_id"] = doc_tags_by_id
    if line_tags_by_key:
        context["line_tags_by_key"] = line_tags_by_key

    signal_names = list(cfg.signals.keys())
    raw_by_signal: dict[str, list[float]] = {n: [] for n in signal_names}
    tag_match_breakdown_by_id: dict[str, dict[str, Any]] = {}
    for i, c in enumerate(chunks):
        for n in signal_names:
            s_cfg = cfg.signals.get(n)
            if s_cfg and s_cfg.weight > 0:
                if trace is not None and n == "tag_match":
                    raw, bd = _compute_signal_raw_with_breakdown(n, c, chunks, s_cfg, context)
                    raw_by_signal[n].append(raw)
                    if bd is not None:
                        cid = str(c.get("id", ""))
                        if cid:
                            tag_match_breakdown_by_id[cid] = bd
                else:
                    raw_by_signal[n].append(_compute_signal_raw(n, c, chunks, s_cfg, context))

    norm_by_signal: dict[str, list[float]] = {}
    for n in signal_names:
        raw = raw_by_signal.get(n, [])
        norm_by_signal[n] = _minmax_normalize(raw) if raw else [0.0] * len(chunks)

    scored: list[tuple[float, dict[str, Any], dict[str, Any] | None]] = []
    for i, c in enumerate(chunks):
        total = 0.0
        weight_sum = 0.0
        contrib: dict[str, dict[str, Any]] | None = {}
        for n in signal_names:
            s_cfg = cfg.signals.get(n)
            if s_cfg and s_cfg.weight > 0:
                norm = norm_by_signal.get(n, [0.0] * len(chunks))
                raw = raw_by_signal.get(n, [0.0] * len(chunks))[i] if i < len(raw_by_signal.get(n, [])) else 0.0
                val = norm[i] if (i < len(norm) and s_cfg.normalize) else raw
                total += s_cfg.weight * val
                weight_sum += s_cfg.weight
                if trace is not None:
                    if contrib is None:
                        contrib = {}
                    entry: dict[str, Any] = {"raw": round(raw, 4), "norm": round(norm[i], 4) if i < len(norm) else round(raw, 4), "weight": s_cfg.weight, "used": "norm" if s_cfg.normalize else "raw"}
                    if n == "tag_match":
                        bd = tag_match_breakdown_by_id.get(str(c.get("id", "")))
                        if bd is not None:
                            entry["breakdown"] = bd
                    contrib[n] = entry
        final = total / weight_sum if weight_sum > 0 else 0.0
        chunk_copy = dict(c)
        chunk_copy["rerank_score"] = round(final, 6)
        scored.append((final, chunk_copy, contrib if trace is not None else None))

    scored.sort(key=lambda x: -x[0])
    out = [c for _, c, _ in scored]

    # Capture trace data before decay
    if trace is not None:
        by_category_keys: list[str] = []
        seen_src: set[str] = set()
        for c in out:
            src = (c.get("retrieval_source") or "vector").lower()
            if src not in seen_src:
                seen_src.add(src)
                by_category_keys.append(src)
        trace["rerank"] = {
            "n_chunks_input": len(chunks),
            "signal_names": signal_names,
            "chunks_before_decay": [
                {
                    "id": str(c.get("id", ""))[:24],
                    "retrieval_source": c.get("retrieval_source"),
                    "rerank_score": c.get("rerank_score"),
                    "provision_type": c.get("provision_type"),
                }
                for c in out
            ],
            "by_category_keys": by_category_keys,
            "raw_by_signal": {n: [round(v, 4) for v in vals] for n, vals in raw_by_signal.items()},
            "norm_by_signal": {n: [round(v, 4) for v in vals] for n, vals in norm_by_signal.items()},
            "reranker_config_snapshot": {
                "name": cfg.name,
                "signals": {
                    n: {"weight": s.weight, "formula": s.formula, "normalize": s.normalize, "params": s.params}
                    for n, s in cfg.signals.items()
                },
            },
        }

    # Per-category decay (preferred) or legacy global decay
    if cfg.post_rerank_decay_by_category or cfg.post_rerank_decay_threshold is not None:
        out = _apply_decay_per_category(out, cfg, trace=trace)
    elif trace is not None:
        trace["decay_per_category"] = []  # no decay applied

    if trace is not None:
        trace["rerank"]["n_chunks_after_decay"] = len(out)
        trace["rerank"]["post_rerank_decay_threshold"] = cfg.post_rerank_decay_threshold
        trace["rerank"]["post_rerank_decay_by_category"] = cfg.post_rerank_decay_by_category
        # per_chunk: signals breakdown for chunks that survived decay (order preserved)
        out_ids = {str(c.get("id")) for c in out}
        trace["rerank"]["per_chunk"] = [
            {"id": str(c.get("id", "")), "rerank_score": c.get("rerank_score"), "signals": contrib}
            for _, c, contrib in scored
            if str(c.get("id")) in out_ids and contrib is not None
        ]
    return out


def rerank_with_config_verbose(
    chunks: list[dict[str, Any]],
    cfg: RerankerConfig,
    *,
    question_tags: Any = None,
    doc_tags_by_id: dict[str, dict[str, set[str]]] | None = None,
    line_tags_by_key: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Rerank and return debug info for emits.
    line_tags_by_key: from fetch_line_tags_for_chunks (line-level tags from policy_lines).
    Returns (reranked_chunks, debug_info).
    """
    debug: dict[str, Any] = {
        "config": {
            "name": cfg.name,
            "combination": cfg.combination_method,
            "signals": {n: {"weight": s.weight, "formula": s.formula, "params": s.params}
                        for n, s in cfg.signals.items()},
        },
        "before_rank": [],
        "after_rank": [],
        "per_chunk": [],
    }
    if not chunks or not cfg.signals:
        return chunks, debug

    context: dict[str, Any] = {}
    if question_tags is not None:
        context["question_tags"] = question_tags
    if doc_tags_by_id:
        context["doc_tags_by_id"] = doc_tags_by_id
    if line_tags_by_key:
        context["line_tags_by_key"] = line_tags_by_key

    signal_names = list(cfg.signals.keys())
    raw_by_signal: dict[str, list[float]] = {n: [] for n in signal_names}
    tag_match_breakdown_by_id: dict[str, dict[str, Any]] = {}
    for i, c in enumerate(chunks):
        for n in signal_names:
            s_cfg = cfg.signals.get(n)
            if s_cfg and s_cfg.weight > 0:
                if n == "tag_match":
                    raw, bd = _compute_signal_raw_with_breakdown(n, c, chunks, s_cfg, context)
                    raw_by_signal[n].append(raw)
                    if bd is not None:
                        cid = str(c.get("id", ""))
                        if cid:
                            tag_match_breakdown_by_id[cid] = bd
                else:
                    raw_by_signal[n].append(_compute_signal_raw(n, c, chunks, s_cfg, context))

    norm_by_signal: dict[str, list[float]] = {}
    for n in signal_names:
        raw = raw_by_signal.get(n, [])
        norm_by_signal[n] = _minmax_normalize(raw) if raw else [0.0] * len(chunks)

    debug["before_rank"] = [
        {"rank": i + 1, "id": str(c.get("id", "")), "similarity": _get_score(c), "doc": (c.get("document_name") or "")[:30]}
        for i, c in enumerate(chunks)
    ]

    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for i, c in enumerate(chunks):
        total = 0.0
        weight_sum = 0.0
        contrib: dict[str, dict[str, float]] = {}
        for n in signal_names:
            s_cfg = cfg.signals.get(n)
            if s_cfg and s_cfg.weight > 0:
                norm = norm_by_signal.get(n, [0.0] * len(chunks))
                raw = raw_by_signal.get(n, [0.0] * len(chunks))[i] if i < len(raw_by_signal.get(n, [])) else 0.0
                val = norm[i] if (i < len(norm) and s_cfg.normalize) else raw
                total += s_cfg.weight * val
                weight_sum += s_cfg.weight
                entry: dict[str, Any] = {"raw": round(raw, 4), "norm": round(norm[i], 4) if i < len(norm) else round(raw, 4), "weight": s_cfg.weight, "used": "norm" if s_cfg.normalize else "raw"}
                if n == "tag_match":
                    bd = tag_match_breakdown_by_id.get(str(c.get("id", "")))
                    if bd is not None:
                        entry["breakdown"] = bd
                contrib[n] = entry
        final = total / weight_sum if weight_sum > 0 else 0.0
        chunk_copy = dict(c)
        chunk_copy["rerank_score"] = round(final, 6)
        scored.append((final, chunk_copy, contrib))

    scored.sort(key=lambda x: -x[0])
    out_chunks = [c for _, c, _ in scored]
    # Per-category decay (preferred) or legacy global decay
    if cfg.post_rerank_decay_by_category or cfg.post_rerank_decay_threshold is not None:
        out_chunks = _apply_decay_per_category(out_chunks, cfg, trace=None)
        out_ids = {str(c.get("id")) for c in out_chunks}
        scored = [(s, c, contrib) for s, c, contrib in scored if str(c.get("id")) in out_ids]
    for i, (_, chunk, contrib) in enumerate(scored):
        debug["after_rank"].append({
            "rank": i + 1,
            "id": str(chunk.get("id", "")),
            "rerank_score": chunk.get("rerank_score"),
            "similarity": _get_score(chunk),
        })
        debug["per_chunk"].append({
            "id": str(chunk.get("id", "")),
            "rerank_score": chunk.get("rerank_score"),
            "signals": contrib,
        })

    return out_chunks, debug
