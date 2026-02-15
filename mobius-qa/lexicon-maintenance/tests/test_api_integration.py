"""Integration tests: require API running at LEXICON_API_URL (default localhost:8010)."""
import os
import pytest
import requests

API_BASE = os.getenv("LEXICON_API_URL", "http://localhost:8010")


def _api_available() -> bool:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _api_available(), reason="Lexicon API not running at " + API_BASE)
class TestLexiconAPI:
    """Integration tests against live API."""

    def test_health(self):
        r = requests.get(f"{API_BASE}/health", timeout=5)
        r.raise_for_status()
        j = r.json()
        assert j.get("status") == "ok"

    def test_policy_lexicon(self):
        r = requests.get(f"{API_BASE}/policy/lexicon", timeout=5)
        r.raise_for_status()
        j = r.json()
        assert "lexicon_version" in j
        assert "lexicon_revision" in j
        assert "tags" in j

    def test_overview_proposed(self):
        r = requests.get(
            f"{API_BASE}/policy/lexicon/overview",
            params={"status": "proposed", "limit": 10, "min_score": "0"},
            timeout=5,
        )
        r.raise_for_status()
        j = r.json()
        assert "rows" in j
        assert "lexicon_version" in j
