"""Tests for SkillEvent emissions — every skill emits at natural boundaries.

Locks the contract: skills emit tool_invoked on start, tool_completed
on success, no_sources when empty, tool_error on failure. Consumer-side
code (chat adapters, MCP adapters) depends on this taxonomy so changes
here have blast radius.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from mobius_skills_core import SkillEvent
from mobius_skills_core.skills.google_search import run_google_search
from mobius_skills_core.skills.web_scrape import run_web_scrape


def _fake_response(payload: dict):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class _Collector:
    """Test-side emitter that records every SkillEvent received."""
    def __init__(self):
        self.events: list[SkillEvent] = []
    def __call__(self, event: SkillEvent) -> None:
        self.events.append(event)
    def signals(self) -> list[str]:
        return [e.signal for e in self.events]
    def steps(self) -> list[str]:
        return [e.step_id for e in self.events]


class TestGoogleSearchEmits:
    def test_happy_path_emits_invoked_then_completed(self):
        c = _Collector()
        payload = {"results": [{"title": "T", "url": "https://x/1"}]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
            run_google_search("q", base_url="http://svc/search", emitter=c)

        assert c.signals() == ["tool_invoked", "tool_completed"]
        invoked = c.events[0]
        assert invoked.step_id == "google_search"
        assert invoked.data["query"] == "q"
        assert invoked.data["max_results"] == 5
        assert invoked.task_type == "info"

        done = c.events[1]
        assert done.data["result_count"] == 1

    def test_empty_results_emits_no_sources(self):
        c = _Collector()
        with patch("urllib.request.urlopen", return_value=_fake_response({"results": []})):
            run_google_search("q", base_url="http://svc/search", emitter=c)
        # tool_invoked first, then no_sources (no tool_completed)
        assert c.signals() == ["tool_invoked", "no_sources"]

    def test_missing_config_emits_single_tool_error(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_SEARCH_URL", raising=False)
        monkeypatch.delenv("CHAT_SKILLS_GOOGLE_SEARCH_URL", raising=False)
        c = _Collector()
        run_google_search("q", emitter=c)
        # Emitted BEFORE tool_invoked — config errors short-circuit
        assert c.signals() == ["tool_error"]
        assert c.events[0].task_type == "blocker"
        assert c.events[0].task_severity == "high"

    def test_empty_query_emits_tool_error_before_invocation(self):
        c = _Collector()
        run_google_search("", base_url="http://svc/search", emitter=c)
        assert c.signals() == ["tool_error"]
        assert c.events[0].data["reason"] == "empty_query"

    def test_http_error_emits_invoked_then_error(self):
        import urllib.error
        c = _Collector()
        err = urllib.error.HTTPError("http://x", 503, "down", {}, None)
        with patch("urllib.request.urlopen", side_effect=err):
            run_google_search("q", base_url="http://svc/search", emitter=c)
        assert c.signals() == ["tool_invoked", "tool_error"]
        assert c.events[1].data["error_type"] == "http"
        assert c.events[1].data["status_code"] == 503

    def test_no_emitter_is_fine(self):
        """Omitted emitter must not crash. This is the hottest path —
        every skill call without a consumer wiring events still works."""
        payload = {"results": [{"title": "T", "url": "https://x/1"}]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
            r = run_google_search("q", base_url="http://svc/search")
        assert r.signal == "ok"

    def test_raising_emitter_is_swallowed(self):
        """Faulty consumer handler must not break the skill."""
        def boom(event):
            raise RuntimeError("consumer bug")

        payload = {"results": [{"title": "T", "url": "https://x/1"}]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
            r = run_google_search("q", base_url="http://svc/search", emitter=boom)
        assert r.signal == "ok"  # skill survived the emitter exception


class TestWebScrapeEmits:
    def test_happy_path_emits_invoked_then_completed(self):
        c = _Collector()
        with patch("urllib.request.urlopen",
                   return_value=_fake_response({"text": "Hello", "summary": ""})):
            run_web_scrape("https://example.com/a", base_url="http://scr/",
                           emitter=c)
        assert c.signals() == ["tool_invoked", "tool_completed"]
        assert c.steps()[0] == "web_scrape.quick"  # mode-specific step_id
        assert c.events[0].data["mode"] == "quick"
        assert c.events[1].data["chars_raw"] == len("Hello")
        assert c.events[1].data["truncated"] is False

    def test_medium_mode_step_id(self):
        c = _Collector()
        with patch("urllib.request.urlopen",
                   return_value=_fake_response({"text": "x"})):
            run_web_scrape("https://example.com", scrape_mode="medium",
                           base_url="http://scr/", emitter=c)
        assert c.events[0].step_id == "web_scrape.medium"

    def test_empty_scrape_emits_no_sources(self):
        c = _Collector()
        with patch("urllib.request.urlopen", return_value=_fake_response({"text": ""})):
            run_web_scrape("https://example.com/empty", base_url="http://scr/",
                           emitter=c)
        assert c.signals() == ["tool_invoked", "no_sources"]

    def test_truncation_flagged_in_completed(self):
        c = _Collector()
        long_text = "A" * 10_000  # exceeds quick cap of 8000
        with patch("urllib.request.urlopen", return_value=_fake_response({"text": long_text})):
            run_web_scrape("https://example.com", base_url="http://scr/", emitter=c)
        done = c.events[-1]
        assert done.signal == "tool_completed"
        assert done.data["truncated"] is True
        assert "truncated" in done.note

    def test_bad_scheme_emits_error_before_invocation(self):
        c = _Collector()
        run_web_scrape("ftp://example.com", base_url="http://scr/", emitter=c)
        assert c.signals() == ["tool_error"]
        assert c.events[0].data["reason"] == "bad_scheme"

    def test_config_missing_emits_blocker_severity_high(self, monkeypatch):
        monkeypatch.delenv("WEB_SCRAPER_URL", raising=False)
        monkeypatch.delenv("CHAT_SKILLS_WEB_SCRAPER_URL", raising=False)
        c = _Collector()
        run_web_scrape("https://example.com", emitter=c)
        assert c.events[0].signal == "tool_error"
        assert c.events[0].task_type == "blocker"
        assert c.events[0].task_severity == "high"


class TestTaskSignalSuggestions:
    """Skills suggest task_type / task_severity per event. Consumers decide
    whether to promote. Lock the policy so consumers can rely on it."""

    def test_tool_invoked_always_info_low(self):
        c = _Collector()
        payload = {"results": [{"title": "T", "url": "https://x/1"}]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
            run_google_search("q", base_url="http://svc/search", emitter=c)
        invoked = c.events[0]
        assert invoked.signal == "tool_invoked"
        assert invoked.task_type == "info"
        assert invoked.task_severity == "low"

    def test_config_missing_is_blocker_high(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_SEARCH_URL", raising=False)
        monkeypatch.delenv("CHAT_SKILLS_GOOGLE_SEARCH_URL", raising=False)
        c = _Collector()
        run_google_search("q", emitter=c)
        assert c.events[0].task_type == "blocker"
        assert c.events[0].task_severity == "high"

    def test_transient_http_is_failure_med(self):
        import urllib.error
        c = _Collector()
        err = urllib.error.HTTPError("http://x", 502, "bad gateway", {}, None)
        with patch("urllib.request.urlopen", side_effect=err):
            run_google_search("q", base_url="http://svc/search", emitter=c)
        err_event = c.events[-1]
        assert err_event.signal == "tool_error"
        assert err_event.task_type == "failure"
        assert err_event.task_severity == "med"


class TestEventShape:
    def test_event_has_timestamp(self):
        c = _Collector()
        payload = {"results": [{"title": "T", "url": "https://x/1"}]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
            run_google_search("q", base_url="http://svc/search", emitter=c)
        for e in c.events:
            assert e.ts_ms > 0

    def test_event_data_is_dict(self):
        c = _Collector()
        payload = {"results": [{"title": "T", "url": "https://x/1"}]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
            run_google_search("q", base_url="http://svc/search", emitter=c)
        for e in c.events:
            assert isinstance(e.data, dict)
