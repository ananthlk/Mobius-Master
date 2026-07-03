"""product_help_search — the chat-invocable skill (the integration seam).

Runs a search; on a gap outcome (docs_gap or feature_request) files the signal
POST-ANSWER and best-effort (never blocks or breaks the answer). Returns an
envelope dict that a thin chat adapter maps onto the chat ``SkillEnvelope``.

Registration into mobius-chat (wiring step, done chat-side):
  1. a ``SkillSpec(name="product_help_search", ...)`` in app/skills/builtin/
     whose handler calls ``run(...)`` below and adapts the dict to a SkillEnvelope;
  2. add ``_registry_block("product_help_search")`` to tool_manifest.py
     (the hand-list gotcha — a skill is invisible to the planner otherwise);
  3. no new LLM stage needed — retrieval only.
"""
from __future__ import annotations

from . import gapwriter
from .search import ProductHelp

SKILL_NAME = "product_help_search"
SKILL_DESCRIPTION = (
    "Answer questions about how to use Mobius itself — features, setup, navigation, "
    "'how do I…' and 'where is…' questions about the product (chat, RAG, lexicon, "
    "skills, strategy). Grounded in the product documentation. Use this when the user "
    "asks about the product rather than about healthcare policy or their data."
)

_engine: ProductHelp | None = None


def _get_engine() -> ProductHelp:
    global _engine
    if _engine is None:
        _engine = ProductHelp()
    return _engine


def run(query: str, *, k: int = 6, audience: str | None = None, module: str | None = None,
        in_scope_only: bool = False, user_id: str = "", thread_id: str | None = None,
        correlation_id: str | None = None) -> dict:
    """Handler. Returns an envelope dict: {text, sources, signal, extra}."""
    result = _get_engine().search(query, k=k, audience=audience, module=module,
                                  in_scope_only=in_scope_only)

    # answer first; THEN file the gap (post-answer, best-effort) — the invariant.
    feedback_id = None
    if result.gap is not None:
        feedback_id = gapwriter.file_gap(
            result.gap, user_id=user_id, thread_id=thread_id, correlation_id=correlation_id)

    signal = "corpus_only" if result.outcome == "answer" else "no_sources"
    return {
        "text": result.text,
        "sources": result.sources,
        "signal": signal,
        "extra": {
            "outcome": result.outcome,
            "s_top": round(result.s_top, 4),
            "tau_gap": result.tau_gap,
            "module": result.module,
            "feedback_id": feedback_id,
        },
    }
