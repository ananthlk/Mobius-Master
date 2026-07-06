"""Web scrape — thin HTTP call to the ``mobius-skills/web-scraper``
microservice.

Single source of truth for:

* **Mode specs**: how much of a site each mode crawls
  (``quick`` / ``medium`` / ``detailed``)
* **Timeouts**: how long each mode is allowed to take
* **Output caps**: how much extracted text each mode is allowed to
  return before truncation

Before this module existed, the chat's ``_run_web_scrape`` helper and
mobius-skills-mcp's ``web_scrape_review`` each kept their own copy of
the spec dict. A literal ``# Keep max_* in sync with mobius-chat
app.services.tool_agent.WEB_SCRAPE_MODE_SPECS`` comment sat over the MCP
version as the maintainer's reminder that the duplication was
deliberate and risky. That reminder is no longer needed — both
consumers now import WEB_SCRAPE_MODE_SPECS from here.

Consumers:

* ``mobius-chat`` wraps this into its builtin ``web_scrape`` skill.
* ``mobius-skills-mcp`` exposes this as the ``web_scrape`` MCP tool
  (formerly ``web_scrape_review``; renamed for consistency).

HTTP contract:

    POST {base}
    body: {url, include_summary, scrape_mode, max_depth,
           max_pages, max_doc_downloads}

The upstream service returns ``{"text": ..., "summary": ...}``.

Configuration:

    WEB_SCRAPER_URL  — base URL of the web-scraper microservice.
                       Example: http://localhost:8002/scrape/review
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

_STEP_ID = "web_scrape"


# Single source of truth for mode specs. Before this module both chat
# (tool_agent.WEB_SCRAPE_MODE_SPECS) and the MCP server kept their own
# copies; they're now gone — import from here.
WEB_SCRAPE_MODE_SPECS: dict[str, dict[str, int]] = {
    "quick":    {"max_depth": 1, "max_pages": 1,  "max_doc_downloads": 0},
    "medium":   {"max_depth": 3, "max_pages": 6,  "max_doc_downloads": 0},
    "detailed": {"max_depth": 5, "max_pages": 50, "max_doc_downloads": 10},
}

# Per-mode HTTP read timeout. Deeper crawls legitimately take longer.
WEB_SCRAPE_MODE_TIMEOUTS_S: dict[str, int] = {
    "quick": 45, "medium": 120, "detailed": 300,
}

# Per-mode output text cap. The scraper can return hundreds of KB
# (especially "detailed"); we cap at skill-exit to keep LLM prompts sane.
WEB_SCRAPE_MODE_OUTPUT_CAPS: dict[str, int] = {
    "quick": 8_000, "medium": 32_000, "detailed": 120_000,
}

_DEFAULT_MODE = "quick"
_VALID_SCHEMES = ("http", "https")


def _normalize_mode(raw: str | None) -> str:
    """Clamp an unknown or missing mode to ``quick``.

    Matches the pre-refactor behavior in both consumers; callers that
    want strict validation can check ``mode in WEB_SCRAPE_MODE_SPECS``
    themselves.
    """
    s = (raw or "").strip().lower()
    return s if s in WEB_SCRAPE_MODE_SPECS else _DEFAULT_MODE


def _get_base_url() -> str:
    """Read the web-scraper base URL from env.

    ``WEB_SCRAPER_URL`` is canonical. Legacy names accepted for
    backward compatibility during the migration.
    """
    return (
        (os.environ.get("WEB_SCRAPER_URL") or "").strip()
        or (os.environ.get("CHAT_SKILLS_WEB_SCRAPER_URL") or "").strip()
    )


def run_web_scrape(
    url: str,
    scrape_mode: str = _DEFAULT_MODE,
    include_summary: bool = False,
    *,
    base_url: str | None = None,
    emitter: Emitter | None = None,
) -> SkillResult:
    """Scrape a URL via the web-scraper microservice.

    Args:
        url: Seed URL. Must be http(s). Empty / non-http → tool_error.
        scrape_mode: ``quick`` | ``medium`` | ``detailed``. Unknown
            values clamp to ``quick``. See module docstring for spec.
        include_summary: If True, ask the scraper for an LLM-generated
            summary (requires Vertex/OpenAI configured on the scraper).
        base_url: Explicit override of the service URL. When None, falls
            back to env resolution. Exposed for tests.

    Returns:
        SkillResult with:
          * text: "URL: <url>\\n\\nscrape_mode: <mode>\\n\\nContent:\\n<truncated>"
          * sources: one SourceRef(url=..., source_type="web")
          * extra["summary"]: LLM summary when requested + produced
          * extra["mode"]: the resolved mode (after clamping)
          * extra["truncated"]: True when the scraper's text exceeded cap
          * signal: "ok" on success; "no_sources" when scraper returned
            empty text; "tool_error" on HTTP / config / network failure.
    """
    if not url or not str(url).strip():
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note="empty url rejected", data={"reason": "empty_url"},
            task_type="failure", task_severity="low",
        ))
        return SkillResult(text="Error: url is required.", signal="tool_error")

    clean_url = str(url).strip()
    parsed = urllib.parse.urlparse(clean_url)
    if parsed.scheme not in _VALID_SCHEMES:
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note=f"invalid url scheme: {parsed.scheme or '(none)'}",
            data={"reason": "bad_scheme", "scheme": parsed.scheme or ""},
            task_type="failure", task_severity="low",
        ))
        return SkillResult(
            text="Error: url must use http or https scheme.",
            signal="tool_error",
        )

    base = (base_url or _get_base_url()).strip()
    if not base:
        logger.warning("run_web_scrape: WEB_SCRAPER_URL not configured")
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note="WEB_SCRAPER_URL not configured",
            data={"reason": "config_missing"},
            task_type="blocker", task_severity="high",
        ))
        return SkillResult(
            text=(
                "Error: WEB_SCRAPER_URL not configured. Point it at the "
                "mobius-skills/web-scraper review endpoint "
                "(e.g. http://localhost:8002/scrape/review)."
            ),
            signal="tool_error",
        )

    mode = _normalize_mode(scrape_mode)
    spec = WEB_SCRAPE_MODE_SPECS[mode]
    timeout_s = WEB_SCRAPE_MODE_TIMEOUTS_S.get(mode, 45)
    cap = WEB_SCRAPE_MODE_OUTPUT_CAPS.get(mode, 8_000)

    # Natural progress emit — human-readable "what I'm doing right now".
    # Mode-specific note matches the legacy chat tool_agent._run_web_scrape
    # wording so UIs that already display "◌ Reading page: …" keep parity.
    domain = parsed.netloc or clean_url[:40]
    mode_notes = {
        "quick":    f"Reading page: {domain}",
        "medium":   f"Site crawl (medium — depth ≤3, up to 6 pages): {domain}",
        "detailed": f"Site crawl (detailed — depth ≤5, up to 50 pages, ≤10 doc downloads): {domain}",
    }
    _safe_emit(emitter, SkillEvent(
        signal="tool_invoked", step_id=f"{_STEP_ID}.{mode}",
        note=mode_notes[mode],
        data={"url": clean_url, "mode": mode, "include_summary": bool(include_summary), **spec},
        task_type="info", task_severity="low",
    ))

    payload = json.dumps({
        "url": clean_url,
        "include_summary": bool(include_summary),
        "scrape_mode": mode,
        **spec,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            base,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode()
        data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = (exc.fp.read().decode() if exc.fp else str(exc))[:300]
        except Exception:
            body = str(exc)
        logger.warning("run_web_scrape HTTP %s: %s", exc.code, body)
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note=f"Scrape failed (HTTP {exc.code})",
            data={"error_type": "http", "status_code": exc.code, "body_preview": body[:200]},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text=f"Scrape failed (HTTP {exc.code}): {body}",
            signal="tool_error",
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("run_web_scrape network error: %s", exc)
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note=f"Scrape failed (network: {exc})",
            data={"error_type": "network", "message": str(exc)},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text=f"Scrape failed (network: {exc}).",
            signal="tool_error",
        )
    except json.JSONDecodeError as exc:
        logger.warning("run_web_scrape JSON decode failed: %s", exc)
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note="Scrape failed (invalid JSON from scraper)",
            data={"error_type": "decode"},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text="Scrape failed (invalid JSON from scraper).",
            signal="tool_error",
        )

    text_raw = (data.get("text") or "").strip()
    summary = (data.get("summary") or "").strip()

    if not text_raw:
        _safe_emit(emitter, SkillEvent(
            signal="no_sources", step_id=_STEP_ID,
            note=f"No content extracted from {domain}",
            data={"url": clean_url, "mode": mode},
            task_type="info", task_severity="low",
        ))
        return SkillResult(
            text=(
                f"No content extracted from {clean_url}. "
                "The page may be empty or block automated access."
            ),
            sources=[SourceRef(
                document_name=parsed.netloc or clean_url,
                source_type="web",
                url=clean_url,
                index=1,
            )],
            signal="no_sources",
            extra={"mode": mode},
        )

    truncated = len(text_raw) > cap
    text_out = text_raw[:cap]

    body = f"URL: {clean_url}\n\nscrape_mode: {mode}\n\nContent:\n{text_out}"
    if truncated:
        body += "\n\n[... truncated ...]"
    if summary:
        body += f"\n\nSummary: {summary}"

    _safe_emit(emitter, SkillEvent(
        signal="tool_completed", step_id=_STEP_ID,
        note=f"Scraped {len(text_raw)} chars from {domain}"
             + (" (truncated)" if truncated else ""),
        data={
            "url": clean_url,
            "mode": mode,
            "chars_raw": len(text_raw),
            "chars_out": len(text_out),
            "truncated": truncated,
            "has_summary": bool(summary),
        },
        task_type="info", task_severity="low",
    ))
    return SkillResult(
        text=body,
        sources=[SourceRef(
            document_name=parsed.netloc or clean_url,
            source_type="web",
            url=clean_url,
            index=1,
            text=text_out[:300],
        )],
        signal="ok",
        extra={
            "mode": mode,
            "truncated": truncated,
            "summary": summary or None,
        },
    )
