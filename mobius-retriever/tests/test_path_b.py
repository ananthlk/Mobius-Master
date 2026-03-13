"""Basic tests for Path B: vector search + limited reranking."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on path when running tests directly
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from unittest.mock import MagicMock, patch

import pytest

from mobius_retriever.config import load_path_b_config, PathBConfig
from mobius_retriever.rerank import rerank_path_b
from mobius_retriever.retriever import retrieve_path_b, ChunkResult, RetrievalResult
from mobius_retriever.vector_search import distance_to_similarity


CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"


def test_config_load_requires_version() -> None:
    """Config without version raises."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("name: test\n")
        path = Path(f.name)
    try:
        with pytest.raises(ValueError, match="version"):
            load_path_b_config(path)
    finally:
        path.unlink(missing_ok=True)


def test_config_load_resolves_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Config resolves ${VAR} from env."""
    monkeypatch.setenv("VERTEX_PROJECT", "my-project")
    monkeypatch.setenv("VERTEX_REGION", "us-east1")
    cfg = load_path_b_config(CONFIGS_DIR / "path_b_v1.yaml")
    assert cfg.vector.project == "my-project"
    assert cfg.vector.region == "us-east1"
    assert cfg.version == "1"
    assert cfg.top_k == 10


def test_distance_to_similarity() -> None:
    """Cosine distance -> similarity mapping."""
    assert distance_to_similarity(0.0) == 1.0
    assert distance_to_similarity(2.0) == 0.0
    assert distance_to_similarity(1.0) == 0.5
    assert distance_to_similarity(None) is None


def test_rerank_confidence_min() -> None:
    """Rerank filters by confidence_min."""
    from mobius_retriever.config import RerankConfig

    chunks = [
        {"id": "a", "text": "x", "confidence": 0.9, "source_type": "chunk"},
        {"id": "b", "text": "y", "confidence": 0.4, "source_type": "chunk"},
    ]
    cfg = RerankConfig(confidence_min=0.5)
    out = rerank_path_b(chunks, cfg)
    assert len(out) == 1
    assert out[0]["id"] == "a"


def test_rerank_hierarchy_sort() -> None:
    """Rerank sorts by source_type hierarchy."""
    from mobius_retriever.config import RerankConfig

    chunks = [
        {"id": "a", "text": "x", "confidence": 0.5, "source_type": "fact"},
        {"id": "b", "text": "y", "confidence": 0.5, "source_type": "hierarchical"},
    ]
    cfg = RerankConfig(apply_hierarchy_sort=True, confidence_min=None)
    out = rerank_path_b(chunks, cfg)
    assert len(out) == 2
    assert out[0]["source_type"] == "hierarchical"
    assert out[1]["source_type"] == "fact"


def test_chunk_result_from_dict() -> None:
    """ChunkResult.from_dict maps fields correctly."""
    d = {"id": "x", "text": "hello", "document_name": "doc", "similarity": 0.8}
    c = ChunkResult.from_dict(d, rank=1)
    assert c.id == "x"
    assert c.text == "hello"
    assert c.similarity == 0.8
    assert c.rank == 1


@patch("mobius_retriever.vector_search._embed_query")
@patch("mobius_retriever.vector_search._vertex_find_neighbors")
@patch("mobius_retriever.vector_search._fetch_metadata")
def test_retrieve_path_b_mocked(
    mock_fetch: MagicMock,
    mock_vertex: MagicMock,
    mock_embed: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path B retrieval with mocked Vertex/Postgres."""
    monkeypatch.setenv("VERTEX_PROJECT", "p")
    monkeypatch.setenv("VERTEX_REGION", "r")
    monkeypatch.setenv("VERTEX_INDEX_ENDPOINT_ID", "e")
    monkeypatch.setenv("VERTEX_DEPLOYED_INDEX_ID", "d")
    monkeypatch.setenv("CHAT_RAG_DATABASE_URL", "postgres://x")

    mock_embed.return_value = [0.1] * 1536
    mock_vertex.return_value = [{"id": "chunk-1", "distance": 0.3}]
    mock_fetch.return_value = {
        "chunk-1": {
            "id": "chunk-1",
            "document_id": "doc-1",
            "text": "Prior auth is required for PT.",
            "page_number": 5,
            "document_display_name": "Manual",
            "source_type": "hierarchical",
        }
    }

    emits: list[str] = []

    result = retrieve_path_b(
        question="What is prior auth for PT?",
        config_path=str(CONFIGS_DIR / "path_b_v1.yaml"),
        emitter=emits.append,
    )

    assert len(result.chunks) == 1
    assert result.chunks[0].text == "Prior auth is required for PT."
    assert result.chunks[0].similarity is not None
    assert result.config_version == "1"
    assert result.path == "path_b"
    assert any("Embedding" in e for e in emits)
