"""Google Programmable Search Engine — thin HTTP call to the
``mobius-skills/google-search`` microservice.

This is the **atomic** search capability: query in, raw results out.
Higher-level compositions (scrape the top result, LLM-summarize snippets
as a fallback, merge jurisdiction into the query) stay in chat, where
they can pull in chat-specific context (active payer/state from thread
state, LLM provider, emit channel). Those compositions USE this function
as a building block.

Consumers:

* ``mobius-chat`` wraps this into a richer ``google_search`` skill that
  adds auto-scrape + LLM summarization.
* ``mobius-skills-mcp`` exposes this as-is for external MCP clients that
  want raw search results.

HTTP contract:

    GET {base}?q=<urlencoded query>&num=<1..10>

The upstream service returns either ``{"results": [...]}`` or
``{"items": [...]}`` (both shapes exist in the wild). Each result is
``{title, snippet (or description), url (or link)}``.

Configuration:

    GOOGLE_SEARCH_URL   — base URL of the google-search microservice.
                          Example: http://localhost:8004/search
                          Required. Missing → SkillResult(signal="tool_error").
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from mobius_skills_core._types import (
    Emitter,
    SkillEvent,
    SkillResult,
    SourceRef,
    _safe_emit,
)

logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S = 15
_MAX_RESULTS_CEILING = 10
_STEP_ID = "google_search"


def _get_base_url() -> str:
    """Read the google-search base URL from env.

    ``GOOGLE_SEARCH_URL`` is the canonical name. ``CHAT_SKILLS_GOOGLE_SEARCH_URL``
    is the legacy name used by mobius-skills-mcp; we accept both during
    the transition.
    """
    return (
        (os.environ.get("GOOGLE_SEARCH_URL") or "").strip()
        or (os.environ.get("CHAT_SKILLS_GOOGLE_SEARCH_URL") or "").strip()
    )


def run_google_search(
    query: str,
    max_results: int = 5,
    *,
    base_url: str | None = None,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
    emitter: Emitter | None = None,
) -> SkillResult:
    """Call the google-search microservice and return parsed results.

    Args:
        query: The search query string. Empty → tool_error.
        max_results: Clamped to [1, 10]. Default 5.
        base_url: Explicit override of the service URL. When None, falls
            back to the env-resolved value. Exposed for tests + for
            callers that pool multiple google-search deployments.
        timeout_s: HTTP read timeout. Default 15s.
        emitter: Optional callback that receives SkillEvent at natural
            boundaries (invoked / completed / no_sources / error).
            Consumer-facing — chat's adapter forwards to its thinking log +
            task-manager promotion; MCP can ignore. None → no emits.

    Returns:
        SkillResult with:
          * text: human-readable "1. title — snippet (url)" block
          * sources: one SourceRef per result (type=web, url populated)
          * extra["results"]: the raw parsed result dicts, for callers
            that want to do their own formatting (e.g. chat's auto-scrape
            step reads extra["results"] to pick which URL to scrape)
          * signal: "ok" when results returned, "no_sources" when the
            service returned an empty list, "tool_error" on HTTP / parse
            failure or missing configuration.
    """
    if not query or not str(query).strip():
        _safe_emit(emitter, SkillEvent(
            signal="tool_error",
            step_id=_STEP_ID,
            note="empty query rejected",
            data={"reason": "empty_query"},
            task_type="failure",
            task_severity="low",
        ))
        return SkillResult(
            text="Error: query is required and cannot be empty.",
            signal="tool_error",
        )

    base = (base_url or _get_base_url()).strip()
    if not base:
        logger.warning("run_google_search: GOOGLE_SEARCH_URL not configured")
        _safe_emit(emitter, SkillEvent(
            signal="tool_error",
            step_id=_STEP_ID,
            note="GOOGLE_SEARCH_URL not configured",
            data={"reason": "config_missing"},
            task_type="blocker",
            task_severity="high",
        ))
        return SkillResult(
            text=(
                "Error: GOOGLE_SEARCH_URL not configured. Point it at the "
                "mobius-skills/google-search API base "
                "(e.g. http://localhost:8004/search)."
            ),
            signal="tool_error",
        )

    clean_query = str(query).strip()
    # Clamp to [1, 10]. None / falsy → 5 (default); explicit 0 → 1 (floor),
    # so a caller asking for "no results" still gets one back rather than
    # the silent default.
    try:
        requested = int(max_results) if max_results is not None else 5
    except (TypeError, ValueError):
        requested = 5
    n = min(_MAX_RESULTS_CEILING, max(1, requested))
    sep = "&" if "?" in base else "?"
    url = (
        base.rstrip("/")
        + sep
        + "q=" + urllib.parse.quote(clean_query)
        + "&num=" + str(n)
    )

    # Emit "invoked" before the HTTP call. Consumers typically render this
    # as "◌ Searching the web for: <query>" in a progress panel.
    _safe_emit(emitter, SkillEvent(
        signal="tool_invoked",
        step_id=_STEP_ID,
        note=f"Searching the web for: {clean_query[:80]}",
        data={"query": clean_query, "max_results": n},
        task_type="info",
        task_severity="low",
    ))

    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode()
        data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        logger.warning("run_google_search HTTP %s: %s", exc.code, exc)
        _safe_emit(emitter, SkillEvent(
            signal="tool_error",
            step_id=_STEP_ID,
            note=f"Search failed (HTTP {exc.code})",
            data={"error_type": "http", "status_code": exc.code},
            task_type="failure",
            task_severity="med",
        ))
        return SkillResult(
            text=f"Search failed (HTTP {exc.code}).",
            signal="tool_error",
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("run_google_search network error: %s", exc)
        _safe_emit(emitter, SkillEvent(
            signal="tool_error",
            step_id=_STEP_ID,
            note=f"Search failed (network: {exc})",
            data={"error_type": "network", "message": str(exc)},
            task_type="failure",
            task_severity="med",
        ))
        return SkillResult(
            text=f"Search failed (network: {exc}).",
            signal="tool_error",
        )
    except json.JSONDecodeError as exc:
        logger.warning("run_google_search JSON decode failed: %s", exc)
        _safe_emit(emitter, SkillEvent(
            signal="tool_error",
            step_id=_STEP_ID,
            note="Search failed (invalid JSON from search service)",
            data={"error_type": "decode"},
            task_type="failure",
            task_severity="med",
        ))
        return SkillResult(
            text="Search failed (invalid JSON from search service).",
            signal="tool_error",
        )

    results = data.get("results") or data.get("items") or []
    if not isinstance(results, list):
        _safe_emit(emitter, SkillEvent(
            signal="tool_error",
            step_id=_STEP_ID,
            note="unexpected response shape from search service",
            data={"error_type": "shape"},
            task_type="failure",
            task_severity="med",
        ))
        return SkillResult(text="Search failed (unexpected response shape).", signal="tool_error")
    if not results:
        _safe_emit(emitter, SkillEvent(
            signal="no_sources",
            step_id=_STEP_ID,
            note="No search results found",
            data={"query": clean_query},
            task_type="info",
            task_severity="low",
        ))
        return SkillResult(text="No search results found.", signal="no_sources")

    # Normalize each result to {title, snippet, url}.
    normalized: list[dict] = []
    lines: list[str] = []
    sources: list[SourceRef] = []
    for i, r in enumerate(results[:n], 1):
        if not isinstance(r, dict):
            continue
        title = (r.get("title") or "").strip()
        snippet = (r.get("snippet") or r.get("description") or "").strip()
        link = (r.get("url") or r.get("link") or "").strip()
        normalized.append({"title": title, "snippet": snippet, "url": link})
        # Formatted text block: "1. Title — snippet (url)"
        line = f"{i}. {title}"
        if snippet:
            line += f" — {snippet}"
        if link:
            line += f" ({link})"
        lines.append(line)
        # SourceRef per result (domain as document_name, url on source)
        domain = ""
        if link:
            try:
                domain = urllib.parse.urlparse(link).netloc or ""
            except Exception:
                domain = ""
        sources.append(
            SourceRef(
                document_name=domain or title[:60] or "web",
                source_type="web",
                url=link or None,
                index=i,
                text=snippet[:300],
            )
        )

    _safe_emit(emitter, SkillEvent(
        signal="tool_completed",
        step_id=_STEP_ID,
        note=f"Found {len(sources)} result(s)",
        data={"result_count": len(sources), "query": clean_query},
        task_type="info",
        task_severity="low",
    ))
    return SkillResult(
        text="\n".join(lines),
        sources=sources,
        signal="ok",
        extra={"results": normalized, "query": clean_query},
    )
