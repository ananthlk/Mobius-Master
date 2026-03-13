"""RAG API: POST /retrieve - Mobius or lazy path. Used by Chat and retrieval-eval."""
from __future__ import annotations

import os
from pathlib import Path

# Load env before imports. mobius-chat/.env LAST so CHAT_RAG_DATABASE_URL (BM25 corpus),
# VERTEX_* take precedence. mstart also loads config then chat for rag-api.
_root = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
    for env_path in (_root / "mobius-config" / ".env", _root / ".env", _root / "mobius-chat" / ".env"):
        if env_path.exists():
            load_dotenv(env_path, override=True)
except Exception:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Mobius RAG API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class RetrieveRequest(BaseModel):
    question: str
    path: str = "mobius"  # "mobius" | "lazy"
    top_k: int = 10
    apply_google: bool = True
    n_factual: int | None = None
    n_hierarchical: int | None = None
    include_trace: bool = False
    filter_payer: str | None = None
    filter_state: str | None = None
    filter_program: str | None = None
    filter_authority_level: str | None = None


class RetrieveResponse(BaseModel):
    docs: list[dict]
    path: str
    n: int
    retrieval_trace: dict | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "rag-api"}


@app.get("/config-check")
def config_check():
    """Diagnostic: whether BM25 postgres_url is configured (no secrets)."""
    mobius_root = Path(__file__).resolve().parents[2]
    config_path = mobius_root / "mobius-retriever" / "configs" / "path_b_v1.yaml"
    if not config_path.exists():
        config_path = mobius_root / "configs" / "path_b_v1.yaml"
    try:
        from mobius_retriever.config import load_path_b_config
        cfg = load_path_b_config(config_path)
        postgres_set = bool((cfg.postgres_url or "").strip())
        return {"bm25_postgres_url_set": postgres_set, "status": "ok"}
    except Exception as e:
        return {"bm25_postgres_url_set": False, "error": str(e), "status": "error"}


@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve(req: RetrieveRequest):
    """Retrieve docs: Mobius (BM25+vector → rerank → assemble) or lazy (vector top-k only)."""
    path = "mobius" if req.path == "mobius" else "lazy"
    mobius_root = Path(__file__).resolve().parents[2]
    config_path = mobius_root / "mobius-retriever" / "configs" / "path_b_v1.yaml"
    if not config_path.exists():
        config_path = mobius_root / "configs" / "path_b_v1.yaml"

    from mobius_retriever.pipeline import run_rag_pipeline

    trace: dict | None = {} if req.include_trace else None
    filter_overrides: dict[str, str] | None = None
    if req.filter_payer or req.filter_state or req.filter_program or req.filter_authority_level:
        filter_overrides = {}
        if req.filter_payer and req.filter_payer.strip():
            filter_overrides["filter_payer"] = req.filter_payer.strip()
        if req.filter_state and req.filter_state.strip():
            filter_overrides["filter_state"] = req.filter_state.strip()
        if req.filter_program and req.filter_program.strip():
            filter_overrides["filter_program"] = req.filter_program.strip()
        if req.filter_authority_level and req.filter_authority_level.strip():
            filter_overrides["filter_authority_level"] = req.filter_authority_level.strip()
    docs = run_rag_pipeline(
        question=req.question,
        path=path,
        config_path=str(config_path),
        top_k=req.top_k,
        apply_google_fallback=req.apply_google,
        google_search_url=os.environ.get("CHAT_SKILLS_GOOGLE_SEARCH_URL", "").strip() or None,
        emitter=None,
        n_factual=req.n_factual,
        n_hierarchical=req.n_hierarchical,
        trace=trace,
        filter_overrides=filter_overrides,
    )
    return RetrieveResponse(
        docs=docs,
        path=path,
        n=len(docs),
        retrieval_trace=trace if trace else None,
    )
