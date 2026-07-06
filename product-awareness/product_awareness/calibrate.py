"""Two-sided τ_gap calibration — the contract's methodology, as one command.

  in-corpus probe:   in-scope docs' own section headings  → should score HIGH
  out-of-corpus probe: known-absent questions              → should score LOW

Suggested τ_gap sits between in-corpus p10 and out-corpus p90 — but only if they
actually separate. With the offline TF embedder they don't (that's the point: it
proves plumbing, not quality). Run this against Vertex + pgvector to get a real value.
"""
from __future__ import annotations

import numpy as np

from . import chunker, config
from .search import ProductHelp

_OUT_OF_CORPUS = [
    "how do I book a flight to paris", "what is the weather tomorrow",
    "recipe for chocolate cake", "who won the world cup last year",
    "translate hello into french", "how do I change a car tire",
    "what is the stock price of apple", "best hiking trails near me",
    "how tall is mount everest", "convert ten miles to kilometers",
]


def _r(x) -> float:
    return round(float(x), 4)


def _in_corpus_queries(in_scope_only: bool = True) -> list[str]:
    qs: list[str] = []
    for p in sorted(config.DOCS_DIR.glob("*.md")):
        meta = config.DOC_META.get(p.name)
        if not meta or (in_scope_only and not meta["in_scope"]):
            continue
        for c in chunker.chunk_file(p):
            if c.status == "planned" or c.section == "Overview":
                continue
            qs.append(f"how do I {c.section.lower()} in {c.module}")
    return qs


def calibrate(in_scope_only: bool = True) -> dict:
    ph = ProductHelp()
    ins = np.array([ph.search(q).s_top for q in _in_corpus_queries(in_scope_only)])
    outs = np.array([ph.search(q).s_top for q in _OUT_OF_CORPUS])
    in_p10 = float(np.percentile(ins, 10)) if len(ins) else 0.0
    out_p90 = float(np.percentile(outs, 90)) if len(outs) else 1.0
    separated = in_p10 > out_p90
    return {
        "embedder": ph.embedder.name,
        "store": ph.store.name,
        "current_tau_gap": ph.tau_gap,
        "in_corpus": {"n": int(len(ins)), "min": _r(ins.min()) if len(ins) else None,
                      "p10": _r(in_p10), "median": _r(np.median(ins)) if len(ins) else None},
        "out_corpus": {"n": int(len(outs)), "max": _r(outs.max()) if len(outs) else None,
                       "p90": _r(out_p90), "median": _r(np.median(outs)) if len(outs) else None},
        "separated": separated,
        "suggested_tau_gap": _r((in_p10 + out_p90) / 2) if separated else None,
        "note": ("clean separation — set PRODUCT_HELP_TAU_GAP to suggested_tau_gap"
                 if separated else
                 "OVERLAP: no threshold separates in/out — embedder too weak "
                 "(expected for the offline TF stand-in; run against Vertex)"),
    }
