# Sprint: Day 3 — Pipeline / Orchestrator Error Boundaries

**Focus module:** `app/pipeline/orchestrator.py`, `app/stages/clarify.py`, `app/stages/resolve.py`, `app/stages/integrate.py`  
**Gate:** `test_chat_pipeline_comprehensive.py` 3x — 0 crashes

---

## Quick Status Summary

| Area | Status | Notes |
|------|--------|-------|
| **Error boundaries** | DONE | try/except around clarify, resolve, integrate |
| **_publish_failed** | DONE | Structured payload; never raises; defensive str(err), thinking_chunks |
| **Gate script** | DONE | test_chat_pipeline_comprehensive.py with scenarios 1–7 |

---

## Task Checklist

### 1. Error boundaries on clarify, resolve, integrate

| Task | Status | Notes |
|------|--------|-------|
| run_clarify in try/except | DONE | On exception → _publish_failed, return |
| run_resolve in try/except | DONE | On exception → _publish_failed, return |
| run_integrate in try/except | DONE | On exception → _publish_failed, return |
| Stage-specific logging | DONE | logger.exception per stage |

### 2. _publish_failed robustness

| Task | Status | Notes |
|------|--------|-------|
| Structured payload always | DONE | status, message, plan, thinking_log, response_source, llm_error, tokens_used, etc. |
| thinking_chunks nullable | DONE | (thinking_chunks or []) |
| str(err) safe | DONE | try/except around str(err) |
| Publish never raises | DONE | clear_progress/store/publish wrapped in try/except |

### 3. Gate script

| Task | Status | Notes |
|------|--------|-------|
| test_chat_pipeline_comprehensive.py | DONE | Runs full pipeline, asserts structured response |
| --scenario N | DONE | Scenarios 1–7 (generic, tool, PHI, scenario-based) |
| --runs N | DONE | Flakiness check |

---

## Gate Tests

### Comprehensive pipeline (Day 3 gate)

```bash
cd /Users/ananth/Mobius
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_chat_pipeline_comprehensive.py --scenario 1 --runs 3
```

**Expected:** 3/3 passed, 0 crashes.

### Single scenario

```bash
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_chat_pipeline_comprehensive.py --scenario 2
```

---

## Scenarios

| ID | Message | Expected status |
|----|---------|-----------------|
| 1 | What are the qualifications for care management? | clarification or completed |
| 2 | What can you do? | completed (tool) |
| 3 | Hello | completed or clarification |
| 4 | What is the status for MRN 98765? | completed (PHI refusal) or clarification |
| 5 | Search for Florida Medicaid eligibility requirements | completed (tool) |
| 6 | A member has income of $1500/month... | completed or clarification |
| 7 | How do I file an appeal? | clarification or completed |

---

## Files Modified

| File | Changes |
|------|---------|
| `app/pipeline/orchestrator.py` | Error boundaries on clarify/resolve/integrate; _publish_failed defensive |
| `mobius-chat/scripts/test_chat_pipeline_comprehensive.py` | NEW — Day 3 gate script |
| `mobius-chat/tests/test_orchestrator.py` | NEW — unit tests for _publish_failed, clarify error boundary |

---

## Definition of Done (Day 3 Gate)

- [x] Error boundaries on clarify, resolve, integrate
- [x] _publish_failed always emits structured payload; never raises
- [x] test_chat_pipeline_comprehensive.py --scenario 1 --runs 3 passes
- [x] 0 crashes on pipeline runs

---

## Regression One-Liner

```bash
cd /Users/ananth/Mobius && PYTHONPATH=mobius-chat python mobius-chat/scripts/test_chat_pipeline_comprehensive.py --scenario 1 --runs 3
```
