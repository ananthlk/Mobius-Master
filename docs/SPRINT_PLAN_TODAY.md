# Sprint plan — Tuesday Feb 24, 2025

> **Context:** V1 Week 1 ([V1_THREE_WEEK_PLAN.md](V1_THREE_WEEK_PLAN.md), [V1_WEEK1_STATUS.md](V1_WEEK1_STATUS.md)). Today focuses on locking Week 1 gates and advancing to Day 3.

---

## Where we are

- **Day 1–2 (Parser + pipeline):** Implementation in place. Pipeline test exists (`test_chat_pipeline_comprehensive.py` — 7 scenarios, 7/7 pass). Card format fixed and baselined (`test_card_format.py`, [CARD_FORMAT_BASE_TEST_RESULTS.md](CARD_FORMAT_BASE_TEST_RESULTS.md)).
- **Day 2 gate:** Partially met — comprehensive pipeline runs 3x with 0 crashes; invalid-JSON fallback not yet covered by an automated test.
- **Day 3 (Foundation regression):** Not yet run; markers exist on some tests only.

---

## Today’s goals

1. **Lock Day 2 gate** — Confirm pipeline gate and optional invalid-JSON test.
2. **Run Day 3 gate** — Foundation regression with `pytest -m "not integration"`.
3. **Optional:** Start Day 4 (lexicon audit) or add Day 1 gate test (`test_agent_routing.py`).

---

## Sprint tasks

### 1. Pipeline gate (Day 2)

- [ ] Run: `PYTHONPATH=mobius-chat python mobius-chat/scripts/test_chat_pipeline_comprehensive.py --runs 3`  
  **Pass:** 21/21 (7 scenarios × 3 runs), 0 crashes.
- [ ] Run: `PYTHONPATH=mobius-chat python mobius-chat/scripts/test_card_format.py`  
  **Pass:** AnswerCard format clean.
- [ ] **(Optional)** Add a test that injects invalid integrator JSON and asserts fallback message and no 500 (e.g. in `tests/` or in a small script).

### 2. Foundation regression (Day 3)

- [ ] Run: `cd mobius-chat && pytest tests/ -v -m "not integration"`  
  **Pass:** All selected tests pass.
- [ ] If tests fail: fix or add `@pytest.mark.integration` / `@pytest.mark.requires_rag` / `@pytest.mark.requires_skills` so the “not integration” set is green.
- [ ] Document result in V1_WEEK1_STATUS or here (e.g. “Day 3 gate: passed with markers X, Y”).

### 3. Day 1 gate (optional today)

- [ ] Add `test_agent_routing.py` (or equivalent) so that:
  - “Search for X” routes to tool.
  - “What can you do?” routes to tool.  
  **Pass:** Tests exist and pass.

### 4. Lexicon audit (Day 4) — optional start

- [ ] Open `mobius-qa/lexicon-maintenance` and list current entries / J-tags.
- [ ] Note gaps: missing payers, doc types, AHCA terms.
- [ ] Create a short checklist or section in a doc (e.g. `docs/LEXICON_AUDIT_CHECKLIST.md`).

---

## Commands quick reference

```bash
# Day 2: Pipeline gate (3 runs)
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_chat_pipeline_comprehensive.py --runs 3

# Day 2: Card format
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_card_format.py

# Day 3: Foundation regression
cd mobius-chat && pytest tests/ -v -m "not integration"
```

---

## End of day

- **Minimum:** Tasks 1 and 2 done; Day 2 and Day 3 gates recorded as pass/fail.
- **Stretch:** Task 3 (agent routing test) or Task 4 (lexicon audit start).
