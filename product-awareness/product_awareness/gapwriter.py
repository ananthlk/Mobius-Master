"""The seam to the feedback agent — best-effort docs_gap / feature_request write.

Per the contract's load-bearing invariant: filing a gap MUST NEVER break the answer
path. Everything here is wrapped; a failure degrades to a log and returns None. When
running standalone (not on the chat import path) there is no DB, so it just logs.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("product_awareness.gapwriter")


def file_gap(gap: dict, *, user_id: str = "", thread_id: str | None = None,
             correlation_id: str | None = None) -> str | None:
    """gap = {category, module, verbatim, summary}. Returns feedback_id or None."""
    if not gap:
        return None
    try:
        # chat-side storage; only importable when running inside mobius-chat
        from app.storage import product_feedback as store  # type: ignore
    except Exception:
        logger.info("gap (standalone, not persisted): [%s/%s] %s",
                    gap.get("category"), gap.get("module"), gap.get("verbatim"))
        return None

    try:
        return store.insert_open_feedback(
            trigger="auto_harvest",   # machine-harvested gap, not user-voiced feedback (contract)
            category=gap["category"],
            area_tags=[gap["module"]],
            verbatim=gap["verbatim"],
            summary=gap.get("summary", ""),
            routed_to=store.route_for(gap["category"]),
            user_id=user_id,
            thread_id=thread_id,
            correlation_id=correlation_id,
        )
    except Exception:
        logger.warning("docs_gap logging failed — continuing", exc_info=True)
        return None
