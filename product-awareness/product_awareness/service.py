"""Standalone retrieval service (FastAPI).

Owns retrieval + disambiguation over the product_docs corpus (Vertex embedder +
pgvector). Stateless w.r.t. feedback: ``/search`` returns the outcome AND a ``gap``
payload, but does NOT write it — the chat-side handler files the gap in-process
(the contract keeps the docs_gap write on the chat side). Parallels mobius-feedback:
a thin service + a chat-side SkillSpec handler.

Run:  PYTHONPATH=. uvicorn product_awareness.service:app --port 8070
"""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from .search import ProductHelp

app = FastAPI(title="product-awareness", version="0.1.0")

_engine: ProductHelp | None = None


def _get_engine() -> ProductHelp:
    global _engine
    if _engine is None:
        _engine = ProductHelp()   # loads embedder + store once
    return _engine


class SearchRequest(BaseModel):
    query: str
    k: int = 6
    audience: str | None = None
    module: str | None = None
    in_scope_only: bool = False


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "product-awareness"}


@app.post("/search")
def search(req: SearchRequest) -> dict:
    """Return {outcome, text, sources, s_top, tau_gap, module, gap}.

    ``gap`` is null for an answer, or {category, module, verbatim, summary} for a
    docs_gap / feature_request outcome — the chat handler files it (best-effort).
    """
    result = _get_engine().search(
        req.query, k=req.k, audience=req.audience,
        module=req.module, in_scope_only=req.in_scope_only)
    return result.to_dict()
