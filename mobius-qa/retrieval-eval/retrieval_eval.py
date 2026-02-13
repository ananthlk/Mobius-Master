#!/usr/bin/env python3
"""
Retrieval-only evaluation for Published RAG (Vertex Vector Search).

Runs two retrieval modes (hier_only vs atomic_plus_hier) on a question set and emits:
- results.csv + results.jsonl (top-k per question per mode)
- summary.md
- similarity/confidence distribution plots

This is intentionally chat-agnostic: it queries Vertex + optionally enriches results by
joining ids to Postgres `published_rag_metadata` (if CHAT_RAG_DATABASE_URL is set).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parent


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def load_questions(path: Path) -> list[dict[str, Any]]:
    data = load_yaml(path)
    qs = data.get("questions") or []
    if not isinstance(qs, list):
        raise ValueError("questions.yaml must contain top-level key 'questions' as a list")
    out: list[dict[str, Any]] = []
    for i, q in enumerate(qs):
        if not isinstance(q, dict):
            continue
        question = (q.get("question") or "").strip()
        if not question:
            continue
        out.append({
            "id": (q.get("id") or f"Q{i+1:03d}").strip(),
            "intent": (q.get("intent") or "unknown").strip().lower(),
            "bucket": (q.get("bucket") or "").strip().lower(),
            "question": question,
        })
    return out


def _require(val: str | None, name: str) -> str:
    v = (val or "").strip()
    if not v:
        raise ValueError(f"Missing required config/env: {name}")
    return v


def _get_cfg_vertex(cfg: dict[str, Any]) -> dict[str, str]:
    vcfg = (cfg.get("vertex") or {}) if isinstance(cfg.get("vertex"), dict) else {}
    project = os.getenv("VERTEX_PROJECT") or vcfg.get("project")
    region = os.getenv("VERTEX_REGION") or vcfg.get("region") or "us-central1"
    endpoint_id = os.getenv("VERTEX_INDEX_ENDPOINT_ID") or vcfg.get("index_endpoint_id")
    deployed_id = os.getenv("VERTEX_DEPLOYED_INDEX_ID") or vcfg.get("deployed_index_id")
    return {
        "project": _require(project, "VERTEX_PROJECT (or config.vertex.project)"),
        "region": _require(region, "VERTEX_REGION (or config.vertex.region)"),
        "endpoint_id": _require(endpoint_id, "VERTEX_INDEX_ENDPOINT_ID (or config.vertex.index_endpoint_id)"),
        "deployed_id": _require(deployed_id, "VERTEX_DEPLOYED_INDEX_ID (or config.vertex.deployed_index_id)"),
    }


def _get_cfg_embedding(cfg: dict[str, Any]) -> dict[str, Any]:
    ecfg = (cfg.get("embedding") or {}) if isinstance(cfg.get("embedding"), dict) else {}
    return {
        "model": (os.getenv("VERTEX_EMBEDDING_MODEL") or ecfg.get("model") or "gemini-embedding-001").strip(),
        "output_dimensionality": int(os.getenv("VERTEX_EMBEDDING_DIMS") or ecfg.get("output_dimensionality") or 1536),
        "task_type": (os.getenv("VERTEX_EMBEDDING_TASK_TYPE") or ecfg.get("task_type") or "RETRIEVAL_DOCUMENT").strip(),
    }


def _get_cfg_filters(cfg: dict[str, Any]) -> dict[str, str]:
    fcfg = (cfg.get("filters") or {}) if isinstance(cfg.get("filters"), dict) else {}
    # We strongly prefer filtering by a unique authority_level so the eval isolates a single doc.
    authority = (os.getenv("RAG_FILTER_AUTHORITY_LEVEL") or fcfg.get("document_authority_level") or "").strip()
    payer = (os.getenv("RAG_FILTER_PAYER") or fcfg.get("document_payer") or "").strip()
    state = (os.getenv("RAG_FILTER_STATE") or fcfg.get("document_state") or "").strip()
    program = (os.getenv("RAG_FILTER_PROGRAM") or fcfg.get("document_program") or "").strip()
    return {
        "document_authority_level": authority,
        "document_payer": payer,
        "document_state": state,
        "document_program": program,
    }


def _get_cfg_run(cfg: dict[str, Any]) -> dict[str, Any]:
    rcfg = (cfg.get("run") or {}) if isinstance(cfg.get("run"), dict) else {}
    top_k = int(os.getenv("RETRIEVAL_EVAL_TOP_K") or rcfg.get("top_k") or 10)
    limit_questions = int(os.getenv("RETRIEVAL_EVAL_LIMIT") or rcfg.get("limit_questions") or 50)
    report_dir = (os.getenv("RETRIEVAL_EVAL_REPORT_DIR") or rcfg.get("report_dir") or "reports").strip()
    return {"top_k": max(1, min(100, top_k)), "limit_questions": max(1, limit_questions), "report_dir": report_dir}


@dataclasses.dataclass(frozen=True)
class Mode:
    name: str
    source_type_allow: list[str] | None  # None => no source_type filter


def _get_cfg_modes(cfg: dict[str, Any]) -> list[Mode]:
    modes_raw = cfg.get("modes") or []
    out: list[Mode] = []
    if not isinstance(modes_raw, list):
        raise ValueError("config.yaml key 'modes' must be a list")
    for m in modes_raw:
        if not isinstance(m, dict):
            continue
        name = (m.get("name") or "").strip()
        if not name:
            continue
        allow = m.get("source_type_allow")
        if allow is None:
            allow_list = None
        elif isinstance(allow, list):
            allow_list = [str(x).strip() for x in allow if str(x).strip()]
            if not allow_list:
                allow_list = None
        else:
            allow_list = None
        out.append(Mode(name=name, source_type_allow=allow_list))
    if not out:
        out = [
            Mode(name="hier_only", source_type_allow=["hierarchical"]),
            Mode(name="atomic_plus_hier", source_type_allow=None),
        ]
    return out


def embed_query(text: str, project: str, region: str, model: str, output_dimensionality: int, task_type: str) -> list[float]:
    """
    Produce an embedding vector for a single query.

    Uses Vertex AI `TextEmbeddingModel` (same shape as mobius-chat's embedding_provider).
    """
    import vertexai
    from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

    vertexai.init(project=project, location=region)
    m = TextEmbeddingModel.from_pretrained(model)
    inputs = [TextEmbeddingInput(text, task_type=task_type)]
    resp = m.get_embeddings(inputs, output_dimensionality=output_dimensionality)
    if not resp or not resp[0].values:
        raise ValueError("Empty embedding returned from Vertex")
    return list(resp[0].values)


def _vertex_namespaces(filters: dict[str, str], source_type_allow: list[str] | None) -> list[Any]:
    from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import Namespace

    ns: list[Any] = []
    if filters.get("document_payer"):
        ns.append(Namespace(name="document_payer", allow_tokens=[filters["document_payer"]], deny_tokens=[]))
    if filters.get("document_state"):
        ns.append(Namespace(name="document_state", allow_tokens=[filters["document_state"]], deny_tokens=[]))
    if filters.get("document_program"):
        ns.append(Namespace(name="document_program", allow_tokens=[filters["document_program"]], deny_tokens=[]))
    if filters.get("document_authority_level"):
        ns.append(Namespace(name="document_authority_level", allow_tokens=[filters["document_authority_level"]], deny_tokens=[]))
    if source_type_allow:
        ns.append(Namespace(name="source_type", allow_tokens=source_type_allow, deny_tokens=[]))
    return ns


def vertex_find_neighbors(
    endpoint_id: str,
    deployed_index_id: str,
    query_embedding: list[float],
    k: int,
    namespaces: list[Any] | None,
    project: str,
    region: str,
) -> list[dict[str, Any]]:
    """Return neighbors as list of dicts with keys: id, distance."""
    from google.cloud import aiplatform

    aiplatform.init(project=project, location=region)
    endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=endpoint_id)
    resp = endpoint.find_neighbors(
        deployed_index_id=deployed_index_id,
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
    return out


def similarity_from_distance(distance: float | None) -> float | None:
    if distance is None:
        return None
    # Cosine distance in [0, 2]; similarity in [0, 1] = 1 - distance/2 (same as mobius-chat)
    try:
        d = float(distance)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, 1.0 - d / 2.0))


def _maybe_fetch_metadata(ids: list[str], chat_db_url: str | None) -> dict[str, dict[str, Any]]:
    """Fetch metadata rows by id from Postgres published_rag_metadata."""
    if not ids or not chat_db_url:
        return {}
    try:
        import psycopg2
        import psycopg2.extras
    except Exception:
        return {}
    try:
        conn = psycopg2.connect(chat_db_url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT
              id,
              document_id,
              source_type,
              source_id,
              text,
              page_number,
              section_path,
              chapter_path,
              document_display_name,
              document_filename
            FROM published_rag_metadata
            WHERE id::text = ANY(%s)
            """,
            (ids,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {str(r["id"]): dict(r) for r in rows}
    except Exception:
        return {}


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _plot_distributions(df, out_dir: Path) -> list[Path]:
    """Write a few simple distribution plots. Returns list of written paths."""
    import matplotlib.pyplot as plt

    written: list[Path] = []
    if df.empty:
        return written

    # 1) Histogram: similarity by mode (overall)
    fig = plt.figure(figsize=(10, 6))
    for mode in sorted(df["mode"].dropna().unique().tolist()):
        sub = df[(df["mode"] == mode) & df["similarity"].notna()]
        if sub.empty:
            continue
        plt.hist(sub["similarity"], bins=30, alpha=0.5, label=mode)
    plt.title("Similarity distribution (all questions, top-k pooled)")
    plt.xlabel("similarity (1 - cosine_distance/2)")
    plt.ylabel("count")
    plt.legend()
    p = out_dir / "similarity_hist_all.png"
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    plt.close(fig)
    written.append(p)

    # 2) ECDF: similarity by mode (overall)
    fig = plt.figure(figsize=(10, 6))
    for mode in sorted(df["mode"].dropna().unique().tolist()):
        sub = df[(df["mode"] == mode) & df["similarity"].notna()].sort_values("similarity")
        if sub.empty:
            continue
        y = (sub["similarity"].rank(method="average") - 1) / max(1, (len(sub) - 1))
        plt.plot(sub["similarity"], y, label=mode)
    plt.title("Similarity ECDF (all questions, top-k pooled)")
    plt.xlabel("similarity")
    plt.ylabel("ECDF")
    plt.legend()
    p = out_dir / "similarity_ecdf_all.png"
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    plt.close(fig)
    written.append(p)

    # 3) Split hist by intent (factual vs canonical)
    intents = [i for i in ["factual", "canonical"] if i in set(df["intent"].dropna().unique())]
    for intent in intents:
        fig = plt.figure(figsize=(10, 6))
        for mode in sorted(df["mode"].dropna().unique().tolist()):
            sub = df[(df["mode"] == mode) & (df["intent"] == intent) & df["similarity"].notna()]
            if sub.empty:
                continue
            plt.hist(sub["similarity"], bins=30, alpha=0.5, label=mode)
        plt.title(f"Similarity distribution ({intent}, top-k pooled)")
        plt.xlabel("similarity")
        plt.ylabel("count")
        plt.legend()
        p = out_dir / f"similarity_hist_{intent}.png"
        fig.tight_layout()
        fig.savefig(p, dpi=150)
        plt.close(fig)
        written.append(p)

    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--questions", default=str(ROOT / "questions.yaml"))
    ap.add_argument("--limit", type=int, default=None, help="Override number of questions to run")
    ap.add_argument("--top-k", type=int, default=None, help="Override top-k neighbors per query")
    ap.add_argument("--sleep-sec", type=float, default=0.0, help="Optional sleep between queries (rate limiting)")
    args = ap.parse_args()

    cfg = load_yaml(Path(args.config))
    qs = load_questions(Path(args.questions))

    v = _get_cfg_vertex(cfg)
    e = _get_cfg_embedding(cfg)
    f = _get_cfg_filters(cfg)
    r = _get_cfg_run(cfg)
    modes = _get_cfg_modes(cfg)

    # Hard requirement: isolation filter token (otherwise you’ll be mixing many docs in the index).
    if not f.get("document_authority_level"):
        raise ValueError(
            "filters.document_authority_level must be set (or env RAG_FILTER_AUTHORITY_LEVEL) "
            "so this eval isolates the Sunshine manual."
        )

    limit_questions = args.limit if args.limit is not None else r["limit_questions"]
    top_k = args.top_k if args.top_k is not None else r["top_k"]
    qs = qs[:limit_questions]

    run_dir = Path(r["report_dir"]) / f"retrieval-eval-{_utc_ts()}"
    if not run_dir.is_absolute():
        run_dir = (ROOT / run_dir).resolve()
    _ensure_dir(run_dir)

    chat_db_url = os.getenv("CHAT_RAG_DATABASE_URL") or os.getenv("CHAT_DATABASE_URL")  # accept both

    print(f"Running retrieval eval: {len(qs)} question(s), top_k={top_k}, modes={[m.name for m in modes]}")
    print(f"Vertex: project={v['project']} region={v['region']}")
    print(f"Vertex endpoint={v['endpoint_id']} deployed_index_id={v['deployed_id']}")
    print(f"Filter: document_authority_level={f['document_authority_level']}")
    if chat_db_url:
        print("Postgres enrichment: enabled (published_rag_metadata)")
    else:
        print("Postgres enrichment: disabled (CHAT_RAG_DATABASE_URL not set)")

    rows: list[dict[str, Any]] = []
    started = time.monotonic()
    for qi, q in enumerate(qs, start=1):
        question = q["question"]
        qid = q["id"]
        intent = q.get("intent") or "unknown"
        bucket = q.get("bucket") or ""

        try:
            emb = embed_query(
                question,
                project=v["project"],
                region=v["region"],
                model=e["model"],
                output_dimensionality=e["output_dimensionality"],
                task_type=e["task_type"],
            )
        except Exception as ex:
            rows.append({
                "qid": qid,
                "intent": intent,
                "bucket": bucket,
                "question": question,
                "mode": "__embed_error__",
                "rank": None,
                "neighbor_id": None,
                "distance": None,
                "similarity": None,
                "confidence": None,
                "error": f"embed_error: {ex}",
            })
            continue

        for mode in modes:
            namespaces = _vertex_namespaces(f, mode.source_type_allow)
            try:
                neighbors = vertex_find_neighbors(
                    endpoint_id=v["endpoint_id"],
                    deployed_index_id=v["deployed_id"],
                    query_embedding=emb,
                    k=top_k,
                    namespaces=namespaces,
                    project=v["project"],
                    region=v["region"],
                )
            except Exception as ex:
                rows.append({
                    "qid": qid,
                    "intent": intent,
                    "bucket": bucket,
                    "question": question,
                    "mode": mode.name,
                    "rank": None,
                    "neighbor_id": None,
                    "distance": None,
                    "similarity": None,
                    "confidence": None,
                    "error": f"vertex_error: {ex}",
                })
                continue

            ids = [n["id"] for n in neighbors if n.get("id")]
            meta_by_id = _maybe_fetch_metadata(ids, chat_db_url)

            for rank, n in enumerate(neighbors, start=1):
                nid = n.get("id")
                dist = n.get("distance")
                sim = similarity_from_distance(dist)
                meta = meta_by_id.get(str(nid)) if nid else None
                doc_name = None
                page_number = None
                section_path = None
                chapter_path = None
                source_type = None
                text_snippet = None
                if meta:
                    doc_name = meta.get("document_display_name") or meta.get("document_filename")
                    page_number = meta.get("page_number")
                    section_path = meta.get("section_path")
                    chapter_path = meta.get("chapter_path")
                    source_type = meta.get("source_type")
                    txt = (meta.get("text") or "").strip()
                    text_snippet = (txt[:240] + "…") if (txt and len(txt) > 240) else (txt or None)

                rows.append({
                    "qid": qid,
                    "intent": intent,
                    "bucket": bucket,
                    "question": question,
                    "mode": mode.name,
                    "rank": rank,
                    "neighbor_id": nid,
                    "distance": dist,
                    "similarity": sim,
                    "confidence": sim,  # placeholder: same mapping as chat today
                    "source_type": source_type,
                    "document_name": doc_name,
                    "page_number": page_number,
                    "section_path": section_path,
                    "chapter_path": chapter_path,
                    "text_snippet": text_snippet,
                    "error": None,
                })

            if args.sleep_sec and args.sleep_sec > 0:
                time.sleep(args.sleep_sec)

        if qi % 5 == 0 or qi == len(qs):
            elapsed = time.monotonic() - started
            print(f"  progress: {qi}/{len(qs)} questions | {elapsed:.1f}s")

    # Write outputs
    results_jsonl = run_dir / "results.jsonl"
    _write_jsonl(results_jsonl, rows)

    import pandas as pd

    df = pd.DataFrame(rows)
    results_csv = run_dir / "results.csv"
    df.to_csv(results_csv, index=False)

    # Summary
    summary_md = run_dir / "summary.md"
    with open(summary_md, "w") as fsum:
        fsum.write("## Retrieval Eval Summary\n\n")
        fsum.write(f"- **run_dir**: `{run_dir}`\n")
        fsum.write(f"- **questions**: {len(qs)}\n")
        fsum.write(f"- **top_k**: {top_k}\n")
        fsum.write(f"- **modes**: {', '.join([m.name for m in modes])}\n")
        fsum.write(f"- **filter.document_authority_level**: `{f['document_authority_level']}`\n")
        if f.get("document_payer"):
            fsum.write(f"- **filter.document_payer**: `{f['document_payer']}`\n")
        fsum.write("\n")

        n_err = int(df["error"].notna().sum()) if "error" in df.columns else 0
        fsum.write(f"- **rows**: {len(df)}\n")
        fsum.write(f"- **errors**: {n_err}\n\n")

        if "similarity" in df.columns and "mode" in df.columns:
            sim_df = df[df["similarity"].notna()].copy()
            if not sim_df.empty:
                grp = sim_df.groupby("mode")["similarity"].agg(["count", "mean", "median", "min", "max"])
                fsum.write("### Similarity stats by mode (pooled over top-k)\n\n")
                try:
                    fsum.write(grp.to_markdown() + "\n\n")
                except ImportError:
                    # pandas.to_markdown requires optional dependency 'tabulate'
                    fsum.write(grp.to_string() + "\n\n")

                # Top-1 only
                top1 = sim_df[sim_df["rank"] == 1]
                if not top1.empty:
                    grp1 = top1.groupby("mode")["similarity"].agg(["count", "mean", "median", "min", "max"])
                    fsum.write("### Similarity stats by mode (top-1 only)\n\n")
                    try:
                        fsum.write(grp1.to_markdown() + "\n\n")
                    except ImportError:
                        fsum.write(grp1.to_string() + "\n\n")

    # Plots
    plot_paths = _plot_distributions(df, run_dir)
    if plot_paths:
        print("Wrote plots:")
        for p in plot_paths:
            print(f"  - {p}")

    print(f"Done. Outputs:\n  - {results_csv}\n  - {results_jsonl}\n  - {summary_md}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
