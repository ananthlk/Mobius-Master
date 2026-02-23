# Sprint: Day 1 — Planner / Parser

**Focus module:** `mobius-chat/app/planner/` (parser.py, mobius_parse.py, stages/plan.py)  
**Gate:** Parser unit tests pass; no crash on malformed LLM output

---

## Quick Status Summary

| Area | Status | Next |
|------|--------|------|
| **Error boundaries** | DONE | plan.py wraps parse in try/except; minimal Plan fallback |
| **Parser robustness** | DONE | mobius_parse handles fallbacks, modality variants |
| **Schema retry** | Not implemented | Out of Day 1 scope |
| **Parser unit tests** | DONE | test_parser.py (7), test_mobius_parse.py (9) |
| **Integration tests** | `mobius-chat/scripts/test_chat_pipeline_comprehensive.py` | Run scenario 1 as gate check |

---

## Task Checklist

### 1. Error boundaries: wrap plan stage in try/except

| Task | Status | Notes |
|------|--------|-------|
| Wrap `run_plan` in try/except in plan stage | DONE | plan.py wraps parse() in try/except |
| On crash: set `ctx.plan` to minimal Plan (1 subquestion = raw message, kind=non_patient) | DONE | _minimal_plan() fallback |
| Ensure pipeline continues or returns graceful response | DONE | Plan stage catches; pipeline continues |

**Current state:** Plan stage catches parse exceptions and sets ctx.plan to minimal Plan. Empty subquestions also trigger minimal plan fallback.

---

### 2. Parser robustness: extend LLM output handling

| Task | Status | Notes |
|------|--------|-------|
| Fallbacks: `{"if": "no_evidence", "then": "web"}` → extract "then" | DONE | mobius_parse._parse_capabilities |
| Modality: `web_scrape`, `google_search` → map to `web` | DONE | mobius_parse._parse_task |
| Handle malformed / non-JSON LLM output | PARTIAL | parse_task_plan_from_json returns None; parser falls back to legacy |
| Handle missing or empty subquestions | PARTIAL | Returns None; legacy path used |
| Handle invalid `kind` / `question_intent` values | DONE | mobius_parse validates; defaults applied |

**Current state:** mobius_parse is reasonably robust. Gaps: other modality variants, malformed JSON inside subquestions.

---

### 3. Schema validation retry: one LLM fix-attempt before legacy

| Task | Status | Notes |
|------|--------|-------|
| On parse_task_plan_from_json failure: call LLM once with "fix this JSON" prompt | NOT DONE | No retry today |
| Pass raw + error message to LLM; get repaired JSON | NOT DONE | |
| Retry parse on repaired output; if still fails → legacy | NOT DONE | |

**Current state:** No schema retry. Parse fails → immediate legacy fallback.

---

### 4. Plan stage error boundary (recommended)

| Task | Status | Notes |
|------|--------|-------|
| In plan.py: try parse(); except → build minimal Plan | DONE | |
| Minimal Plan: 1 SubQuestion(id="sq1", text=effective_message, kind="non_patient") | DONE | _minimal_plan() |
| Still run blueprint on minimal plan | DONE | |

---

## Test Checklist

### Unit tests to add

| Test | Status | File |
|------|--------|------|
| `test_parse_empty_message` — returns Plan with empty subquestions | DONE | tests/test_parser.py |
| `test_parse_mobius_valid_json` — valid TaskPlan JSON → Plan with subquestions | DONE | tests/test_mobius_parse.py |
| `test_parse_mobius_fallback_dict` — `{"if":"no_evidence","then":"web"}` in fallbacks → parsed | DONE | tests/test_mobius_parse.py |
| `test_parse_mobius_modality_web_scrape` — modality "web_scrape" → maps to "web" | DONE | tests/test_mobius_parse.py |
| `test_parse_mobius_malformed_json` — invalid JSON → legacy fallback, no crash | DONE | tests/test_mobius_parse.py |
| `test_parse_mobius_validation_error` — Pydantic validation error → legacy fallback | DONE | test_parse_empty_returns_none, etc. |
| `test_mobius_parse_subquestion_missing_text` — skips subquestion, continues | DONE | tests/test_mobius_parse.py |
| `test_run_plan_on_parse_exception` — parse raises → minimal plan set, no re-raise | DONE | tests/test_parser.py |

### Integration / gate tests

| Test | Status | Notes |
|------|--------|-------|
| Run `mobius-chat/scripts/test_chat_pipeline_comprehensive.py --scenario 1` | MANUAL | Single query; should complete |
| Inject mock LLM returning malformed JSON — no crash | NOT DONE | |
| Inject mock LLM raising exception — no crash | NOT DONE | |

---

## Files to Modify

| File | Changes |
|------|---------|
| `app/stages/plan.py` | Wrap parse() in try/except; on exception, set ctx.plan = minimal Plan |
| `tests/test_parser.py` | NEW — parser unit tests |
| `tests/test_mobius_parse.py` | NEW — mobius_parse unit tests (or merge into test_parser) |

---

## Definition of Done (Day 1 Gate)

- [x] Plan stage has error boundary: parse failure → minimal plan, no crash
- [x] Parser unit tests exist and pass (≥6 tests) — 16 tests in test_parser.py + test_mobius_parse.py
- [x] Malformed LLM output does not crash pipeline
- [x] `pytest mobius-chat/tests/test_parser.py mobius-chat/tests/test_mobius_parse.py -v` passes
- [ ] `mobius-chat/scripts/test_chat_pipeline_comprehensive.py --scenario 1` completes without crash (manual check OK)

