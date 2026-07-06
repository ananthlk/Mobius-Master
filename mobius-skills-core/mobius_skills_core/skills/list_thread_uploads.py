"""List uploads on a chat thread — pure formatter.

Takes a pre-fetched list of upload records and returns a human-readable
markdown table. **State-fetching is explicitly the consumer's job** —
this skill is about rendering, not about reaching into state storage.

Why the split
-------------
The two surfaces that wrap this skill source upload records differently:

* **mobius-chat** reads them from in-process thread state
  (``app.storage.threads.get_state(tid)["active"]["uploaded_files"]``).
* **mobius-skills-mcp** fetches them over HTTP from the chat's
  ``GET /chat/thread/{tid}/uploads`` endpoint.

If the formatter reached into state itself, the shared package would
have to import chat's storage module or ship an HTTP client — each
option couples it to one consumer. Passing the list in keeps the core
state-neutral and lets each consumer do its own fetch with its own
error handling.

Consumers
---------
* mobius-chat's builtin ``list_thread_document_uploads``.
* mobius-skills-mcp's ``list_chat_thread_uploads`` (renamed to
  ``list_thread_uploads`` in Day 3 for consistency).
"""
from __future__ import annotations

from typing import Any

from mobius_skills_core._types import (
    Emitter,
    SkillEvent,
    SkillResult,
    _safe_emit,
)

_STEP_ID = "list_thread_uploads"


# Default row cap for the table. Users rarely have more uploads than
# this; when they do, we truncate with an "_Showing X of Y_" footer.
_DEFAULT_ROW_CAP = 20


def run_list_thread_uploads(
    thread_id: str,
    uploaded_files: list[dict[str, Any]] | None = None,
    *,
    row_cap: int = _DEFAULT_ROW_CAP,
    emitter: Emitter | None = None,
) -> SkillResult:
    """Format a markdown table of uploads on a thread.

    Args:
        thread_id: The thread identifier. Empty / whitespace returns a
            "no thread yet" message rather than an error — matches the
            legacy UX where a fresh chat session hasn't persisted a
            thread id yet.
        uploaded_files: The pre-fetched upload records. Each dict is
            expected (but not required) to have ``purpose``, ``filename``,
            ``org_name``, ``row_count``, ``uploaded_at``. Missing fields
            render as ``—``. Invalid entries (non-dicts) are filtered
            out silently. Pass an empty list when the thread has no
            uploads; pass ``None`` when you haven't fetched yet (same
            visible result, different semantic in callers that want to
            distinguish "not fetched" vs "fetched, zero files").
        row_cap: Max rows before truncation. Default 20.
        emitter: Optional SkillEvent callback.

    Returns:
        SkillResult(text=<markdown table>, signal="no_sources").
        Always succeeds — this skill has no failure modes.
    """
    tid = (thread_id or "").strip()
    if not tid:
        _safe_emit(emitter, SkillEvent(
            signal="tool_completed", step_id=_STEP_ID,
            note="No thread yet — returned fresh-session message",
            data={"thread_id": ""},
            task_type="info", task_severity="low",
        ))
        return SkillResult(
            text=(
                "No chat thread is available yet. Send a message in "
                "Mobius Chat first, then ask what files are attached."
            ),
            signal="no_sources",
        )

    _safe_emit(emitter, SkillEvent(
        signal="tool_invoked", step_id=_STEP_ID,
        note=f"Listing uploads on thread {tid[:16]}…",
        data={"thread_id": tid},
        task_type="info", task_severity="low",
    ))

    files = [u for u in (uploaded_files or []) if isinstance(u, dict)]

    lines = [
        f"**Thread:** `{tid}`",
        f"**Uploads on file:** {len(files)} (newest listed first)",
        "",
    ]

    if not files:
        lines.append(
            "No documents uploaded yet. Use ⋯ → **Upload file**, "
            "or `POST /chat/roster-upload`."
        )
    else:
        lines.append("| # | Purpose | File | Organization | Rows | Uploaded (UTC) |")
        lines.append("|---|---------|------|--------------|------|----------------|")
        for i, u in enumerate(files[:row_cap], 1):
            purpose = str(u.get("purpose") or "—").replace("|", "/")
            filename = str(u.get("filename") or "—").replace("|", "/")
            org_name = str(u.get("org_name") or "—").replace("|", "/")
            rows = u.get("row_count") if u.get("row_count") is not None else "—"
            uploaded = str(u.get("uploaded_at") or "—").replace("|", "/")
            lines.append(
                f"| {i} | {purpose} | {filename} | {org_name} | "
                f"{rows} | {uploaded} |"
            )
        if len(files) > row_cap:
            lines.append(f"\n_Showing {row_cap} of {len(files)} uploads._")

    _safe_emit(emitter, SkillEvent(
        signal="tool_completed", step_id=_STEP_ID,
        note=f"Listed {len(files)} upload(s)",
        data={"thread_id": tid, "upload_count": len(files),
              "displayed": min(len(files), row_cap)},
        task_type="info", task_severity="low",
    ))

    return SkillResult(
        text="\n".join(lines),
        signal="no_sources",
        extra={"upload_count": len(files), "thread_id": tid},
    )
