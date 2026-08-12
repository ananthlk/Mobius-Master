# Filler a (BM25) — Calibration Plan (Eval Gate)

**Status:** DRAFT — awaiting Eval sign-off before implementation.

**Owner:** Filler a agent (this session).

**Gate:** Eval conditional-blocked on calibration before Filler a ships.

---

## 1. Hypothesis

**Baseline (uniform top-N):** Sort Pool candidates by bm25_score (descending), assign top-N to all slots regardless of slot semantics. No slot-specific filtering or ranking.

**Proposed (per-semantic):** Same BM25 sort, but apply slot-semantic-specific filtering/ranking (e.g., external_context slots prefer web/external sources). Improves relevance per slot posture.

---

## 2. Test Harness

**Query bank:** CMHC 26-query bank (same as Pool/Shape calibrations).

**Per-query flow:**
1. Query → Shape (produces AnswerShapeResult with slots) → Pool (produces candidates with bm25_score) → **Filler a (baseline and proposed, run separately)**
2. Collect metrics per slot, per posture.
3. Compare baseline vs proposed.

---

## 3. Metrics (before/after)

### Per-posture metrics:
- **Occupancy rate** (`actual_occupied / capacity` per slot per posture)
- **Recall** (% of Pool candidates that got assigned; should NOT change, same pool)
- **Under-fill rate** (% of slots that occupancy < capacity; should NOT increase)
- **Coverage diversity** (for FAN_OUT postures, % of unique top themes represented in filled slots)

### Acceptance criteria:
- ✅ Per-posture recall: baseline ≥ proposed - 0.02 (no regression)
- ✅ FAN_OUT diversity: proposed ≥ 80% of unique themes (thematic exploration working)
- ✅ Under-fill: proposed ≤ baseline + 5% (not worse than uniform top-N)

---

## 4. Baseline Implementation (NUMBER-MOVING gate)

Run uniform top-N (no slot-semantic filtering) against all 26 queries:

```python
def fill_shape_uniform_topn(pool_result, shape_result):
    """Baseline: ignore slot semantics, just take top-N by bm25_score."""
    scored = [c for c in pool_result.candidates if c.bm25_score is not None]
    scored.sort(key=lambda c: c.bm25_score, reverse=True)
    
    filled_slots = []
    remaining = scored.copy()
    
    for slot in shape_result.slots:
        assigned = remaining[:slot.capacity]
        remaining = remaining[slot.capacity:]
        # No semantic filtering, just top-N
        filled_slots.append(FilledSlot(...occupancy..., chunks=assigned))
    
    return FilledShape(slots=filled_slots, filling_strategy="uniform_topn")
```

**Baseline run:** Measure per-query occupancy, recall, under-fill on cmhc-26.

---

## 5. Proposed Implementation (Filler a v0.1)

Current implementation: Same BM25 sort, but non-overlapping per-slot assignment + v1 semantic filtering placeholder.

**Current:** `fill_shape_bm25()` in `filler_a.py` (tests passing, 15/15).

**Semantic filtering details (v1):**
- `direct_answer`: no filtering, take highest-score (same as baseline).
- `thematic_exploration`: no filtering v1 (defer theme-specific filtering to Router).
- `external_context`: **placeholder** — could filter by `source_type in ['web', 'external']`, but v1 takes all (re-evaluate post-Pool).

---

## 6. Run Protocol

1. **Baseline pass:** Uniform top-N on cmhc-26.
   - Output: `baseline_metrics.json` (per-query occupancy, recall, under-fill).
2. **Proposed pass:** Filler a v0.1 on cmhc-26 (same queries, same Pool outputs).
   - Output: `proposed_metrics.json`.
3. **Comparison:** Per-query and aggregate (mean/std) metrics.
4. **Decision:** Does proposed ≥ acceptance criteria? If yes, ready for sign-off.

---

## 7. Expected Outcomes

- **Occupancy:** Proposed likely similar to baseline (both fill top-N).
- **Recall:** Same (both consume the same Pool).
- **Diversity (FAN_OUT):** Proposed should maintain/improve if semantic filtering is tuned; baseline is the floor.
- **Under-fill:** Proposed ≤ baseline + 5%.

**Likely result:** Proposed ≈ baseline on these metrics (v1 semantic filtering is minimal). If so, Eval approval focuses on "not worse + meets diversity target for FAN_OUT," not on beating baseline.

---

## 8. Timeline & Dependencies

- **Prerequisite:** Pool's bm25_score live (DONE 2026-07-23).
- **This calibration:** ~2-3 hours once Eval confirms protocol.
- **Blocker release:** Once metrics show proposed ≥ acceptance criteria, Eval signs off.
- **Ship gate:** Eval approval + TECH's confirmed answer on parent spec.

---

## 9. Open Questions for Eval

1. **Baseline fair?** Uniform top-N is correct baseline, or should baseline also apply semantic filtering?
2. **Diversity metric threshold:** 80% theme coverage for FAN_OUT is the right bar, or should it be higher/lower?
3. **Regression tolerance:** baseline ≥ proposed - 0.02 on per-posture recall, or stricter?
4. **Per-arm variation:** Should we run before/after per-arm (tag_select, vector, inherited get different distributions), or aggregate only?

---

## 10. Sign-off

- [ ] Eval: Approves protocol + metrics + acceptance criteria.
- [ ] Filler a: Runs calibration on cmhc-26 (baseline + proposed).
- [ ] Eval: Reviews results, confirms acceptance criteria met.
- [ ] Retriever: Routes for parent-spec close (Chat/UX/DB/Eval/TECH).
