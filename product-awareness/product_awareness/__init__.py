"""product-awareness — an independent, ownable module.

Its own corpus (`product_docs`), its own embedder, its own vector store. Nothing
here imports another Mobius module's internals; the only cross-module touch is the
best-effort docs_gap write in ``gapwriter`` (chat-side, guarded and optional). See
``docs/product-awareness-feedback-contract.md`` for the seam.
"""

__all__ = ["config", "chunker", "embedder", "store", "ingest", "search"]
