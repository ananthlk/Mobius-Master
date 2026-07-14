"""product_help_search — retrieve over the product_docs corpus and classify the outcome.

The single-threshold invariant (see contract): ONE constant, ``τ_gap``, decides both
"I can't answer" and "fire a gap". Three outcomes, read off the reality-gate:

    s_top < τ_gap                      -> docs_gap        ("no docs yet")
    s_top >= τ_gap and status=planned  -> feature_request ("planned, not available")
    s_top >= τ_gap and status=current  -> answer
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import embedder as embedder_mod, store as store_mod


@dataclass
class SearchResult:
    outcome: str                     # answer | docs_gap | feature_request
    query: str
    s_top: float
    tau_gap: float
    text: str                        # user-facing answer / message
    module: str                      # best module (for the answer, or the gap area_tag)
    sources: list[dict] = field(default_factory=list)
    gap: dict | None = None          # payload for gapwriter when a gap should be filed
    demo: dict | None = None         # {script_id, title} — mobius-interact "Show me" ref
    recital: dict | None = None      # {verbatim, section, document_id} — quote as written

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome, "query": self.query, "s_top": round(self.s_top, 4),
            "tau_gap": self.tau_gap, "module": self.module, "text": self.text,
            "sources": self.sources, "gap": self.gap, "demo": self.demo,
            "recital": self.recital,
        }


def _section_text(module: str, section: str) -> str | None:
    """Reconstruct one section's verbatim text, in order, from the chunks file.

    Chunk text is ``# {title} — {heading}\\n\\n{piece}``; the heading prefix is
    stripped so the payload is pure quotable prose."""
    import json as _json

    from . import config as _cfg

    path = _cfg.CHUNKS_DIR / f"{module}.jsonl"
    if not path.exists():
        return None
    pieces = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = _json.loads(line)
        if rec.get("section") == section:
            t = rec.get("text", "")
            pieces.append(t.split("\n\n", 1)[1] if "\n\n" in t else t)
    return "\n\n".join(pieces) if pieces else None


class ProductHelp:
    """Holds the embedder + store so they load once. Call ``search`` per query."""

    def __init__(self):
        self.embedder = embedder_mod.get_embedder()
        self.store = store_mod.get_store()
        self.tau_gap = embedder_mod.tau_gap_for(self.embedder)

    def _where(self, audience, module, in_scope_only) -> dict | None:
        w: dict = {}
        if audience:
            w["audience"] = audience
        if module:
            w["module"] = module
        if in_scope_only:
            w["in_scope"] = True
        return w or None

    def search(self, query: str, k: int = 6, audience: str | None = None,
               module: str | None = None, in_scope_only: bool = False) -> SearchResult:
        query = (query or "").strip()
        where = self._where(audience, module, in_scope_only)
        hits = self.store.query(self.embedder.embed([query])[0], k=k, where=where)
        s_top = hits[0]["score"] if hits else 0.0

        # --- MISS: nothing relevant -> docs_gap ---
        if not hits or s_top < self.tau_gap:
            # On a true miss we don't reliably know the intended module — a below-threshold
            # chunk's module is a bad guess that pollutes the backlog ranking (e.g. odd
            # "operations_suite" buckets). Attribute to the explicit filter if the caller
            # set one, else "unknown" — the verbatim is what a human triages anyway.
            guess = module or "unknown"
            return SearchResult(
                outcome="docs_gap", query=query, s_top=s_top, tau_gap=self.tau_gap,
                module=guess, text="I don't have documentation on that yet.",
                sources=[],
                gap={"category": "docs_gap", "module": guess, "verbatim": query,
                     "summary": f"no doc for: {query[:80]}"},
            )

        top = hits[0]
        top_module = top["metadata"]["module"]

        # --- PLANNED HIT: retrieval succeeded on a "not yet available" section ---
        if top["metadata"].get("status") == "planned":
            return SearchResult(
                outcome="feature_request", query=query, s_top=s_top, tau_gap=self.tau_gap,
                module=top_module,
                text=(f"That's planned but not available yet — see the "
                      f"\"{top['metadata']['section']}\" section of the {top_module} docs."),
                sources=self._sources(hits),
                gap={"category": "feature_request", "module": top_module, "verbatim": query,
                     "summary": f"asked for planned capability: {query[:80]}"},
            )

        # --- ANSWER: current docs above threshold ---
        current = [h for h in hits if h["metadata"].get("status") != "planned"]
        from . import config as _cfg  # local import keeps module load light
        import re as _re
        demo = None
        for mod, pat, ref in _cfg.DEMO_KEYWORDS:   # keyword overrides first (collisions)
            if mod == top_module and _re.search(pat, query, _re.IGNORECASE):
                demo = ref
                break
        if demo is None:
            demo = _cfg.DEMOS.get((top_module, top["metadata"].get("section", "")))
        # verbatim/recital sections: tell the consumer NOT to resummarize —
        # quote the text as written (and offer the full doc via the reader).
        recital = None
        top_section = top["metadata"].get("section", "")
        if (top_module, top_section) in _cfg.VERBATIM_SECTIONS:
            recital = {"verbatim": True, "section": top_section,
                       "document_id": f"product-docs:{top_module}"}
        # Recital payloads carry ONLY the matched section, reconstructed in order
        # from the chunks file — not the top-k score mixture (which can splice
        # several verbatim sections into one blob; UX finding 2026-07-13).
        if recital:
            text = _section_text(top_module, top_section) or top["document"]
        else:
            text = "\n\n---\n\n".join(h["document"] for h in current[:3])
        return SearchResult(
            outcome="answer", query=query, s_top=s_top, tau_gap=self.tau_gap,
            module=top_module,
            text=text,
            sources=self._sources(current),
            gap=None,
            demo=demo,
            recital=recital,
        )

    @staticmethod
    def _sources(hits: list[dict]) -> list[dict]:
        return [{
            "chunk_id": h["id"],
            "module": h["metadata"]["module"],
            "section": h["metadata"]["section"],
            "doc_type": h["metadata"].get("doc_type"),
            "source_path": h["metadata"].get("source_path"),
            "score": round(h["score"], 4),
        } for h in hits]
