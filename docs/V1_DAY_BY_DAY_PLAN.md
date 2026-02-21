# V1 Production: Day-by-Day Plan

> **LOCKED** — This plan is committed. Do not deviate. See `.cursor/rules/v1-plan-lock.mdc` for enforcement. New ideas go to post-v1 backlog.

---

Concrete daily schedule with focus module/agent, through code lock and production migration. Includes lexicon work and retagging for staging.

**Total: ~25 working days (5 weeks)**

---

## Week 1: Foundation + Non-Failing Chat

### Day 1 — **Planner / Parser** (mobius-chat)
- **Module:** `app/planner/parser.py`, `app/planner/mobius_parse.py`
- Error boundaries: wrap plan stage in try/except, fallback to minimal plan on crash
- Parser robustness: extend LLM output handling (fallbacks, modality variants)
- Schema validation retry: one LLM fix-attempt before legacy fallback
- **Gate:** Parser unit tests pass; no crash on malformed LLM output

### Day 2 — **Blueprint / Routing** (mobius-chat)
- **Module:** `app/planner/blueprint.py`
- Add explicit routing: "Search for X" → tool, "What can you do?" → tool
- Update planner prompt for `capabilities_primary=web` on search queries
- **Gate:** `test_agent_routing.py` — Search and capability questions route to tool

### Day 3 — **Pipeline / Orchestrator** (mobius-chat)
- **Module:** `app/pipeline/orchestrator.py`, `app/stages/resolve.py`, `app/stages/integrate.py`
- Error boundaries on clarify, resolve, integrate
- Ensure `_publish_failed` always returns structured payload
- **Gate:** `test_chat_pipeline_comprehensive.py` 3x — 0 crashes

### Day 4 — **Responder / Integrator** (mobius-chat)
- **Module:** `app/responder/final.py`
- Fallback when integrator LLM returns invalid JSON
- **Gate:** Inject invalid JSON; verify fallback message, no 500

### Day 5 — **Regression suite (foundation)**
- Consolidate unit tests: parser, blueprint, doc_assembly
- Add `pytest` markers: `integration`, `requires_rag`, `requires_skills`
- **Gate:** `pytest mobius-chat/tests/ -v -m "not integration"` passes

---

## Week 2: RAG Corpus + Lexicon + Quality

### Day 6 — **Lexicon audit** (mobius-qa/lexicon-maintenance, mobius-retriever)
- **Module:** `mobius-qa/lexicon-maintenance`, `mobius-retriever/jpd_tagger`
- Audit current lexicon: entries, J-tags (jurisdiction), P-tags, D-tags
- Document gaps: missing payers, doc types, AHCA terms
- **Deliverable:** Lexicon audit checklist; list of terms to add/fix

### Day 7 — **Corpus ingestion setup** (mobius-rag, mobius-dbt)
- **Module:** `mobius-rag`, `mobius-dbt`
- Define schema for 6 doc types: provider_manual, member_manual, clinical_policy, payment_policy, pa_lookup, web_scrape
- Ingest first 2–3 plans (e.g. Sunshine, United, Molina) with existing docs
- Ensure metadata: source_type, payer, document_type
- **Gate:** Documents visible in RAG; filterable by payer and type

### Day 8 — **Lexicon updates for new docs**
- **Module:** `mobius-qa/lexicon-maintenance`, `sync_qa_lexicon_to_rag`, `sync_rag_lexicon_to_chat`
- Add lexicon entries for new plans and doc types
- Run `reload_clean_lexicon` / sync scripts
- **Gate:** JPD tagger returns j_tags for sample questions on new plans

### Day 9 — **AHCA ingestion**
- **Module:** `mobius-rag`, ingestion pipeline
- Ingest AHCA regulatory/Medicaid documents
- Tag with state=FL, regulatory_agency=AHCA
- **Gate:** AHCA docs in corpus; retrievable by jurisdiction filter

### Day 10 — **Expansion to 10 plans**
- **Module:** `mobius-rag`, ingestion
- Ingest remaining plans to reach 10 (provider manual, member manual, clinical policy, payment policy, PA lookup, web scrape per plan)
- **Gate:** Corpus has ≥10 plans; all 6 doc types represented

---

## Week 3: RAG Quality + Retagging + Eval

### Day 11 — **Retagging sprint (staging prep)**
- **Module:** `mobius-rag` Path B worker, `mobius-qa/lexicon-maintenance`
- Re-run document tagging with updated lexicon
- Fix document_tags, policy_line_tags for new/updated entries
- **Gate:** document_tags populated for new docs; sync_rag_lexicon_to_chat succeeds

### Day 12 — **Retrieval eval test set**
- **Module:** `mobius-qa/retrieval-eval`, `mobius-qa/retrieval-eval-studio`
- Build curated set: 50–100 Q&A pairs across doc types and plans
- Ground-truth: mark correct chunks/documents per question
- **Gate:** Test set checked in; recall@5 baseline measured

### Day 13 — **Recall optimization**
- **Module:** `mobius-retriever`, `mobius-rag-api`, BM25/hierarchical config
- Tune retrieval (chunk size, K, hierarchical vs factual mix)
- Iterate until recall@5 ≥ 80% on test set
- **Gate:** Recall ≥ 80% overall; per-doc-type breakdown documented

### Day 14 — **Answer accuracy eval**
- **Module:** Full pipeline (mobius-chat → RAG → LLM)
- Run questions where recall passes; score answers (correct / partial / incorrect / hallucination)
- Tune doc assembly, confidence thresholds
- **Gate:** Accuracy ≥ ~90% on questions with successful recall

