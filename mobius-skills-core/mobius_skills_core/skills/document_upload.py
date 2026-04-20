"""Document-upload info skill — returns the "how to attach files" markdown.

This is the simplest skill in the package. It takes no inputs, makes no
network calls, hits no DB. Every call returns the same canned markdown
explaining how a user attaches a file to a chat thread and what the
downstream retrieval flow looks like.

Why it exists as a skill at all
-------------------------------
It lets the planner route "how do I upload a file?" questions through
the same dispatcher as everything else. Before this pattern, the chat
had keyword triggers ("how do I upload", "attach a file", etc.) hard-
coded into the planner prompt. With this skill registered, the planner
picks it explicitly and the user gets a consistent response shape —
same SourceRef, same signal taxonomy, same task-manager emit trail.

Consumers
---------
* mobius-chat's builtin ``document_upload_skill`` wraps this for the
  chat's ReAct loop.
* mobius-skills-mcp exposes this for external MCP clients (e.g. Claude
  Desktop asking "how do I attach a file to Mobius Chat?").

Both surfaces return the same markdown. The content is versioned in
this module so updates (new file types, new purposes, new endpoints)
land in exactly one place.
"""
from __future__ import annotations

from mobius_skills_core._types import (
    Emitter,
    SkillEvent,
    SkillResult,
    _safe_emit,
)

_STEP_ID = "document_upload"


# ── Canonical upload markdown ──
#
# Reflects the 2026-04-18 disconnect: roster_reconciliation is retired,
# instant_rag is the only active purpose, and the full credentialing /
# roster workflow is being rebuilt as a standalone skill set. When those
# ship, this markdown gains a second "purposes" bullet — not a new
# version of the skill.
DOCUMENT_UPLOAD_MARKDOWN = """\
## Document upload skill (Mobius Chat)

**What it does:** Attach files to **this chat thread** so other tools can search them. Each upload is chunked + embedded once; afterwards you can ask natural-language questions and the `search_uploaded_document` skill retrieves the relevant passages with page citations. You can upload **multiple documents at different times**; each is stored on the thread with a timestamp and filename.

**End user:** Tap **⋯** next to Send → **Upload file** → pick a **PDF, DOCX, CSV, or XLSX**. The upload runs instant-RAG in the background; a receipt banner confirms when indexing is complete.

**Supported purpose:**
- `instant_rag` — the default. Chunks + embeds the document so `search_uploaded_document` can search inside it.

**HTTP API (integrations / MCP):**
- `POST /chat/roster-upload` — multipart form: `file`, `org_name`, `file_purpose="instant_rag"`, `thread_id` (optional; response returns the thread_id used).
- `GET /chat/thread/{thread_id}/uploads` — list uploads on the thread (newest first), each with filename, purpose, row/chunk count, and timestamp.

**Note:** File bytes cannot be sent inside plain chat text; use the UI button or multipart POST. `file_purpose` values other than `instant_rag` return 400 today — roster / credentialing uploads will come back as their own skill integration.

**Next step:** After uploading, ask a question about the document (e.g. *"what does section 3.2 say about prior auth?"*). Chat will pick `search_uploaded_document` and return scoped chunks with page citations — no separate search command needed.
"""


def run_document_upload_info(
    *,
    emitter: Emitter | None = None,
) -> SkillResult:
    """Return the canonical upload-instructions markdown.

    No inputs, no network, no errors. The only two outcomes are: skill
    registry rejects the call (empty caller, etc.) — which never reaches
    this function because the handler signature has no required args —
    or the markdown is returned.

    Args:
        emitter: Optional SkillEvent callback. Fires ``tool_invoked``
            and ``tool_completed`` so consumers that promote events to
            task-manager log the call for analytics. Both are tagged
            ``task_type="info"`` / ``severity="low"``.

    Returns:
        SkillResult(text=DOCUMENT_UPLOAD_MARKDOWN, signal="no_sources")
    """
    _safe_emit(emitter, SkillEvent(
        signal="tool_invoked", step_id=_STEP_ID,
        note="User asked how to upload a document",
        data={},
        task_type="info", task_severity="low",
    ))
    _safe_emit(emitter, SkillEvent(
        signal="tool_completed", step_id=_STEP_ID,
        note="Returned upload instructions",
        data={"markdown_length": len(DOCUMENT_UPLOAD_MARKDOWN)},
        task_type="info", task_severity="low",
    ))
    return SkillResult(
        text=DOCUMENT_UPLOAD_MARKDOWN,
        signal="no_sources",
    )
