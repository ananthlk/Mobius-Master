"""Unit tests for mobius_skills_core.skills.document_upload.

Smallest skill in the package — no inputs, no network, returns canned
markdown. Tests lock:
  * The markdown contains the key affordances a consumer depends on
    (HTTP endpoint, UI instructions, purpose list).
  * The skill emits tool_invoked + tool_completed in order.
  * The signal is ``no_sources`` (the chat integrator treats this as
    an informational response, not a retrieval hit).
"""
from __future__ import annotations

from mobius_skills_core import SkillEvent
from mobius_skills_core.skills.document_upload import (
    DOCUMENT_UPLOAD_MARKDOWN,
    run_document_upload_info,
)


class _Collector:
    def __init__(self):
        self.events: list[SkillEvent] = []
    def __call__(self, event: SkillEvent) -> None:
        self.events.append(event)


class TestMarkdownContent:
    """Contract: what a consumer can rely on finding in the markdown."""

    def test_http_endpoint_documented(self):
        assert "POST /chat/roster-upload" in DOCUMENT_UPLOAD_MARKDOWN
        assert "GET /chat/thread/{thread_id}/uploads" in DOCUMENT_UPLOAD_MARKDOWN

    def test_ui_affordance_documented(self):
        assert "⋯" in DOCUMENT_UPLOAD_MARKDOWN
        assert "Upload file" in DOCUMENT_UPLOAD_MARKDOWN

    def test_supported_file_types_documented(self):
        # PDF/DOCX/CSV/XLSX are the four types the upload pipeline accepts
        for t in ("PDF", "DOCX", "CSV", "XLSX"):
            assert t in DOCUMENT_UPLOAD_MARKDOWN

    def test_instant_rag_purpose_documented(self):
        assert "instant_rag" in DOCUMENT_UPLOAD_MARKDOWN

    def test_search_uploaded_document_next_step(self):
        assert "search_uploaded_document" in DOCUMENT_UPLOAD_MARKDOWN


class TestResult:
    def test_default_call_returns_markdown(self):
        r = run_document_upload_info()
        assert r.signal == "no_sources"
        assert r.text == DOCUMENT_UPLOAD_MARKDOWN
        # No sources (it's an info/doc response, not a retrieval hit)
        assert r.sources == []


class TestEmits:
    def test_fires_invoked_then_completed(self):
        c = _Collector()
        run_document_upload_info(emitter=c)
        signals = [e.signal for e in c.events]
        assert signals == ["tool_invoked", "tool_completed"]

    def test_both_events_info_low_severity(self):
        c = _Collector()
        run_document_upload_info(emitter=c)
        for e in c.events:
            assert e.task_type == "info"
            assert e.task_severity == "low"
            assert e.step_id == "document_upload"

    def test_no_emitter_ok(self):
        r = run_document_upload_info()
        assert r.text == DOCUMENT_UPLOAD_MARKDOWN
