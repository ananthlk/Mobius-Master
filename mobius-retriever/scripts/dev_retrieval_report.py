#!/usr/bin/env python3
"""Run retrieval on dev questions and produce a markdown report.

Output per question:
- question
- JPD tags (p, d, j) from the question
- BM25 paragraphs and sentences (with raw_score)
- Vector search results (with similarity, distance)
- Top sentence/paragraph with answer
- Out-of-syllabus flag (expect_in_manual=false)

Requires: CHAT_RAG_DATABASE_URL, RAG_FILTER_AUTHORITY_LEVEL
For vector: VERTEX_* env vars (Vertex AI)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Add src to path
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Load env: dev report uses dev Chat DB (34.135.72.145) + dev Vertex so BM25 and
# vector both read from the same synced corpus. Explicitly set dev vars so they
# win over mobius-config or shell (e.g. Cursor workspace env).
def _load_env() -> None:
    import os
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    root = Path(__file__).resolve().parent.parent.parent
    chat_env = root / "mobius-chat" / ".env"
    if chat_env.exists():
        vals = dotenv_values(chat_env)
        for k in ("CHAT_RAG_DATABASE_URL", "VERTEX_PROJECT_ID", "VERTEX_PROJECT", "VERTEX_INDEX_ENDPOINT_ID", "VERTEX_DEPLOYED_INDEX_ID", "VERTEX_LOCATION", "VERTEX_REGION"):
            v = vals.get(k, "")
            if v:
                os.environ[k] = str(v)
        if not os.environ.get("VERTEX_PROJECT") and os.environ.get("VERTEX_PROJECT_ID"):
            os.environ["VERTEX_PROJECT"] = os.environ["VERTEX_PROJECT_ID"]
        if not os.environ.get("VERTEX_REGION") and os.environ.get("VERTEX_LOCATION"):
            os.environ["VERTEX_REGION"] = os.environ["VERTEX_LOCATION"]
        # RAG_FILTER_AUTHORITY_LEVEL: "" = no filter (all docs in corpus); default "contract_source_of_truth"
        # Experiment: include all docs (no authority filter); reranker can boost contract_source_of_truth later
        os.environ["RAG_FILTER_AUTHORITY_LEVEL"] = ""
        if "RAG_FILTER_AUTHORITY_LEVEL" not in os.environ:
            os.environ["RAG_FILTER_AUTHORITY_LEVEL"] = "contract_source_of_truth"


_load_env()

import yaml
from mobius_retriever.jpd_tagger import tag_question_and_resolve_document_ids, fetch_document_tags_by_ids, fetch_line_tags_for_chunks
from mobius_retriever.retriever import retrieve_bm25, retrieve_path_b
from mobius_retriever.config import (
    load_path_b_config,
    load_reranker_config,
    load_retrieval_cutoffs,
    load_bm25_sigmoid_config,
    apply_normalize_bm25,
)
from mobius_retriever.vector_search import vector_search
from mobius_retriever.reranker import rerank_with_config_verbose


# Stopwords for "has answer" heuristic
_STOP = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "could should may might must shall can what how when where which who whom "
    "this that these those it its i me my we our you your he she they them "
    "for of to in on at by with from as into through during before after "
    "and or but if then so because until while"
    .split()
)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _question_key_terms(question: str) -> set[str]:
    """Extract meaningful terms from question for overlap check."""
    tokens = _tokenize(question)
    return tokens - _STOP


def _has_likely_answer(question: str, text: str, min_overlap: int = 2) -> bool:
    """Heuristic: question key terms appear in retrieved text."""
    if not text:
        return False
    q_terms = _question_key_terms(question)
    t_terms = _tokenize(text)
    overlap = len(q_terms & t_terms)
    return overlap >= min_overlap


def _chunk_id(chunk) -> str:
    """Get chunk id for gold matching."""
    return str(chunk.get("id", "") or getattr(chunk, "id", "") or "")


def _chunk_parent_id(chunk) -> str | None:
    """Get parent_metadata_id if present (for sentence->paragraph gold matching)."""
    pid = chunk.get("parent_metadata_id") if isinstance(chunk, dict) else getattr(chunk, "parent_metadata_id", None)
    return str(pid) if pid else None


def _gold_in_chunks(chunks: list, gold_ids: set[str], top_k: int) -> bool:
    """True if any of the top-k chunks matches a gold_id (by id or parent_metadata_id)."""
    if not gold_ids:
        return False
    for c in chunks[:top_k]:
        cid = _chunk_id(c)
        pid = _chunk_parent_id(c)
        if cid in gold_ids or (pid and pid in gold_ids):
            return True
    return False


def _truncate(text: str, max_len: int = 200) -> str:
    if not text:
        return ""
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 3].rsplit(" ", 1)[0] + "..."


def _normalize_for_dedup(text: str) -> str:
    """Normalize text for deduplication: collapse whitespace, lowercase."""
    if not text:
        return ""
    return " ".join((text or "").lower().split())


def _top3_rerank_from_debug(debug: dict, ranked: list, _g, _truncate) -> list[dict]:
    """Extract top 3 rerank (raw, norm, final, snippet) from reranker debug."""
    out: list[dict] = []
    if not debug or not ranked:
        return out
    ranked_by_id = {str(_g(c, "id")): c for c in ranked}
    for pc in debug.get("per_chunk", [])[:3]:
        sig = (pc.get("signals") or {}).get("score", {})
        chunk = ranked_by_id.get(pc.get("id", ""), {})
        out.append({
            "raw": sig.get("raw", 0),
            "norm": sig.get("norm", 0),
            "final": pc.get("rerank_score") or 0,
            "snippet": _truncate(_g(chunk, "text") or "", 40).replace("|", "\\|").replace("\n", " "),
        })
    return out


def _bm25_to_rerank_dict(c, bm25_cfg: dict) -> dict:
    """Convert BM25 chunk to reranker dict with similarity = sigmoid(raw_score)."""
    raw = c.get("raw_score") if isinstance(c, dict) else getattr(c, "raw_score", None)
    pt = c.get("provision_type", "sentence") if isinstance(c, dict) else getattr(c, "provision_type", "sentence")
    sim = apply_normalize_bm25(float(raw or 0), pt, bm25_cfg) if bm25_cfg else (float(raw or 0) / 50.0)
    return {
        "id": c.get("id") if isinstance(c, dict) else getattr(c, "id", None),
        "text": c.get("text") if isinstance(c, dict) else getattr(c, "text", ""),
        "document_id": c.get("document_id") if isinstance(c, dict) else getattr(c, "document_id", None),
        "document_name": c.get("document_name") if isinstance(c, dict) else getattr(c, "document_name", ""),
        "document_authority_level": c.get("document_authority_level") if isinstance(c, dict) else getattr(c, "document_authority_level", None),
        "similarity": sim,
        "raw_score": raw,
        "provision_type": pt,
        "source_type": c.get("source_type", "hierarchical") if isinstance(c, dict) else getattr(c, "source_type", "hierarchical"),
    }


def _dedupe_by_text(chunks: list, max_items: int = 10) -> list:
    """Keep first occurrence per normalized text (preserves order = best score first)."""
    seen: set[str] = set()
    out: list = []
    for c in chunks:
        if len(out) >= max_items:
            break
        text = c.get("text") if isinstance(c, dict) else getattr(c, "text", None)
        norm = _normalize_for_dedup(text or "")
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(c)
    return out


def main() -> int:
    config_path = Path(__file__).resolve().parent.parent / "configs" / "path_b_v1.yaml"
    questions_path = Path(__file__).resolve().parent.parent / "eval_questions_dev.yaml"
    out_path = Path(__file__).resolve().parent.parent / "reports" / "dev_retrieval_report.md"

    if not config_path.exists():
        print("Config not found:", config_path, file=sys.stderr)
        return 1
    if not questions_path.exists():
        print("Questions not found:", questions_path, file=sys.stderr)
        return 1

    with open(questions_path) as f:
        data = yaml.safe_load(f) or {}
    questions = data.get("questions") or []

    config = load_path_b_config(config_path)
    rag_url = config.rag_database_url or config.postgres_url
    # Empty = no filter (all docs); unset = default contract_source_of_truth
    _al = (config.filters.document_authority_level or "").strip()
    auth_level = None if _al == "" else (_al or "contract_source_of_truth")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    summary_rows: list[dict] = []

    def _g(c, k, default=None):
        return c.get(k, default) if isinstance(c, dict) else getattr(c, k, default)

    def _chunk_text(c) -> str:
        return str(_g(c, "text") or "")

    # Intro (summary table inserted after first ---)
    lines.append("# Dev Retrieval Report")
    lines.append("")
    lines.append("JPD + BM25 + Vector retrieval on eval_questions_dev.yaml.")
    lines.append("")
    lines.append("**Note on sentence vs paragraph BM25:** Sentence-level BM25 tends to outperform paragraph-level for fact-based queries.")
    lines.append("")
    lines.append("---")
    lines.append("")

    for q in questions:
        qid = q.get("id", "?")
        question = q.get("question", "")
        expect_in_manual = q.get("expect_in_manual", True)
        golden_answer = q.get("golden_answer") or q.get("gold_answer") or ""
        gold_ids = set(str(x) for x in (q.get("gold_ids") or q.get("gold_parent_metadata_ids") or []))

        lines.append(f"## {qid}")
        lines.append("")
        lines.append(f"**Question:** {question}")
        lines.append("")

        # JPD tags
        jpd = tag_question_and_resolve_document_ids(question, rag_url, emitter=None)
        p_list = list(jpd.p_tags.keys()) if jpd.p_tags else []
        d_list = list(jpd.d_tags.keys()) if jpd.d_tags else []
        j_list = list(jpd.j_tags.keys()) if jpd.j_tags else []
        lines.append("**Tags from question (J/P/D):**")
        lines.append(f"- p_tags: {p_list or '(none)'}")
        lines.append(f"- d_tags: {d_list or '(none)'}")
        lines.append(f"- j_tags: {j_list or '(none)'}")
        lines.append(f"- document_ids resolved: {len(jpd.document_ids)} doc(s)")
        lines.append("")

        # BM25 retrieval
        bm = retrieve_bm25(
            question=question,
            config_path=str(config_path),
            authority_level=auth_level,
            use_jpd_tagger=True,
            emitter=None,
        )

        paragraphs_raw = [c for c in bm.chunks if getattr(c, "provision_type", "") == "paragraph"]
        sentences_raw = [c for c in bm.chunks if getattr(c, "provision_type", "") == "sentence"]
        paragraphs = _dedupe_by_text(paragraphs_raw, 20)
        sentences = _dedupe_by_text(sentences_raw, 20)

        # BM25 reranking (same signals as vector: score, tag_match, decay_from_top, etc.)
        bm25_sent_reranked: list[dict] = []
        bm25_para_reranked: list[dict] = []
        bm25_sent_debug: dict = {}
        bm25_para_debug: dict = {}
        bm25_cfg = load_bm25_sigmoid_config()
        reranker_cfg = load_reranker_config(config.rerank.reranker_config_path) if config.rerank.reranker_config_path else None
        if reranker_cfg and bm25_cfg and rag_url:
            jpd_for_bm = tag_question_and_resolve_document_ids(question, rag_url, emitter=None)
            for label, chunks_in, pt in [("sentence", sentences, "sentence"), ("paragraph", paragraphs, "paragraph")]:
                if not chunks_in:
                    continue
                dicts = [_bm25_to_rerank_dict(c, bm25_cfg) for c in chunks_in]
                doc_ids = list({str(d.get("document_id", "")) for d in dicts if d.get("document_id")})
                doc_tags_bm = fetch_document_tags_by_ids(rag_url, doc_ids) if doc_ids else {}
                line_tags_bm = fetch_line_tags_for_chunks(rag_url, dicts) if dicts else {}
                qtags = jpd_for_bm if (reranker_cfg.signals and "tag_match" in reranker_cfg.signals and jpd_for_bm.has_tags) else None
                ranked, debug = rerank_with_config_verbose(dicts, reranker_cfg, question_tags=qtags, doc_tags_by_id=doc_tags_bm, line_tags_by_key=line_tags_bm)
                if label == "sentence":
                    bm25_sent_reranked = ranked
                    bm25_sent_debug = debug
                else:
                    bm25_para_reranked = ranked
                    bm25_para_debug = debug

        def _g(c, k, default=None):
            return c.get(k, default) if isinstance(c, dict) else getattr(c, k, default)

        lines.append("**BM25 Retrieved (paragraphs, raw_score) [deduped by text, top 20]:**")
        for i, c in enumerate(paragraphs[:20], 1):
            doc = (c.document_name or "")[:40]
            rs = getattr(c, "raw_score", None)
            score_s = f" raw_score={rs:.3f}" if rs is not None else ""
            lines.append(f"  {i}. `{c.id}` |{score_s} {doc} | {_truncate(c.text, 80)}")
        if not paragraphs:
            lines.append("  (none)")
        lines.append("")

        lines.append("**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**")
        for i, c in enumerate(sentences[:20], 1):
            doc = (c.document_name or "")[:40]
            rs = getattr(c, "raw_score", None)
            score_s = f" raw_score={rs:.3f}" if rs is not None else ""
            lines.append(f"  {i}. `{c.id}` |{score_s} {doc} | {_truncate(c.text, 80)}")
        if not sentences:
            lines.append("  (none)")
        lines.append("")

        # BM25 Top 3 by rerank + per-chunk signals (sentence, paragraph)
        for label, ranked, debug in [
            ("BM25 Sentence", bm25_sent_reranked, bm25_sent_debug),
            ("BM25 Paragraph", bm25_para_reranked, bm25_para_debug),
        ]:
            if ranked and debug and debug.get("per_chunk"):
                lines.append(f"**{label} Top 3 by rerank (raw | normalized | final):**")
                lines.append("| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |")
                lines.append("|------|-------|-----------------|--------------|----------------|---------|")
                for rank, pc in enumerate(debug.get("per_chunk", [])[:3], 1):
                    cid = pc.get("id", "")
                    sig = (pc.get("signals") or {}).get("score", {})
                    raw = sig.get("raw", 0)
                    norm = sig.get("norm", 0)
                    final = pc.get("rerank_score") or 0
                    chunk = next((c for c in ranked if str(_g(c, "id")) == cid), {})
                    snippet = _truncate(_g(chunk, "text") or "", 50).replace("|", "\\|").replace("\n", " ")
                    lines.append(f"| {rank} | `{str(cid)[:12]}...` | {raw:.4f} | {norm:.4f} | {final:.4f} | {snippet} |")
                lines.append("")
                lines.append(f"**{label} per-chunk signals (raw, norm, weight) — Top 5:**")
                rc = debug.get("config", {})
                weights_str = "  ".join(f"{n}={sc.get('weight',0)}" for n, sc in (rc.get("signals") or {}).items())
                lines.append(f"  Weights: {weights_str}")
                for pc in debug.get("per_chunk", [])[:5]:
                    lines.append(f"  id={str(pc.get('id', ''))[:24]}... rerank_score={pc.get('rerank_score', 0):.4f}")
                    for sig_name, vals in (pc.get("signals") or {}).items():
                        lines.append(f"    {sig_name}: raw={vals.get('raw')} norm={vals.get('norm')} weight={vals.get('weight')}")
                        bd = vals.get("breakdown") if isinstance(vals, dict) else None
                        if sig_name == "tag_match" and bd:
                            src = bd.get("tag_source", "?")
                            ov = bd.get("overlap") or {}
                            by_type = bd.get("by_type") or {}
                            lines.append(f"      tag_source={src}")
                            for kind, label in [("p_tags", "p"), ("d_tags", "d"), ("j_tags", "j")]:
                                items = ov.get(kind) or []
                                if items:
                                    lines.append(f"      overlap {label}: {by_type.get(label, {})} tags={[x.get('tag') for x in items]} contrib={[x.get('contrib') for x in items]}")
                lines.append("")

        # Vector search with reranker verbose (before/after ranks, signal emits)
        vec_chunks: list = []
        vec_error: str | None = None
        vec_logs: list[str] = []
        vec_raw: list = []
        rerank_debug: dict = {}

        def _capture(msg: str) -> None:
            vec_logs.append(msg)

        try:
            st = getattr(config.filters, "source_type_allow", None)
            vec_raw_list = vector_search(question, config, source_type_allow=st, emitter=_capture)
            cutoffs = load_retrieval_cutoffs()
            vec_raw_list = [c for c in vec_raw_list if (c.get("similarity") or 0.0) >= cutoffs.vector_abstention_cutoff]

            if config.rerank.reranker_config_path and vec_raw_list:
                reranker_cfg = load_reranker_config(config.rerank.reranker_config_path)
                question_tags = None
                doc_tags_by_id = {}
                line_tags_vec: dict = {}
                if rag_url and "tag_match" in reranker_cfg.signals:
                    jpd = tag_question_and_resolve_document_ids(question, rag_url, emitter=None)
                    if jpd.has_tags:
                        question_tags = jpd
                        doc_ids = list({str(c.get("document_id", "")) for c in vec_raw_list if c.get("document_id")})
                        if doc_ids:
                            doc_tags_by_id = fetch_document_tags_by_ids(rag_url, doc_ids)
                        line_tags_vec = fetch_line_tags_for_chunks(rag_url, vec_raw_list) if vec_raw_list else {}
                vec_raw_list, rerank_debug = rerank_with_config_verbose(
                    vec_raw_list, reranker_cfg,
                    question_tags=question_tags, doc_tags_by_id=doc_tags_by_id,
                    line_tags_by_key=line_tags_vec,
                )

            vec_raw = vec_raw_list
            vec_chunks = _dedupe_by_text(vec_raw_list, 20)
        except Exception as e:
            vec_chunks = []
            vec_raw = []
            vec_error = str(e)

        lines.append("**Vector Retrieved (similarity, rerank_score) [deduped by text, top 10]:**")
        if vec_error:
            lines.append(f"  not working — Vertex config or connectivity: `{vec_error}`")
        elif not vec_chunks:
            lines.append("  (0 results)")
            for log in vec_logs[-6:]:
                if "Vertex" in log or "Postgres" in log or "namespace" in log.lower() or "neighbor" in log.lower():
                    lines.append(f"  — {log}")
        else:
            def _g(c, k, default=None):
                return c.get(k, default) if isinstance(c, dict) else getattr(c, k, default)

            for i, c in enumerate(vec_chunks[:10], 1):
                doc = (_g(c, "document_name") or "")[:40]
                sim = _g(c, "similarity")
                dist = _g(c, "distance")
                rs = _g(c, "rerank_score")
                score_s = f" sim={sim:.3f}" if sim is not None else ""
                if rs is not None:
                    score_s += f" rerank={rs:.3f}"
                if dist is not None:
                    score_s += f" dist={dist:.3f}"
                text = _g(c, "text") or ""
                cid = _g(c, "id")
                lines.append(f"  {i}. `{cid}` |{score_s} {doc} | {_truncate(text, 80)}")

            # Reranker emits: config, before/after ranks, per-chunk signals
            if rerank_debug:
                rc = rerank_debug.get("config", {})
                lines.append("")
                lines.append("**Reranker config (emits):**")
                lines.append(f"- combination: {rc.get('combination', 'additive')}")
                for sig, s in (rc.get("signals") or {}).items():
                    lines.append(f"- {sig}: weight={s.get('weight')} formula={s.get('formula')} params={s.get('params', {})}")

                lines.append("")
                lines.append("**Ranks BEFORE rerank (by similarity):**")
                for b in rerank_debug.get("before_rank", [])[:10]:
                    lines.append(f"  {b['rank']}. id={b['id'][:12]}... sim={b['similarity']:.3f} doc={b['doc']}")

                lines.append("")
                lines.append("**Ranks AFTER rerank (by rerank_score):**")
                for a in rerank_debug.get("after_rank", [])[:10]:
                    lines.append(f"  {a['rank']}. id={a['id'][:12]}... rerank={a['rerank_score']:.3f} sim={a['similarity']:.3f}")

                # Top 3 by rerank: raw (similarity), normalized (score signal norm), final (rerank_score)
                lines.append("")
                lines.append("**Top 3 by rerank (raw | normalized | final):**")
                lines.append("| Rank | Chunk | Raw (sim) | Norm (score) | Final (rerank) | Snippet |")
                lines.append("|------|-------|-----------|--------------|----------------|---------|")
                vec_by_id = {str(_g(c, "id")): c for c in vec_raw}
                for rank, pc in enumerate(rerank_debug.get("per_chunk", [])[:3], 1):
                    cid = pc.get("id", "")
                    sig = (pc.get("signals") or {}).get("score", {})
                    raw = sig.get("raw", 0)
                    norm = sig.get("norm", 0)
                    final = pc.get("rerank_score") or 0
                    chunk = vec_by_id.get(cid, {})
                    snippet = _truncate(_g(chunk, "text") or "", 50).replace("|", "\\|").replace("\n", " ")
                    lines.append(f"| {rank} | `{cid[:12]}...` | {raw:.4f} | {norm:.4f} | {final:.4f} | {snippet} |")

                lines.append("")
                lines.append("**Per-chunk signals (raw, norm, weight):**")
                for pc in rerank_debug.get("per_chunk", [])[:10]:
                    lines.append(f"  id={pc['id'][:20]}... rerank_score={pc['rerank_score']:.3f}")
                    for sig, vals in (pc.get("signals") or {}).items():
                        lines.append(f"    {sig}: raw={vals.get('raw')} norm={vals.get('norm')} weight={vals.get('weight')}")
                        # Tag match breakdown: question tags, doc tags, overlap per P/D/J
                        bd = vals.get("breakdown") if isinstance(vals, dict) else None
                        if sig == "tag_match" and bd:
                            qq = bd.get("question_tags") or {}
                            dd = bd.get("doc_tags") or {}
                            ov = bd.get("overlap") or {}
                            by_type = bd.get("by_type") or {}
                            lines.append(f"      tag_source={bd.get('tag_source', '?')}")
                            lines.append(f"      question_tags: p={list((qq.get('p_tags') or {}).keys())} d={list((qq.get('d_tags') or {}).keys())} j={list((qq.get('j_tags') or {}).keys())}")
                            lines.append(f"      doc_tags (this chunk): p={list((dd.get('p_tags') or {}).keys())[:8]} d={list((dd.get('d_tags') or {}).keys())[:8]} j={list((dd.get('j_tags') or {}).keys())[:8]}")
                            for kind, label in [("p_tags", "p"), ("d_tags", "d"), ("j_tags", "j")]:
                                items = ov.get(kind) or []
                                if items:
                                    tbt = by_type.get(label, {})
                                    lines.append(f"      overlap {label}: {tbt} — tags: {[x.get('tag') for x in items]} (q_score, doc_decayed, contrib): {[(x.get('tag'), x.get('q_score'), x.get('doc_decayed'), x.get('contrib')) for x in items]}")
            lines.append("")

        # Top paragraph/sentence with answer (use reranked top 1 when available)
        top_para = bm25_para_reranked[0] if bm25_para_reranked else (paragraphs[0] if paragraphs else None)
        top_sent = bm25_sent_reranked[0] if bm25_sent_reranked else (sentences[0] if sentences else None)
        para_has = top_para and _has_likely_answer(question, _g(top_para, "text") or "")
        sent_has = top_sent and _has_likely_answer(question, _g(top_sent, "text") or "")

        lines.append("**Top paragraph with answer:**")
        if top_para:
            rs = _g(top_para, "raw_score")
            rr = _g(top_para, "rerank_score")
            score_s = f" | raw_score={rs:.3f}" if rs is not None else ""
            if rr is not None:
                score_s += f" rerank={rr:.3f}"
            lines.append(f"- paragraph_id: `{_g(top_para, 'id')}` | doc: {_g(top_para, 'document_name') or '?'}{score_s}")
            lines.append(f"- text: {_truncate(_g(top_para, 'text') or '', 300)}")
            lines.append(f"- likely_has_answer: {para_has}")
        else:
            lines.append("- (no paragraphs retrieved)")
        lines.append("")

        lines.append("**Top sentence with answer:**")
        if top_sent:
            rs = _g(top_sent, "raw_score")
            rr = _g(top_sent, "rerank_score")
            score_s = f" | raw_score={rs:.3f}" if rs is not None else ""
            if rr is not None:
                score_s += f" rerank={rr:.3f}"
            lines.append(f"- paragraph_id: `{_g(top_sent, 'id')}` | doc: {_g(top_sent, 'document_name') or '?'}{score_s}")
            lines.append(f"- text: {_truncate(_g(top_sent, 'text') or '', 300)}")
            lines.append(f"- likely_has_answer: {sent_has}")
        else:
            lines.append("- (no sentences retrieved)")
        lines.append("")

        if vec_chunks:
            top_vec = vec_chunks[0]
            _gv = lambda k: top_vec.get(k) if isinstance(top_vec, dict) else getattr(top_vec, k, None)
            sim = _gv("similarity")
            dist = _gv("distance")
            rs = _gv("rerank_score")
            lines.append("**Top vector result:**")
            score_s = f" sim={sim:.3f}" if sim is not None else ""
            if rs is not None:
                score_s += f" rerank={rs:.3f}"
            if dist is not None:
                score_s += f" dist={dist:.3f}"
            lines.append(f"- paragraph_id: `{_gv('id')}` | doc: {_gv('document_name') or '?'} |{score_s}")
            lines.append(f"- text: {_truncate(_gv('text') or '', 300)}")
            lines.append("")

        # Summary row for golden-answer hit table + top 3 rerank
        sent_for_top = bm25_sent_reranked if bm25_sent_reranked else sentences
        para_for_top = bm25_para_reranked if bm25_para_reranked else paragraphs
        top1_sent = sent_for_top[0] if sent_for_top else None
        top1_para = para_for_top[0] if para_for_top else None
        top1_vec = vec_chunks[0] if vec_chunks else None
        in1 = lambda chks, g: _gold_in_chunks(chks, g, 1) if g else None
        in3 = lambda chks, g: _gold_in_chunks(chks, g, 3) if g else None

        # Top 3 by rerank (raw, norm, final) for summary - vector
        top3_rerank: list[dict] = []
        if rerank_debug and vec_raw:
            vec_by_id = {str(_g(c, "id")): c for c in vec_raw}
            for pc in rerank_debug.get("per_chunk", [])[:3]:
                sig = (pc.get("signals") or {}).get("score", {})
                chunk = vec_by_id.get(pc.get("id", ""), {})
                top3_rerank.append({
                    "raw": sig.get("raw", 0),
                    "norm": sig.get("norm", 0),
                    "final": pc.get("rerank_score") or 0,
                    "snippet": _truncate(_g(chunk, "text") or "", 40).replace("|", "\\|").replace("\n", " "),
                })

        summary_rows.append({
            "qid": qid,
            "question": _truncate(question, 55),
            "golden": _truncate(golden_answer, 40) if golden_answer else ("—" if not gold_ids else f"{len(gold_ids)} ids"),
            "bm25_sent_top1": _truncate(_chunk_text(top1_sent), 50) if top1_sent else "—",
            "bm25_sent_in1": "✓" if in1(sent_for_top, gold_ids) else ("✗" if gold_ids else "—"),
            "bm25_sent_in3": "✓" if in3(sent_for_top, gold_ids) else ("✗" if gold_ids else "—"),
            "bm25_para_top1": _truncate(_chunk_text(top1_para), 50) if top1_para else "—",
            "bm25_para_in1": "✓" if in1(para_for_top, gold_ids) else ("✗" if gold_ids else "—"),
            "bm25_para_in3": "✓" if in3(para_for_top, gold_ids) else ("✗" if gold_ids else "—"),
            "vec_para_top1": _truncate(_chunk_text(top1_vec), 50) if top1_vec else "—",
            "vec_para_in1": "✓" if in1(vec_chunks, gold_ids) else ("✗" if gold_ids else "—"),
            "vec_para_in3": "✓" if in3(vec_chunks, gold_ids) else ("✗" if gold_ids else "—"),
            "top3_rerank": top3_rerank,
            "top3_bm25_sent_rerank": _top3_rerank_from_debug(bm25_sent_debug, bm25_sent_reranked, _g, _truncate),
            "top3_bm25_para_rerank": _top3_rerank_from_debug(bm25_para_debug, bm25_para_reranked, _g, _truncate),
        })

        # Out of syllabus
        out_of_syllabus = not expect_in_manual
        if out_of_syllabus:
            lines.append("**OUT OF SYLLABUS** (expect_in_manual=false)")
        else:
            lines.append("**In syllabus** (expect_in_manual=true)")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Insert summary table after intro (before first ##)
    intro_len = 0
    for i, ln in enumerate(lines):
        if ln.strip().startswith("## "):
            intro_len = i
            break

    summary_lines: list[str] = []
    if summary_rows:
        summary_lines.append("## Summary: Golden Answer in Top 1 / Top 3")
        summary_lines.append("")
        summary_lines.append("| ID | Question | Golden | BM25 Sent Top1 | In1 | In3 | BM25 Para Top1 | In1 | In3 | Vec Para Top1 | In1 | In3 |")
        summary_lines.append("|----|----------|--------|----------------|-----|-----|----------------|-----|-----|---------------|-----|-----|")
        def _esc(s: str) -> str:
            return (s or "").replace("|", "\\|").replace("\n", " ")[:50]

        for r in summary_rows:
            summary_lines.append(
                f"| {r['qid']} | {_esc(r['question'])} | {_esc(r['golden'])} | {_esc(r['bm25_sent_top1'])} | {r['bm25_sent_in1']} | {r['bm25_sent_in3']} | "
                f"{_esc(r['bm25_para_top1'])} | {r['bm25_para_in1']} | {r['bm25_para_in3']} | "
                f"{_esc(r['vec_para_top1'])} | {r['vec_para_in1']} | {r['vec_para_in3']} |"
            )
        summary_lines.append("")
        summary_lines.append("*In1 = golden answer in top 1; In3 = golden answer in top 3. ✓/✗ when gold_ids provided; — when no gold labels.*")
        summary_lines.append("")
        summary_lines.append("---")
        summary_lines.append("")
        summary_lines.append("## Summary: Top 3 by rerank (raw | normalized | final)")
        summary_lines.append("")
        for r in summary_rows:
            summary_lines.append(f"### {r['qid']}")
            for label, tr in [
                ("Vector", r.get("top3_rerank") or []),
                ("BM25 Sentence", r.get("top3_bm25_sent_rerank") or []),
                ("BM25 Paragraph", r.get("top3_bm25_para_rerank") or []),
            ]:
                if tr:
                    summary_lines.append(f"**{label}:**")
                    summary_lines.append("| Rank | Raw | Norm | Final | Snippet |")
                    summary_lines.append("|------|-----|------|-------|---------|")
                    for i, t in enumerate(tr, 1):
                        summary_lines.append(f"| {i} | {t['raw']:.4f} | {t['norm']:.4f} | {t['final']:.4f} | {t['snippet']} |")
                    summary_lines.append("")
                elif label == "Vector":
                    summary_lines.append("**Vector:** — (no vector/rerank)")
                    summary_lines.append("")
        summary_lines.append("---")
        summary_lines.append("")

    # Prepend summary after intro
    final_lines = lines[:intro_len] + summary_lines + lines[intro_len:]
    with open(out_path, "w") as f:
        f.write("\n".join(final_lines))

    print(f"Report written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