### Day 15 — **RAG graceful degradation**
- **Module:** `app/services/non_patient_rag.py`, `app/services/retriever_backend.py`
- When RAG API down: clear message + offer Google search
- When lexicon/JPD fails: skip tagging, use parsed state
- **Gate:** RAG down → no crash; user gets graceful message

---

## Week 4: Skills + Persistence + Regression

### Day 16 — **Skills: Google + Scraper** (mobius-chat, mobius-skills)
- **Module:** `app/services/tool_agent.py`, `mobius-skills/google-search`, `mobius-skills/web-scraper`
- Verify mstart exports URLs; fix any routing gaps
- **Gate:** `test_skills_integration.py` — Google, scraper, tool-agent search all pass

### Day 17 — **Skills: One more** (mobius-chat, mobius-skills)
- **Module:** `app/services/tool_agent.py`, capability registry
- Implement NPI lookup or chosen skill; add to MCP
- **Gate:** New skill returns valid answer for test query

### Day 18 — **Persistence & emission** (mobius-chat)
- **Module:** `app/storage/progress.py`, `app/communication/gate.py`, `app/storage/threads.py`
- Optional Redis: DB-only fallback when Redis down
- E2E streaming test: POST → poll → assert thinking + final
- **Gate:** Multi-turn with jurisdiction change; state persists; streaming works

### Day 19 — **Full regression suite**
- **Module:** `mobius-chat/scripts`, `mobius-chat/tests`
- Run: comprehensive pipeline, agent routing, skills integration
- Add `scripts/smoke_test_v1.sh`
- **Gate:** All tests pass; smoke test < 5 min

### Day 20 — **Documentation & runbook**
- **Module:** `docs/`
- V1 runbook: env vars, mstart, health checks, known limitations
- Document RAG corpus scope, lexicon sync, staging retag process
- **Gate:** New dev can follow runbook and run smoke test

---

## Week 5: Code Lock + Production Migration

### Day 21 — **Code freeze / lock**
- **Module:** All
- Final regression run; fix any last issues
- Lock main branch for v1; no new features
- **Deliverable:** Tagged release candidate (e.g. v1.0.0-rc1)

### Day 22 — **Staging migration prep**
- **Module:** `scripts/`, `docs/MIGRATE_LOCAL_TO_CLOUD.md`
- Run full lexicon sync: QA → RAG → Chat
- Retag documents for staging corpus
- Verify sync_mart_to_chat, sync_rag_lexicon_to_chat
- **Gate:** Staging DB has full corpus + lexicon; Chat can query

### Day 23 — **Staging deployment**
- **Module:** Infra, mstart, env
- Deploy Chat, RAG API, worker, skills to staging
- Point to staging Cloud SQL; run migrations
- **Gate:** Staging chat UI loads; sample RAG query returns answer

### Day 24 — **Production migration**
- **Module:** Infra, migration scripts
- Run `migrate_local_to_cloud_sql.sh` if migrating data
- Update production env (Cloud SQL, Redis, Vertex)
- Deploy production stack
- **Gate:** Production health checks pass; no data loss

### Day 25 — **Production validation**
- **Module:** All
- Smoke test on production
- Monitor first real traffic; fix critical issues
- **Deliverable:** V1 in production; post-mortem notes

---

## Module / Agent Focus Summary

| Day | Primary module | Secondary |
|-----|----------------|-----------|
| 1 | mobius-chat/planner | mobius_parse |
| 2 | mobius-chat/planner (blueprint) | prompts |
| 3 | mobius-chat/pipeline, stages | — |
| 4 | mobius-chat/responder | — |
| 5 | mobius-chat/tests | — |
| 6 | mobius-qa/lexicon-maintenance | mobius-retriever/jpd_tagger |
| 7 | mobius-rag, mobius-dbt | ingestion |
| 8 | lexicon-maintenance | sync scripts |
| 9 | mobius-rag | AHCA docs |
| 10 | mobius-rag | ingestion |
| 11 | mobius-rag Path B | lexicon-maintenance |
| 12 | mobius-qa/retrieval-eval | — |
| 13 | mobius-retriever | mobius-rag-api |
| 14 | mobius-chat (full pipeline) | doc_assembly |
| 15 | mobius-chat/non_patient_rag | retriever_backend |
| 16 | mobius-chat/tool_agent | mobius-skills |
| 17 | mobius-chat/tool_agent | MCP |
| 18 | mobius-chat/storage | communication |
| 19 | mobius-chat tests | scripts |
| 20 | docs | — |
| 21 | All (code freeze) | — |
| 22 | mobius-dbt sync | lexicon |
| 23 | Infra / staging | — |
| 24 | Migration scripts | Infra |
| 25 | Production validation | — |

---

## Lexicon Work (Ongoing)

- **Day 6:** Audit
- **Day 8:** Updates for new plans
- **Day 11:** Retagging sprint (staging)
- **Day 22:** Full sync + retag for staging

As new documents are ingested, schedule follow-up lexicon sessions to add terms and retag. Budget ~0.5 day per 2–3 new plans added post-v1.

---

## Dependencies

- Days 7–10 (corpus) can overlap with Days 6, 8 (lexicon) if split across people
- Day 11 (retagging) requires Day 10 (corpus) complete
- Day 13 (recall) requires Day 12 (test set) complete
- Days 21–25 are sequential; no parallelization
