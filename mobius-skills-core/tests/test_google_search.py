"""Unit tests for mobius_skills_core.skills.google_search.

Mocks ``urllib.request.urlopen`` so tests run with zero network. Every
test documents what contract it's locking in.
"""
from __future__ import annotations

import io
import json
from unittest.mock import patch, MagicMock

import pytest

from mobius_skills_core.skills.google_search import run_google_search


def _fake_response(payload: dict, status: int = 200):
    """Build a mock response object that matches urlopen's context-manager shape."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestInputValidation:
    def test_empty_query_tool_error(self):
        r = run_google_search("", base_url="http://x/search")
        assert r.signal == "tool_error"
        assert "query is required" in r.text

    def test_whitespace_only_query_tool_error(self):
        r = run_google_search("   \n\t  ", base_url="http://x/search")
        assert r.signal == "tool_error"

    def test_missing_base_url_tool_error(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_SEARCH_URL", raising=False)
        monkeypatch.delenv("CHAT_SKILLS_GOOGLE_SEARCH_URL", raising=False)
        r = run_google_search("anything")
        assert r.signal == "tool_error"
        assert "GOOGLE_SEARCH_URL" in r.text


class TestHappyPath:
    def test_results_shape_results_key(self):
        payload = {
            "results": [
                {"title": "Foo", "snippet": "A foo page", "url": "https://example.com/foo"},
                {"title": "Bar", "snippet": "A bar page", "url": "https://example.com/bar"},
            ]
        }
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
            r = run_google_search("foo bar", base_url="http://svc/search")
        assert r.signal == "ok"
        assert len(r.sources) == 2
        assert r.sources[0].source_type == "web"
        assert r.sources[0].url == "https://example.com/foo"
        assert r.sources[0].document_name == "example.com"
        assert "Foo" in r.text and "Bar" in r.text
        assert r.extra["query"] == "foo bar"
        assert len(r.extra["results"]) == 2

    def test_results_shape_items_key(self):
        """The upstream service can return 'items' instead of 'results' — accept both."""
        payload = {"items": [{"title": "T", "description": "D", "link": "https://e.com/p"}]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
            r = run_google_search("q", base_url="http://svc/search")
        assert r.signal == "ok"
        assert r.sources[0].url == "https://e.com/p"
        assert r.sources[0].text == "D"

    def test_max_results_clamped_to_ten(self):
        payload = {"results": [{"title": f"T{i}", "url": f"https://x/{i}"} for i in range(15)]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            r = run_google_search("q", max_results=50, base_url="http://svc/search")
        # Effective n=10
        assert len(r.sources) == 10
        # URL built with num=10
        called_url = m.call_args[0][0].full_url
        assert "num=10" in called_url

    def test_max_results_clamped_to_one(self):
        payload = {"results": [{"title": "T", "url": "https://x/1"}]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            run_google_search("q", max_results=0, base_url="http://svc/search")
        called_url = m.call_args[0][0].full_url
        assert "num=1" in called_url


class TestEmptyResults:
    def test_empty_results_list(self):
        with patch("urllib.request.urlopen", return_value=_fake_response({"results": []})):
            r = run_google_search("nothing matches", base_url="http://svc/search")
        assert r.signal == "no_sources"
        assert "No search results" in r.text

    def test_missing_results_key_treated_as_empty(self):
        with patch("urllib.request.urlopen", return_value=_fake_response({})):
            r = run_google_search("q", base_url="http://svc/search")
        assert r.signal == "no_sources"


class TestErrorPaths:
    def test_http_error_surfaces_as_tool_error(self):
        import urllib.error
        err = urllib.error.HTTPError("http://x", 500, "Server Error", {}, None)
        with patch("urllib.request.urlopen", side_effect=err):
            r = run_google_search("q", base_url="http://svc/search")
        assert r.signal == "tool_error"
        assert "HTTP 500" in r.text

    def test_url_error_surfaces_as_tool_error(self):
        import urllib.error
        err = urllib.error.URLError("connection refused")
        with patch("urllib.request.urlopen", side_effect=err):
            r = run_google_search("q", base_url="http://svc/search")
        assert r.signal == "tool_error"
        assert "network" in r.text

    def test_invalid_json_surfaces_as_tool_error(self):
        resp = MagicMock()
        resp.read.return_value = b"not-json-at-all"
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=resp):
            r = run_google_search("q", base_url="http://svc/search")
        assert r.signal == "tool_error"
        assert "invalid JSON" in r.text


class TestUrlConstruction:
    def test_url_encodes_query(self):
        payload = {"results": [{"title": "T", "url": "https://x/1"}]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            run_google_search("foo bar & baz", base_url="http://svc/search")
        called_url = m.call_args[0][0].full_url
        # urlencoded: space → +, & → %26
        assert "foo%20bar" in called_url or "foo+bar" in called_url
        # The important part — we never pass a raw '&' that'd corrupt the query string
        # (the url has its own &num=, so the encoded & from the query shows as %26)
        assert "%26" in called_url

    def test_base_url_with_trailing_slash_handled(self):
        payload = {"results": [{"title": "T", "url": "https://x/1"}]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            run_google_search("q", base_url="http://svc/search/")
        called_url = m.call_args[0][0].full_url
        assert "search?q=" in called_url  # no double slash

    def test_env_fallback_when_base_url_not_passed(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_SEARCH_URL", "http://env-svc/search")
        payload = {"results": [{"title": "T", "url": "https://x/1"}]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            run_google_search("q")
        called_url = m.call_args[0][0].full_url
        assert "env-svc" in called_url

    def test_legacy_env_name_accepted(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_SEARCH_URL", raising=False)
        monkeypatch.setenv("CHAT_SKILLS_GOOGLE_SEARCH_URL", "http://legacy/search")
        payload = {"results": [{"title": "T", "url": "https://x/1"}]}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            run_google_search("q")
        called_url = m.call_args[0][0].full_url
        assert "legacy" in called_url
