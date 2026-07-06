"""Central config. Independent by design — no imports from other Mobius modules."""
from __future__ import annotations

import os
from pathlib import Path

# --- paths ---
MODULE_ROOT = Path(__file__).resolve().parent.parent          # product-awareness/
REPO_ROOT = MODULE_ROOT.parent                                # Mobius/
DOCS_DIR = REPO_ROOT / "docs" / "product-docs"                # source manuals
CORPUS_DIR = MODULE_ROOT / "corpus"                           # chunks + built index live here
CHUNKS_DIR = CORPUS_DIR / "chunks"                            # <module>.jsonl (inspectable)
INDEX_DIR = CORPUS_DIR / "index"                              # built vectors (npz / chroma)

# --- store / collection ---
COLLECTION = os.environ.get("PRODUCT_DOCS_COLLECTION", "product_docs")
# Prod backend = pgvector on the existing Cloud SQL Postgres (durable, deployed, the
# platform's cutover target after the 2026-04-27 mobius-chroma VM outage). Its OWN table,
# so we own every column — no policy-corpus contamination, no shared-schema whitelist.
DATABASE_URL = os.environ.get("PRODUCT_DOCS_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
PG_TABLE = os.environ.get("PRODUCT_DOCS_TABLE", "product_docs_embeddings")

# --- embedding ---
# Prod embedder: Vertex AI gemini-embedding-001, pinned to 1536-dim — the platform's
# own embedder (mobius-rag / instant-rag), so no new dependency/credential. NOTE:
# gemini-embedding-001 returns 3072-dim by default; output_dimensionality=1536 is
# REQUIRED to match our vector(1536) column. Offline/dev+test: a local TF hashing
# embedder. Selected by PRODUCT_DOCS_EMBEDDER (auto|vertex|openai|local). Env falls
# back to the platform's EMBEDDING_MODEL / EMBEDDING_DIMENSIONS for consistency.
EMBED_MODEL = os.environ.get("PRODUCT_DOCS_EMBED_MODEL") or os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001")
EMBED_DIM = int(os.environ.get("PRODUCT_DOCS_EMBED_DIM") or os.environ.get("EMBEDDING_DIMENSIONS", "1536"))

# --- chunking ---
MAX_CHUNK_CHARS = int(os.environ.get("PRODUCT_DOCS_MAX_CHUNK_CHARS", "1600"))
EXCLUDE_SECTIONS = {"Doc-readiness notes"}   # author meta, not user content — never ingested

# --- gap-filing threshold: THE single source of truth (see contract) ---
# One constant governs BOTH "I can't answer" AND "fire a docs_gap" — they cannot drift,
# because there is only one value. Embedder-specific; calibrate two-sided on the real
# corpus. 0.35 is the OpenAI (cosine) start; the offline TF embedder uses TAU_GAP_TF.
TAU_GAP = float(os.environ.get("PRODUCT_HELP_TAU_GAP", "0.35"))
TAU_GAP_TF = float(os.environ.get("PRODUCT_HELP_TAU_GAP_TF", "0.12"))

# module slug + audience + scope, keyed by source filename (mirrors the contract slug map)
DOC_META: dict[str, dict] = {
    "mobius-chat.md":              {"module": "chat",            "audience": "user",  "in_scope": True},
    "rag-backend.md":              {"module": "rag",             "audience": "dev",   "in_scope": True},
    "lexicon.md":                  {"module": "lexicon",         "audience": "dev",   "in_scope": True},
    "skills.md":                   {"module": "skills",          "audience": "mixed", "in_scope": True},
    "story-ui-and-landing.md":     {"module": "strategy",        "audience": "mixed", "in_scope": True},
    "eval.md":                     {"module": "eval",            "audience": "dev",   "in_scope": True},
    "mobius-os.md":                {"module": "os",              "audience": "user",  "in_scope": False},
    "credentialing-and-roster.md": {"module": "credentialing",   "audience": "user",  "in_scope": False},
    "user-and-auth.md":            {"module": "auth",            "audience": "mixed", "in_scope": False},
    "mobius-document-viewer.md":   {"module": "document-viewer", "audience": "mixed", "in_scope": False},
    "infrastructure.md":           {"module": "infra",           "audience": "dev",   "in_scope": False},
}

# doc_type by section heading (falls back to "reference")
SECTION_DOC_TYPE: dict[str, str] = {
    "Purpose": "concept",
    "Audience": "concept",
    "Capabilities": "reference",
    "Navigation & Access": "how-to",
    "Key User Workflows": "how-to",
    "Integrations": "reference",
    "Not yet available (planned)": "reference",
}
