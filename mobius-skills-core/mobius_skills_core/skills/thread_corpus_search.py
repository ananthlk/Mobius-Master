"""Thread corpus search — lazy retrieval over a single user-uploaded doc.

Wraps ``run_lazy_rag`` with a filter scoped to exactly one uploaded
document on a chat thread. This is the "search inside this PDF I just
attached" skill.

When a user uploads a file to a chat thread, mobius-rag's ``/upload``
endpoint chunks + embeds it and writes the
chunks to the same Chroma collection the approved corpus uses, tagged
with ``instant_rag="true"`` + ``document_id=<upload id>``. This skill
queries Chroma with that exact filter so it only returns chunks from
the one uploaded document.

Replaces ``mobius-chat.app.services.instant_rag_search.lazy_rag_search``
(Day 5, 2026-04-20). The old function becomes a thin adapter that
delegates here + translates the return shape.
"""
from __future__ import annotations

import logging

from mobius_skills_core._types import (
    Emitter,
    SkillEvent,
    SkillResult,
    _safe_emit,
)
from mobius_skills_core.skills.corpus_search import ChromaConfig
from mobius_skills_core.skills.lazy_rag import run_lazy_rag

logger = logging.getLogger(__name__)

_STEP_ID = "thread_corpus_search"


def run_thread_corpus_search(
    document_id: str,
    question: str,
    *,
    embed_query,
    chroma: ChromaConfig,
    k: int = 8,
    emitter: Emitter | None = None,
) -> SkillResult:
    """Search a single user-uploaded document on the thread.

    Args:
        document_id: The upload's document_id. Empty → no_sources with
            a "missing id" note. (Not tool_error — empty id is a
            reasonable caller mistake worth logging, not a blocker.)
        question: The natural-language question.
        embed_query: Caller's embedding provider.
        chroma: Chroma backend configuration.
        k: Max chunks to return. Default 8 — these documents are small
            (≤100 chunks typical) so 8 is usually plenty.
        emitter: SkillEvent callback.

    Returns:
        SkillResult with chunks/sources from the one uploaded document.
        ``authority="user-asserted"`` on each SourceRef so downstream
        integrators know to hedge confidence (user-uploaded docs are
        not vetted).
    """
    tid = (document_id or "").strip()
    if not tid:
        _safe_emit(emitter, SkillEvent(
            signal="no_sources", step_id=_STEP_ID,
            note="document_id is required for thread_corpus_search",
            data={"reason": "empty_document_id"},
            task_type="info", task_severity="low",
        ))
        return SkillResult(
            text="",
            signal="no_sources",
            extra={"reason": "empty_document_id"},
        )

    # Scope strictly to this upload. The instant_rag="true" belt is
    # redundant given document_id but catches corruption where a chunk
    # was mis-tagged during ingest.
    where = {
        "$and": [
            {"document_id": tid},
            {"instant_rag": "true"},
        ]
    }

    return run_lazy_rag(
        query=question,
        embed_query=embed_query,
        chroma=chroma,
        k=k,
        where=where,
        default_document_name="Uploaded document",
        step_id=_STEP_ID,
        emitter=emitter,
    )
