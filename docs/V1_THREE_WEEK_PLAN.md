# V1 Production: 3-Week Compressed Plan

> **Schedule variant** of the locked [V1_DAY_BY_DAY_PLAN.md](V1_DAY_BY_DAY_PLAN.md). Same scope and gates; 25 days compressed into **15 working days**. Lexicon work is non-negotiable.

---

## How this compresses

| 3-week day | Covers (original) | Approach |
|------------|-------------------|----------|
| 1 | Day 1 + Day 2 | Parser + routing in one sprint |
| 2 | Day 3 + Day 4 | Pipeline + responder error handling |
| 3 | Day 5 | Foundation regression (unchanged) |
| 4 | Day 6 | Lexicon audit (unchanged) |
| 5 | Day 7 + Day 8 | Corpus setup + lexicon updates same day |
| 6 | Day 9 + Day 10 | AHCA + expand to 10 plans |
| 7 | Day 11 | Retagging sprint (unchanged) |
| 8 | Day 12 + Day 13 | Eval set + recall tuning |
| 9 | Day 14 + Day 15 | Accuracy eval + RAG degradation |
| 10 | Day 16 + Day 17 | Both skills sprints (Google, scraper, +1) |
| 11 | Day 18 | Persistence & emission (unchanged) |
| 12 | Day 19 + Day 20 | Full regression + runbook |
| 13 | Day 21 | Code freeze / lock |
| 14 | Day 22 + Day 23 | Staging prep + deploy |
| 15 | Day 24 + Day 25 | Production migration + validation |

**Tradeoff:** Tighter days and less buffer. If you slip, first place to add time is splitting Week 2 (RAG) or Week 3 (skills + lock) back out.

---

## Week 1 (Days 1–5): Foundation + Lexicon Start

### Day 1 — Parser + routing
- **From:** V1 Days 1–2
- Parser: error boundaries, schema retry, fallback on malformed LLM output
- Blueprint: explicit routing for "Search for X" and "What can you do?"; `capabilities_primary=web` for search
- **Gate:** Parser tests pass; `test_agent_routing.py` — Search and capability questions route to tool

### Day 2 — Pipeline + responder
- **From:** V1 Days 3–4
- Orchestrator/stages: error boundaries on clarify, resolve, integrate; `_publish_failed` always structured
- Responder: fallback when integrator returns invalid JSON
- **Gate:** `test_chat_pipeline_comprehensive.py` 3x — 0 crashes; invalid JSON → fallback, no 500

### Day 3 — Foundation regression
- **From:** V1 Day 5
- Consolidate unit tests; add pytest markers (`integration`, `requires_rag`, `requires_skills`)
- **Gate:** `pytest mobius-chat/tests/ -v -m "not integration"` passes

### Day 4 — Lexicon audit
- **From:** V1 Day 6
- Audit lexicon: entries, J/P/D tags; document gaps (payers, doc types, AHCA)
- **Deliverable:** Lexicon audit checklist; terms to add/fix

### Day 5 — Corpus + lexicon updates
- **From:** V1 Days 7–8
- Schema for 6 doc types; ingest 2–3 plans with metadata; ensure filterable by payer/type
- Add lexicon entries for new plans; run reload/sync; verify JPD tagger on sample questions
- **Gate:** Docs in RAG filterable; JPD returns j_tags for new plans

---

## Week 2 (Days 6–9): RAG to 10 Plans + Eval + Quality

### Day 6 — AHCA + 10 plans
- **From:** V1 Days 9–10
- Ingest AHCA (state=FL, regulatory_agency=AHCA)
- Ingest remaining plans to reach 10; all 6 doc types
- **Gate:** Corpus ≥10 plans; AHCA retrievable by jurisdiction

### Day 7 — Retagging sprint
- **From:** V1 Day 11
- Re-run tagging with updated lexicon; fix document_tags, policy_line_tags
- **Gate:** document_tags populated; sync_rag_lexicon_to_chat succeeds

### Day 8 — Eval set + recall
- **From:** V1 Days 12–13
- Build 50–100 Q&A pairs; ground-truth chunks; recall@5 baseline
- Tune retrieval until recall@5 ≥ 80%
- **Gate:** Recall ≥ 80%; per-doc-type breakdown documented

### Day 9 — Accuracy + degradation
- **From:** V1 Days 14–15
- Answer accuracy eval (correct/partial/incorrect/hallucination); tune to ~90%
- RAG down → clear message + offer Google; JPD/lexicon fail → skip tagging, use parsed state
- **Gate:** Accuracy ≥ ~90% where recall passes; RAG down → no crash

---

## Week 3 (Days 10–15): Skills, Lock, Staging, Production

### Day 10 — Skills (Google, scraper, +1)
- **From:** V1 Days 16–17
- Verify mstart exports URLs; Google + scraper + tool-agent tests
- Implement one more skill (e.g. NPI lookup); add to MCP
- **Gate:** `test_skills_integration.py` pass; new skill returns valid answer

### Day 11 — Persistence & emission
- **From:** V1 Day 18
- Optional Redis; DB-only fallback; E2E streaming test
- **Gate:** Multi-turn + jurisdiction change persists; streaming works

### Day 12 — Regression + runbook
- **From:** V1 Days 19–20
- Full regression; `scripts/smoke_test_v1.sh` < 5 min
- V1 runbook: env vars, mstart, health checks, corpus/lexicon/staging
- **Gate:** All tests pass; new dev can run smoke from runbook

### Day 13 — Code freeze
- **From:** V1 Day 21
- Final regression; lock main for v1; tag release candidate (e.g. v1.0.0-rc1)

### Day 14 — Staging
- **From:** V1 Days 22–23
- Full lexicon sync QA→RAG→Chat; retag for staging; verify sync_mart_to_chat, sync_rag_lexicon_to_chat
- Deploy Chat, RAG API, worker, skills to staging; migrations
- **Gate:** Staging chat UI loads; sample RAG query returns answer

### Day 15 — Production
- **From:** V1 Days 24–25
- Migrate (e.g. migrate_local_to_cloud_sql.sh if needed); production env; deploy stack
- Smoke test; monitor first traffic; fix critical issues
- **Deliverable:** V1 in production; post-mortem notes

---

## Checklist (same as V1 scope)

- [ ] Non-failing chat (parser, routing, pipeline, responder)
- [ ] RAG: 6 doc types, 10 plans, AHCA, 80% recall, ~90% accuracy
- [ ] Lexicon: audit (Day 4), updates (Day 5), retag (Day 7), staging sync (Day 14)
- [ ] Skills: Google search, scraper, +1
- [ ] Persistence + emission
- [ ] Code lock + staging + production migration

---

## Risk and buffer

- **No buffer days.** If you need one, pull it from: (a) splitting Day 5 into corpus-only vs lexicon-only, or (b) splitting Day 8 into eval-only vs recall-only.
- **Parallel work:** If you have a second person, Week 1 Day 4 (lexicon audit) can run in parallel with Day 3 (regression); Week 2 Day 7 (retagging) can overlap with start of Day 8 (eval set).
- **Fallback:** If 3 weeks is not achievable, the canonical [V1_DAY_BY_DAY_PLAN.md](V1_DAY_BY_DAY_PLAN.md) remains the 5-week baseline; use this doc as the aggressive track and revert to 25 days if needed.
