"""Tests for the feedback classifier service.

The LLM call (``app.llm_client.llm_complete``) is monkeypatched so tests are
deterministic and offline.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

import app.main as main
from app.main import _parse_json, app
from app.policy import coerce_category, coerce_sentiment, coerce_severity, route_for

client = TestClient(app)


def _stub_llm(payload: dict):
    def _fn(*args, **kwargs):
        return json.dumps(payload), {"model": "stub", "provider": "test"}
    return _fn


# ---- health -----------------------------------------------------------------

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "mobius-feedback"


# ---- JSON extraction --------------------------------------------------------

def test_parse_plain_json():
    assert _parse_json('{"a": 1}') == {"a": 1}


def test_parse_fenced_json():
    assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_with_prose_around():
    assert _parse_json('Here you go:\n{"a": 1}\nDone.') == {"a": 1}


# ---- coercion ---------------------------------------------------------------

def test_coerce_offtaxonomy_falls_back():
    assert coerce_category("nonsense") == "other"
    assert coerce_category("BUG") == "bug"
    assert coerce_sentiment("angry") == "neutral"
    assert coerce_severity("critical") == "low"


def test_routing():
    assert route_for("bug") == "triage_queue"
    assert route_for("coverage_gap") == "corpus_backlog"
    assert route_for("praise") == "none"
    assert route_for("feature_request") == "product_backlog"


# ---- classify happy path ----------------------------------------------------

def test_classify_happy_path(monkeypatch):
    monkeypatch.setattr(main, "llm_complete", _stub_llm({
        "category": "coverage_gap",
        "sentiment": "negative",
        "severity": "high",
        "summary": "Ohio Medicaid fee schedule missing",
        "tidied": "The Ohio Medicaid fee schedule is not in the corpus.",
    }))
    r = client.post("/classify", json={
        "verbatim": "you don't have the ohio medicaid fee schedule, keep getting no source",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["classification"]["category"] == "coverage_gap"
    assert body["classification"]["severity"] == "high"
    assert body["routed_to"] == "corpus_backlog"
    assert body["skipped"] is False


def test_classify_offtaxonomy_is_coerced(monkeypatch):
    monkeypatch.setattr(main, "llm_complete", _stub_llm({
        "category": "totally_made_up",
        "sentiment": "furious",
        "severity": "sev1",
        "summary": "x",
        "tidied": "y",
    }))
    r = client.post("/classify", json={"verbatim": "something"})
    body = r.json()
    assert body["classification"]["category"] == "other"
    assert body["classification"]["sentiment"] == "neutral"
    assert body["classification"]["severity"] == "low"


def test_classify_empty_verbatim_skips():
    r = client.post("/classify", json={"verbatim": "   "})
    body = r.json()
    assert body["skipped"] is True
    assert body["reason"] == "empty_verbatim"


def test_classify_llm_failure_falls_back(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("router down")
    monkeypatch.setattr(main, "llm_complete", _boom)
    r = client.post("/classify", json={
        "verbatim": "the sidebar is confusing",
        "provisional_category": "usability",
    })
    body = r.json()
    assert body["reason"] == "llm_unavailable"
    # falls back to the provisional category, keeps the user's words
    assert body["classification"]["category"] == "usability"
    assert "sidebar" in body["classification"]["tidied"]


def test_classify_unparseable_output_falls_back(monkeypatch):
    monkeypatch.setattr(main, "llm_complete",
                        lambda *a, **k: ("not json at all", {}))
    r = client.post("/classify", json={"verbatim": "it's too slow"})
    body = r.json()
    assert body["reason"] == "parse_failed"
    assert "slow" in body["classification"]["tidied"]
