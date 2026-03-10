"""Tests for mobius-skills-mcp tool validation (google_search, web_scrape_review)."""

import pytest
from unittest.mock import patch

# Import the tool functions directly (they are plain functions under the decorator)
from app.server import google_search, web_scrape_review


def test_mobius_skills_mcp_google_search_empty_query():
    """Empty or whitespace-only query returns error, no HTTP call."""
    assert google_search("") == "Error: query is required and cannot be empty."
    assert google_search("   ") == "Error: query is required and cannot be empty."
    assert google_search("\t\n") == "Error: query is required and cannot be empty."


def test_mobius_skills_mcp_web_scrape_invalid_url():
    """Invalid URL (empty or non-http(s) scheme) returns error."""
    assert web_scrape_review("") == "Error: url is required."
    assert web_scrape_review("   ") == "Error: url is required."
    assert web_scrape_review("ftp://example.com") == "Error: url must use http or https scheme."
    assert web_scrape_review("javascript:alert(1)") == "Error: url must use http or https scheme."
    assert web_scrape_review("file:///etc/passwd") == "Error: url must use http or https scheme."


def test_mobius_skills_mcp_google_search_config_missing():
    """When GOOGLE_SEARCH_URL not configured, returns config error."""
    with patch("app.server.GOOGLE_SEARCH_URL", ""):
        result = google_search("Florida Medicaid")
        assert "Error: CHAT_SKILLS_GOOGLE_SEARCH_URL not configured" in result


def test_mobius_skills_mcp_web_scrape_config_missing():
    """When WEB_SCRAPER_URL not configured, returns config error."""
    with patch("app.server.WEB_SCRAPER_URL", ""):
        result = web_scrape_review("https://example.com")
        assert "Error: CHAT_SKILLS_WEB_SCRAPER_URL not configured" in result
