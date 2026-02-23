# Planner Rigidity Investigation — Findings

**Date:** 2025-02-19  
**Script:** `mobius-chat/scripts/diagnose_planner_output.py`  
**Queries:** 6 complex queries from `planner_complex_queries.txt`

---

## Summary

| Question | Answer |
|----------|--------|
| Does the LLM produce `steps`? | **No** — all tasks had `steps: []` |
| Does the LLM produce task `fallbacks`? | **Yes** — 4/6 queries had at least one `no_evidence -> web` fallback |
| Does the LLM produce `retry_policy`? | **Partially** — LLM outputs `max_retries`, `delay_seconds`; our schema expects `on_missing_jurisdiction`, `on_no_results`, `on_tool_error` (we use defaults) |
| Decomposition quality? | **Mixed** — some under-split (compare), most multi-part queries well decomposed |

---

## Per-Query Findings

### Q1: Compare care management programs (Sunshine, United, Molina)

- **Subquestions:** 1 (under-split — expected 3–4 for compare)
- **Tasks:** 1, fallbacks: 1 (`no_evidence -> web`)
- **Issue:** "Do not over-split" may discourage splitting compare queries into one subquestion per entity
- **Pipeline:** Would work but retrieves once for all; no per-payer retrieval

### Q2: Prior auth + grievance + appeal for Sunshine

- **Subquestions:** 3 ✓
- **Tasks:** 3, fallbacks: 4 ✓
- **Good:** Correctly decomposed; each task has `no_evidence -> web` fallback

### Q3: Search FL Medicaid, then compare to Sunshine manual

- **Subquestions:** 2 ✓
- **Tasks:** 3 (LLM invented task3 for "reasoning" comparison depending on task1+task2)
- **Fallbacks:** 0 — sq2 has `ask_user` fallback, not `web`, so `on_rag_fail` not set
- **Note:** Pipeline does not support `depends_on` or multi-task DAGs; runs flat per subquestion

### Q4: Qualifications + "if not in docs, search web"

- **Subquestions:** 1 ✓
- **Fallbacks:** 1 (`no_evidence -> web`) ✓
- **Good:** User’s explicit fallback intent captured

### Q5: Scrape URL, summarize appeals, check against manual

- **Subquestions:** 2 ✓
- **Parser gap:** Raw had `capabilities_needed.primary: "web_scrape"`; parser doesn’t map `web_scrape` → `web`, so defaulted to `rag`. Task modality correctly maps `web_scrape` → `web`. Deterministic route triggers still route "Scrape https://" to tool.

### Q6: Appeal + grievance + FPL income

- **Subquestions:** 3 ✓
- **Tasks:** 3, fallbacks: 3 ✓
- **Good:** Clear decomposition

---

## Conclusions

1. **Planner is not rigid for decomposition** — multi-part queries are generally split correctly.
2. **Compare queries under-split** — guidance to split "compare A, B, C" into one subquestion per entity would help.
3. **Fallbacks are produced** — `no_evidence -> web` appears when appropriate; pipeline uses them via `on_rag_fail`.
4. **Steps never produced** — prompt does not ask for them; parser does not parse them; pipeline does not execute them. No change unless we add step execution.
5. **Parser gap:** `capabilities_needed.primary: "web_scrape"` should map to `"web"` (same as task modality).
6. **retry_policy** — LLM uses different keys; we rely on defaults. Low priority.

---

## Phase 3 Actions Taken

1. **Prompt updates** — Encourage fallbacks for complex queries; soften over-split rule for compare cases.
2. **Parser fix** — Map `web_scrape` (and similar) to `web` in `_parse_capabilities`.
