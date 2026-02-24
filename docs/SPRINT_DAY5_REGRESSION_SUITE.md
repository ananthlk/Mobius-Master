# Sprint: Day 5 — Regression Suite (Foundation)

**Focus:** mobius-chat tests — consolidate, add markers, fast foundation gate  
**Gate:** `pytest mobius-chat/tests/ -v -m "not integration"` passes

---

## Objectives

1. **Consolidate unit tests** — Parser, blueprint (route_triggers), doc_assembly are the core; ensure they’re clearly covered and runnable as a set.
2. **Add pytest markers** — `integration`, `requires_rag`, `requires_skills` so we can run “foundation” tests without external services.
3. **Foundation gate** — `-m "not integration"` must pass for quick CI/local feedback.

---

## Quick Status Summary

| Area | Status | Notes |
|------|--------|-------|
| **Parser tests** | DONE | test_parser.py, test_mobius_parse.py |
| **Blueprint / routing** | DONE | test_route_triggers.py, test_clarify.py (refinement) |
| **Doc assembly** | DONE | test_doc_assembly.py (unit), test_doc_assembly_integration.py (integration) |
| **Markers** | DONE | `integration`, `requires_rag`, `requires_skills` in conftest.py |
| **Tagged tests** | DONE | doc_assembly_integration, mcp_skills_integration, mcp_manager (1 test) |

---

## Task Checklist

### 1. Register pytest markers

| Task | Status | Notes |
|------|--------|-------|
| conftest.py in mobius-chat/tests | DONE | Registers `integration`, `requires_rag`, `requires_skills` |
| skip_if_* unchanged | DONE | doc_assembly_integration keeps skip_if_no_db / skip_if_no_google |

### 2. Tag tests with markers

| Task | Status | Notes |
|------|--------|-------|
| test_doc_assembly_integration.py | DONE | All 5 tests: `integration` + `requires_rag` / `requires_skills` as appropriate |
| test_mcp_skills_integration.py | DONE | All 4 tests: `integration`, `requires_skills` |
| test_mcp_manager.py (test_call_tool_google_search_integration) | DONE | `integration`, `requires_skills` |
| All other test_*.py | — | No marker = foundation |

### 3. Consolidation (optional)

| Task | Status | Notes |
|------|--------|-------|
| Foundation set | DONE | 147 tests with `-m "not integration"` (parser, doc_assembly, route_triggers, refined_query, etc.) |
| run_regression_tests.sh | — | Can add `--foundation` to run pytest -m "not integration" for fast path |

### 4. Definition of Done

| Item | Status |
|------|--------|
| Markers registered | DONE |
| Integration tests tagged | DONE |
| `pytest mobius-chat/tests/ -v -m "not integration"` passes | DONE (147 passed) |

---

## Marker semantics

| Marker | Meaning |
|--------|---------|
| `integration` | Needs external service (DB, MCP, Google, etc.); skip in fast/CI run |
| `requires_rag` | Needs RAG DB (e.g. CHAT_RAG_DATABASE_URL) |
| `requires_skills` | Needs skills/MCP (e.g. CHAT_SKILLS_GOOGLE_SEARCH_URL) |

Tests that already use `skip_if_no_db` / `skip_if_no_google` can be marked `@pytest.mark.integration` (and optionally `requires_rag` / `requires_skills`) so `-m "not integration"` excludes them.

---

## Gate commands

**Foundation only (no integration):**
```bash
cd /Users/ananth/Mobius
PYTHONPATH=mobius-chat pytest mobius-chat/tests/ -v -m "not integration"
```

**Full suite (including integration; may skip if env not set):**
```bash
PYTHONPATH=mobius-chat pytest mobius-chat/tests/ -v
```

**Existing regression script (unit + agent routing + optional pipeline):**
```bash
./scripts/run_regression_tests.sh           # unit + agent routing
./scripts/run_regression_tests.sh --full    # + comprehensive pipeline
```

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `mobius-chat/pytest.ini` or `mobius-chat/tests/conftest.py` | CREATE or UPDATE — register markers |
| `mobius-chat/tests/test_doc_assembly_integration.py` | Add `@pytest.mark.integration` (and optionally requires_rag/requires_skills) |
| `mobius-chat/tests/test_mcp_skills_integration.py` | Add `@pytest.mark.integration`, `@pytest.mark.requires_skills` |
| `mobius-chat/tests/test_mcp_manager.py` | Add `@pytest.mark.integration` to integration test(s) |
| `docs/SPRINT_DAY5_REGRESSION_SUITE.md` | This doc |

---

## Dependencies

- **Day 4:** Responder/integrator and display fix (done)
- **Next (Day 6):** Lexicon audit (mobius-qa/lexicon-maintenance, mobius-retriever)
