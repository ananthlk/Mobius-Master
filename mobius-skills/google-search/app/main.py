"""FastAPI app: GET /search?q=..., GET /health. Chat doc assembly uses CHAT_SKILLS_GOOGLE_SEARCH_URL pointing here."""
import logging

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.services.search import search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mobius Google Search", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    """Health check."""
    return {"ok": True, "service": "mobius-google-search"}


@app.get("/search")
def search_endpoint(q: str = Query(..., description="Search query"), num: int = Query(5, ge=1, le=10)):
    """
    Web search. Returns JSON: {"items": [{"title": str, "snippet": str, "url": str}, ...]}.
    Chat doc assembly expects this shape (items or results).
    """
    results = search(q, max_results=num)
    # Chat doc_assembly accepts "items" or "results"; we use "items" to match Google CSE format
    return {"items": results, "results": results}
