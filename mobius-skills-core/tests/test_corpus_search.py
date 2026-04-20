"""Unit tests for mobius_skills_core.skills.corpus_search.

These tests never touch a real Chroma index or Postgres. Both backends
are mocked, and the metadata hydration path is exercised against a
fake ``db_query_fn`` that returns preset rows. Contract tests lock:

  * Input validation — empty query, missing backend, missing db path.
  * Backend selection — Chroma wins when both are set.
  * Metadata hydration — db_query_fn preferred; falls back to
    psycopg2 when not supplied.
  * Ordering — final chunk order matches vector-store ranking.
  * Distance → similarity conversion.
  * SkillResult shape — chunks + sources + signal + extra.
  * Emit contract at every boundary.
  * Graceful handling when vector hits but metadata rows are missing.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mobius_skills_core import SkillEvent
from mobius_skills_core.skills.corpus_search import (
    ChromaConfig,
    CorpusFilters,
    VertexConfig,
    run_corpus_search,
)


# ── Test doubles ─────────────────────────────────────────────────────


def _fake_embed(_q: str) -> list[float]:
    """Deterministic fake embedding (dim=1536 like production)."""
    return [0.1] * 1536


def _chroma_result(ids: list[str], distances: list[float]) -> dict:
    """Build the dict shape Chroma.query() returns."""
    return {
        "ids": [ids],
        "distances": [distances],
    }


class _MockChromaCollection:
    """Stand-in for a chromadb Collection."""
    def __init__(self, response: dict):
        self._response = response
        self.last_query: dict = {}

    def query(self, query_embeddings, n_results, where=None, include=None):
        self.last_query = {
            "n_results": n_results,
            "where": where,
            "include": include,
        }
        return self._response


def _fake_chroma_factory(response: dict) -> MagicMock:
    """Patch target for _get_chroma_collection — returns a collection
    that replies with the supplied response dict."""
    collection = _MockChromaCollection(response)
    m = MagicMock()
    m.return_value = collection
    m._collection = collection
    return m


def _db_query_hit(rows: list[dict]):
    """Build a ``db_query_fn`` side_effect that returns a db-agent-shaped
    response."""
    def fn(sql, db, params=None, max_rows=1000):
        cols = list(rows[0].keys()) if rows else []
        return {
            "columns": cols,
            "rows": [[r.get(c) for c in cols] for r in rows],
            "row_count": len(rows),
            "truncated": False,
        }
    return fn


def _db_query_error(msg: str):
    def fn(sql, db, params=None, max_rows=1000):
        return {"error": {"code": "relation_missing", "message": msg}}
    return fn


class _Collector:
    def __init__(self):
        self.events: list[SkillEvent] = []
    def __call__(self, event: SkillEvent) -> None:
        self.events.append(event)


_CHROMA = ChromaConfig(persist_dir="/tmp/fake-chroma", collection="published_rag")


# ── Input validation ─────────────────────────────────────────────────


class TestInputValidation:
    def test_empty_query(self):
        r = run_corpus_search(
            "",
            embed_query=_fake_embed,
            chroma=_CHROMA,
            db_query_fn=_db_query_hit([]),
        )
        assert r.signal == "tool_error"
        assert "query is required" in r.text

    def test_no_backend_configured(self):
        r = run_corpus_search(
            "Sunshine H0036",
            embed_query=_fake_embed,
            db_query_fn=_db_query_hit([]),
        )
        assert r.signal == "tool_error"
        assert "neither chroma nor vertex" in r.text

    def test_no_db_path_configured(self):
        r = run_corpus_search(
            "x",
            embed_query=_fake_embed,
            chroma=_CHROMA,
        )
        assert r.signal == "tool_error"
        assert "no metadata path" in r.text


# ── Chroma happy path ────────────────────────────────────────────────


class TestChromaBackend:
    def test_ids_returned_in_ranking_order(self):
        response = _chroma_result(["id-1", "id-2", "id-3"], [0.2, 0.4, 0.6])
        rows = [
            {"id": "id-3", "document_id": "doc-c", "document_display_name": "C",
             "text": "third", "page_number": 3, "paragraph_index": 0,
             "source_type": "chunk", "document_filename": "c.pdf"},
            {"id": "id-1", "document_id": "doc-a", "document_display_name": "A",
             "text": "first", "page_number": 1, "paragraph_index": 0,
             "source_type": "chunk", "document_filename": "a.pdf"},
            {"id": "id-2", "document_id": "doc-b", "document_display_name": "B",
             "text": "second", "page_number": 2, "paragraph_index": 0,
             "source_type": "chunk", "document_filename": "b.pdf"},
        ]
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=_MockChromaCollection(response),
        ):
            r = run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA, db_query_fn=_db_query_hit(rows),
            )
        assert r.signal == "ok"
        # Must come back in vector-store order (id-1, id-2, id-3), not DB order
        names = [c.document_name for c in r.chunks]
        assert names == ["A", "B", "C"]
        # Source index matches ranking
        assert [s.index for s in r.sources] == [1, 2, 3]

    def test_distance_to_similarity_conversion(self):
        # distance 0 → similarity 1.0, distance 2 → similarity 0.0
        response = _chroma_result(["id-1", "id-2"], [0.0, 2.0])
        rows = [
            {"id": "id-1", "document_id": "d", "document_display_name": "D",
             "text": "t", "page_number": 1, "paragraph_index": 0,
             "source_type": "chunk", "document_filename": ""},
            {"id": "id-2", "document_id": "d", "document_display_name": "D",
             "text": "t", "page_number": 2, "paragraph_index": 0,
             "source_type": "chunk", "document_filename": ""},
        ]
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=_MockChromaCollection(response),
        ):
            r = run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA, db_query_fn=_db_query_hit(rows),
            )
        assert r.chunks[0].score == 1.0   # distance 0 → max similarity
        assert r.chunks[1].score == 0.0   # distance 2 → zero similarity

    def test_filters_applied_to_chroma_where(self):
        response = _chroma_result(["id-1"], [0.3])
        rows = [{"id": "id-1", "document_id": "d",
                 "document_display_name": "D", "text": "t",
                 "page_number": 1, "paragraph_index": 0,
                 "source_type": "policy", "document_filename": ""}]
        collection = _MockChromaCollection(response)
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=collection,
        ):
            run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA,
                filters=CorpusFilters(
                    payer="Sunshine Health",
                    state="FL",
                    source_type_allow=["policy", "summary"],
                ),
                db_query_fn=_db_query_hit(rows),
            )
        where = collection.last_query["where"]
        # 3 conditions → $and shape
        assert "$and" in where
        kinds = [list(c.keys())[0] for c in where["$and"]]
        assert "document_payer" in kinds
        assert "document_state" in kinds
        assert "source_type" in kinds

    def test_single_filter_no_and_wrapper(self):
        response = _chroma_result(["id-1"], [0.3])
        rows = [{"id": "id-1", "document_id": "d",
                 "document_display_name": "D", "text": "t",
                 "page_number": 1, "paragraph_index": 0,
                 "source_type": "chunk", "document_filename": ""}]
        collection = _MockChromaCollection(response)
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=collection,
        ):
            run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA,
                filters=CorpusFilters(payer="Sunshine Health"),
                db_query_fn=_db_query_hit(rows),
            )
        where = collection.last_query["where"]
        # Single filter — no $and wrapping
        assert where == {"document_payer": "Sunshine Health"}

    def test_no_vector_hits_returns_no_sources(self):
        response = _chroma_result([], [])
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=_MockChromaCollection(response),
        ):
            r = run_corpus_search(
                "obscure query", embed_query=_fake_embed,
                chroma=_CHROMA, db_query_fn=_db_query_hit([]),
            )
        assert r.signal == "no_sources"
        assert r.chunks == []

    def test_vector_hits_but_no_metadata_rows(self):
        """Sync lag: vector store returned ids, Postgres has no rows."""
        response = _chroma_result(["id-missing"], [0.2])
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=_MockChromaCollection(response),
        ):
            r = run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA, db_query_fn=_db_query_hit([]),
            )
        assert r.signal == "no_sources"
        assert "out of sync" in r.text
        assert r.extra["vector_hit_count"] == 1


# ── Metadata hydration paths ─────────────────────────────────────────


class TestMetadataHydration:
    def test_db_agent_path_preferred(self):
        """When both db_query_fn and database_url are set, db_query_fn wins."""
        response = _chroma_result(["id-1"], [0.3])
        rows = [{"id": "id-1", "document_id": "d",
                 "document_display_name": "D", "text": "t",
                 "page_number": 1, "paragraph_index": 0,
                 "source_type": "chunk", "document_filename": ""}]

        db_calls = []
        def fn(sql, db, params=None, max_rows=1000):
            db_calls.append({"db": db, "ids": params["ids"] if params else None})
            return {
                "columns": list(rows[0].keys()),
                "rows": [[r.get(c) for c in rows[0].keys()] for r in rows],
            }

        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=_MockChromaCollection(response),
        ):
            r = run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA,
                db_query_fn=fn, database="chat",
                database_url="postgresql://nope/there",  # should NOT be used
            )
        assert db_calls[0]["db"] == "chat"
        assert db_calls[0]["ids"] == ["id-1"]
        assert r.signal == "ok"

    def test_db_agent_error_surfaces_as_tool_error(self):
        # db-agent returns structured error → skill returns no_sources
        # (empty row set) since _hydrate returns [] on error. Vector
        # hit with no metadata row → the "sync lag" no_sources branch.
        response = _chroma_result(["id-1"], [0.3])
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=_MockChromaCollection(response),
        ):
            r = run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA,
                db_query_fn=_db_query_error("relation does not exist"),
            )
        assert r.signal == "no_sources"


# ── Emit contract ────────────────────────────────────────────────────


class TestEmits:
    def test_happy_path_invoked_then_completed(self):
        response = _chroma_result(["id-1"], [0.3])
        rows = [{"id": "id-1", "document_id": "d",
                 "document_display_name": "D", "text": "t",
                 "page_number": 1, "paragraph_index": 0,
                 "source_type": "chunk", "document_filename": ""}]
        c = _Collector()
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=_MockChromaCollection(response),
        ):
            run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA, db_query_fn=_db_query_hit(rows),
                emitter=c,
            )
        signals = [e.signal for e in c.events]
        assert signals == ["tool_invoked", "tool_completed"]
        # tool_completed carries chunk_count
        assert c.events[-1].data["chunk_count"] == 1

    def test_empty_query_no_invoked_fired(self):
        c = _Collector()
        run_corpus_search(
            "", embed_query=_fake_embed,
            chroma=_CHROMA, db_query_fn=_db_query_hit([]),
            emitter=c,
        )
        # Short-circuits before tool_invoked
        assert [e.signal for e in c.events] == ["tool_error"]

    def test_no_backend_blocker_severity(self):
        c = _Collector()
        run_corpus_search(
            "q", embed_query=_fake_embed,
            db_query_fn=_db_query_hit([]), emitter=c,
        )
        assert c.events[0].task_type == "blocker"
        assert c.events[0].task_severity == "high"

    def test_embed_failure_emits_tool_error(self):
        def boom(_q):
            raise RuntimeError("embed service down")
        c = _Collector()
        r = run_corpus_search(
            "q", embed_query=boom,
            chroma=_CHROMA, db_query_fn=_db_query_hit([]),
            emitter=c,
        )
        assert r.signal == "tool_error"
        err_events = [e for e in c.events if e.signal == "tool_error"]
        assert any(e.data.get("error_type") == "embed" for e in err_events)

    def test_vector_search_failure_emits_tool_error(self):
        def boom_collection(*_a, **_kw):
            raise RuntimeError("chroma broken")
        c = _Collector()
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            side_effect=boom_collection,
        ):
            r = run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA, db_query_fn=_db_query_hit([]),
                emitter=c,
            )
        assert r.signal == "tool_error"
        err_events = [e for e in c.events if e.signal == "tool_error"]
        assert any(e.data.get("error_type") == "vector" for e in err_events)

    def test_no_emitter_ok(self):
        response = _chroma_result(["id-1"], [0.3])
        rows = [{"id": "id-1", "document_id": "d",
                 "document_display_name": "D", "text": "t",
                 "page_number": 1, "paragraph_index": 0,
                 "source_type": "chunk", "document_filename": ""}]
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=_MockChromaCollection(response),
        ):
            r = run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA, db_query_fn=_db_query_hit(rows),
            )
        assert r.signal == "ok"


# ── SkillResult shape ────────────────────────────────────────────────


class TestResultShape:
    def test_source_preview_truncated_at_300(self):
        long_text = "A" * 500
        response = _chroma_result(["id-1"], [0.3])
        rows = [{"id": "id-1", "document_id": "d",
                 "document_display_name": "D", "text": long_text,
                 "page_number": 1, "paragraph_index": 0,
                 "source_type": "chunk", "document_filename": ""}]
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=_MockChromaCollection(response),
        ):
            r = run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA, db_query_fn=_db_query_hit(rows),
            )
        assert r.sources[0].text.endswith("…")
        assert len(r.sources[0].text) <= 301  # 300 + ellipsis
        # chunks retain full text
        assert r.chunks[0].text == long_text

    def test_chunk_metadata_contains_distance(self):
        response = _chroma_result(["id-1"], [0.7])
        rows = [{"id": "id-1", "document_id": "d",
                 "document_display_name": "D", "text": "t",
                 "page_number": 1, "paragraph_index": 5,
                 "source_type": "chunk", "document_filename": ""}]
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=_MockChromaCollection(response),
        ):
            r = run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA, db_query_fn=_db_query_hit(rows),
            )
        md = r.chunks[0].metadata
        assert md["distance"] == 0.7
        assert md["source_type"] == "chunk"
        assert md["paragraph_index"] == 5

    def test_fallback_to_document_filename_when_display_name_empty(self):
        response = _chroma_result(["id-1"], [0.3])
        rows = [{"id": "id-1", "document_id": "d",
                 "document_display_name": None, "text": "t",
                 "page_number": 1, "paragraph_index": 0,
                 "source_type": "chunk", "document_filename": "fallback.pdf"}]
        with patch(
            "mobius_skills_core.skills.corpus_search._get_chroma_collection",
            return_value=_MockChromaCollection(response),
        ):
            r = run_corpus_search(
                "q", embed_query=_fake_embed,
                chroma=_CHROMA, db_query_fn=_db_query_hit(rows),
            )
        assert r.chunks[0].document_name == "fallback.pdf"
