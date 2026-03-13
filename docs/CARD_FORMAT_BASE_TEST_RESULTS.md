# Card Format Base Test Results

Baseline test results for the AnswerCard formatting fix. Run these tests before and after changes to verify card display remains correct.

## Test Commands

### 1. Card format verification (single message)

```bash
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_card_format.py -m "What can you do?"
```

Pass: exits 0, prints `[OK] AnswerCard format is clean (ok)`  
Fail: exits 1, prints `[FAIL] AnswerCard format issue: <reason>`

Custom message:
```bash
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_card_format.py --message "How do I file an appeal?"
```

### 2. Comprehensive pipeline gate (all scenarios)

```bash
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_chat_pipeline_comprehensive.py
```

Pass: `7/7 passed`, `All pipeline runs completed without crash`  
Gate: Run 3x with 0 crashes for flakiness check:
```bash
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_chat_pipeline_comprehensive.py --runs 3
```

---

## Base Results (captured 2025-02-24)

### Card format test

| Message | Status | Format OK | Notes |
|---------|--------|-----------|-------|
| "What can you do?" | completed | ✓ | Full AnswerCard with sections |
| "How do I file an appeal?" | clarification | ✓ | Clean direct_answer, sections=[] |
| "What are the qualifications for care management?" | clarification | ✓ | Same clarification response |

All three pass the format check: `direct_answer` is human-readable text, not raw JSON.

### Comprehensive pipeline (7 scenarios)

| # | Message | Status |
|---|---------|--------|
| 1 | What are the qualifications for care management? | clarification |
| 2 | What can you do? | completed |
| 3 | Hello | clarification |
| 4 | What is the status for MRN 98765? | completed |
| 5 | Search for Florida Medicaid eligibility requirements | clarification |
| 6 | A member has income of $1500/month and two chronic conditions. Do they meet eligibility? | clarification |
| 7 | How do I file an appeal? | clarification |

Result: 7/7 passed (no crashes).

---

## What the format check validates

- `direct_answer` is a string of human-readable text (not raw JSON or ```json blocks)
- `sections` is an array
- `mode` is FACTUAL, CANONICAL, or BLENDED
- Top-level JSON parses as valid AnswerCard

## Environment

- `QUEUE_TYPE=memory` (in-process test)
- Loads `.env` from mobius-chat, mobius-config, or repo root

### Run environment for gates

- **Venv:** Use the repo venv so `python` and `pytest` resolve. From repo root:
  - `source .venv/bin/activate` (or `. .venv/bin/activate`), then run the commands below; or
  - `python -m pytest` instead of `pytest` when the venv is activated.
- **Pipeline / card format scripts:** Run from **Mobius repo root** with `PYTHONPATH=mobius-chat`. No database required for the gate: if `CHAT_RAG_DATABASE_URL` points to 127.0.0.1:5433 and the DB (or Cloud SQL Proxy) is down, you may see "Failed to persist turn" in logs; the pipeline still completes and tests pass. For persistence, start Cloud SQL Proxy or local Postgres and point `CHAT_RAG_DATABASE_URL` at it.
- **Day 3 gate (pytest):** Run from `mobius-chat` with venv active: `pytest tests/ -v -m "not integration"`. Integration tests (real DB, MCP, Google) are marked and excluded by that filter.
