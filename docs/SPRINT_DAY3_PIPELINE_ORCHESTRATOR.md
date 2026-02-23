# Sprint: Day 3 — Pipeline / Orchestrator & Gate Scripts

**Focus module:** `app/pipeline/orchestrator.py`, clarify/resolve/integrate stages, gate scripts  
**Gate:** `test_chat_pipeline_comprehensive.py` 3× — 0 crashes; full regression passes

---

## Objectives

1. **Verify pipeline robustness** — Error boundaries and `_publish_failed` are already in place; validate they work.
2. **Add Day 3 gate script** — `test_chat_pipeline_comprehensive.py` (referenced by `run_regression_tests.sh` but not yet created).
3. **Integrate gate into regression** — `./scripts/run_regression_tests.sh --full` exercises the full pipeline.
4. **Baseline for future days** — Ensure continuity/persistence (Day 2) works end-to-end under the gate.

---

## Quick Status Summary

| Area | Status | Notes |
|------|--------|-------|
| **Error boundaries** | DONE | try/except around clarify, resolve, integrate |
| **_publish_failed** | DONE | Structured payload; never raises; defensive str(err), thinking_chunks |
| **Gate script** | TODO | test_chat_pipeline_comprehensive.py — create |
| **Regression integration** | PARTIAL | run_regression_tests.sh references it; script missing |

---

## Task Checklist

### 1. Verify existing error boundaries (no code change)

| Task | Status | Notes |
|------|--------|-------|
| Confirm run_clarify in try/except | DONE | On exception → _publish_failed, return |
| Confirm run_resolve in try/except | DONE | On exception → _publish_failed, return |
| Confirm run_integrate in try/except | DONE | On exception → _publish_failed, return |
| Confirm stage-specific logging | DONE | logger.exception per stage |

### 2. Verify _publish_failed robustness

| Task | Status | Notes |
|------|--------|-------|
| Structured payload always | DONE | status, message, plan, thinking_log, response_source, llm_error, tokens_used, etc. |
| thinking_chunks nullable | DONE | list(thinking_chunks) if thinking_chunks else [] |
| str(err) safe | DONE | try/except around str(err) |
| Publish never raises | DONE | clear_progress/store/publish wrapped in try/except |

### 3. Create Day 3 gate script

| Task | Status | Notes |
|------|--------|-------|
| Create test_chat_pipeline_comprehensive.py | TODO | Runs full pipeline via POST or direct run_pipeline |
| --scenario N | TODO | Scenarios 1–7 |
| --runs N | TODO | Flakiness check (default 1, 3 for gate) |
| Assert: structured response (status, message) | TODO | No crash; status in {clarification, completed, failed} |

### 4. Regression integration

| Task | Status | Notes |
|------|--------|-------|
| run_regression_tests.sh --full calls gate | DONE | Already wired; script must exist |
| run_regression_tests.sh --scenario1 | DONE | Quick smoke |
| Document gate one-liner | TODO | In this doc |

---

## Gate Script Design: test_chat_pipeline_comprehensive.py

**Location:** `mobius-chat/scripts/test_chat_pipeline_comprehensive.py`

**Invocation:**
```bash
cd /Users/ananth/Mobius
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_chat_pipeline_comprehensive.py --scenario 1 --runs 3
```

**Scenarios:**

| ID | Message | Expected status |
|----|---------|-----------------|
| 1 | What are the qualifications for care management? | clarification or completed |
| 2 | What can you do? | completed (tool) |
| 3 | Hello | completed or clarification |
| 4 | What is the status for MRN 98765? | completed (PHI refusal) or clarification |
| 5 | Search for Florida Medicaid eligibility requirements | completed (tool) |
| 6 | A member has income of $1500/month and needs Medicaid. What are the requirements? | completed or clarification |
| 7 | How do I file an appeal? | clarification or completed |

**Implementation approach:**
- Use `run_pipeline` directly or POST to chat API (depending on app setup).
- Capture response from store_response or queue; assert `status` in allowed set.
- No exception = pass. `--runs N`: run scenario N times; all must pass.

---

## Definition of Done (Day 3 Gate)

- [x] Error boundaries on clarify, resolve, integrate
- [x] _publish_failed always emits structured payload; never raises
- [ ] test_chat_pipeline_comprehensive.py exists and runs
- [ ] test_chat_pipeline_comprehensive.py --scenario 1 --runs 3 passes
- [ ] ./scripts/run_regression_tests.sh --full passes (when gate script exists)

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `mobius-chat/scripts/test_chat_pipeline_comprehensive.py` | CREATE |
| `docs/SPRINT_DAY3_PIPELINE_ORCHESTRATOR.md` | UPDATE (this doc) |

---

## Regression One-Liner

```bash
cd /Users/ananth/Mobius && PYTHONPATH=mobius-chat python mobius-chat/scripts/test_chat_pipeline_comprehensive.py --scenario 1 --runs 3
```

**Full regression (includes gate):**
```bash
./scripts/run_regression_tests.sh --full
```

---

## Dependencies

- **Day 2:** Multi-turn continuity, answer persistence, RAG fallback (merged)
- **Environment:** RAG/Vertex/Skills optional for some scenarios; gate should handle skips gracefully
- **Next (Day 4):** Responder/integrator JSON fallback (`docs/V1_DAY_BY_DAY_PLAN.md`)
