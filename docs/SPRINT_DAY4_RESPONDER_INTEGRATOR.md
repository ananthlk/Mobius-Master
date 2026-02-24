# Sprint: Day 4 — Responder / Integrator JSON Fallback

**Focus module:** `app/responder/final.py`, integrate stage  
**Gate:** Inject invalid JSON from integrator; verify fallback message returned, no 500

---

## Objectives

1. **Harden integrator output handling** — When the consolidator LLM returns invalid or non–AnswerCard JSON, respond with a safe fallback (no crash, no 500).
2. **Gate test** — Test that invalid JSON path yields a structured response (fallback or wrapped prose), not an exception.
3. **Display: no raw JSON in card** — As the response is displayed, the user must not see raw JSON first; the card should show only the formatted message. (Current behavior: JSON appears in the card, then it converts to formatted message — we should not display the raw JSON.)

---

## Quick Status Summary

| Area | Status | Notes |
|------|--------|-------|
| **JSON extraction** | DONE | `_extract_json_from_text` — strips fences, finds `{...}` |
| **Parse + repair** | DONE | `_parse_answer_card`: json.loads → json_repair; invalid → `_repair_json` (LLM retry) |
| **Prose fallback** | DONE | Not valid AnswerCard → wrap in minimal AnswerCard (mode=FACTUAL, direct_answer=prose) |
| **LLM failure fallback** | DONE | Exception → `_fallback_message(plan, stub_answers)` |
| **Gate test** | TODO | Unit test: inject invalid JSON → assert fallback/wrapped, no raise |
| **Display: no raw JSON** | TODO | Card must not show raw JSON first; render formatted message only |

---

## Task Checklist

### 1. Responder: invalid JSON handling

| Task | Status | Notes |
|------|--------|-------|
| Extract JSON from markdown/fences | DONE | `_extract_json_from_text` |
| Parse with json.loads then json_repair | DONE | `_parse_answer_card` |
| Retry via LLM when invalid JSON | DONE | `_repair_json` |
| Wrap non–AnswerCard prose in minimal card | DONE | `{"mode": "FACTUAL", "direct_answer": text, "sections": []}` |
| On integrator exception → fallback message | DONE | `_fallback_message(plan, stub_answers)` |

### 2. Display: card must not show raw JSON first

| Task | Status | Notes |
|------|--------|-------|
| Frontend/card renders AnswerCard from JSON without showing raw JSON | TODO | User sees formatted message only; no flash of JSON then convert |

### 3. Gate test

| Task | Status | Notes |
|------|--------|-------|
| Unit test: mock/simulate invalid integrator output | TODO | Call format_response or integrate with fake invalid JSON |
| Assert: response is string (fallback or JSON), no exception | TODO | |
| Optional: test _parse_answer_card with invalid input | TODO | Direct unit test for final.py |

### 4. Definition of Done

| Item | Status |
|------|--------|
| Invalid JSON does not cause 500 or uncaught exception | DONE (in code) |
| Card does not display raw JSON before formatted message | TODO |
| Gate test exists and passes | TODO |

---

## Gate Test Design

**Option A — Unit test in `tests/test_responder_final.py` (or similar):**

- Call `format_response(plan, stub_answers, user_message)` with a **mocked** LLM that returns invalid JSON (e.g. `"not json at all"` or `"{ broken"`).
- Assert: return value is a non-empty string (either fallback prose or valid JSON string).
- Assert: no exception raised.

**Option B — Integration:**

- In integrate stage, if we can inject a test path that forces consolidator output to invalid JSON, run pipeline and assert `status != "failed"` and response has a message.

Recommendation: **Option A** for a fast, deterministic gate.

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `app/responder/final.py` | No change if current behavior is sufficient |
| `mobius-chat/tests/test_responder_final.py` | CREATE — gate test (invalid JSON → fallback) |

---

## Regression One-Liner

```bash
cd /Users/ananth/Mobius && PYTHONPATH=mobius-chat .venv/bin/python -m pytest mobius-chat/tests/test_responder_final.py -v
```

---

## Dependencies

- **Day 3:** Pipeline/orchestrator and gate script (done)
- **Next (Day 5):** Regression suite consolidation, pytest markers (`integration`, `requires_rag`, `requires_skills`)
