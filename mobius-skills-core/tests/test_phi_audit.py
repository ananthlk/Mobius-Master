"""Unit tests for mobius_skills_core.skills.phi_audit.

Pure skill — no network, no DB, no env reads. Tests lock:

  1. **Detection correctness.** Every pattern fires on a positive
     example and stays quiet on a negative. Critical because these
     regexes drive HIPAA audit rows.
  2. **Result shape.** ``SkillResult.extra["finding"]`` is a
     ``PhiFinding`` with a fully populated ``audit_payload`` on
     detection, empty on non-detection.
  3. **Emit contract.** ``tool_invoked`` / ``tool_completed`` always
     fire; ``phi_detected`` fires only when PHI is present, with
     ``task_type="insight"`` + ``task_severity="high"``.
  4. **Safety.** Empty text, None text, and emitter-raising-exception
     never raise from the skill.
"""
from __future__ import annotations

import pytest

from mobius_skills_core.skills.phi_audit import (
    PHI_PATTERNS,
    PhiFinding,
    detect_phi,
    run_phi_audit,
)


# ── Detection correctness ────────────────────────────────────────────


class TestDetectPhi:
    def test_ssn_dashed(self):
        types, count = detect_phi("patient SSN 123-45-6789 on file")
        assert "ssn" in types
        assert count >= 1

    def test_ssn_bare_9_digits(self):
        types, count = detect_phi("ID 123456789 submitted")
        # Bare 9-digit run matches both ssn (with optional separators)
        # and the 9digit_id fallback — deliberate overlap.
        assert "9digit_id" in types
        assert count >= 1

    def test_member_id(self):
        types, _ = detect_phi("Member ID: ABC123456")
        assert "member_id" in types

    def test_patient_name_context(self):
        types, _ = detect_phi("Patient: Jane Smith")
        assert "patient_name" in types

    def test_dob(self):
        types, _ = detect_phi("DOB: 03/14/1985")
        assert "dob" in types

    def test_mrn(self):
        types, _ = detect_phi("MRN: A1B2C3")
        assert "mrn" in types

    def test_no_false_positive_on_generic_number(self):
        types, count = detect_phi("We served 42 clients this month.")
        assert types == []
        assert count == 0

    def test_empty_string(self):
        assert detect_phi("") == ([], 0)

    def test_none_safe(self):
        # Defensive: callers sometimes pass optional strings.
        assert detect_phi(None) == ([], 0)  # type: ignore[arg-type]


# ── Result shape ─────────────────────────────────────────────────────


class TestRunPhiAuditResultShape:
    def test_no_phi_returns_ok(self):
        r = run_phi_audit("Hello, how's the weather?", event_type="request")
        assert r.signal == "ok"
        assert r.extra["detected"] is False
        assert r.extra["phi_types"] == []
        assert r.extra["phi_count"] == 0
        assert r.extra["audit_payload"] == {}
        assert isinstance(r.extra["finding"], PhiFinding)
        assert r.extra["finding"].detected is False

    def test_phi_detected_returns_phi_signal(self):
        r = run_phi_audit(
            "Patient SSN 123-45-6789",
            event_type="request_phi_detected",
            correlation_id="c-1",
            thread_id="t-1",
            stage="resolve",
            model_used="claude-haiku-4-5",
            action_taken="logged_only",
            hipaa_mode_active=True,
            baa_available=True,
        )
        assert r.signal == "phi_detected"
        assert r.extra["detected"] is True
        assert "ssn" in r.extra["phi_types"]
        assert r.extra["phi_count"] >= 1

        payload = r.extra["audit_payload"]
        # Host-schema-shaped: every field present for direct INSERT.
        assert payload["correlation_id"] == "c-1"
        assert payload["thread_id"] == "t-1"
        assert payload["event_type"] == "request_phi_detected"
        assert payload["stage"] == "resolve"
        assert payload["model_used"] == "claude-haiku-4-5"
        assert payload["action_taken"] == "logged_only"
        assert payload["hipaa_mode_active"] is True
        assert payload["baa_available"] is True
        assert "ssn" in payload["phi_types"]

    def test_finding_dataclass_matches_flat_keys(self):
        """Both access paths (finding.* and extra['*']) return the
        same data — callers can use either idiom."""
        r = run_phi_audit("Member ID: X1", event_type="req")
        finding: PhiFinding = r.extra["finding"]
        assert finding.detected == r.extra["detected"]
        assert finding.phi_types == r.extra["phi_types"]
        assert finding.phi_count == r.extra["phi_count"]


# ── Emit contract ────────────────────────────────────────────────────


class _CapturingEmitter:
    """Collect every SkillEvent the skill emits."""

    def __init__(self):
        self.events = []

    def __call__(self, event):
        self.events.append(event)


class TestEmissions:
    def test_invoked_and_completed_always_fire(self):
        emitter = _CapturingEmitter()
        run_phi_audit("innocuous text", event_type="req", emitter=emitter)
        signals = [e.signal for e in emitter.events]
        assert "tool_invoked" in signals
        assert "tool_completed" in signals
        # No PHI → no phi_detected event.
        assert "phi_detected" not in signals

    def test_phi_detected_event_on_match(self):
        emitter = _CapturingEmitter()
        run_phi_audit(
            "SSN 123-45-6789",
            event_type="request_phi_detected",
            stage="resolve",
            emitter=emitter,
        )
        phi_events = [e for e in emitter.events if e.signal == "phi_detected"]
        assert len(phi_events) == 1
        ev = phi_events[0]
        # Routing hints for consumers that promote to task-manager.
        assert ev.task_type == "insight"
        assert ev.task_severity == "high"
        assert ev.step_id == "phi_audit"
        assert "ssn" in ev.data["phi_types"]

    def test_step_id_consistent_across_emissions(self):
        emitter = _CapturingEmitter()
        run_phi_audit("Patient: Foo", event_type="req", emitter=emitter)
        for e in emitter.events:
            assert e.step_id == "phi_audit"

    def test_emitter_exception_does_not_break_skill(self):
        def evil_emitter(_event):
            raise RuntimeError("consumer bug")

        # Must not raise — audit must never break the caller's flow.
        r = run_phi_audit("SSN 123-45-6789", event_type="req", emitter=evil_emitter)
        assert r.signal == "phi_detected"


# ── Safety ───────────────────────────────────────────────────────────


class TestSafety:
    def test_empty_text_ok_signal(self):
        r = run_phi_audit("", event_type="req")
        assert r.signal == "ok"

    def test_missing_optional_args(self):
        # correlation_id, thread_id, stage, model_used all optional.
        r = run_phi_audit("SSN 123-45-6789", event_type="req")
        assert r.signal == "phi_detected"
        assert r.extra["audit_payload"]["correlation_id"] is None
        assert r.extra["audit_payload"]["thread_id"] is None


# ── Pattern library exposure ─────────────────────────────────────────


class TestPatternLibrary:
    def test_patterns_importable(self):
        # Callers that want to redact (not just detect) need direct
        # access to the compiled regexes.
        assert "ssn" in PHI_PATTERNS
        assert "mrn" in PHI_PATTERNS
        # Cheap sanity: every entry is a compiled pattern.
        import re
        for label, pat in PHI_PATTERNS.items():
            assert isinstance(pat, re.Pattern), f"{label} is not a compiled pattern"
