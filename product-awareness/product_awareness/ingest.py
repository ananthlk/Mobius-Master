"""Ingest: manuals → chunks (JSONL in corpus/chunks/) → embeddings → vector store.

Fearlessly rebuildable: ``ingest(reset=True)`` wipes and rebuilds the whole corpus.
That safety is the point of the module owning its own DB (see design notes)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import config, embedder as embedder_mod, store as store_mod
from .chunker import Chunk, chunk_file


def _source_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(config.REPO_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "uncommitted"
    except Exception:
        return "uncommitted"


def build_chunks(scope: str = "all") -> list[Chunk]:
    """Chunk every known manual and write one JSONL per module to corpus/chunks/."""
    commit = _source_commit()
    config.CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    all_chunks: list[Chunk] = []
    for path in sorted(config.DOCS_DIR.glob("*.md")):
        chunks = chunk_file(path, source_commit=commit)
        if not chunks:
            continue
        module = chunks[0].module
        out_path = config.CHUNKS_DIR / f"{module}.jsonl"
        with out_path.open("w") as f:
            for c in chunks:
                f.write(json.dumps(c.to_dict()) + "\n")
        all_chunks.extend(chunks)
    if scope == "in":
        all_chunks = [c for c in all_chunks if c.in_scope]
    return all_chunks


def ingest_from_chunks(scope: str = "all", reset: bool = True) -> dict:
    """Embed pre-chunked JSONL (corpus/chunks/*.jsonl) into the store — no source
    manuals needed. Chunking is done offline + committed; this is what runs in-cloud
    (the image ships corpus/chunks, not docs/product-docs)."""
    metas: list[dict] = []
    for jf in sorted(config.CHUNKS_DIR.glob("*.jsonl")):
        for line in jf.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if scope == "in" and not rec.get("in_scope"):
                continue
            metas.append(rec)
    emb = embedder_mod.get_embedder()
    store = store_mod.get_store()
    if reset:
        store.reset()
    if metas:
        vectors = emb.embed([m["text"] for m in metas])
        store.add(
            ids=[m["chunk_id"] for m in metas],
            vectors=vectors,
            metadatas=[{k: v for k, v in m.items() if k != "text"} for m in metas],
            documents=[m["text"] for m in metas],
        )
    return {"chunks": len(metas), "modules": sorted({m["module"] for m in metas}),
            "planned_chunks": sum(1 for m in metas if m.get("status") == "planned"),
            "embedder": emb.name, "store": store.name, "scope": scope,
            "source": "chunks-jsonl"}


def ingest(scope: str = "all", reset: bool = True) -> dict:
    """Full pipeline: chunk → embed → write to the vector store. Returns a summary."""
    chunks = build_chunks(scope=scope)
    emb = embedder_mod.get_embedder()
    store = store_mod.get_store()
    if reset:
        store.reset()
    if chunks:
        vectors = emb.embed([c.text for c in chunks])
        store.add(
            ids=[c.chunk_id for c in chunks],
            vectors=vectors,
            metadatas=[{k: v for k, v in c.to_dict().items() if k != "text"} for c in chunks],
            documents=[c.text for c in chunks],
        )
    modules = sorted({c.module for c in chunks})
    return {
        "chunks": len(chunks),
        "modules": modules,
        "planned_chunks": sum(1 for c in chunks if c.status == "planned"),
        "embedder": emb.name,
        "store": store.name,
        "scope": scope,
        "chunks_dir": str(config.CHUNKS_DIR),
        "index_dir": str(config.INDEX_DIR),
    }
