"""Lazy corpus search — vector-only retrieval over the approved corpus.

The 3rd retrieval skill in the 2×2 framework:

+----------------------+------------------------+-------------------------+
|                      | **Heavyweight**        | **Lazy (this skill)**   |
|                      | (accuracy-first)       | (capture-first)         |
+----------------------+------------------------+-------------------------+
| Approved corpus      | corpus_search          | lazy_corpus_search      |
| (published, tagged)  | (Day 4)                | (Day 5 — this)          |
+----------------------+------------------------+-------------------------+
| Thread uploads       | — (N/A, small set)     | thread_corpus_search    |
| (ephemeral)          |                        | (Day 5)                 |
+----------------------+------------------------+-------------------------+

Use when the caller wants a fast, broad scan of the approved corpus
— quick copilot-mode questions, agentic first-pass exploration before
committing to a heavier retrieval round. Higher default ``k`` than the
heavyweight path (default 16 vs. 10) because the goal is recall, not
precision. No BM25 stage, no tag-match rerank, no confidence filter,
no sibling-paragraph expansion — just embed → vector search → return.

``corpus_search`` remains the right tool when citations matter and
precision is worth paying for. ``lazy_corpus_search`` is the right
tool when broad coverage is worth more than careful scoring.

How the filter works
--------------------
The approved corpus writes ``instant_rag=FALSE`` to Postgres and
typically omits the key (or writes ``"false"``) in Chroma metadata.
User-uploaded chunks write ``instant_rag="true"``. To scope to
"approved only", we filter out ``instant_rag="true"``:

    {"instant_rag": {"$ne": "true"}}

Plus any metadata filters the caller supplies (payer / state /
program / authority_level / source_type_allow) — same shape as the
heavy ``corpus_search`` so callers can swap skills without rebuilding
filter shapes.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from mobius_skills_core._types import (
    Emitter,
    SkillResult,
)
from mobius_skills_core.skills.corpus_search import (
    ChromaConfig,
    CorpusFilters,
)
from mobius_skills_core.skills.lazy_rag import run_lazy_rag

logger = logging.getLogger(__name__)

_STEP_ID = "lazy_corpus_search"
_DEFAULT_K_LAZY = 16  # recall > precision


def run_lazy_corpus_search(
    query: str,
    *,
    embed_query: Callable[[str], list[float]],
    chroma: ChromaConfig,
    filters: CorpusFilters | None = None,
    k: int = _DEFAULT_K_LAZY,
    include_uploads: bool = False,
    emitter: Emitter | None = None,
) -> SkillResult:
    """Fast vector search over the approved corpus.

    Args:
        query: Natural-language query.
        embed_query: Caller's embedding provider.
        chroma: Chroma backend configuration.
        filters: ``CorpusFilters`` — same shape ``corpus_search`` uses
            (payer / state / program / authority_level /
            source_type_allow). All filters AND-ed together.
        k: Max chunks to return. Default 16 (vs. 10 in the heavy
            ``corpus_search``) because this skill is recall-oriented.
        include_uploads: When False (default), excludes user-uploaded
            chunks via ``instant_rag != "true"`` — the skill searches
            the approved corpus only. When True, searches both
            approved corpus and uploads (useful when the caller wants
            capture across everything indexed). Default False matches
            the skill's name/intent.
        emitter: SkillEvent callback.

    Returns:
        SkillResult with chunks/sources from the approved corpus.
        ``authority="corpus"`` on each SourceRef (integrator treats
        these as vetted content).
    """
    # Build the Chroma ``where`` filter. Start with the caller's
    # metadata filters, then add the instant_rag exclusion unless the
    # caller explicitly opted in.
    effective = filters or CorpusFilters()
    conditions: list[dict[str, Any]] = []

    if effective.payer:
        conditions.append({"document_payer": effective.payer})
    if effective.state:
        conditions.append({"document_state": effective.state})
    if effective.program:
        conditions.append({"document_program": effective.program})
    if effective.authority_level:
        conditions.append({"document_authority_level": effective.authority_level})
    if effective.source_type_allow:
        conditions.append({"source_type": {"$in": list(effective.source_type_allow)}})

    if not include_uploads:
        # Exclude user-uploaded chunks. Chroma metadata stores
        # instant_rag as a string ("true"/"false") or omits it — the
        # $ne operator correctly matches both (missing key != "true").
        conditions.append({"instant_rag": {"$ne": "true"}})

    where: dict[str, Any] | None
    if not conditions:
        where = None
    elif len(conditions) == 1:
        where = conditions[0]
    else:
        where = {"$and": conditions}

    return run_lazy_rag(
        query=query,
        embed_query=embed_query,
        chroma=chroma,
        k=k,
        where=where,
        default_document_name="document",
        step_id=_STEP_ID,
        emitter=emitter,
    )
