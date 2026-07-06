"""Feedback classification taxonomy + coercion/validation.

The LLM is asked to return one of these enum values; ``coerce_*`` maps anything
off-taxonomy back onto a safe default so a bad generation never breaks the caller.
"""
from __future__ import annotations

CATEGORIES = {
    "accuracy_trust",   # wrong / unsupported answer, bad sources
    "coverage_gap",     # missing payer / state / topic in the corpus
    "bug",              # something broke or errored
    "speed",            # too slow
    "usability",        # confusing UI / navigation
    "feature_request",  # "I wish it could…"
    "praise",           # what's working well
    "other",            # anything else
}
DEFAULT_CATEGORY = "other"

SENTIMENTS = {"positive", "negative", "neutral", "mixed"}
DEFAULT_SENTIMENT = "neutral"

SEVERITIES = {"low", "medium", "high"}
DEFAULT_SEVERITY = "low"

# Category → where the item should be routed downstream (chat-side applies this).
ROUTING = {
    "accuracy_trust": "triage_queue",
    "bug": "triage_queue",
    "coverage_gap": "corpus_backlog",
    "speed": "product_backlog",
    "usability": "product_backlog",
    "feature_request": "product_backlog",
    "other": "product_backlog",
    "praise": "none",
}

MAX_SUMMARY_CHARS = 160
MAX_TIDIED_CHARS = 600


def coerce_category(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v if v in CATEGORIES else DEFAULT_CATEGORY


def coerce_sentiment(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v if v in SENTIMENTS else DEFAULT_SENTIMENT


def coerce_severity(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v if v in SEVERITIES else DEFAULT_SEVERITY


def route_for(category: str) -> str:
    return ROUTING.get(category, "product_backlog")
