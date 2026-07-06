"""Unit tests for mobius_skills_core.skills.web_scrape."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from mobius_skills_core.skills.web_scrape import (
    WEB_SCRAPE_MODE_SPECS,
    WEB_SCRAPE_MODE_OUTPUT_CAPS,
    _normalize_mode,
    run_web_scrape,
)


def _fake_response(payload: dict):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestModeNormalization:
    def test_known_modes_pass_through(self):
        for m in ("quick", "medium", "detailed"):
            assert _normalize_mode(m) == m

    def test_uppercase_normalized(self):
        assert _normalize_mode("QUICK") == "quick"

    def test_unknown_clamps_to_quick(self):
        assert _normalize_mode("crazy") == "quick"
        assert _normalize_mode("") == "quick"
        assert _normalize_mode(None) == "quick"


class TestSpecContract:
    """Mode specs are the primary value of this module — lock their shape."""

    def test_three_modes_exist(self):
        assert set(WEB_SCRAPE_MODE_SPECS.keys()) == {"quick", "medium", "detailed"}

    def test_quick_is_single_page(self):
        assert WEB_SCRAPE_MODE_SPECS["quick"]["max_pages"] == 1
        assert WEB_SCRAPE_MODE_SPECS["quick"]["max_depth"] == 1

    def test_detailed_has_document_download_budget(self):
        assert WEB_SCRAPE_MODE_SPECS["detailed"]["max_doc_downloads"] == 10
        # Quick and medium don't
        assert WEB_SCRAPE_MODE_SPECS["quick"]["max_doc_downloads"] == 0
        assert WEB_SCRAPE_MODE_SPECS["medium"]["max_doc_downloads"] == 0

    def test_caps_monotonic(self):
        q, m, d = (WEB_SCRAPE_MODE_OUTPUT_CAPS[k] for k in ("quick", "medium", "detailed"))
        assert q < m < d


class TestInputValidation:
    def test_empty_url(self):
        r = run_web_scrape("", base_url="http://scr/")
        assert r.signal == "tool_error"
        assert "url is required" in r.text

    def test_invalid_scheme(self):
        r = run_web_scrape("file:///etc/passwd", base_url="http://scr/")
        assert r.signal == "tool_error"
        assert "http or https" in r.text

    def test_ftp_scheme_rejected(self):
        r = run_web_scrape("ftp://example.com", base_url="http://scr/")
        assert r.signal == "tool_error"

    def test_missing_base_url(self, monkeypatch):
        monkeypatch.delenv("WEB_SCRAPER_URL", raising=False)
        monkeypatch.delenv("CHAT_SKILLS_WEB_SCRAPER_URL", raising=False)
        r = run_web_scrape("https://example.com")
        assert r.signal == "tool_error"
        assert "WEB_SCRAPER_URL" in r.text


class TestHappyPath:
    def test_quick_mode_default(self):
        payload = {"text": "Page content here.", "summary": ""}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            r = run_web_scrape("https://example.com/foo", base_url="http://scr/scrape")

        assert r.signal == "ok"
        assert "Page content here" in r.text
        assert "scrape_mode: quick" in r.text
        assert r.sources[0].url == "https://example.com/foo"
        assert r.sources[0].document_name == "example.com"
        assert r.extra["mode"] == "quick"
        assert r.extra["truncated"] is False
        # Body should carry the spec for quick
        req = m.call_args[0][0]
        body = json.loads(req.data.decode())
        assert body["scrape_mode"] == "quick"
        assert body["max_pages"] == 1
        assert body["max_depth"] == 1

    def test_medium_mode_forwards_spec(self):
        payload = {"text": "x"}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            run_web_scrape("https://x.com", scrape_mode="medium", base_url="http://scr/")
        req = m.call_args[0][0]
        body = json.loads(req.data.decode())
        assert body["max_depth"] == 3
        assert body["max_pages"] == 6

    def test_unknown_mode_clamps_to_quick(self):
        payload = {"text": "x"}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            r = run_web_scrape("https://x.com", scrape_mode="nonsense", base_url="http://scr/")
        assert r.extra["mode"] == "quick"
        req = m.call_args[0][0]
        body = json.loads(req.data.decode())
        assert body["scrape_mode"] == "quick"

    def test_truncation_flag_when_text_exceeds_cap(self):
        # Quick cap = 8000
        long_text = "A" * 10_000
        with patch("urllib.request.urlopen", return_value=_fake_response({"text": long_text})):
            r = run_web_scrape("https://x.com", base_url="http://scr/")
        assert r.extra["truncated"] is True
        assert "[... truncated ...]" in r.text
        # Content in r.text is capped
        assert r.text.count("A") == 8_000

    def test_no_truncation_below_cap(self):
        with patch("urllib.request.urlopen", return_value=_fake_response({"text": "A" * 100})):
            r = run_web_scrape("https://x.com", base_url="http://scr/")
        assert r.extra["truncated"] is False
        assert "[... truncated ...]" not in r.text

    def test_summary_appended_when_requested_and_present(self):
        payload = {"text": "body", "summary": "one-line summary"}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)) as m:
            r = run_web_scrape(
                "https://x.com",
                include_summary=True,
                base_url="http://scr/",
            )
        assert "Summary: one-line summary" in r.text
        assert r.extra["summary"] == "one-line summary"
        req = m.call_args[0][0]
        body = json.loads(req.data.decode())
        assert body["include_summary"] is True

    def test_summary_absent_when_empty_in_response(self):
        with patch("urllib.request.urlopen", return_value=_fake_response({"text": "body"})):
            r = run_web_scrape("https://x.com", base_url="http://scr/")
        assert "Summary:" not in r.text
        assert r.extra["summary"] is None


class TestEmptyScrape:
    def test_empty_text_returns_no_sources(self):
        with patch("urllib.request.urlopen", return_value=_fake_response({"text": ""})):
            r = run_web_scrape("https://example.com/empty", base_url="http://scr/")
        assert r.signal == "no_sources"
        assert "No content extracted" in r.text
        # Still returns a source ref so integrators can attribute the attempt
        assert len(r.sources) == 1
        assert r.sources[0].url == "https://example.com/empty"


class TestErrorPaths:
    def test_http_error_includes_body_snippet(self):
        import urllib.error, io
        # HTTPError with a body
        fp = io.BytesIO(b"Upstream blocked this URL")
        err = urllib.error.HTTPError("http://x", 503, "Unavailable", {}, fp)
        with patch("urllib.request.urlopen", side_effect=err):
            r = run_web_scrape("https://x.com", base_url="http://scr/")
        assert r.signal == "tool_error"
        assert "HTTP 503" in r.text

    def test_network_error(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            r = run_web_scrape("https://x.com", base_url="http://scr/")
        assert r.signal == "tool_error"
        assert "network" in r.text

    def test_bad_json_response(self):
        resp = MagicMock()
        resp.read.return_value = b"not-json"
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=resp):
            r = run_web_scrape("https://x.com", base_url="http://scr/")
        assert r.signal == "tool_error"
        assert "invalid JSON" in r.text


class TestEnvFallback:
    def test_canonical_env_name(self, monkeypatch):
        monkeypatch.setenv("WEB_SCRAPER_URL", "http://env-scr/")
        with patch("urllib.request.urlopen", return_value=_fake_response({"text": "x"})) as m:
            run_web_scrape("https://x.com")
        assert "env-scr" in m.call_args[0][0].full_url

    def test_legacy_env_name(self, monkeypatch):
        monkeypatch.delenv("WEB_SCRAPER_URL", raising=False)
        monkeypatch.setenv("CHAT_SKILLS_WEB_SCRAPER_URL", "http://legacy-scr/")
        with patch("urllib.request.urlopen", return_value=_fake_response({"text": "x"})) as m:
            run_web_scrape("https://x.com")
        assert "legacy-scr" in m.call_args[0][0].full_url
