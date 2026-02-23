# Intent / Jurisdiction Continuity: Test Baseline

**Date:** 2026-02-19  
**Purpose:** Establish baseline before implementing parse-strip, continuity redraft, and reframe with strip+recombine.

---

## Regression Suite Baseline

| Suite | Result | Notes |
|-------|--------|-------|
| Unit tests | 96 passed, 3 skipped | Includes intent_jurisdiction_continuity |
| Agent routing | 8/8 passed | "What can you do?" can vary (LLM); Day 2 adds pattern override |
| Skills integration | Skipped | CHAT_SKILLS_* not set |

**Run:** `./scripts/run_regression_tests.sh`

---

## Current Behavior (Documented by Tests)

### Intent with jurisdiction embedded

- **"what is the care management program for Sunshine"** + jurisdiction Sunshine Health  
  - `build_refined_query` may produce: "what is the care management program for Sunshine for Sunshine Health"  
  - No strip of jurisdiction from intent; avoid_duplicate only when full summary is in base

- **"what is the care management program for Sunshine Health"** + same jurisdiction  
  - avoid_duplicate works; no duplication

### Jurisdiction change ("how about for United")

- **"how about for United Healthcare"**  
  - `classify_message` → **new_question** (not jurisdiction_change)  
  - Same intent is lost; we treat as new question

- **"how about United"** (short)  
  - May be slot_fill (matches United) or new_question

### Follow-up with reference ("can you search for it")

- **"can you search the web for it"** after prior turn about income criteria  
  - `classify_message` → new_question (or slot_fill depending on heuristics)  
  - `compute_refined_query` with plan_text = "can you search the web for it"  
  - **Result: refined_query = "can you search the web for it"** — prior topic (income criteria) is lost

### reframe_for_retrieval

- Returns question as-is; no last_intent, no jurisdiction merge

---

## Gaps to Fix

1. **Parse and strip** — Extract jurisdiction from intent; store clean intent separately
2. **Continuity / jurisdiction_change** — "how about for United" should preserve intent, swap jurisdiction
3. **Follow-up expansion** — "can you search for it" should merge with last_intent
4. **reframe_for_retrieval** — Accept last_intent, jurisdiction; strip embedded jurisdiction; recombine

---

## How to Re-run Baseline

```bash
cd /Users/ananth/Mobius
PYTHONPATH=mobius-chat pytest mobius-chat/tests/ -v -m "not integration" -q
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_agent_routing.py
```

After implementation changes, re-run and compare. The 3 skipped tests in `TestDesiredParseStrip`, `TestDesiredContinuityRedraft`, `TestDesiredRecombine` should be un-skipped and pass.
