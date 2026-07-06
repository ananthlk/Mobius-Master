"""HIPAA PHI detection skill — pure, regex-based, no I/O.

Why a skill (not chat-only)?
-----------------------------
PHI crops up everywhere a Mobius product reads user input or LLM output:
chat turns, credentialing workflow messages, roster-upload pipelines,
emailed adjudication requests, future clinical tools. Each surface
needs the same "did we just touch PHI?" signal to drive audit rows,
routing decisions (HIPAA-eligible model?), and redaction.

Keeping the detector in ``mobius-skills-core`` means:

* **One source of regex truth.** Adding a pattern (new MRN format, new
  member-id convention) updates every caller on next release.
* **Pure function.** No DB, no HTTP, no env reads on the hot path —
  just ``run_phi_audit(text, ...) → SkillResult[extra=PhiFinding]``.
  Callers compose their own audit write / redaction / block policy.
* **Consistent emit contract.** Hosts that forward ``SkillEvent`` to a
  task-manager / Slack / metrics pipeline get ``phi_detected`` signals
  for free, without each caller re-inventing the shape.

What this skill does NOT do
---------------------------
* **No database writes.** Chat's ``phi_audit_log`` table and future
  shared audit stores are host concerns. The skill returns what was
  found; the host decides where (if anywhere) to persist. Rationale:
  skills-core is imported by multiple products with different schemas.
* **No redaction.** Callers that want to strip PHI before an LLM call
  do it themselves (the regex set is exposed via ``PHI_PATTERNS`` for
  that purpose).
* **No policy decisions** (allow / block / reroute). Those are
  product-specific and live in the caller.

Emit contract
-------------
* ``tool_invoked`` at call entry (step_id="phi_audit", low-traffic).
* ``phi_detected`` when any pattern matches — ``task_type="insight"``,
  ``task_severity="high"``. Consumers that route to task-manager get a
  HIPAA audit row in their task feed automatically.
* ``tool_completed`` at return, with ``data`` carrying phi_count +
  phi_types for downstream metrics.

No ``tool_error`` emissions — this skill has no failure mode other
than malformed regex, which would be a build-time concern.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from mobius_skills_core._types import (
    Emitter,
    SkillEvent,
    SkillResult,
    _safe_emit,
)


_STEP_ID = "phi_audit"


# ── Patterns ─────────────────────────────────────────────────────────
#
# Exposed at module level so callers that want to redact (not just
# detect) can iterate over the same patterns. Adding a pattern here
# flows to every caller on release.
#
# Pattern design notes:
#   * ``ssn`` and ``9digit_id`` overlap deliberately — a bare 9-digit
#     run may or may not be an SSN. We report both matches so auditors
#     can disambiguate (``phi_types=["ssn","9digit_id"]`` is a stronger
#     signal than either alone).
#   * ``patient_name`` intentionally under-matches. Name detection is a
#     known hard problem; a strict ``patient: Foo`` context lookahead
#     is better than false-positive spam. Callers that need aggressive
#     name detection should layer an NER pass on top.
#   * All patterns are non-capturing where possible to keep match
#     counts predictable for ``phi_count``.


PHI_PATTERNS: dict[str, re.Pattern[str]] = {
    "ssn":           re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
    "member_id":     re.compile(r"member\s*(?:id|#|number)\s*[:#]?\s*\S+", re.I),
    "patient_name":  re.compile(r"patient\s*(?:name)?\s*[:]\s*[A-Z][a-z]+", re.I),
    "dob":           re.compile(r"\b(?:dob|date of birth)\b\s*[:]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", re.I),
    "mrn":           re.compile(r"\b(?:mrn|medical record)\s*[:#]?\s*[A-Z0-9-]+", re.I),
    # 9-digit run (un-separated SSNs, member ids written without dashes)
    "9digit_id":     re.compile(r"\b\d{9}\b"),
}


# ── Result shape ─────────────────────────────────────────────────────


@dataclass
class PhiFinding:
    """What ``run_phi_audit`` found. Packed into ``SkillResult.extra``.

    ``detected`` is a convenience — hosts often just branch on it.
    ``audit_payload`` is a pre-baked dict shaped for ``phi_audit_log``-
    style schemas; a host with that schema can INSERT it directly
    without reconstructing fields.
    """

    detected: bool = False
    phi_types: list[str] = field(default_factory=list)
    phi_count: int = 0
    audit_payload: dict = field(default_factory=dict)


# ── Public API ───────────────────────────────────────────────────────


def detect_phi(text: str) -> tuple[list[str], int]:
    """Pure detection — no emission, no side effects.

    Lower-level than ``run_phi_audit``; use when you want detection
    without the skill ceremony (e.g. inline redaction before a prompt
    build). ``run_phi_audit`` is the right call for audit-trail use.
    """
    if not text:
        return [], 0
    hits: list[str] = []
    total = 0
    for label, pat in PHI_PATTERNS.items():
        matches = pat.findall(text)
        if matches:
            hits.append(label)
            total += len(matches)
    return hits, total


def run_phi_audit(
    text: str,
    *,
    event_type: str,
    correlation_id: str | None = None,
    thread_id: str | None = None,
    stage: str | None = None,
    model_used: str | None = None,
    action_taken: str = "logged_only",
    hipaa_mode_active: bool = False,
    baa_available: bool = False,
    emitter: Emitter | None = None,
) -> SkillResult:
    """Scan ``text`` for PHI and return a structured finding.

    Non-detection case: returns ``signal="ok"`` with ``detected=False``
    and no ``phi_detected`` emission. Detection case: returns
    ``signal="phi_detected"`` with a fully-formed ``audit_payload``
    that hosts can persist however they like.

    Parameters
    ----------
    text:
        The content to scan — user message, LLM output, email body,
        uploaded document's OCR text, etc.
    event_type:
        Semantic label that flows into the audit row:
        ``"request_phi_detected"``, ``"response_phi_detected"``,
        ``"llm_blocked_non_hipaa_model"``, ``"manual_review"``, etc.
        Host-defined — the skill does not validate.
    correlation_id / thread_id:
        Link the audit row back to the originating turn/thread. Both
        optional — credentialing workflows, for example, have no
        ``thread_id``.
    stage / model_used / action_taken:
        Attribution for the audit row. ``action_taken`` taxonomy (from
        chat's original writer): ``"allowed"`` / ``"blocked"`` /
        ``"redacted"`` / ``"logged_only"``.
    hipaa_mode_active / baa_available:
        Booleans the host computes (e.g. from ``CHAT_HIPAA_MODE`` env
        and vendor BAA table). The skill doesn't read env — it passes
        these through into ``audit_payload``.
    emitter:
        Standard skill emitter. See module docstring for signals.

    Returns
    -------
    SkillResult
        ``signal`` is ``"phi_detected"`` on match, ``"ok"`` otherwise.
        ``extra["finding"]`` is a ``PhiFinding`` dataclass (also
        exposed flat as ``extra["detected"]`` / ``extra["phi_types"]``
        / ``extra["phi_count"]`` for convenience).
    """
    _safe_emit(
        emitter,
        SkillEvent(
            signal="tool_invoked",
            step_id=_STEP_ID,
            note=f"Scanning for PHI (event_type={event_type!r}, stage={stage!r})",
            data={"event_type": event_type, "stage": stage, "text_len": len(text or "")},
        ),
    )

    phi_types, phi_count = detect_phi(text or "")
    detected = bool(phi_types)

    audit_payload: dict = {}
    if detected:
        audit_payload = {
            "correlation_id": correlation_id,
            "thread_id": thread_id,
            "event_type": event_type,
            "phi_types": phi_types,
            "phi_count": phi_count,
            "stage": stage,
            "model_used": model_used,
            "action_taken": action_taken,
            "hipaa_mode_active": hipaa_mode_active,
            "baa_available": baa_available,
        }
        _safe_emit(
            emitter,
            SkillEvent(
                signal="phi_detected",
                step_id=_STEP_ID,
                note=(
                    f"PHI detected ({phi_count} match(es), types={phi_types}) "
                    f"in event_type={event_type!r}"
                ),
                data=audit_payload,
                task_type="insight",     # hosts can route to task-manager / Slack / audit feed
                task_severity="high",    # PHI is always high severity for ops review
            ),
        )

    finding = PhiFinding(
        detected=detected,
        phi_types=phi_types,
        phi_count=phi_count,
        audit_payload=audit_payload,
    )

    _safe_emit(
        emitter,
        SkillEvent(
            signal="tool_completed",
            step_id=_STEP_ID,
            note=(
                f"PHI audit complete: {phi_count} match(es)"
                if detected
                else "PHI audit complete: no matches"
            ),
            data={
                "detected": detected,
                "phi_types": phi_types,
                "phi_count": phi_count,
            },
        ),
    )

    return SkillResult(
        text="",  # no primary payload — this is an audit skill, not a content skill
        signal="phi_detected" if detected else "ok",
        extra={
            "finding": finding,
            # Flatten for callers that don't want to unpack the dataclass:
            "detected": detected,
            "phi_types": phi_types,
            "phi_count": phi_count,
            "audit_payload": audit_payload,
        },
    )
