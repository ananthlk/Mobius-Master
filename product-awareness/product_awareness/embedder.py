"""Pluggable embedder.

Prod: Vertex AI ``gemini-embedding-001`` pinned to 1536-dim — the platform's own
embedder (mobius-rag / instant-rag), so no new dependency or credential. Offline/dev+test:
a deterministic local TF-hashing embedder (numpy only) that preserves lexical similarity,
so the whole pipeline runs and the retrieval + τ_gap logic is testable without creds.
(OpenAI ``text-embedding-3-small`` is kept as an optional alternative.)

Selection (``PRODUCT_DOCS_EMBEDDER``): ``auto`` (default) → Vertex if VERTEX_PROJECT_ID
+ google-genai are present, else local; ``vertex`` / ``openai`` / ``local`` force one.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Protocol

import numpy as np

from . import config

_TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    dim: int
    name: str

    def embed(self, texts: list[str]) -> np.ndarray: ...


def _stable_bucket(token: str, dim: int) -> int:
    """Process-stable hash. Python's builtin hash() is salted per process, which would
    put ingest and query tokens in different buckets across runs — md5 avoids that."""
    return int.from_bytes(hashlib.md5(token.encode("utf-8")).digest()[:4], "little") % dim


class HashingTfEmbedder:
    """Local, deterministic, offline. Hashes tokens into ``dim`` buckets, tf-weighted,
    L2-normalized. NOT the production model — a faithful stand-in that keeps lexical
    similarity so retrieval + the τ_gap disambiguation can be exercised without creds."""

    def __init__(self, dim: int = config.EMBED_DIM):
        self.dim = dim
        self.name = "local-tf-hash"

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for tok in _TOKEN.findall(text.lower()):
                out[row, _stable_bucket(tok, self.dim)] += 1.0
            norm = float(np.linalg.norm(out[row]))
            if norm:
                out[row] /= norm
        return out


class OpenAIEmbedder:
    """Production embedder. 1536-dim, matches the platform query path."""

    def __init__(self, model: str | None = None, dim: int | None = None):
        import openai  # lazy — only imported when actually selected

        self._client = openai.OpenAI()
        self.model = model or config.EMBED_MODEL
        self.dim = dim or config.EMBED_DIM
        self.name = self.model

    def embed(self, texts: list[str]) -> np.ndarray:
        resp = self._client.embeddings.create(model=self.model, input=texts)
        return np.array([d.embedding for d in resp.data], dtype=np.float32)


class VertexEmbedder:
    """Production embedder — Vertex AI ``gemini-embedding-001`` via google-genai.

    Mirrors the platform's embedder (mobius-skills/instant-rag). gemini-embedding-001
    returns 3072-dim by default, so ``output_dimensionality`` is pinned to 1536 to match
    our ``vector(1536)`` column — without it, writes/queries dim-mismatch.
    """

    def __init__(self, model: str | None = None, dim: int | None = None):
        from google import genai  # lazy — only when selected
        from google.genai import types

        project = os.environ.get("VERTEX_PROJECT_ID")
        if not project:
            raise RuntimeError("VertexEmbedder: VERTEX_PROJECT_ID required")
        location = os.environ.get("VERTEX_LOCATION", "us-central1")
        self._types = types
        self.model = model or config.EMBED_MODEL      # gemini-embedding-001
        self.dim = dim or config.EMBED_DIM            # 1536
        self.name = self.model
        self._client = genai.Client(vertexai=True, project=project, location=location)

    def embed(self, texts: list[str]) -> np.ndarray:
        out: list[list[float]] = []
        for i in range(0, len(texts), 50):
            batch = texts[i:i + 50]
            res = self._client.models.embed_content(
                model=self.model,
                contents=batch,
                config=self._types.EmbedContentConfig(output_dimensionality=self.dim),
            )
            out.extend(e.values for e in res.embeddings)
        return np.array(out, dtype=np.float32)


def get_embedder() -> Embedder:
    choice = os.environ.get("PRODUCT_DOCS_EMBEDDER", "auto").lower()
    if choice == "vertex":
        return VertexEmbedder()
    if choice == "openai":
        return OpenAIEmbedder()
    if choice == "local":
        return HashingTfEmbedder(config.EMBED_DIM)
    # auto: prefer the platform's Vertex embedder, else fall back to the local TF hasher
    if os.environ.get("VERTEX_PROJECT_ID"):
        try:
            import google.genai  # noqa: F401

            return VertexEmbedder()
        except Exception:
            pass
    return HashingTfEmbedder(config.EMBED_DIM)


def tau_gap_for(embedder: Embedder) -> float:
    """The single answerability/gap threshold — embedder-specific (see contract)."""
    return config.TAU_GAP_TF if embedder.name == "local-tf-hash" else config.TAU_GAP
