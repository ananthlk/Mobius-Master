# V1 Week 1 Status

> As of **Feb 24, 2025**. Assessed against [V1_THREE_WEEK_PLAN.md](V1_THREE_WEEK_PLAN.md) Week 1 (Days 1–5).

---

## Day 1 — Parser + routing

| Deliverable | Status | Notes |
|------------|--------|--------|
| Parser error boundaries | ✅ Done | `parser.py`: try/except in `_llm_decompose_mobius`, `_llm_decompose`; fallback to rule-based decompose on empty/malformed LLM output. |
| Parser schema retry | ⚠️ Partial | No explicit “one LLM fix then legacy” in parser. Mobius parse is lenient; responder has `_repair_json` for integrator only. |
| Blueprint routing | ✅ Done | `route_triggers.py`: “search for”, “what can you do”, “search the web”, etc. → `tool`; “check our manual”, etc. → RAG. `blueprint.py` uses `detect_route` and `capabilities_primary` (web/tools → tool). |
| **Gate: Parser tests pass** | ❌ Not met | No parser/blueprint unit tests in `mobius-chat/tests/`. |
| **Gate: test_agent_routing.py** | ❌ Not met | File does not exist. Search and capability routing not covered by tests. |

**Action:** Add parser unit tests (e.g. malformed LLM output → fallback plan). Add `test_agent_routing.py` (or equivalent) so “Search for X” and “What can you do?” route to tool.

---

## Day 2 — Pipeline + responder

| Deliverable | Status | Notes |
|------------|--------|--------|
| Error boundaries (clarify, resolve, integrate) | ✅ Done | `orchestrator.py`: each of `run_clarify`, `run_resolve`, `run_integrate` wrapped in try/except → `_publish_failed`. |
| _publish_failed always structured | ✅ Done | `_publish_failed` builds payload with status, message, thinking_log, response_source, thread_id, etc.; never raises. |
| Responder invalid JSON fallback | ✅ Done | `responder/final.py`: `_parse_answer_card` (json + json_repair) → if None, `_repair_json` (one LLM retry) → minimal AnswerCard or `_fallback_message`; top-level except → `_fallback_message`. |
| **Gate: test_chat_pipeline_comprehensive.py 3x — 0 crashes** | ❌ Not met | File does not exist. No automated pipeline crash test. |
| **Gate: Invalid JSON → fallback, no 500** | ⚠️ Unverified | Logic present; no test that injects invalid JSON and asserts fallback + no 500. |

**Action:** Add `test_chat_pipeline_comprehensive.py` (or equivalent) that runs pipeline 3x and asserts no crashes. Add test that injects invalid integrator JSON and asserts fallback message and no 500.

**Note:** Plan stage (`run_plan`) is not wrapped in try/except; a plan-stage exception is caught by the outer pipeline try/except and still goes to `_publish_failed`. Optional hardening: wrap `run_plan` (and optionally `run_classify`) in try/except for clearer error payload.

---

## Day 3 — Foundation regression

| Deliverable | Status | Notes |
|------------|--------|--------|
| Pytest markers | ✅ Done | `test_doc_assembly_integration.py` uses `@pytest.mark.integration`, `@pytest.mark.requires_rag`, `@pytest.mark.requires_skills`. |
| Consolidate unit tests | ⚠️ Partial | Tests exist: `test_doc_assembly.py`, `test_doc_assembly_integration.py`, `test_refined_query.py`, `test_short_term_memory.py`. No explicit consolidation of “parser, blueprint, doc_assembly”; no markers on non-integration tests. |
| **Gate: pytest -m "not integration" passes** | ⚠️ Unknown | Need to run `pytest mobius-chat/tests/ -v -m "not integration"` and confirm all non-integration tests pass. |

**Action:** Run `pytest mobius-chat/tests/ -v -m "not integration"`. Add markers to any tests that are integration/requires_rag/requires_skills so the gate is well-defined. Add `scripts/smoke_test_v1.sh` later (plan has it in Day 12).

---

## Day 4 — Lexicon audit

| Deliverable | Status | Notes |
|------------|--------|--------|
| Lexicon codebase | ✅ Present | `mobius-qa/lexicon-maintenance`: repo, `reload_clean_lexicon`, API, frontend. |
| Audit: entries, J/P/D tags, gaps | ❌ Not done | No checklist or doc found for “missing payers, doc types, AHCA terms”. |
| **Deliverable: Lexicon audit checklist; terms to add/fix** | ❌ Not done | Not produced. |

**Action:** Run lexicon audit: list entries, J-tags (jurisdiction), P/D tags; document gaps (payers, doc types, AHCA). Produce checklist and term list.

---

## Day 5 — Corpus + lexicon updates

| Deliverable | Status | Notes |
|------------|--------|--------|
| Schema for 6 doc types | ❌ Not in place | V1 expects provider_manual, member_manual, clinical_policy, payment_policy, pa_lookup, web_scrape. RAG has `source_type` (e.g. hierarchical, fact) but no `document_type` / 6-type schema in codebase. |
| Ingest 2–3 plans, metadata filterable by payer/type | ❓ Unknown | Not verified; would need RAG ingestion docs or DB inspection. |
| Lexicon entries for new plans; sync; JPD on sample questions | ❓ Blocked | Depends on Day 4 audit and corpus schema. |
| **Gate: Docs in RAG filterable; JPD returns j_tags for new plans** | ❌ Not met | Schema and ingest not aligned to plan; gate not verified. |

**Action:** Define RAG schema (or metadata) for 6 doc types and payer; implement or confirm ingestion for 2–3 plans with that metadata. After Day 4, add lexicon entries and run sync; verify JPD tagger on sample questions.

---

## Week 1 summary

| Day | Focus | Gate status | Blocker / next step |
|-----|--------|-------------|----------------------|
| 1 | Parser + routing | ❌ | Add parser tests + `test_agent_routing.py` (or equivalent). |
| 2 | Pipeline + responder | ❌ | Add `test_chat_pipeline_comprehensive.py` (or equivalent) + invalid-JSON test. |
| 3 | Foundation regression | ⚠️ | Run `pytest -m "not integration"`; add markers where needed. |
| 4 | Lexicon audit | ❌ | Produce audit checklist and terms to add/fix. |
| 5 | Corpus + lexicon | ❌ | Define 6 doc types in RAG; ingest 2–3 plans; then lexicon sync + JPD check. |

**Overall:** Implementation for Days 1–2 (parser, routing, pipeline error handling, responder fallback) is largely in place. **Gates are missing** because the named test files don’t exist and the planned tests weren’t added. Days 3–5 depend on running the test suite, doing the lexicon audit, and defining/ingesting the RAG corpus with the 6 doc types.

**Recommended order:** (1) Add Day 1–2 gate tests so Week 1 foundation is verifiable. (2) Run Day 3 gate. (3) Execute Day 4 lexicon audit. (4) Define RAG schema and ingestion for Day 5, then lexicon updates and JPD check.
