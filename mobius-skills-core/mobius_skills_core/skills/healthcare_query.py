"""Healthcare data lookup — thin HTTP POST to the
``mobius-skills/healthcare`` microservice.

The upstream service answers questions about:

* ICD-10-CM / ICD-9 codes (meaning of F32.1, Z00.00, etc.)
* Medicare / Medicaid coverage summaries (NCD / LCD)
* CPT / HCPCS wording
* NPI registry facts when the question is a 10-digit NPI number

Jurisdiction is deliberately NOT merged into the query — this is an
entity-lookup tool, and mixing active-thread payer / state into an NPI
or ICD question produces wrong results.

HTTP contract::

    POST {HEALTHCARE_URL}/healthcare/query
    body: {"question": "<the question>"}

    200 OK:
        {"answer": "<human-readable answer>"}

Configuration:

    HEALTHCARE_URL   — base URL of the healthcare microservice.
                       Example: http://localhost:8007
                       Required. Missing → SkillResult(signal="tool_error").

Consumers:

* mobius-chat wraps this in its builtin ``healthcare_query`` skill
  (reads the question from the user message / planner inputs).
* mobius-skills-mcp exposes this as-is for external MCP clients.
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

_STEP_ID = "healthcare_query"
_DEFAULT_TIMEOUT_S = 30


def _get_base_url() -> str:
    return (
        (os.environ.get("HEALTHCARE_URL") or "").strip()
        or (os.environ.get("CHAT_SKILLS_HEALTHCARE_URL") or "").strip()
    )


def run_healthcare_query(
    question: str,
    *,
    base_url: str | None = None,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
    emitter: Emitter | None = None,
) -> SkillResult:
    """Ask the healthcare microservice.

    Args:
        question: The healthcare question. Empty → tool_error.
        base_url: Explicit override of the service URL. When None, env-
            resolved. Exposed for tests.
        timeout_s: HTTP read timeout. Default 30s (NCD/LCD lookups can
            hit upstream databases).
        emitter: Optional SkillEvent callback. Consumer-facing.

    Returns:
        SkillResult with:
          * text: the answer string from the upstream service
          * sources: one SourceRef(document_name="Healthcare lookup",
                                    source_type="external")
          * signal: "no_sources" (this data is an external API lookup,
            not RAG corpus or web content; chat's integrator knows to
            treat it as authoritative external reference)
          * signal on error: "tool_error" with the error in text
    """
    if not question or not str(question).strip():
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note="empty question rejected",
            data={"reason": "empty_question"},
            task_type="failure", task_severity="low",
        ))
        return SkillResult(
            text="Error: question is required.",
            signal="tool_error",
        )

    base = (base_url or _get_base_url()).strip()
    if not base:
        logger.warning("run_healthcare_query: HEALTHCARE_URL not configured")
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note="HEALTHCARE_URL not configured",
            data={"reason": "config_missing"},
            task_type="blocker", task_severity="high",
        ))
        return SkillResult(
            text=(
                "Error: HEALTHCARE_URL not configured. Point it at the "
                "mobius-skills/healthcare API base "
                "(e.g. http://localhost:8007)."
            ),
            signal="tool_error",
        )

    clean_question = str(question).strip()
    url = base.rstrip("/") + "/healthcare/query"
    payload = json.dumps({"question": clean_question}).encode("utf-8")

    _safe_emit(emitter, SkillEvent(
        signal="tool_invoked", step_id=_STEP_ID,
        note=f"Looking up healthcare data: {clean_question[:80]}",
        data={"question": clean_question},
        task_type="info", task_severity="low",
    ))

    try:
        req = urllib.request.Request(
            url,
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
            body = (exc.fp.read().decode() if exc.fp else str(exc))[:500]
        except Exception:
            body = str(exc)
        logger.warning("run_healthcare_query HTTP %s: %s", exc.code, body)
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note=f"Healthcare query failed (HTTP {exc.code})",
            data={"error_type": "http", "status_code": exc.code,
                  "body_preview": body[:200]},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text=f"Healthcare query failed ({exc.code}): {body}",
            signal="tool_error",
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("run_healthcare_query network error: %s", exc)
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note=f"Healthcare query failed (network: {exc})",
            data={"error_type": "network", "message": str(exc)},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text=(
                f"Healthcare query failed: {exc}. Ensure the healthcare "
                "service is running (e.g. port 8007) and HEALTHCARE_URL "
                "is set."
            ),
            signal="tool_error",
        )
    except json.JSONDecodeError as exc:
        logger.warning("run_healthcare_query JSON decode failed: %s", exc)
        _safe_emit(emitter, SkillEvent(
            signal="tool_error", step_id=_STEP_ID,
            note="Healthcare query failed (invalid JSON)",
            data={"error_type": "decode"},
            task_type="failure", task_severity="med",
        ))
        return SkillResult(
            text="Healthcare query failed (invalid JSON from service).",
            signal="tool_error",
        )

    answer = (data.get("answer") or "").strip()
    if not answer:
        _safe_emit(emitter, SkillEvent(
            signal="no_sources", step_id=_STEP_ID,
            note="Healthcare query returned no answer",
            data={"question": clean_question},
            task_type="info", task_severity="low",
        ))
        return SkillResult(
            text="Healthcare query returned no answer.",
            signal="no_sources",
        )

    _safe_emit(emitter, SkillEvent(
        signal="tool_completed", step_id=_STEP_ID,
        note="Healthcare lookup returned an answer",
        data={"question": clean_question, "answer_length": len(answer)},
        task_type="info", task_severity="low",
    ))
    # signal="no_sources" is correct here — matches the chat integrator's
    # interpretation. Healthcare data is an external API lookup, not
    # RAG corpus or web-scraped content; the integrator cites it via
    # SourceRef(source_type="external") rather than treating the
    # response as a retrieval hit.
    return SkillResult(
        text=answer,
        sources=[SourceRef(
            document_name="Healthcare lookup",
            index=1,
            text=answer[:300],
            source_type="external",
            authority="external",
        )],
        signal="no_sources",
        extra={"question": clean_question},
    )
