"""CLI: ingest / search / stats.

    PYTHONPATH=product-awareness python3 -m product_awareness.cli ingest
    PYTHONPATH=product-awareness python3 -m product_awareness.cli search "how do I sign in with google"
    PYTHONPATH=product-awareness python3 -m product_awareness.cli stats
"""
from __future__ import annotations

import argparse
import json

from . import config
from .ingest import ingest, ingest_from_chunks
from .search import ProductHelp
from .store import get_store


def _cmd_ingest(args) -> None:
    summary = ingest(scope=args.scope, reset=not args.no_reset)
    print(json.dumps(summary, indent=2))


def _cmd_ingest_from_chunks(args) -> None:
    summary = ingest_from_chunks(scope=args.scope, reset=not args.no_reset)
    print(json.dumps(summary, indent=2))


def _cmd_search(args) -> None:
    res = ProductHelp().search(
        args.query, k=args.k, audience=args.audience,
        module=args.module, in_scope_only=args.in_scope)
    d = res.to_dict()
    print(f"[{d['outcome']}]  s_top={d['s_top']}  τ_gap={d['tau_gap']}  module={d['module']}")
    if d["gap"]:
        print(f"  → would file: {d['gap']['category']}  area_tag={d['gap']['module']}")
    print("  sources:", ", ".join(f"{s['module']}:{s['section']}({s['score']})"
                                   for s in d["sources"][:4]) or "(none)")
    if args.verbose:
        print("\n" + d["text"][:800])


def _cmd_stats(args) -> None:
    store = get_store()
    print(json.dumps({"store": store.name, "collection": config.COLLECTION,
                      "count": store.count(),
                      "chunks_dir": str(config.CHUNKS_DIR),
                      "index_dir": str(config.INDEX_DIR)}, indent=2))


def _cmd_calibrate(args) -> None:
    from .calibrate import calibrate
    report = calibrate(in_scope_only=not args.all)
    print(json.dumps(report, indent=2))
    if report["suggested_tau_gap"] is not None:
        print(f"\nexport PRODUCT_HELP_TAU_GAP={report['suggested_tau_gap']}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="product_awareness")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest", help="chunk manuals + build the vector index")
    pi.add_argument("--scope", choices=["all", "in"], default="all")
    pi.add_argument("--no-reset", action="store_true", help="append instead of rebuild")
    pi.set_defaults(func=_cmd_ingest)

    pfc = sub.add_parser("ingest-from-chunks",
                         help="embed pre-chunked corpus/chunks/*.jsonl (in-cloud path)")
    pfc.add_argument("--scope", choices=["all", "in"], default="all")
    pfc.add_argument("--no-reset", action="store_true")
    pfc.set_defaults(func=_cmd_ingest_from_chunks)

    ps = sub.add_parser("search", help="query the product_docs corpus")
    ps.add_argument("query")
    ps.add_argument("--k", type=int, default=6)
    ps.add_argument("--audience", default=None)
    ps.add_argument("--module", default=None)
    ps.add_argument("--in-scope", action="store_true", dest="in_scope")
    ps.add_argument("-v", "--verbose", action="store_true")
    ps.set_defaults(func=_cmd_search)

    pt = sub.add_parser("stats", help="show corpus stats")
    pt.set_defaults(func=_cmd_stats)

    pc = sub.add_parser("calibrate", help="two-sided τ_gap calibration probe")
    pc.add_argument("--all", action="store_true", help="include out-of-scope modules")
    pc.set_defaults(func=_cmd_calibrate)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
