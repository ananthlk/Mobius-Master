"""Shape tests for SkillResult + SourceRef + ChunkRef + SkillUsage."""
from __future__ import annotations

from mobius_skills_core import ChunkRef, SkillResult, SkillUsage, SourceRef


class TestSkillResult:
    def test_defaults_empty_and_ok(self):
        r = SkillResult()
        assert r.text == ""
        assert r.sources == []
        assert r.chunks == []
        assert r.usage is None
        assert r.signal == "ok"
        assert r.extra == {}
        assert r.has_content() is False
        assert r.is_error() is False

    def test_has_content_true_when_text_set(self):
        assert SkillResult(text="x").has_content() is True

    def test_has_content_true_when_sources_set(self):
        assert SkillResult(sources=[SourceRef(document_name="d")]).has_content() is True

    def test_is_error_on_tool_error(self):
        assert SkillResult(signal="tool_error").is_error() is True
        assert SkillResult(signal="no_sources").is_error() is False

    def test_extra_escape_hatch(self):
        r = SkillResult(extra={"results": [1, 2, 3], "query": "x"})
        assert r.extra["results"] == [1, 2, 3]
        assert r.extra["query"] == "x"


class TestSourceRef:
    def test_minimal_construction(self):
        s = SourceRef(document_name="Doc A")
        assert s.document_name == "Doc A"
        assert s.url is None
        assert s.index == 0
        assert s.authority is None

    def test_web_shape(self):
        s = SourceRef(
            document_name="example.com",
            source_type="web",
            url="https://example.com/page",
            index=1,
            text="preview",
        )
        assert s.source_type == "web"
        assert s.url == "https://example.com/page"


class TestChunkRef:
    def test_metadata_defaults_empty_dict(self):
        c = ChunkRef(text="body", score=0.9, document_id="doc-1")
        assert c.metadata == {}

    def test_metadata_carries_arbitrary(self):
        c = ChunkRef(metadata={"payer": "Sunshine", "state": "FL"})
        assert c.metadata["payer"] == "Sunshine"


class TestSkillUsage:
    def test_zero_defaults(self):
        u = SkillUsage()
        assert u.input_tokens == 0
        assert u.output_tokens == 0
        assert u.latency_ms == 0
        assert u.cost_usd == 0.0
        assert u.is_fallback is False
