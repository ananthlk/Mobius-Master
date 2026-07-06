"""Unit tests for mobius_skills_core.skills.list_thread_uploads.

Pure formatter — no network, no state. Tests lock:
  * Empty thread_id returns "no thread yet" message
  * Empty upload list returns "no uploads yet" message
  * Populated list produces a markdown table with correct columns
  * Missing fields render as em-dash (—) rather than "None" or blanks
  * Pipe characters in fields are sanitised (table columns)
  * Row cap truncates + shows "X of Y" footer
  * Non-dict entries in the list are filtered silently
"""
from __future__ import annotations

from mobius_skills_core import SkillEvent
from mobius_skills_core.skills.list_thread_uploads import run_list_thread_uploads


class _Collector:
    def __init__(self):
        self.events: list[SkillEvent] = []
    def __call__(self, event: SkillEvent) -> None:
        self.events.append(event)


class TestEmptyThread:
    def test_empty_thread_id(self):
        r = run_list_thread_uploads("")
        assert r.signal == "no_sources"
        assert "No chat thread is available yet" in r.text

    def test_whitespace_thread_id(self):
        r = run_list_thread_uploads("   \t\n")
        assert "No chat thread is available yet" in r.text

    def test_empty_thread_id_still_fires_completed(self):
        c = _Collector()
        run_list_thread_uploads("", emitter=c)
        signals = [e.signal for e in c.events]
        # Short-circuit path: only one event, the completion
        assert signals == ["tool_completed"]


class TestEmptyUploads:
    def test_none_uploads(self):
        r = run_list_thread_uploads("thread-abc", None)
        assert "**Thread:** `thread-abc`" in r.text
        assert "**Uploads on file:** 0" in r.text
        assert "No documents uploaded yet" in r.text
        # No table headers when no rows
        assert "| # |" not in r.text

    def test_empty_list(self):
        r = run_list_thread_uploads("t-1", [])
        assert "**Uploads on file:** 0" in r.text


class TestPopulatedTable:
    def test_single_row_renders_table(self):
        files = [{
            "purpose": "instant_rag",
            "filename": "roster.csv",
            "org_name": "Sunshine Health",
            "row_count": 42,
            "uploaded_at": "2026-04-20T10:00:00Z",
        }]
        r = run_list_thread_uploads("t-1", files)
        assert "**Uploads on file:** 1" in r.text
        assert "| 1 | instant_rag | roster.csv | Sunshine Health | 42 | 2026-04-20T10:00:00Z |" in r.text
        assert "| # | Purpose | File | Organization | Rows | Uploaded (UTC) |" in r.text

    def test_multiple_rows_numbered_in_order(self):
        files = [
            {"filename": "a.pdf"},
            {"filename": "b.pdf"},
            {"filename": "c.pdf"},
        ]
        r = run_list_thread_uploads("t-1", files)
        for i, fn in enumerate(("a.pdf", "b.pdf", "c.pdf"), 1):
            assert f"| {i} |" in r.text and fn in r.text

    def test_missing_fields_render_as_dash(self):
        files = [{"filename": "only_name.pdf"}]
        r = run_list_thread_uploads("t-1", files)
        # Every other column should be "—"
        line = [ln for ln in r.text.splitlines() if "only_name.pdf" in ln][0]
        # Field count: # | Purpose | File | Organization | Rows | Uploaded
        # "—" should appear 4 times (purpose, org_name, rows, uploaded_at)
        assert line.count("—") == 4

    def test_row_count_zero_rendered_as_zero(self):
        """row_count=0 is a real value, not missing — should render as "0"."""
        files = [{"filename": "empty.csv", "row_count": 0}]
        r = run_list_thread_uploads("t-1", files)
        line = [ln for ln in r.text.splitlines() if "empty.csv" in ln][0]
        assert "| 0 |" in line  # the "Rows" column shows 0, not —

    def test_pipe_characters_sanitised(self):
        """Pipes in filenames / orgs must not break the markdown table."""
        files = [{
            "filename": "a|b.pdf",
            "org_name": "Left|Right LLC",
            "purpose": "foo|bar",
        }]
        r = run_list_thread_uploads("t-1", files)
        line = [ln for ln in r.text.splitlines() if "a/b.pdf" in ln][0]
        # Pipe replaced with '/' — filename + org_name + purpose all sanitised
        assert "Left/Right LLC" in line
        assert "foo/bar" in line
        # The raw pipe should not appear in the data cells (just the
        # table structure pipes at column boundaries)
        # A clean cell line of 6 cells => 7 pipes
        assert line.count("|") == 7

    def test_non_dict_entries_filtered(self):
        """Bad entries in the list are silently dropped."""
        files = [
            {"filename": "good.pdf"},
            "not a dict",
            None,
            {"filename": "also_good.pdf"},
        ]
        r = run_list_thread_uploads("t-1", files)
        assert "**Uploads on file:** 2" in r.text
        assert "good.pdf" in r.text
        assert "also_good.pdf" in r.text


class TestRowCap:
    def test_default_cap_20(self):
        files = [{"filename": f"f-{i}.pdf"} for i in range(25)]
        r = run_list_thread_uploads("t-1", files)
        assert "_Showing 20 of 25 uploads._" in r.text
        # f-0 through f-19 present; f-20..f-24 suppressed
        assert "f-0.pdf" in r.text
        assert "f-19.pdf" in r.text
        assert "f-20.pdf" not in r.text

    def test_custom_cap(self):
        files = [{"filename": f"f-{i}.pdf"} for i in range(10)]
        r = run_list_thread_uploads("t-1", files, row_cap=5)
        assert "_Showing 5 of 10 uploads._" in r.text

    def test_under_cap_no_footer(self):
        files = [{"filename": "a.pdf"}, {"filename": "b.pdf"}]
        r = run_list_thread_uploads("t-1", files)
        assert "Showing" not in r.text  # no truncation footer


class TestEmits:
    def test_populated_emits_invoked_then_completed(self):
        c = _Collector()
        run_list_thread_uploads("t-1", [{"filename": "a.pdf"}], emitter=c)
        signals = [e.signal for e in c.events]
        assert signals == ["tool_invoked", "tool_completed"]
        # Completion carries count metadata
        done = c.events[-1]
        assert done.data["upload_count"] == 1
        assert done.data["displayed"] == 1

    def test_truncation_reflected_in_completed_event(self):
        c = _Collector()
        files = [{"filename": f"{i}.pdf"} for i in range(30)]
        run_list_thread_uploads("t-1", files, emitter=c)
        done = c.events[-1]
        assert done.data["upload_count"] == 30
        assert done.data["displayed"] == 20

    def test_empty_thread_id_emits_only_completed(self):
        c = _Collector()
        run_list_thread_uploads("", emitter=c)
        signals = [e.signal for e in c.events]
        assert signals == ["tool_completed"]


class TestResultExtras:
    def test_extra_carries_upload_count(self):
        r = run_list_thread_uploads("t-1", [{"filename": "a.pdf"}])
        assert r.extra["upload_count"] == 1
        assert r.extra["thread_id"] == "t-1"
