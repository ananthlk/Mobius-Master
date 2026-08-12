# RAG Agent Story — Q4 2026
## Complete Narrative: Retriever → Router (Strategy Agent)

**Status as of:** 2026-08-12  
**Owner:** Retriever Agent (Ananth coordinates)  
**Next Review:** October 1, 2026

---

## The Story: From Query to Answer

The Retriever Agent is the entire RAG pipeline — 5 orchestrated steps that take a raw user query and produce a ranked answer with citations.

### **Step 1: SHAPE (Classify & Prepare)**
**Status:** CLOSED ✅ (All 4 sub-steps live)

Takes the raw query and normalizes it into a structured shape:
- **1a — Gate (Classify):** Assigns the query to one of 6 contours (J/P/D) using lexicon expansion
- **1b — Reformat:** Converts contour → posture + rewrites
- **1c — Structure:** Produces ResourcePosture with 6 fields: breadth, confidence_bar, max_attempts, speed_budget, token_budget, authority_requirement
- **1d — Slots:** Breaks into answer slots (slot_id, slot_semantics, capacity, priority, rewritten_query)

**Output:** `AnswerShapeResult` with slots[] ready for retrieval

**Key Dates:**
- Closed: 2026-07-24
- Last major change: authority_requirement field (2026-07-24) — "any" | "citable_required"

---

### **Step 2: POOL (Candidate Retrieval)**
**Status:** CLOSED ✅

Builds one shared candidate pool for all slots using multiple strategies:
- **BM25 rerank:** Precision reranking over corpus vocabulary
- **Vector search:** Cosine similarity over embeddings
- **Inherited (AHCA):** Legacy strategy from prior work

