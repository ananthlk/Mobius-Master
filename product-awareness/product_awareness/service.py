"""Standalone retrieval service (FastAPI).

Owns retrieval + disambiguation over the product_docs corpus (Vertex embedder +
pgvector). Stateless w.r.t. feedback: ``/search`` returns the outcome AND a ``gap``
payload, but does NOT write it — the chat-side handler files the gap in-process
(the contract keeps the docs_gap write on the chat side). Parallels mobius-feedback:
a thin service + a chat-side SkillSpec handler.

Run:  PYTHONPATH=. uvicorn product_awareness.service:app --port 8070
"""
from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import config
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


class DocRequest(BaseModel):
    document_id: str
    view: str = "full"
    model_config = {"extra": "ignore"}   # tolerate the proxy's extra fields


def _load_doc(module: str) -> dict | None:
    """Reconstruct a product doc from its shipped chunks (corpus/chunks/<module>.jsonl)
    into the chat doc-reader panel's envelope shape — no source markdown needed."""
    path = config.CHUNKS_DIR / f"{module}.jsonl"
    if not path.exists():
        return None
    chunks = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not chunks:
        return None
    title = chunks[0].get("doc_title", module)
    sections: list[dict] = []
    by_heading: dict[str, dict] = {}
    for c in chunks:
        heading = c.get("section", "")
        text = c.get("text", "")
        # chunk text is "# {title} — {section}\n\n{content}" — strip the prepended heading
        content = text.split("\n\n", 1)[1] if "\n\n" in text else text
        if heading not in by_heading:
            sec = {"section_id": f"sec-{len(sections)}", "heading": heading, "depth": 1,
                   "page_start": None, "page_end": None, "body_markdown": content,
                   "citations": [], "tags": {"j_tags": [], "p_tags": [], "d_tags": []}}
            by_heading[heading] = sec
            sections.append(sec)
        else:
            by_heading[heading]["body_markdown"] += "\n\n" + content
    toc = [{"heading": s["heading"], "depth": 1, "page_range": "", "section_id": s["section_id"]}
           for s in sections]
    return {
        "envelope_id": f"product-docs-{module}",
        "document_id": f"product-docs:{module}",
        "view": "full",
        "display_name": title,
        "payer": "",
        "authority_level": "product docs",
        "provenance": {"source_type": "product_docs", "source_url": "",
                       "effective_date": "", "verification_tier": "instant"},
        "toc": toc,
        "sections": sections,
        "summary": None,
        "tags": {"j_tags": [], "p_tags": [], "d_tags": []},
        "tag_coverage": 0.0,
        "rendering_hints": {"preferred_format": "markdown", "citation_style": "inline",
                            "collapsible_sections": True, "max_depth": 3},
        "cached_at": None, "expires_at": None, "created_at": "",
    }


@app.post("/doc")
def doc(req: DocRequest) -> dict:
    """Render a product doc in the chat doc-reader panel's envelope shape.

    `document_id` = 'product-docs:<module>' — chat's doc_reader proxy routes these here
    instead of to the RAG doc-reader, so product docs render without living in rag.documents.
    """
    module = req.document_id.split(":", 1)[1] if ":" in req.document_id else req.document_id
    result = _load_doc(module)
    if result is None:
        raise HTTPException(status_code=404, detail=f"no product doc for {req.document_id!r}")
    return result