---

## Regression Test Suite (run after every change)

Run these to establish baseline and catch regressions:

### 1. Unit tests (fast, ~30s, no external services)

```bash
cd /Users/ananth/Mobius
PYTHONPATH=mobius-chat pytest mobius-chat/tests/test_doc_assembly.py mobius-chat/tests/test_refined_query.py mobius-chat/tests/test_short_term_memory.py -v --tb=short
```

**Baseline (2026-02-21):** 86 tests — all pass (incl. test_parser, test_mobius_parse; test_doc_assembly_integration excluded)

### 2. Agent routing (LLM + blueprint, ~45s, RAG optional)

```bash
cd /Users/ananth/Mobius
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_agent_routing.py
```

**Baseline (2026-02-21):** 7 passed, 1 failed — "What can you do?" routes to reasoning instead of tool (Day 2 blueprint fix)

### 3. Skills integration (requires mstart / skills URLs)

```bash
cd /Users/ananth/Mobius
# With mstart running:
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_skills_integration.py
```

**Baseline (2026-02-21):** 0/3 passed — CHAT_SKILLS_* URLs not set (SKIP when not running mstart)

### 4. Comprehensive pipeline (LLM, RAG, skills; ~10–15 min for all 7)

```bash
cd /Users/ananth/Mobius
# Single scenario (fast check):
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_chat_pipeline_comprehensive.py --scenario 1
# All scenarios:
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_chat_pipeline_comprehensive.py
```

**Baseline (2026-02-21):** Scenario 1 runs but slow; RAG DB/API often unavailable locally; skills URLs needed for scenarios 4, 7

### One-liner: unit tests + agent routing (quick regression)

```bash
cd /Users/ananth/Mobius && PYTHONPATH=mobius-chat pytest mobius-chat/tests/test_doc_assembly.py mobius-chat/tests/test_refined_query.py mobius-chat/tests/test_short_term_memory.py mobius-chat/tests/test_parser.py mobius-chat/tests/test_mobius_parse.py -v --tb=short -q && PYTHONPATH=mobius-chat python mobius-chat/scripts/test_agent_routing.py
```

### Parse testing cadence (2026-02-19+)

**Run parser/planner tests after every few sprints.** As new capabilities get added, new docs ingested, and prompts evolve, the parse baseline drifts. Re-run `run_pipeline_stream.py`, `trace_icd_clarify.py`, and parser unit tests to verify decomposition and clarification behavior still match intent. See `scripts/run_pipeline_stream.py` for local verification without worker.

---

## Out of Scope (Day 1)

- Schema validation retry (LLM fix-attempt) — defer to later
- Blueprint routing changes — Day 2
- Comprehensive pipeline tests — Day 3

---

## Backlog: Planner Content Improvements

**Planner gives better plan + path-specific emit messages**

1. **Better plan from planner (LLM):** The planner is not yet producing optimal plans (e.g. scrape+answer as one tool flow, correct capabilities_primary, fewer wrong splits). Improve planner prompt and/or output schema so plans are more accurate before we emit.

2. **Path-specific parser emit messages:** Replace generic `"I can look this up"` with intent-specific messages per subquestion, based on kind + capabilities_primary:
   - RAG: "I'll look this up in our materials."
   - Web scrape: "I intend to read the specific webpage."
   - Web search: "I'll search the web for this."
   - Reasoning: "I'll reason through this."
   - Patient: "This looks personal; I don't have access to your records."

   Include as part of planner content/prompt improvements so emits accurately reflect how each part will be answered.

---

## Parser Exception & Failure Logging (GCP)

Every parser-related failure is logged for monitoring in dev (mstart) and prod (Cloud Run). Query GCP logs for these messages:

| Failure | Log message | Level |
|---------|-------------|-------|
| **Plan stage: parse threw** | `Plan stage: parse failed, using minimal plan: {e}` | WARNING |
| **Plan stage: empty plan** | `Plan stage: parse returned empty plan, using minimal plan.` | WARNING |
| **Mobius LLM empty** | `[parser] Mobius LLM returned empty response; falling back to legacy.` | WARNING |
| **Mobius parse failed** | `[parser] Mobius parse failed; falling back to legacy.` | WARNING |
| **Mobius exception** | `[parser] Mobius decomposition failed: {e}` | WARNING |
| **Legacy LLM empty** | `[parser] Legacy LLM returned empty response; using rule-based fallback.` | WARNING |
| **Legacy LLM not JSON** | `LLM decomposition: response is not JSON (model may have answered). Using fallback.` | WARNING |
| **Legacy LLM no subquestions** | `[parser] Legacy LLM response has no valid subquestions; using rule-based fallback.` | WARNING |
| **Legacy LLM parsed empty** | `[parser] Legacy LLM subquestions parsed to empty; using rule-based fallback.` | WARNING |
| **Legacy LLM exception** | `LLM decomposition failed, using rule-based fallback: {e}` | WARNING |
| **Legacy LLM timeout** | `[parser] LLM call timed out: {te}` | ERROR |
| **Legacy LLM call exception** | `[parser] LLM call raised exception: {e}` | ERROR |
| **mobius_parse JSON error** | `[mobius_parse] JSON decode error: {e}` | WARNING |
