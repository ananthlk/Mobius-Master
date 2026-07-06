"""Shared data types for mobius-skills-core.

Kept deliberately small. Skills return these primitive shapes; consumer
adapters (chat's SkillEnvelope, MCP's text block) translate as needed.
Keeping the core shapes minimal avoids coupling this package to
consumer-specific concepts (MCP protocol formatters, chat's emit
envelope, etc.).

Design principles:

* **Flat dataclasses** — no inheritance, no protocols. Easy to serialize
  and inspect.
* **Every field has a default** — skills that don't produce a field leave
  it empty; consumers don't have to care which fields exist.
* **No datetime objects** — timestamps are ISO strings. Avoids timezone
  drift when handing off across process boundaries.
* **No JSON serialization in the skill** — return the dataclass;
  consumers choose their own encoding.

Emissions + task signals
------------------------
Skills are observable: they call an optional ``emitter`` callback at
natural boundaries (invoked / progress / completed / error). Each call
passes a ``SkillEvent`` — a minimal structured shape that any consumer
can enrich for its own surface:

* mobius-chat's adapter upgrades SkillEvent → EmitEnvelope (adding
  correlation_id, thread_id, user_id, timestamp_ms, source_module) and
  routes to the task-manager promotion writer based on
  ``task_type`` / ``task_severity``.
* mobius-skills-mcp's adapter either discards events (MCP tool results
  are single-shot returns) or forwards via MCP server-sent notifications
  when the client session supports them.
* Future consumers choose their own translation.

The skill itself never imports consumer-specific code, and never makes
assumptions about whether the event will be displayed, logged,
promoted, or ignored.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SourceRef:
    """One citation source returned by a skill.

    Fields mirror what downstream integrators already know how to cite.
    ``document_name`` is the only required-in-practice field — the rest
    depend on source type (web pages have url, RAG chunks have page
    numbers, etc.).
    """

    document_name: str = ""
    document_id: str | None = None
    source_type: str = ""           # "web" | "corpus" | "upload" | "external"
    url: str | None = None
    page_number: int | None = None
    index: int = 0                  # 1-based ordinal within this result set
    text: str = ""                  # short preview (≤300 chars typical)
    authority: str | None = None    # "high" | "user-asserted" | "external"
    confidence_label: str | None = None  # legacy RAG label (process_confident, ...)


@dataclass
class ChunkRef:
    """A retrieval chunk — richer than SourceRef, used by RAG skills.

    SourceRef is the citation shape; ChunkRef is the pre-citation
    retrieval result. Retrieval skills return ChunkRef[]; consumers
    flatten to SourceRef[] for display.
    """

    text: str = ""
    score: float = 0.0
    document_id: str = ""
    document_name: str = ""
    page_number: int | None = None
    chunk_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillUsage:
    """Per-call usage telemetry returned by a skill.

    Skills that don't call an LLM still return this (with zeros) so
    consumers can attribute time + cost consistently. ``model`` is the
    identifier the call actually used (post-fallback, post-routing), not
    the planner's requested model.
    """

    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    is_fallback: bool = False       # True when provider routing fell back to an alt model


@dataclass
class SkillResult:
    """The shape every skill returns.

    Consumers (chat's builtin adapter, MCP adapter) translate this to
    their surface format.

    ``signal`` is a short string the consumer can switch on for behavior
    (e.g. "no_sources" → show empty state; "google_only" → display the
    web-sources disclaimer). Keep the taxonomy small and consumer-
    neutral — "ok" / "no_sources" / "tool_error" covers most cases.
    """

    text: str = ""                                  # primary payload (synthesis-free raw text is fine)
    sources: list[SourceRef] = field(default_factory=list)
    chunks: list[ChunkRef] = field(default_factory=list)  # retrieval-skill only; empty otherwise
    usage: SkillUsage | None = None
    signal: str = "ok"                              # "ok" | "no_sources" | "tool_error" | skill-specific
    extra: dict[str, Any] = field(default_factory=dict)   # escape hatch for consumer-specific payload

    def is_error(self) -> bool:
        return self.signal == "tool_error"

    def has_content(self) -> bool:
        return bool(self.text or self.sources or self.chunks)


# ── Emissions + task signals ──────────────────────────────────────────


@dataclass
class SkillEvent:
    """A structured event emitted by a skill at natural boundaries.

    Skills call ``emitter(SkillEvent(...))`` when invoked, while making
    progress, on completion, and on failure. The shape is deliberately
    minimal — consumer adapters enrich it (chat adds correlation_id +
    thread_id + user_id + timestamp; MCP may forward as a notification;
    others may ignore entirely).

    Fields:

    * ``signal`` — short string the consumer switches on. Standard values:
      ``"tool_invoked"``, ``"tool_progress"``, ``"tool_completed"``,
      ``"no_sources"``, ``"tool_error"``. Skills can define their own
      skill-specific signals on top.
    * ``step_id`` — stable identifier for the step (``"google_search"``,
      ``"web_scrape.quick"``, ``"corpus_search.rerank"``). Consumers
      correlate progress/completed pairs by step_id.
    * ``note`` — human-readable line. UI consumers display this directly.
    * ``data`` — structured payload (query, url, result_count, error
      code, etc). Consumers that only want the note ignore this.
    * ``task_type`` — suggestion to the consumer: should this be promoted
      to a task-manager task? ``"info"`` / ``"insight"`` / ``"blocker"`` /
      ``"failure"``. ``None`` means "don't promote — this is chat-side
      chatter only". Consumers are not obligated to honor this.
    * ``task_severity`` — same pattern: ``"low"`` / ``"med"`` / ``"high"``
      or ``None``. Only meaningful when ``task_type`` is set.
    * ``ts_ms`` — monotonic-ish timestamp in milliseconds since epoch.
      Filled automatically at construction.

    Consumers that don't want events pass ``emitter=None`` (the no-op
    default baked into every skill's signature).
    """

    signal: str
    step_id: str = ""
    note: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    task_type: str | None = None
    task_severity: str | None = None
    ts_ms: int = field(default_factory=lambda: int(time.time() * 1000))


# Emitter contract: consumers plug a callable that receives SkillEvents.
# Skills treat it as fire-and-forget — if the emitter raises, the skill
# continues (the consumer's emit pipeline shouldn't be able to break the
# skill's execution).
Emitter = Callable[[SkillEvent], None]


def _noop_emitter(_event: SkillEvent) -> None:
    """Default emitter when the consumer doesn't provide one. No-op.

    Using a real no-op function (instead of ``None``) lets skill code
    write ``emitter(event)`` unconditionally without ``if emitter:``
    guards at every emission site. The guard happens once, at skill
    entry, to normalize the incoming ``emitter`` argument.
    """


def _safe_emit(emitter: Emitter | None, event: SkillEvent) -> None:
    """Call ``emitter(event)`` swallowing exceptions.

    Skills use this wrapper so that a faulty consumer-side handler never
    corrupts the skill's control flow. Logs at debug on swallow so
    ops can diagnose emit loss without taking the skill down.
    """
    if emitter is None:
        return
    try:
        emitter(event)
    except Exception:  # noqa: BLE001  — deliberate: emit must never break skill
        import logging
        logging.getLogger(__name__).debug(
            "skill emitter raised on event signal=%r step_id=%r; swallowed",
            event.signal, event.step_id, exc_info=True,
        )
