"""Tests for lazy_rag + its two wrapper skills.

Covers:
  * run_lazy_rag — generic filter-dispatched vector search.
  * run_thread_corpus_search — wrapped filter for a single upload.
  * run_lazy_corpus_search — wrapped filter for the approved corpus
    with optional include_uploads.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mobius_skills_core import SkillEvent
from mobius_skills_core.skills.corpus_search import ChromaConfig, CorpusFilters
from mobius_skills_core.skills.lazy_rag import run_lazy_rag
from mobius_skills_core.skills.lazy_corpus_search import run_lazy_corpus_search
from mobius_skills_core.skills.thread_corpus_search import run_thread_corpus_search


def _fake_embed(_q: str) -> list[float]:
    return [0.1] * 1536


class _FakeChromaCollection:
    def __init__(self, response: dict, probe_response: dict | None = None):
        self.response = response
        self.probe_response = probe_response or {"ids": []}
        self.last_query: dict = {}

    def query(self, query_embeddings, n_results, where=None, include=None):
        self.last_query = {"n_results": n_results, "where": where, "include": include}
        return self.response

    def get(self, where=None, limit=1):
        return self.probe_response


def _chroma_resp(chunks: list[tuple[str, str, dict, float]]) -> dict:
    """Build the response shape Chroma's .query returns. Each chunk:
    (id, text, metadata_dict, distance)."""
    if not chunks:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    ids, docs, metas, dists = zip(*chunks)
    return {
        "ids": [list(ids)],
        "documents": [list(docs)],
        "metadatas": [list(metas)],
        "distances": [list(dists)],
    }


class _Collector:
    def __init__(self):
        self.events: list[SkillEvent] = []
    def __call__(self, event: SkillEvent) -> None:
        self.events.append(event)


_CHROMA = ChromaConfig(persist_dir="/tmp/fake", collection="published_rag")


# ── run_lazy_rag (generic) ───────────────────────────────────────────


class TestRunLazyRag:
    def test_empty_query_tool_error(self):
        r = run_lazy_rag("", embed_query=_fake_embed, chroma=_CHROMA)
        assert r.signal == "tool_error"

    def test_happy_path_returns_chunks_in_order(self):
        chunks = [
            ("id-1", "First chunk text", {"document_id": "d1", "display_name": "Doc A", "page_number": 1}, 0.2),
            ("id-2", "Second chunk text", {"document_id": "d1", "display_name": "Doc A", "page_number": 2}, 0.4),
        ]
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=_FakeChromaCollection(_chroma_resp(chunks)),
        ):
            r = run_lazy_rag("q", embed_query=_fake_embed, chroma=_CHROMA)
        assert r.signal == "ok"
        assert len(r.chunks) == 2
        # Text preserved in chunks, truncated+… in sources
        assert r.chunks[0].text == "First chunk text"
        # Scoring: 1 - distance/2
        assert r.chunks[0].score == round(1.0 - 0.2 / 2, 4)
        # Separator-joined in .text for LLM consumption
        assert "First chunk text" in r.text
        assert "---" in r.text
        assert "Second chunk text" in r.text

    def test_empty_chunks_sets_vector_count_hint(self):
        """When Chroma returns nothing, probe how many vectors match
        the filter — tells diagnostics whether filter matches nothing
        vs. similarity was too low."""
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=_FakeChromaCollection(_chroma_resp([]), probe_response={"ids": ["x"]}),
        ):
            r = run_lazy_rag("q", embed_query=_fake_embed, chroma=_CHROMA)
        assert r.signal == "no_sources"
        # probe returned 1 → similarity missed, not filter mismatch
        assert r.extra["vector_count_hint"] == 1

    def test_where_passed_through(self):
        collection = _FakeChromaCollection(_chroma_resp([]))
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=collection,
        ):
            run_lazy_rag(
                "q", embed_query=_fake_embed, chroma=_CHROMA,
                where={"custom_key": "custom_value"}, k=5,
            )
        assert collection.last_query["where"] == {"custom_key": "custom_value"}
        assert collection.last_query["n_results"] == 5

    def test_embed_failure_emits_tool_error(self):
        def boom(_q):
            raise RuntimeError("embed down")
        c = _Collector()
        r = run_lazy_rag("q", embed_query=boom, chroma=_CHROMA, emitter=c)
        assert r.signal == "tool_error"
        err_events = [e for e in c.events if e.signal == "tool_error"]
        assert any(e.data.get("error_type") == "embed" for e in err_events)

    def test_empty_text_chunks_filtered(self):
        chunks = [
            ("id-1", "", {"document_id": "d1"}, 0.2),      # empty
            ("id-2", "   ", {"document_id": "d1"}, 0.3),   # whitespace
            ("id-3", "real text", {"document_id": "d1"}, 0.4),
        ]
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=_FakeChromaCollection(_chroma_resp(chunks)),
        ):
            r = run_lazy_rag("q", embed_query=_fake_embed, chroma=_CHROMA)
        # Only the non-empty chunk comes through
        assert len(r.chunks) == 1
        assert r.chunks[0].text == "real text"

    def test_all_chunks_empty_returns_no_sources(self):
        chunks = [("id-1", "", {"document_id": "d1"}, 0.2)]
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=_FakeChromaCollection(_chroma_resp(chunks)),
        ):
            r = run_lazy_rag("q", embed_query=_fake_embed, chroma=_CHROMA)
        assert r.signal == "no_sources"

    def test_chroma_open_failure(self):
        c = _Collector()
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            side_effect=RuntimeError("cannot open chroma"),
        ):
            r = run_lazy_rag("q", embed_query=_fake_embed, chroma=_CHROMA, emitter=c)
        assert r.signal == "tool_error"
        assert "chroma" in r.text.lower()

    def test_step_id_override_reflected_in_emits(self):
        c = _Collector()
        chunks = [("id-1", "text", {"document_id": "d1"}, 0.2)]
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=_FakeChromaCollection(_chroma_resp(chunks)),
        ):
            run_lazy_rag(
                "q", embed_query=_fake_embed, chroma=_CHROMA,
                step_id="thread_corpus_search", emitter=c,
            )
        assert all(e.step_id == "thread_corpus_search" for e in c.events)

    def test_metadata_fallback_chain(self):
        """display_name > document_display_name > filename > document_filename > default."""
        cases = [
            ({"display_name": "A"}, "A"),
            ({"document_display_name": "B"}, "B"),
            ({"filename": "c.pdf"}, "c.pdf"),
            ({"document_filename": "d.pdf"}, "d.pdf"),
            ({}, "document"),  # pure default
        ]
        for meta, expected_name in cases:
            chunks = [("id-1", "text", {"document_id": "d1", **meta}, 0.2)]
            with patch(
                "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
                return_value=_FakeChromaCollection(_chroma_resp(chunks)),
            ):
                r = run_lazy_rag(
                    "q", embed_query=_fake_embed, chroma=_CHROMA,
                )
            assert r.chunks[0].document_name == expected_name, (
                f"meta={meta} expected={expected_name} got={r.chunks[0].document_name}"
            )

    def test_authority_label_user_asserted_when_instant_rag(self):
        chunks = [("id-1", "text", {"document_id": "d1", "instant_rag": "true"}, 0.2)]
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=_FakeChromaCollection(_chroma_resp(chunks)),
        ):
            r = run_lazy_rag("q", embed_query=_fake_embed, chroma=_CHROMA)
        assert r.sources[0].authority == "user-asserted"

    def test_authority_label_corpus_when_approved(self):
        chunks = [("id-1", "text", {"document_id": "d1"}, 0.2)]  # no instant_rag key
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=_FakeChromaCollection(_chroma_resp(chunks)),
        ):
            r = run_lazy_rag("q", embed_query=_fake_embed, chroma=_CHROMA)
        assert r.sources[0].authority == "corpus"


# ── run_thread_corpus_search ────────────────────────────────────────


class TestThreadCorpusSearch:
    def test_empty_document_id_returns_no_sources(self):
        r = run_thread_corpus_search(
            "", "question", embed_query=_fake_embed, chroma=_CHROMA,
        )
        assert r.signal == "no_sources"
        assert r.extra["reason"] == "empty_document_id"

    def test_filter_scopes_to_document_and_instant_rag(self):
        collection = _FakeChromaCollection(_chroma_resp([]))
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=collection,
        ):
            run_thread_corpus_search(
                "doc-abc", "question", embed_query=_fake_embed, chroma=_CHROMA,
            )
        where = collection.last_query["where"]
        assert "$and" in where
        conditions = where["$and"]
        # Both scopes present
        assert {"document_id": "doc-abc"} in conditions
        assert {"instant_rag": "true"} in conditions

    def test_happy_path_sets_authority_user_asserted(self):
        chunks = [("id-1", "text", {"document_id": "doc-abc", "instant_rag": "true"}, 0.2)]
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=_FakeChromaCollection(_chroma_resp(chunks)),
        ):
            r = run_thread_corpus_search(
                "doc-abc", "question", embed_query=_fake_embed, chroma=_CHROMA,
            )
        assert r.signal == "ok"
        assert r.sources[0].authority == "user-asserted"

    def test_default_document_name_for_missing_metadata(self):
        chunks = [("id-1", "text", {"document_id": "doc-abc", "instant_rag": "true"}, 0.2)]
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=_FakeChromaCollection(_chroma_resp(chunks)),
        ):
            r = run_thread_corpus_search(
                "doc-abc", "q", embed_query=_fake_embed, chroma=_CHROMA,
            )
        # thread wrapper sets "Uploaded document" as default
        assert r.chunks[0].document_name == "Uploaded document"

    def test_step_id_is_thread_corpus_search(self):
        c = _Collector()
        run_thread_corpus_search(
            "", "q", embed_query=_fake_embed, chroma=_CHROMA, emitter=c,
        )
        assert c.events[0].step_id == "thread_corpus_search"


# ── run_lazy_corpus_search ──────────────────────────────────────────


class TestLazyCorpusSearch:
    def test_default_excludes_uploads(self):
        """Without include_uploads, the $ne filter is added."""
        collection = _FakeChromaCollection(_chroma_resp([]))
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=collection,
        ):
            run_lazy_corpus_search("q", embed_query=_fake_embed, chroma=_CHROMA)
        where = collection.last_query["where"]
        assert where == {"instant_rag": {"$ne": "true"}}

    def test_include_uploads_true_no_exclusion(self):
        collection = _FakeChromaCollection(_chroma_resp([]))
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=collection,
        ):
            run_lazy_corpus_search(
                "q", embed_query=_fake_embed, chroma=_CHROMA,
                include_uploads=True,
            )
        # No filter at all — approve + upload mixed
        assert collection.last_query["where"] is None

    def test_filters_combined_with_instant_rag_exclusion(self):
        collection = _FakeChromaCollection(_chroma_resp([]))
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=collection,
        ):
            run_lazy_corpus_search(
                "q", embed_query=_fake_embed, chroma=_CHROMA,
                filters=CorpusFilters(payer="Sunshine Health", state="FL"),
            )
        where = collection.last_query["where"]
        conditions = where["$and"]
        assert {"document_payer": "Sunshine Health"} in conditions
        assert {"document_state": "FL"} in conditions
        assert {"instant_rag": {"$ne": "true"}} in conditions

    def test_default_k_is_16_capture_oriented(self):
        """Higher default than corpus_search's 10 — recall over precision."""
        collection = _FakeChromaCollection(_chroma_resp([]))
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=collection,
        ):
            run_lazy_corpus_search("q", embed_query=_fake_embed, chroma=_CHROMA)
        assert collection.last_query["n_results"] == 16

    def test_step_id_is_lazy_corpus_search(self):
        c = _Collector()
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=_FakeChromaCollection(_chroma_resp([])),
        ):
            run_lazy_corpus_search(
                "q", embed_query=_fake_embed, chroma=_CHROMA, emitter=c,
            )
        assert all(e.step_id == "lazy_corpus_search" for e in c.events)

    def test_authority_label_corpus(self):
        chunks = [("id-1", "text", {"document_id": "d1"}, 0.2)]
        with patch(
            "mobius_skills_core.skills.lazy_rag._get_chroma_collection",
            return_value=_FakeChromaCollection(_chroma_resp(chunks)),
        ):
            r = run_lazy_corpus_search(
                "q", embed_query=_fake_embed, chroma=_CHROMA,
            )
        assert r.sources[0].authority == "corpus"
