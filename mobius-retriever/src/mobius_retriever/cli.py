"""CLI for mobius-retriever. Emits each step to stdout."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Package root: src/mobius_retriever/cli.py -> src/
PKG_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PKG_ROOT.parent  # src/
PROJECT_ROOT = SRC_ROOT.parent  # mobius-retriever/

# Load mobius-config/.env if present (so Vertex/Postgres env vars are set)
def _load_env() -> None:
    for candidate in [
        PROJECT_ROOT.parent / "mobius-config" / ".env",
        PROJECT_ROOT.parent / ".env",
        Path.cwd() / "mobius-config" / ".env",
        Path.cwd() / ".env",
    ]:
        if candidate.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(candidate, override=False)
                break
            except ImportError:
                break
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mobius_retriever.retriever import retrieve_path_b, retrieve_bm25


def _emit(msg: str) -> None:
    print(f"[retriever] {msg}", flush=True)


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="Mobius Retriever - Path B (vector + limited rerank)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    path_b = subparsers.add_parser("path-b", help="Run Path B: vector search + limited reranking")
    path_b.add_argument("--question", "-q", required=True, help="Search question")
    path_b.add_argument("--config", "-c", default=None, help="Path to config YAML (default: configs/path_b_v1.yaml)")
    path_b.add_argument("--source-type", action="append", help="Filter by source_type (repeat for multiple)")
    path_b.add_argument("--top-k", type=int, default=None, help="Override top_k from config")

    db_check = subparsers.add_parser(
        "db-check",
        help="Verify Postgres URL and corpus size (BM25 reads from this DB). Ensures retriever and DBT sync target match.",
    )
    db_check.add_argument("--config", "-c", default=None, help="Path to config YAML (uses postgres_url)")

    benchmark = subparsers.add_parser(
        "benchmark",
        help="Run BM25 N times to measure latency (for scope/narrowing decision). Use --all-source-types for full corpus.",
    )
    benchmark.add_argument("--question", "-q", required=True, help="Search question")
    benchmark.add_argument("--config", "-c", default=None, help="Config YAML path")
    benchmark.add_argument("--runs", "-n", type=int, default=10, help="Number of runs (default: 10)")
    benchmark.add_argument(
        "--all-source-types",
        action="store_true",
        help="Search full corpus (hierarchical+fact). Default: hierarchical only.",
    )
    benchmark.add_argument("--plot", action="store_true", help="Plot latency histogram (requires matplotlib)")
    benchmark.add_argument("--tagged", action="store_true", help="Use question tags to filter BM25 corpus")
    benchmark.add_argument("--jpd", action="store_true", help="Use J/P/D tagger to scope BM25 corpus by document_ids")

    benchmark_tagged = subparsers.add_parser(
        "benchmark-tagged",
        help="Compare BM25 with vs without question tags: time, accuracy (overlap), record for previous-run comparison",
    )
    benchmark_tagged.add_argument("--question", "-q", required=True, help="Search question")
    benchmark_tagged.add_argument("--config", "-c", default=None, help="Config YAML path")
    benchmark_tagged.add_argument("--runs", "-n", type=int, default=3, help="Runs per mode (default: 3)")
    benchmark_tagged.add_argument("--output", "-o", default=None, help="Write results JSON (default: mobius-retriever/benchmark_tagged_<ts>.json)")
    benchmark_tagged.add_argument("--jpd", action="store_true", help="Use J/P/D tagger to scope BM25 corpus by document_ids")

    compare = subparsers.add_parser("compare", help="Run Vector (Path B) and BM25 side by side, no reranking")
    compare.add_argument("--question", "-q", required=True, help="Search question")
    compare.add_argument("--config", "-c", default=None, help="Path to config YAML (default: configs/path_b_v1.yaml)")
    compare.add_argument("--top-k", type=int, default=10, help="Top-k for each path")
    compare.add_argument("--tagged", action="store_true", help="Use question tags to filter BM25 corpus")
    compare.add_argument("--jpd", action="store_true", help="Use J/P/D tagger to scope BM25 corpus by document_ids")
    compare.add_argument("--gold-ids", default="", help="Comma-separated gold parent_metadata_ids to check hit@k (e.g. from questions.yaml)")

    retrieval_report = subparsers.add_parser(
        "retrieval-report",
        help="Run BM25 (and optionally Vector) and show paragraph_ids, document_ids, gold hit. No Vertex needed if --bm25-only.",
    )
    retrieval_report.add_argument("--question", "-q", required=True, help="Search question")
    retrieval_report.add_argument("--config", "-c", default=None, help="Config YAML path")
    retrieval_report.add_argument("--jpd", action="store_true", help="Use J/P/D tagger")
    retrieval_report.add_argument("--gold-ids", default="", help="Comma-separated gold parent_metadata_ids to check hit@k")
    retrieval_report.add_argument("--bm25-only", action="store_true", help="Skip Vector (use when Vertex not configured)")

    args = parser.parse_args()

    if args.command == "path-b":
        config_path = args.config
        if not config_path:
            # Default: configs/path_b_v1.yaml relative to project root (mobius-retriever/)
            default = SRC_ROOT.parent / "configs" / "path_b_v1.yaml"
            if default.exists():
                config_path = str(default)
            else:
                _emit("Error: --config required when configs/path_b_v1.yaml not found")
                return 1
        _emit(f"Input: question={args.question[:60]}{'...' if len(args.question) > 60 else ''}")
        _emit(f"Config: {config_path}")
        source_type_allow = args.source_type if args.source_type else None
        result = retrieve_path_b(
            question=args.question,
            config_path=config_path,
            source_type_allow=source_type_allow,
            emitter=_emit,
        )
        _emit(f"Config version: {result.config_version} name: {result.config_name}")
        _emit(f"Output: {len(result.chunks)} chunk(s)")
        for i, c in enumerate(result.chunks, 1):
            sim = c.similarity
            sim_s = f"{sim:.3f}" if sim is not None else "—"
            snippet = (c.text or "")[:120] + ("…" if len(c.text or "") > 120 else "")
            _emit(f"  [{i}] score={sim_s} type={c.source_type} page={c.page_number} | {snippet}")
        return 0

    if args.command == "db-check":
        config_path = args.config or str(SRC_ROOT.parent / "configs" / "path_b_v1.yaml")
        if not Path(config_path).exists():
            _emit(f"Error: config not found: {config_path}")
            return 1
        from mobius_retriever.config import load_path_b_config
        cfg = load_path_b_config(Path(config_path))
        url = (cfg.postgres_url or "").strip()
        if not url:
            _emit("postgres_url is empty. Set CHAT_RAG_DATABASE_URL (or CHAT_DATABASE_URL) in env.")
            return 1
        # Mask password in URL for display
        import re
        def _mask(u: str) -> str:
            m = re.match(r"^(postgresql://[^:]+:)([^@]*)(@.*)$", u)
            return f"{m.group(1)}****{m.group(3)}" if m else u
        _emit(f"postgres_url: {_mask(url)}")
        dbt_url = os.environ.get("CHAT_DATABASE_URL", "").strip()
        if dbt_url and dbt_url != url:
            _emit(f"CHAT_DATABASE_URL (mobius-dbt): {_mask(dbt_url)}")
            _emit("WARNING: URLs differ. Retriever and DBT sync may use different DBs.")
        elif dbt_url:
            _emit("CHAT_DATABASE_URL matches postgres_url (same DB).")
        try:
            import psycopg2
            conn = psycopg2.connect(url)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM published_rag_metadata")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM published_rag_metadata WHERE source_type = 'hierarchical'")
            hierarchical = cur.fetchone()[0]
            # BM25 applies authority_level filter when set (skips if placeholder unresolved)
            auth = (cfg.filters.document_authority_level or "").strip()
            if auth and "${" not in auth:
                cur.execute(
                    "SELECT COUNT(*) FROM published_rag_metadata WHERE source_type = 'hierarchical' AND document_authority_level = %s",
                    (auth,),
                )
                filtered = cur.fetchone()[0]
                _emit(f"published_rag_metadata: {total} total, {hierarchical} hierarchical, {filtered} hierarchical+authority_level={auth!r} (BM25 corpus)")
            else:
                _emit(f"published_rag_metadata: {total} total, {hierarchical} hierarchical (BM25 corpus; no authority_level filter)")
            cur.close()
            conn.close()
        except Exception as e:
            _emit(f"DB check failed: {e}")
            return 1
        return 0

    if args.command == "benchmark":
        import statistics
        import time
        config_path = args.config or str(SRC_ROOT.parent / "configs" / "path_b_v1.yaml")
        if not Path(config_path).exists():
            _emit(f"Error: config not found: {config_path}")
            return 1
        st = ["hierarchical", "fact"] if args.all_source_types else None
        _emit("=== BM25 Latency Benchmark ===")
        _emit(f"Question: {args.question[:80]}{'...' if len(args.question) > 80 else ''}")
        _emit(f"Corpus: {'all (hierarchical+fact)' if st else 'hierarchical only'}")
        _emit(f"Tags: {'question-derived (payer/program/state)' if args.tagged else 'none'}")
        _emit(f"Runs: {args.runs}")
        _emit("")
        timings: list[float] = []
        for i in range(args.runs):
            emitter = _emit if i == 0 else (lambda _: None)
            t0 = time.perf_counter()
            result = retrieve_bm25(
                question=args.question,
                config_path=config_path,
                source_types=st,
                use_question_tags=args.tagged,
                use_jpd_tagger=getattr(args, "jpd", False),
                emitter=emitter,
            )
            t_ms = (time.perf_counter() - t0) * 1000
            timings.append(t_ms)
            if i == 0:
                _emit(f"Run 1: {len(result.chunks)} results, {t_ms:.0f}ms")
                _emit("")
                _emit("--- BM25 top results ---")
                paras = [c for c in result.chunks if getattr(c, "provision_type", "sentence") == "paragraph"]
                sents = [c for c in result.chunks if getattr(c, "provision_type", "sentence") == "sentence"]
                for label, items in [("paragraph", paras), ("sentence", sents)]:
                    if items:
                        _emit(f"  --- {label} provisions ---")
                        for j, c in enumerate(items[:10], 1):
                            score_str = f"raw_score={c.raw_score:.4f}" if c.raw_score is not None else "raw_score=N/A"
                            pg = f" p{c.page_number}" if c.page_number is not None else ""
                            doc = (c.document_name or "doc")[:40]
                            txt_full = (c.text or "").replace("\n", " ")
                            max_len = 800
                            txt = txt_full[:max_len] + ("..." if len(txt_full) > max_len else "")
                            _emit(f"  [{j}] {score_str}{pg} | {doc}")
                            _emit(f"      {txt}")
                _emit("")
            else:
                _emit(f"Run {i + 1}: {t_ms:.0f}ms")
        _emit("")
        _emit(f"Latency (ms): min={min(timings):.0f} max={max(timings):.0f} mean={statistics.mean(timings):.0f} median={statistics.median(timings):.0f}" + (f" stdev={statistics.stdev(timings):.1f}" if len(timings) > 1 else ""))
        if args.plot and timings:
            try:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots()
                ax.hist(timings, bins=min(20, len(timings)), edgecolor="black", alpha=0.7)
                ax.set_xlabel("Latency (ms)")
                ax.set_ylabel("Count")
                ax.set_title("BM25 Latency Benchmark")
                out_path = SRC_ROOT.parent / "benchmark_latency.png"
                fig.savefig(out_path, dpi=100)
                _emit(f"Plot saved: {out_path}")
            except ImportError:
                _emit("--plot requires matplotlib: pip install matplotlib")
        return 0

    if args.command == "benchmark-tagged":
        import json
        import statistics
        import time
        from datetime import datetime, timezone
        from mobius_retriever.tagger import tag_question

        config_path = args.config or str(SRC_ROOT.parent / "configs" / "path_b_v1.yaml")
        if not Path(config_path).exists():
            _emit(f"Error: config not found: {config_path}")
            return 1
        n = max(1, args.runs)
        _emit("=== BM25 Tagged vs Untagged Benchmark ===")
        _emit(f"Question: {args.question[:80]}{'...' if len(args.question) > 80 else ''}")
        qt = tag_question(args.question)
        filters = qt.as_filters()
        _emit(f"Tags extracted: {filters if filters else '(none)'}")
        _emit("")

        def _run(use_tags: bool, quiet: bool = False) -> tuple[list, list[float]]:
            timings: list[float] = []
            last_chunks: list = []
            for i in range(n):
                t0 = time.perf_counter()
                r = retrieve_bm25(
                    question=args.question,
                    config_path=config_path,
                    use_question_tags=use_tags,
                    use_jpd_tagger=getattr(args, "jpd", False),
                    emitter=None if (quiet and i > 0) else _emit,
                )
                t_ms = (time.perf_counter() - t0) * 1000
                timings.append(t_ms)
                last_chunks = r.chunks
            return last_chunks, timings

        _emit("--- Untagged (full corpus) ---")
        unchunks, untimes = _run(False, quiet=False)
        _emit(f"Latency: min={min(untimes):.0f} max={max(untimes):.0f} mean={statistics.mean(untimes):.0f}ms")
        _emit("")

        _emit("--- Tagged (filtered corpus) ---")
        tchunks, ttimes = _run(True, quiet=False)
        _emit(f"Latency: min={min(ttimes):.0f} max={max(ttimes):.0f} mean={statistics.mean(ttimes):.0f}ms")
        _emit("")

        # Overlap: fraction of tagged top-k that appear in untagged top-k (by chunk id)
        uids = {str(c.id) for c in unchunks}
        overlap = sum(1 for c in tchunks if str(c.id) in uids) / max(1, len(tchunks))
        _emit(f"Accuracy (overlap): {overlap:.1%} of tagged results in untagged top-{len(unchunks)}")
        _emit("")

        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_path = args.output or str(SRC_ROOT.parent / f"benchmark_tagged_{ts}.json")
        rec = {
            "timestamp": ts,
            "question": args.question[:200],
            "tags": filters,
            "runs": n,
            "untagged": {
                "mean_ms": statistics.mean(untimes),
                "min_ms": min(untimes),
                "max_ms": max(untimes),
                "results": len(unchunks),
            },
            "tagged": {
                "mean_ms": statistics.mean(ttimes),
                "min_ms": min(ttimes),
                "max_ms": max(ttimes),
                "results": len(tchunks),
            },
            "overlap_pct": overlap * 100,
        }
        with open(out_path, "w") as f:
            json.dump(rec, f, indent=2)
        _emit(f"Results written: {out_path}")
        return 0

    if args.command == "compare":
        import time
        config_path = args.config
        if not config_path:
            default = SRC_ROOT.parent / "configs" / "path_b_v1.yaml"
            config_path = str(default) if default.exists() else ""
        if not config_path:
            _emit("Error: --config required when configs/path_b_v1.yaml not found")
            return 1
        _emit("=== Compare: Vector (Path B) vs BM25 (no reranking) ===")
        _emit(f"Question: {args.question}")
        _emit("")
        # Vector (Path B)
        _emit("--- Vector (hierarchical chunks) ---")
        t0_vec = time.perf_counter()
        vec = retrieve_path_b(
            question=args.question,
            config_path=config_path,
            emitter=_emit,
        )
        for i, c in enumerate(vec.chunks, 1):
            snippet = (c.text or "")[:100] + ("…" if len(c.text or "") > 100 else "")
            _emit(f"  [{i}] score={c.score_display} page={c.page_number} | {snippet}")
        t_vec = (time.perf_counter() - t0_vec) * 1000
        _emit(f"[timing] Vector: {t_vec:.0f}ms")
        _emit("")
        # BM25
        _emit("--- BM25 (paragraph + sentence provisions) ---")
        t0_bm = time.perf_counter()
        bm = retrieve_bm25(
            question=args.question,
            config_path=config_path,
            top_k=getattr(args, "top_k", 10),
            use_question_tags=getattr(args, "tagged", False),
            use_jpd_tagger=getattr(args, "jpd", False),
            emitter=_emit,
        )
        for i, c in enumerate(bm.chunks, 1):
            pt = getattr(c, "provision_type", "sentence")
            snippet = (c.text or "")[:100] + ("…" if len(c.text or "") > 100 else "")
            _emit(f"  [{i}] [{pt}] raw_score={c.score_display} page={c.page_number} | {snippet}")
        t_bm = (time.perf_counter() - t0_bm) * 1000
        _emit(f"[timing] BM25: {t_bm:.0f}ms")
        _emit("")
        # Retrieval report: paragraph ids, document ids, gold hit
        _emit("--- Retrieval report (paragraph_id, document_id, document) ---")
        gold_ids = [x.strip() for x in (getattr(args, "gold_ids", "") or "").split(",") if x.strip()]
        if gold_ids:
            _emit(f"gold_parent_metadata_ids: {gold_ids}")
        vec_pids = [str(c.id) for c in vec.chunks if c.id]
        vec_docs = [(str(c.id), str(c.document_id) if c.document_id else "", c.document_name or "") for c in vec.chunks]
        bm_pids = [str(c.id) for c in bm.chunks if c.id]
        bm_docs = [(str(c.id), str(c.document_id) if c.document_id else "", c.document_name or "") for c in bm.chunks]
        _emit("Vector (Hierarchical) returned:")
        for i, (pid, doc_id, doc_name) in enumerate(vec_docs[:15], 1):
            gold_mark = " <-- GOLD" if pid in gold_ids else ""
            _emit(f"  {i}. paragraph_id={pid} document_id={doc_id} doc={doc_name[:50]}{gold_mark}")
        vec_hit = next((i for i, pid in enumerate(vec_pids, 1) if pid in gold_ids), None)
        _emit(f"  -> gold_rank={vec_hit} (1-indexed, None=miss)")
        _emit("BM25 returned:")
        for i, (pid, doc_id, doc_name) in enumerate(bm_docs[:15], 1):
            gold_mark = " <-- GOLD" if pid in gold_ids else ""
            _emit(f"  {i}. paragraph_id={pid} document_id={doc_id} doc={doc_name[:50]}{gold_mark}")
        bm_hit = next((i for i, pid in enumerate(bm_pids, 1) if pid in gold_ids), None)
        _emit(f"  -> gold_rank={bm_hit} (1-indexed, None=miss)")
        _emit("")
        _emit(f"Vector: {len(vec.chunks)} ({t_vec:.0f}ms) | BM25: {len(bm.chunks)} ({t_bm:.0f}ms)")
        return 0

    if args.command == "retrieval-report":
        config_path = args.config or str(SRC_ROOT.parent / "configs" / "path_b_v1.yaml")
        if not Path(config_path).exists():
            _emit(f"Error: config not found: {config_path}")
            return 1
        gold_ids = [x.strip() for x in (args.gold_ids or "").split(",") if x.strip()]
        _emit("=== Retrieval report: BM25 (paragraph_id, document_id, document) ===")
        _emit(f"Question: {args.question[:100]}{'...' if len(args.question) > 100 else ''}")
        if gold_ids:
            _emit(f"gold_parent_metadata_ids: {gold_ids}")
        _emit("")
        bm = retrieve_bm25(
            question=args.question,
            config_path=config_path,
            use_jpd_tagger=args.jpd,
            emitter=_emit,
        )
        bm_pids = [str(c.id) for c in bm.chunks if c.id]
        seen_docs: dict[str, str] = {}
        for c in bm.chunks:
            did = str(c.document_id) if c.document_id else ""
            dname = (c.document_name or "")[:50]
            if did and did not in seen_docs:
                seen_docs[did] = dname
        _emit("BM25 returned (paragraph_id, document_id, document):")
        for i, c in enumerate(bm.chunks[:20], 1):
            pid = str(c.id)
            did = str(c.document_id) if c.document_id else ""
            dname = (c.document_name or "")[:50]
            gold_mark = " <-- GOLD" if pid in gold_ids else ""
            pt = getattr(c, "provision_type", "?")
            _emit(f"  {i}. [{pt}] paragraph_id={pid} document_id={did} doc={dname}{gold_mark}")
        bm_hit = next((i for i, pid in enumerate(bm_pids, 1) if pid in gold_ids), None)
        _emit(f"  -> gold_rank={bm_hit} (1-indexed, None=missed)")
        _emit("")
        _emit(f"Unique documents in BM25 top-20: {len(seen_docs)}")
        for did, dname in list(seen_docs.items())[:10]:
            _emit(f"  document_id={did} -> {dname}")
        if not args.bm25_only:
            _emit("")
            _emit("--- Vector (hierarchical) ---")
            try:
                vec = retrieve_path_b(question=args.question, config_path=config_path, emitter=_emit)
                vec_pids = [str(c.id) for c in vec.chunks if c.id]
                for i, c in enumerate(vec.chunks[:10], 1):
                    pid = str(c.id)
                    did = str(c.document_id) if c.document_id else ""
                    gold_mark = " <-- GOLD" if pid in gold_ids else ""
                    _emit(f"  {i}. paragraph_id={pid} document_id={did}{gold_mark}")
                vec_hit = next((i for i, pid in enumerate(vec_pids, 1) if pid in gold_ids), None)
                _emit(f"  -> gold_rank={vec_hit}")
            except Exception as e:
                _emit(f"Vector skipped: {e}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
