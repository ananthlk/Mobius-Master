# Filler b (Vector Search) — Calibration Plan (Eval Gate)

**Status:** DRAFT — awaiting Eval sign-off before implementation. Same standing hold as every filler (Fillers parent spec: Eval conditional-green-on-logic, build-blocked pending a per-filler calibration plan).

**Owner:** Filler b agent (this session).

**Gate:** Eval conditional-blocked on calibration before Filler b ships.

**Read this first:** Filler a's calibration sign-off was retracted — reported numbers were never produced by a real run (skipped test stub, no artifact). This plan documents the *protocol*; no numbers in this document are calibration results, and none will be reported as such until an actual run produces a reproducible artifact.

---

## 1. Hypothesis

**Baseline (uniform top-N):** Sort Pool's vector-arm candidates by `.score` (cosine similarity, descending), assign top-N to all slots regardless of slot semantics.

**Proposed:** Same sort, same v1 behavior — Filler b currently has no slot-semantic-specific filtering (identical honesty note to Filler a's plan: v1 semantic filtering is a placeholder, not yet implemented). So baseline and proposed are expected to be **identical** at this version; this calibration establishes the vector arm's raw occupancy/recall numbers, not a "does filtering help" comparison.

---

## 2. Test Harness

**Query bank:** CMHC 26-query bank (same as Pool/Shape/Filler a calibrations — `eval/queries_cmhc.yaml`, per the standing gotcha that an unqualified bank_path silently loads the wrong bank and reports all-zeros).

**Per-query flow:**
1. Query → Shape (Gate→Reformat→Structure→Slots, produces `AnswerShapeResult`) → Pool (`run_pool_for_query`, produces candidates with `.score` per arm) → **Filler b** (`fill_shape_vector`).
2. Collect metrics per slot, per posture, **per query's actual vector-arm candidate set** (not the whole pool — Filler b only ever sees `source_arm == "vector"` rows).
3. No baseline/proposed split needed this version (see §1) — single pass, report raw metrics.

---

## 3. Metrics

### Per-posture metrics:
- **Occupancy rate** (`actual_occupied / capacity` per slot per posture)
- **Vector-arm contribution rate** (what fraction of Pool's total candidates for that query were `source_arm == "vector"` — if a query's pool has zero/few vector candidates, Filler b's occupancy is structurally capped regardless of ranking quality; must be reported alongside occupancy, not conflated with it)
- **Under-fill rate** (% of slots that occupancy < capacity)
- **Junk-chunk contamination rate** (NEW, specific to this filler — see §4): % of assigned chunks per query whose `text` matches the known degenerate-chunk patterns already confirmed live (bare `"-"`, bare section-header words, PDF-viewer UI chrome). This is not a metric Filler a needed because BM25's term-match requirement naturally excludes near-empty text; vector similarity does not.

### Acceptance criteria:
- ✅ Occupancy ≥ 80% wherever vector-arm contribution rate ≥ capacity (i.e., don't under-fill when there was enough real supply — a Filler b bug, not a Pool/corpus issue, would show up here)
- ✅ Junk-chunk contamination rate reported per query, **no acceptance threshold set yet** — this is a known corpus defect (~9.6% of the corpus is a single `"-"` character; separately escalated to Curation/Maintaining, tracked via a spawned cleanup task, not a Filler b fix). Calibration should measure it so post-cleanup improvement is visible later, not gate Filler b's sign-off on a problem Filler b can't fix.
- ✅ Deterministic: same Pool output → same assignment (already covered by unit test `test_deterministic_order`, re-confirm at the integration level)

---

## 4. Known confound — corpus junk chunks (read before interpreting results)

Verified live against dev DB (`docs/rag-agents/filler-b-vector-tracker.md`): ~9.6% of the embedded corpus is degenerate junk (`"-"`, bare headers, PDF-viewer chrome) that returns genuine, non-buggy cosine-similarity scores and can win top-N vector slots outright — confirmed for 2/2 test queries during build verification. This means:

- Some cmhc-26 queries may show Filler b "successfully" filling slots with junk if the vector arm's actual top candidates for that query happen to be junk chunks. That is a **Pool/corpus quality result being measured**, not a Filler b ranking defect — Filler b is correctly ranking what it was given.
- Report junk-chunk contamination rate explicitly per query (§3) so Eval can distinguish "Filler b ranks correctly" from "the corpus is polluted for this query" — don't let corpus noise block Filler b's own sign-off, and don't let Filler b's sign-off hide the corpus problem either.
- Re-run this calibration after the corpus cleanup task lands (task flagged separately, out of Filler b's scope) as a natural before/after check on real recall improvement — worth flagging to Eval as a planned follow-up, not part of this gate.

---

## 5. Run Protocol

1. **Single pass:** `fill_shape_vector()` on cmhc-26, real Shape→Pool→Filler b pipeline (not synthetic fixtures — this is the gap between unit tests, already done, and calibration).
   - Output: `filler_b_vector_metrics.json` (per-query occupancy, vector-arm contribution rate, under-fill, junk-contamination rate).
2. **Aggregate:** mean/std across the 26 queries, broken out by posture (PRECISE/FAN_OUT/RELY_ON_EXTERNAL/CLARIFY_REPHRASE).
3. **Decision:** does the run meet §3's acceptance criteria? If yes, ready for sign-off; junk-contamination numbers reported for visibility, not as a blocking bar.

---

## 6. Timeline & Dependencies

- **Prerequisite:** Pool's vector arm live and verified (DONE — confirmed live 2026-07-23, this session).
- **This calibration:** not yet run. Requires the real Shape→Pool pipeline wired end-to-end for 26 real queries — a heavier lift than Filler a's equivalent since it needs live embedding calls (not free/instant like BM25's `ts_rank_cd`), so expect real API latency (verified ~4.6s embed + ~2.4s vector search for one query live during build verification — cache-cold; cache-warm should be much faster per `_embed_with_cache`).
- **Blocker release:** Eval confirms this protocol (§3 acceptance criteria, especially the junk-contamination non-blocking treatment in §4) before the run is executed and reported.

---

## 7. Open Questions for Eval

1. Is "measure junk-contamination, don't gate on it" the right call, or should Eval want a hard ceiling even before the corpus cleanup lands?
2. Same baseline-fairness question Filler a raised: is uniform top-N (no semantic filtering) an acceptable v1 bar, or does Eval want semantic filtering built before calibration counts?
3. Should the vector-arm-contribution-rate metric (§3) be reported back to Router/Pool as a signal (e.g., "this query's vector arm was starved, don't trust Filler b's occupancy as a ranking-quality signal for it") — this seems like exactly the kind of per-strategy prior Router's Eval-owned-priors design (`router-module-spec.md`) will eventually want, flagging for cross-design awareness, not deciding here.

---

## 8. Sign-off

- [ ] Eval: Approves protocol + metrics + acceptance criteria, including junk-contamination treatment (§4).
- [ ] Filler b: Runs calibration on cmhc-26 (real pipeline, real artifact).
- [ ] Eval: Reviews results, confirms acceptance criteria met.
- [ ] Retriever: Routes for parent-spec close (Chat/UX/DB/Eval/TECH).
