"""Unit tests for mobius_skills_core.skills.healthcare_query."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from mobius_skills_core import SkillEvent
from mobius_skills_core.skills.healthcare_query import run_healthcare_query


def _fake_response(payload: dict):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class _Collector:
    def __init__(self):
        self.events: list[SkillEvent] = []
    def __call__(self, event: SkillEvent) -> None:
        self.events.append(event)


class TestInputValidation:
    def test_empty_question(self):
        r = run_healthcare_query("", base_url="http://hc/")
        assert r.signal == "tool_error"
        assert "question is required" in r.text

    def test_whitespace_question(self):
        r = run_healthcare_query("   \n", base_url="http://hc/")
        assert r.signal == "tool_error"

    def test_missing_config(self, monkeypatch):
        monkeypatch.delenv("HEALTHCARE_URL", raising=False)
        monkeypatch.delenv("CHAT_SKILLS_HEALTHCARE_URL", raising=False)
        r = run_healthcare_query("What is ICD-10 F32.1?")
        assert r.signal == "tool_error"
        assert "HEALTHCARE_URL" in r.text


class TestHappyPath:
    def test_answer_returned_with_source(self):
        payload = {"answer": "F32.1 is Major depressive disorder, single episode, moderate."}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
            r = run_healthcare_query("What is ICD-10 F32.1?", base_url="http://hc/")
        assert r.signal == "no_sources"  # external lookup, not RAG
        assert "F32.1" in r.text
        assert "Major depressive disorder" in r.text
        assert len(r.sources) == 1
        assert r.sources[0].document_name == "Healthcare lookup"
        assert r.sources[0].source_type == "external"
        assert r.sources[0].authority == "external"

    def test_post_body_carries_question(self):
        payload = {"answer": "x"}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            run_healthcare_query("What is NPI 1234567890?", base_url="http://hc/")
        req = m.call_args[0][0]
        body = json.loads(req.data.decode())
        assert body == {"question": "What is NPI 1234567890?"}

    def test_url_appends_healthcare_query_path(self):
        payload = {"answer": "x"}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            run_healthcare_query("q", base_url="http://hc/")
        assert m.call_args[0][0].full_url == "http://hc/healthcare/query"

    def test_trailing_slash_handled(self):
        payload = {"answer": "x"}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            run_healthcare_query("q", base_url="http://hc//")
        # Double slash should not appear in the final URL
        assert m.call_args[0][0].full_url == "http://hc/healthcare/query"


class TestEmptyAnswer:
    def test_empty_answer_returns_no_sources_message(self):
        with patch("urllib.request.urlopen", return_value=_fake_response({"answer": ""})):
            r = run_healthcare_query("obscure", base_url="http://hc/")
        assert r.signal == "no_sources"
        assert "no answer" in r.text.lower()
        # No source attached when no answer
        assert r.sources == []

    def test_missing_answer_key(self):
        with patch("urllib.request.urlopen", return_value=_fake_response({})):
            r = run_healthcare_query("q", base_url="http://hc/")
        assert r.signal == "no_sources"


class TestErrorPaths:
    def test_http_error(self):
        import urllib.error
        import io
        fp = io.BytesIO(b"Service temporarily unavailable")
        err = urllib.error.HTTPError("http://x", 503, "Unavailable", {}, fp)
        with patch("urllib.request.urlopen", side_effect=err):
            r = run_healthcare_query("q", base_url="http://hc/")
        assert r.signal == "tool_error"
        assert "503" in r.text

    def test_network_error(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            r = run_healthcare_query("q", base_url="http://hc/")
        assert r.signal == "tool_error"
        # Error text points operators at the service + env var
        assert "Healthcare query failed" in r.text
        assert "healthcare service is running" in r.text

    def test_bad_json(self):
        resp = MagicMock()
        resp.read.return_value = b"not-json"
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=resp):
            r = run_healthcare_query("q", base_url="http://hc/")
        assert r.signal == "tool_error"
        assert "invalid JSON" in r.text


class TestEmits:
    def test_happy_path_emits_invoked_then_completed(self):
        c = _Collector()
        with patch("urllib.request.urlopen", return_value=_fake_response({"answer": "x"})):
            run_healthcare_query("q", base_url="http://hc/", emitter=c)
        signals = [e.signal for e in c.events]
        assert signals == ["tool_invoked", "tool_completed"]

    def test_empty_answer_emits_no_sources(self):
        c = _Collector()
        with patch("urllib.request.urlopen", return_value=_fake_response({"answer": ""})):
            run_healthcare_query("q", base_url="http://hc/", emitter=c)
        signals = [e.signal for e in c.events]
        assert signals == ["tool_invoked", "no_sources"]

    def test_config_missing_blocker_severity(self, monkeypatch):
        monkeypatch.delenv("HEALTHCARE_URL", raising=False)
        monkeypatch.delenv("CHAT_SKILLS_HEALTHCARE_URL", raising=False)
        c = _Collector()
        run_healthcare_query("q", emitter=c)
        assert c.events[0].task_type == "blocker"
        assert c.events[0].task_severity == "high"

    def test_http_error_includes_status_code_in_data(self):
        import urllib.error
        c = _Collector()
        err = urllib.error.HTTPError("http://x", 500, "err", {}, None)
        with patch("urllib.request.urlopen", side_effect=err):
            run_healthcare_query("q", base_url="http://hc/", emitter=c)
        err_event = c.events[-1]
        assert err_event.data["error_type"] == "http"
        assert err_event.data["status_code"] == 500

    def test_no_emitter_ok(self):
        with patch("urllib.request.urlopen", return_value=_fake_response({"answer": "x"})):
            r = run_healthcare_query("q", base_url="http://hc/")
        assert r.signal == "no_sources"


class TestEnvFallback:
    def test_canonical_env(self, monkeypatch):
        monkeypatch.setenv("HEALTHCARE_URL", "http://env-hc/")
        payload = {"answer": "x"}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            run_healthcare_query("q")
        assert "env-hc" in m.call_args[0][0].full_url

    def test_legacy_env(self, monkeypatch):
        monkeypatch.delenv("HEALTHCARE_URL", raising=False)
        monkeypatch.setenv("CHAT_SKILLS_HEALTHCARE_URL", "http://legacy-hc/")
        payload = {"answer": "x"}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            run_healthcare_query("q")
        assert "legacy-hc" in m.call_args[0][0].full_url
