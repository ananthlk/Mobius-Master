# RAG Restructure — Coordination Board

_Ananth's monitor. **Leads coordinate** (they don't do all the work). Each actor owns their **Status** block and prepends to the **Log**. Live dashboard mirrors this file._

**Design of record:** [Module Schematic](https://claude.ai/code/artifact/5c5eca99-21aa-442e-9a94-8b65bf5daaba) · spec: `docs/rag-target-structure-spec.md`
**Sequence (Ananth):** latency ≫ recall ≫ refactor · **updated:** 2026-07-22

---

## Leadership model
| phase | scope | lead (coordinates) | actors |
|---|---|---|---|
| **P1 · now (2-day)** | latency + recall | **EVAL** | RAG (code+data), DB (query plans), TECH (gates) |
| **P2 · deferred** | 7-module refactor (behind flag) | **TECH** | RAG (build), EVAL (outcomes), DB (Tier-3 schema) |

## Gate scoreboard
| gate | target | owner | status |
|---|---|---|---|
| latency | forced arm p50 & p95 < 5s | EVAL | 🔴 arm a: NOT pool-size (Ananth caught it) — payer BM25 = 4.8s over a TINY 19-doc pool; non-payer = 120ms over 1186. Hypothesis: relaxed k-of-n re-run drops pool scoping → full-table scan. RAG confirming SQL. |
| recall (accuracy) | oracle_recall → 0.60 | EVAL | 🟢 **MET: oracle 0.595** (s-fix ALONE, corpus untouched); router 0.345→0.433. Validates s-contamination diagnosis. |
| contract byte-compat | 12-field diff clean | TECH | ⬜ enforced on every L0–L7 touch |
| bandit intact | routing keys non-null (non-s) | TECH + EVAL | ⬜ |
| router ceiling | 0.65 (P2) | EVAL | ⬜ NOT routing-reachable: oracle caps 0.595 < 0.65, union_proxy 0.35 → needs refactor ceiling-lift (retrieval quality) |
| **prod stability** | no leaked txns | DB | 🟢 RESOLVED — RAG code fix (0634270) + DB guardrail; 37/200 conns, Payor unblocked |

## Open blockers
- 🔴 **CRITICAL: Shape-Reformat FAN_OUT latency not viable (2026-07-23 live test).** Embedding 81 fanout_codes via Vertex's `gemini-embedding-001` (1-input-per-call) = ~18.8s total (swapped to `text-embedding-004` batchable → ~9.2s embed alone, still ~17-19s with DB + Gate). **Root cause confirmed: embed-on-the-fly is architecturally unsound.** **Fix required before Step 1b ships:** precompute lexicon-code embeddings, cache them, refresh on Curation's publish cadence. Needs DB decision: where cache lives (new column on `policy_lexicon_entries`? companion table?) + ownership (Curation's pipeline or Reformat's init?). **Blocks Reformat sign-off + any FAN_OUT live eval.**
- **✅ Corpus wedge CLOSED (nothing to do):** DB forensics settled it — the 424 = 276 needs_ocr (no text) + 148 completed-but-EMPTY scraped news/directory pages (ZERO chunks). Nothing to purge, nothing to publish; none anchor a cmhc answer. The 0.47→0.60 gap is **NOT corpus content** — it's retrieval/router quality (calibration will localize it). VACUUM/REINDEX stood down permanently. 276 needs_ocr → content-less cleanup workstream (off critical path).
- **Re-calibrate on clean rev:** after RAG forces traffic on 0634270 (leak + s-fix) + 869a3fe (ILIKE), EVAL re-runs cmhc calibration → the ACTUAL post-s-fix oracle/router decides whether any heal is needed.
- ~~P0 leak~~ **RESOLVED** · ~~ROUTER_VERSION~~ **CONFIRMED v1** (env unset → v1; v2 code-present, not activated).

---

## Actor status

### EVAL (P1 lead) — coordinating latency + recall; owns outcome gates
- ✅ **Scope lens signed** + **per-module review complete** (4 signed: router, fillers, synthesis, contract).
- ⏳ **Pool edge measurement** (strict↔relaxed union): 4-config calibration on cmhc bank (union SAFE if ≥baseline−0.02).
- 🔴 **Shape/timing blocked on loop instrumentation** (Gate D): escalation loop :3137-3399 untimed; every segment timed=BLOCKER for latency validation.
- ✅ Tier-2/Tier-3 scorer lock pending (Ananth ratifying unification for synthesis sign-off).
- ✅ Eval-boundary (3-tier) + outcomes-gate sections drafted → `docs/rag-eval-boundary-and-outcomes.md`.
- ✅ **Shape-Reformat (Step 1b) co-authored** (2026-07-23): queries_reformat_postures.yaml (13 test cases covering all 6 postures + tentative CLARIFY_REPHRASE). Bounding analysis signed: N=3 is exploration constraint, not bug (empirically tunes via top-3 intent capture rate + downstream user feedback). Proposed w_p=0.4, w_l=0.6 for hybrid scoring; tune after reformat.py unit tests. UX/Chat/DB packages landed; Eval ready for build phase.
- **Conditional GREEN on Outcomes lens:** once pool+timing+tier gates land, post before/after per-cut, complete per-module sign-offs.

### RAG — owns engine code + corpus-heal execution
- ✅ Latency gate passed (rev 00468-mdh): dtag-skip@pool>200, skip_synthesis honored, c/d→a redirect.
- ✅ P0 leak PATCHED (0634270): fact-store gated on j:payor + async-with on bg tasks. **Two-for-one: also fixes s-contamination.**
- ✅ ROUTER_VERSION=v1 · ✅ ILIKE pool-scoped · ✅ **traffic live on 00470-txf**; 00471 (labels) in flight.
- ✅ Two-for-one verified: "timely filing CMHC" s→a, 3 chunks. Corpus purge HELD pending defect reproduction.

### TECH (P2 lead) — owns structural gates + module map
- ✅ Gate model + 7-module map + 3 machine-checkable checks signed; my §A/§B folded into spec (consistent, no divergence).
- ✅ Serving router determined: v1 (v2 imports v1) — consolidation is a NUMBER-MOVING MERGE.
- ⏸ **PARKED per Ananth (HOLD — don't build P2 ahead of P1):** gate tooling + router spec wait for a real P1 cut to gate.

### DB — owns query plans (P1) + Tier-3 schema (P2)
- 🟢 P0 leak verified closed (37/200 conns); guardrail binding.
- ✅ Query-plan diagnostics: uuid-cast + ILIKE pool-scope endorsed; `document_tags` autovacuum tightened (0.02).
- ✅ **424 forensics:** = docs absent from rpe (EXCEPT count). 276 needs_ocr + 148 real; **publish-not-purge**; active re-embed may self-heal. VACUUM stood down (INSERT-heavy → ANALYZE + HNSW refresh).
- ⏳ Re-count residual after re-embed drains; hand RAG the doc_ids to PUBLISH if any remain.

---

---

## Gate review status (for Ananth)

| gate | owner | verdict | notes |
|---|---|---|---|
| **Scope alignment** | all 6 lenses | ✅ GREEN | Retriever Alignment Board signed by all 6 lenses (2026-07-22). |
| **Routing contract** | EVAL | ✅ VERIFIED | Option (a) holds for shape-first sequencing; feature_vector values differ (raw→decomposed context) but structure/writer/importer locked. Not a telemetry migration. |
| **Pool edge** | EVAL | ⏳ PENDING | strict↔relaxed fallback: union SAFE or NUMBER-MOVING? 4-config calibration in flight. |
| **Loop timing** | TECH | ⏳ PENDING | Gate D blocker: escalation loop :3137-3399 untimed; need per-segment ms on every retry. TECH to instrument. |
| **Tier-2/3 lock** | Ananth | ⏳ PENDING | Scorer versioning + writer unification. Ananth's ratification needed. |

---

## Log (newest first)
- `07-23` EVAL: **Complete Shape layer coordination (Step 1a/1b/1c).**
  - **Gate (Step 1a):** ✅ CLOSED 2026-07-22 (commit 2f57369). 26-case contour bank proven live.
  - **Reformat (Step 1b):** Built + tested 2026-07-23, 12/13 cases PASS. Theme clustering works (k-means: 80 codes → 3 themes, balanced/coherent). **CRITICAL BLOCKER: FAN_OUT latency ~18.8s (embed-on-fly not viable). Fix: lexicon-embedding cache + Curation refresh. Blocks sign-off.**
  - **Structure (Step 1c):** Design signed 2026-07-23 (UX/Chat/DB/Eval). Lookup table v1 (18 cells: posture × caller_mode) is correct; hand-set cells anchor to existing code. **Blocker: caller_mode vocabulary bug (3-way incompatible vocabularies, pre-existing) must be resolved by TECH/DB before table cells lock.** Eval bank spec drafted (posture×caller_mode → convergence-rate + cost metrics).
  - **Cross-blocker:** Shape-Reformat embedding cache + Shape-Structure caller_mode normalization are both pre-reqs for shipping. Both are infrastructure decisions (not Shape defects), high-priority fixes needed before any Step 1 sign-off.
- `07-22` EVAL: **shape-first sequencing verified** — Router takes filled_shape as input; feature_vector values differ (raw→decomposed context). Option (a) holds: routing structure + writer + importer locked; not a telemetry migration. Bandit learns consistently per flag state.
- `07-22` EVAL: **per-module review complete** — 4 modules signed (router, fillers, synthesis, contract); 3 gates pending (pool edge, loop timing, tier lock). Conditional GREEN on Outcomes lens pending gates.
- `07-22` EVAL: **arm-a diagnosis CORRECTED** (Ananth caught the inconsistency) — NOT pool size. Payer BM25 = 4.8s over a **19-doc** pool; non-payer = 120ms over **1186** AHCA docs. So AHCA breadth is fine; the payer/inherited-authority path likely runs BM25 UNSCOPED (relaxed k-of-n re-run drops include_document_ids → full-table ts_rank_cd). RAG confirming the SQL. (Supersedes the "2000-doc pool" note below.)
- `07-22` EVAL: ~~arm-a latency: BM25 over ~2000-doc AHCA pool~~ — WRONG (pool is 19 docs); corrected above. Retrieval on a well-tagged query IS ms (48-120ms). Recall on a = systematic partial (~0.40 every query, not query-specific).
- `07-22` EVAL: **calibration LANDED (00471, clean)** — oracle 0.473→**0.595** (goal ~MET by s-fix ALONE), router 0.345→0.433. 0.65 = ceiling problem (refactor), NOT routing (union_proxy 0.35). Latency NOT recovered (~3s floor, un-instrumented). Per-strategy isolation running (wf_feb38ea9).
- `07-22` EVAL: clean calibration KICKED on 00471 (wf_6ddf0611) — the decisive P1-recall number (oracle/router/union + gap localization).
- `07-22` DB: **corpus wedge CLOSED** — 424 are empty (276 needs_ocr + 148 zero-chunk scraped pages); nothing to purge OR publish; re-embed drained by 05:05; VACUUM stood down permanently.
- `07-22` DB: 424 forensics — ABSENT-from-rpe (publish-not-purge); 276 needs_ocr + 148 real; active re-embed (2666 jobs today) may self-heal; VACUUM stood down.
- `07-22` EVAL: calibration HELD for corpus-settle (won't pin a baseline on a churning corpus); s-fix direction already verified.
- `07-22` RAG: **traffic live on 00470-txf** (s-fix + ILIKE); two-for-one verified (s→a, 3 chunks); 00471 labels in flight.
- `07-22` TECH: **parked per Ananth** (HOLD — P2 waits for P1 to prove out).
- `07-22` EVAL: calibration will run on 00471 (avoids mixed-build straddle) → the number that decides the recall track.
- `07-22` EVAL: **424-phantom premise unverified — purge HELD**; re-calibrate on clean rev to re-derive the accuracy gap; DB running COUNT-only reproduction.
- `07-22` DB: P0 leak RESOLVED & VERIFIED (37/200 conns, idle-in-txn 4@1s); guardrail binding; Payor unblocked.
- `07-22` RAG: P0 leak PATCHED (0634270, two-for-one w/ s-fix); ROUTER_VERSION=v1 confirmed; ILIKE pool-scoped (869a3fe).
- `07-22` EVAL: eval-boundary (3-tier) + outcomes-gate sections drafted → `docs/rag-eval-boundary-and-outcomes.md`; ILIKE tagged NUMBER-MOVING.
- `07-22` TECH: accepted P2 lead + P1 structural-gates; standing up runnable checks in `scripts/techday/`.
- `07-22` DB: connection-leak incident handled + guardrail; latency query-plan diagnostics posted; VACUUM/REINDEX queued post-heal.
- `07-22` TECH: serving router = v1 (v2 imports v1); no dead router — consolidation is NUMBER-MOVING merge; spec finalized on their side.
- `07-22` Ananth: signed off; **latency ≫ recall ≫ refactor**; DB looped in; EVAL leads P1, TECH leads P2.
- `07-22` EVAL: audit refuted refactor-first (3/10) → surgical+data-first (7.5); schematic published; boundary (3-tier scorer) defined.
- `07-22` RAG: latency gate passed 8/8 < 12s @ rev 00468-mdh.