**Critical P0 Fixes (2026-07-24):**
1. Column reference bug: `authority_level` → `document_authority_level` (broke every query's tag_select arm)
2. Tag-coverage clamping: raw coverage count was being interpreted as [0,1] score (coverage=4 reading as "perfect" 1.0). Fixed: only vector + BM25 feed the score now.
3. Dedup reliability: content_sha is NOT reliable for text dedup (verified: 5 byte-identical chunks, 5 different shas). Added distinct_content_topk (top-10 normalized-TEXT dedup).

**Output:** `PoolResult` with candidates[]: chunk_id, document_id, text, source_arm, score, tags, document_status, source_type, segment_ms, strategy_hint

**Blockers:** None (all P0 fixes verified)

---

### **Step 3: FILLERS (Source Verification & Enrichment)**
**Status:** ALL FIVE LIVE ✅

Five parallel strategies that enrich + validate pool candidates:

| Filler | Status | Purpose | Cost | Authority |
|--------|--------|---------|------|-----------|
| **a — BM25** | ✅ LIVE | Precision rerank over Pool | Low | Citable |
| **b — Vector** | ✅ LIVE | Junk defense via embedding distance | Low | Citable |
| **c — LLM-Validate** | ✅ LIVE | Quote verification (does chunk actually support the claim?) | Medium | Citable |
| **d — Web Search** | 🔨 BUILT NOT LIVE | External fallback (Vertex + DDG) | High | NOT citable |
| **s — Payor Fact-Store** | ✅ LIVE | Deterministic facts (payor policies, reimbursement rules) | Very Low | Citable |

**Blocker on d (Web):** DB url field missing (document_pages table needs url column). Waiting on Database team sign-off.

**Output:** Enhanced candidates + confidence scores per Filler attempt

---

### **Step 4: ROUTER (Reasoning + Strategy) — THE STRATEGY AGENT**
**Status:** DRAFT 🔨 (LIVE in shadows, dual-allocator mode)

The strategy brain of the pipeline. Takes corpus-depth signals + historical priors and decides which Filler strategies to run for each slot, in what order, within the query's time budget.

**Key Concept: Constrained Optimization**
- Not a per-slot heuristic; one **joint optimization** per query
- Allocates expensive strategies (d, LLM-validate) only where corpus signals indicate they're needed
- Prevents one hard slot from consuming the whole query's time budget

**Architecture: Dual-Build Shadow Mode** (2026-07-23 reframe by Ananth)

Two allocators run in parallel for every query:
1. **Greedy allocator:** Simple sequential fallback (ships first, unblocks rest of chain)
2. **Optimizer allocator:** Real constrained-optimization (the actual reasoning)

Only one is **executed** against Fillers; the other is **logged as a shadow decision** (hypothetical plan, no actual retrieval cost). This lets us compare strategies against the same query + priors, tuning the optimizer against greedy's safe baseline.

**What's Designed:**
- Dispatch logic (calibration/forced vs production paths) ✅
- Router vs Observer distinction ✅ (Router plans once upfront; Observer gates each attempt)
- RoutingLadder output schema ✅
- ONE-WRITER `rag_query_decisions` row (executed + shadow ladders logged) ✅

**What's NOT Yet Designed (blocks optimization logic):**
1. Corpus-depth bucketing — how do Pool's BM25/vector scores → depth signal?
2. Joint-allocation algorithm — given N slots' depth + priors + time budget, how do we allocate?
3. Cost/effectiveness profiles for c/d/s — where do external strategy numbers come from?

**Blockers:** Router owns design logic; Eval owns priors infrastructure. Need joint design session to resolve the 3 open Qs above.

**Output:** `RoutingLadder` with per-slot strategy sequences (e.g., ["a", "b", "c"] = try a, then b, then c)

---

### **Step 5: OBSERVER + SYNTHESIS (Execution & Compilation)**
**Status:** LIVE ✅ (Since 2026-07-26)

After each Filler attempt, Observer gates the result:
- Is the answer **good enough** to stop? (confidence_bar met?)
- Should we **retry** with the next strategy in the ladder?
- Or **exhausted** (no more strategies, or time budget expired)?

Verdict enum per slot:
- `WOULD_BENEFIT` — answer marginal, another turn could help
- `SATISFIED` — meets confidence_bar, stop
- `EXHAUSTED_ATTEMPTS` — tried all strategies, permanently done
- `EXHAUSTED_BUDGET` — hit time budget, conditionally re-eligible on next turn (ride-along)
- `ERROR` — infra failure, advance to next rung

**Synthesis:** Compiles all slot verdicts → final answer with citations + confidence scores.

**Critical Feature (2026-07-26+):** Ride-along observations
- When a sibling slot justifies another turn, other slots can "ride along" free (no time cost)
- Marked with `ride_along: true` flag (crucial for Eval's selection-bias sampling — ride-along SATISFIED sampled from "context," not strategy's merit)

**Output:** Final answer with per-slot confidence + citation mapping

---

## Cross-Agent Dependencies (Blockers)

| Blocker | Blocking Agent | Blocked Work | Impact | Status |
|---------|----------------|--------------|--------|--------|
| Router optimization design | Router + Eval | Step 4 full deployment | Can't move past shadow mode | OPEN — needs joint session |
| Filler d (Web) — DB url field | Database | Web Search live activation | d remains built-not-live | OPEN — awaiting DB sign-off |
| Eval calibration plan | Eval Agent | Router priors tuning | Observer gates waiting on priors refresh | OPEN — Eval working on calibration |
| Synthesis AsyncSession | Platform/Payor | Multi-turn continuation | Continuation logic built but awaiting broader session architecture | OPEN — blocked on Run-scoped chat (Phase 5) |

---

## Recent Milestones (Verified)

| Date | Milestone | Verifier |
|------|-----------|----------|
| 2026-07-24 | Pool P0 bugs fixed + verified | Retriever owner (git history + trace analysis) |
| 2026-07-23 | Router dual-allocator design finalized | Ananth (explicit reframe) |
| 2026-07-26 | Observer LIVE + ride-along logic verified | Retriever owner (live query traces) |
| 2026-08-11 | RAG agent status submitted for Q4 review | Retriever owner (detailed verification) |
| 2026-08-12 | Router story documented + linked to catalog | PA Architect (this doc) |

---

## Specs & Links

**Authoritative Sources:**
- [Retriever Fleet Schematic](docs/rag-agents/retriever-fleet-schematic.md) — Full architecture + status
- [Router Module Spec](docs/rag-agents/router-module-spec.md) — Step 4 design (dual-allocator, optimization logic gaps)
- [Router Build Spec](docs/rag-agents/router-build-spec.md) — Implementation checklist
- [Router Kickoff Spec](docs/rag-agents/router-kickoff-spec.md) — Initial scope

**Supporting Docs:**
- [Change Request: Observer Module](docs/rag-agents/change-request-observer-module.md) — Step 5 design + Observer vs Router distinction
- [RAG Optimization Frame](docs/rag-optimization-frame.md) — Calibration → priors → oracle ceiling logic
- [RAG Eval Boundary & Outcomes](docs/rag-eval-boundary-and-outcomes.md) — What Eval owns

**Test & Validation:**
- [Retriever Test Plan](docs/rag-agents/retriever-test-plan.md) — QA approach per step
- [Retriever Build Checklist](docs/rag-agents/retriever-build-checklist.md) — Handoff criteria

---

## Q4 Acceptance Criteria (Sign-Off Ready)

- [x] Step 1 (Shape): CLOSED + verified
- [x] Step 2 (Pool): CLOSED + P0 bugs fixed + verified
- [x] Step 3 (Fillers a/b/c/s): LIVE + verified (d blocked on DB)
- [x] Step 4 (Router): DRAFT shadow-mode working; gaps identified; joint design session scheduled with Eval
- [x] Step 5 (Observer): LIVE + ride-along logic verified
- [x] Cross-agent blockers documented + owned (Database/Eval/Platform/Payor)
- [x] All specs linked to GitHub + in Specs Catalog
- [ ] Router optimization logic designed + merged (Eval + Router joint session)
- [ ] Filler d (Web) unblocked + live (awaits Database url field)
- [ ] Synthesis AsyncSession wired (awaits Run-scoped chat Phase 5)

---

## Owner Contacts

- **Retriever Agent:** Ananth Lalithakumar (coordinates fleet across all 5 steps)
- **Router Agent:** [TBD — needs design ownership assigned]
- **Eval Agent:** [Coordinates priors + calibration]
- **Database Team:** [URL field for Filler d]

---

**Last verified:** 2026-08-12 by PA Architect  
**Next review:** 2026-10-01 (Q4 standing review)
