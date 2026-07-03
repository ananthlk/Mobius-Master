"""Tests for the product-awareness pipeline.

Two layers:
  * disambiguation LOGIC — stubbed retrieval, deterministic (does not depend on
    embedder quality; the offline TF embedder has no reliable semantic separation).
  * chunker + ingest smoke — runs the real manuals through the real (numpy) backend.

Runnable without pytest:  python3 tests/test_pipeline.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PRODUCT_DOCS_STORE", "numpy")
os.environ.setdefault("PRODUCT_DOCS_EMBEDDER", "local")

from product_awareness import chunker, config, embedder as em  # noqa: E402
from product_awareness import ingest as ingest_mod  # noqa: E402
from product_awareness.search import ProductHelp  # noqa: E402


def _engine(hits, tau=0.3):
    ph = ProductHelp.__new__(ProductHelp)   # bypass __init__ (no real store)
    ph.embedder = em.HashingTfEmbedder(16)
    ph.tau_gap = tau

    class _Stub:
        def query(self, vec, k, where=None):
            return hits

    ph.store = _Stub()
    return ph


def _hit(module, section, status, score):
    return {"id": f"{module}:{section}:0", "score": score,
            "metadata": {"module": module, "section": section, "status": status},
            "document": f"{module} {section} body"}


def test_answer_on_current_hit():
    r = _engine([_hit("chat", "Capabilities", "current", 0.5)]).search("q")
    assert r.outcome == "answer" and r.gap is None


def test_feature_request_on_planned_hit():
    r = _engine([_hit("auth", "Not yet available (planned)", "planned", 0.5)]).search("q")
    assert r.outcome == "feature_request"
    assert r.gap["category"] == "feature_request" and r.gap["module"] == "auth"


def test_docs_gap_below_threshold():
    r = _engine([_hit("chat", "Capabilities", "current", 0.05)]).search("q")
    assert r.outcome == "docs_gap" and r.gap["category"] == "docs_gap"
    assert r.gap["module"] == "chat"          # best-guess area_tag from closest hit


def test_docs_gap_on_empty():
    r = _engine([]).search("q")
    assert r.outcome == "docs_gap" and r.gap["module"] == "unknown"


def test_chunker_flags_planned_and_excludes_meta():
    chunks = chunker.chunk_file(config.DOCS_DIR / "user-and-auth.md")
    assert any(c.status == "planned" for c in chunks), "must flag Not-yet-available"
    assert all(c.section != "Doc-readiness notes" for c in chunks), "must drop author meta"
    assert any(c.section == "Overview" for c in chunks), "must emit an overview chunk"
    planned = [c for c in chunks if c.status == "planned"]
    assert all("planned" in c.section.lower() for c in planned)


def test_ingest_smoke():
    summ = ingest_mod.ingest(scope="all")
    assert summ["chunks"] > 0 and summ["planned_chunks"] > 0
    assert summ["store"] == "numpy" and summ["embedder"] == "local-tf-hash"


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run()
