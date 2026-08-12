# Filler b (Vector Search) — Progress Tracker

**Status:** Code + unit tests complete, verified against live dev DB. Same pattern as `pool-simulation-tracker.md` et al.

---

## What was built

- `app/services/retriever/fillers/filler_b.py` — `fill_shape_vector()`. Structural template: `filler_a.py`.
- `app/services/retriever/fillers/test_filler_b.py` — 12 unit tests, real pytest execution, all passing.

## Verified-before-trust (not repeating Filler a's retracted-sign-off mistake)

**Field distinction, verified directly in code** (`pool/public_adapter.py:198-201`): vector-arm candidates carry cosine similarity in `PoolCandidate.score`; `tag_select` carries a coverage *count* in the same field; `inherited` explicitly sets `score=None`. Filtering on "score is not None" (Filler a's pattern for `bm25_score`, which — unlike `.score` — really is computed uniformly across every arm) would silently mix a tag-coverage count in with cosine similarities. Filler b filters `source_arm == "vector"` explicitly. Covered by `test_excludes_non_vector_arms` and `test_mixed_arms_and_unscored`.

**Unit tests — real execution, real artifact:**
```
$ uv run pytest app/services/retriever/fillers/test_filler_b.py -v
============================== 12 passed in 0.04s ==============================
```
All 12 pass, including the critical `test_reads_score_not_bm25_score` regression guard (mirrors Filler a's near-miss).

**Live-DB verification** (cloud-sql-proxy :5433, dev): ran `PublicSourceAdapter.vector_search()` directly against two different real queries.
- Query 1 ("timely filing deadline for Sunshine Health FL Medicaid claims") → 8 candidates, `score=0.797202063654677`, descending, all `source_arm="vector"`.
- Query 2 ("credentialing requirements for a new provider group") → different score (0.708954), confirming scores genuinely vary by query, not a hardcoded/constant-bug artifact.

This confirms Pool really does populate `.score` with real, per-query cosine similarity for the vector arm — the assumption Filler b's whole design rests on.

## Real finding, NOT Filler b's bug — corpus/chunking quality (escalating, not fixing here)

Both live queries above returned a **top-N entirely composed of degenerate junk chunks** — for query 1, every one of the top-8 results was the literal text `"Florida Medicaid o CHIP"` repeated verbatim across 8 different documents; for query 2, the top-5 were all a bare `"-"` character.

Traced the scale directly:
```sql
SELECT text, count(*) FROM rag_published_embeddings
WHERE embedding_vec IS NOT NULL AND length(trim(text)) <= 30
GROUP BY text ORDER BY count(*) DESC LIMIT 15;
```
- `"-"` — **185,261 rows** (~9.6% of the entire 1,937,353-row embedded corpus)
- `"‐"` (lookalike dash) — 14,234
- `"GOVERNOR"` / `"SECRETARY"` — 9,618 / 8,652
- UI chrome that leaked in from PDF extraction: `"MS Word Viewer"` (1,003), `"Ok, I understand"` (1,003), `"Windows Media Player"` (1,002), `"Twitter.com/AHCA_FL"` (1,530)

These embed to real, non-buggy vectors — short/degenerate text embeds near a generic region that happens to score moderately-high cosine similarity against almost any query, and `bm25_score=0.0` doesn't filter them out of the vector arm (bm25 is computed with an AND-query, so it correctly scores 0 on these, but the vector arm doesn't consult bm25 at all).

**Why this is out of Filler b's scope, not something to patch here:** Filler b's contract is read-only over `PoolResult` — it correctly ranks whatever Pool hands it. The defect is upstream, in the chunking/embedding pipeline publishing sub-30-character junk chunks (headers, PDF-viewer chrome, bare punctuation) as first-class embedded rows with no minimum-content-length gate. Fixing it here would mean Filler b re-deriving content-quality judgments Pool/Curation already own — exactly the kind of scope violation this fleet's process rules forbid.

**Escalated:** reported to Retriever (cross-session) for routing to Curation (owns chunk→embed→tag→publish) / Maintaining (owns nightly corpus-integrity sweeps); also flagged to Ananth directly given the ~10%-of-corpus scale.

## Correction (2026-07-23, post-reranking-replication) — earlier "junk contamination 0%" claim was wrong

While spot-checking the reranked results for cmhc001 (real live pipeline run, not synthetic), found that **all 10 of its assigned top-N chunks are the literal text `"Florida Medicaid o CHIP"`** — the exact junk-boilerplate cluster identified earlier in this doc. My calibration script's `junk_contamination_rate` metric reported **0%** for this query, which was wrong for it specifically.

Root cause: the junk detector used a hardcoded set of known offenders (`"-"`, `"GOVERNOR"`, etc., drawn from a `length <= 30` frequency histogram) plus a `length <= 2` fallback. `"Florida Medicaid o CHIP"` is 23 characters and wasn't frequent enough to appear in that specific top-15 histogram, so it slipped through undetected. **The earlier "0% junk contamination across all real bank queries" claim (reported to Eval/Retriever) was an artifact of an incomplete proxy heuristic, not genuine absence of junk** — correcting that now rather than let it stand.

Separately, verified the new composite reranking (sim/authority/length/jpd + decay floor) does **not** fix this case: `_length_score` correctly scores these 23-char chunks at 0.0 (below the 50-char floor), but that's only a 0.05-weighted signal against `sim`'s 0.25 weight — the junk cluster's raw cosine similarity (0.797) has too large a margin over whatever real content exists for this query for a 0.05-weighted penalty to overcome. Composite-reranked order was byte-identical to the pre-reranking raw-score order for this query (verified directly, chunk-id-by-chunk-id). **This is real, correctly-scoped evidence that reranking alone cannot solve the corpus-junk problem — the fix has to be upstream (the min-content-length gate already flagged to Curation/Maintaining), not downstream in any filler's ranking logic**, regardless of how many real signals that filler's rerank composite includes.

## Stopgap fix (2026-07-23, same day) — Retriever reproduced 100%-junk occupancy live

Retriever independently ran `fill_shape_vector` against the primary example query (Sunshine Health timely filing) and got **occupancy=10/10, all 10 chunks the literal text "Florida Medicaid o CHIP"** — the composite reranking above genuinely was not enough; sim's 0.25 weight beat length's 0.05-weighted penalty on real data, exactly as the correction above predicted in principle but now confirmed as a live, reproducible failure, not a theoretical one.

Two stopgap mitigations added, both using only data already on `PoolCandidate` (no new seam, no DB call — stays inside gate b):
1. **Hard length floor** (`_MIN_CHUNK_LENGTH = 50`, legacy's own `_length_score` zero-point) — candidates below it are dropped BEFORE ranking, not soft-penalized. An outright filter isn't weight-tunable around; this is what actually works.
2. **Exact-text dedup** — candidates sharing byte-identical `.text` collapse to their best-scoring instance before slot assignment. Verified live that `content_sha` does NOT catch this (15 identical-text rows all had distinct content_sha — salted per-document, not a pure content hash), so dedup is on raw `.text`.

Re-ran the exact reproduction query after the fix: **occupancy=0/10, not 10/10-junk.** Honest empty beats confident-wrong. Checked `tag_select` for the same query to confirm this isn't a corpus-wide dead end: **185 real, substantive candidates** (claim dispute resolution program, telemedicine definitions, etc.) — the vector arm alone was 100% poisoned for this query, the corpus itself is fine, BM25 would serve real content.

36/36 unit tests pass (up from 12), including a direct regression test reproducing Retriever's exact failure shape (`test_reproduces_retriever_failure_case_now_fixed`). Retriever independently re-verified: same occupancy=0 result, 24/24 filler_b tests + 174 fleet-wide, no regressions.

**Real, important gap surfaced by this fix, not caused by it:** Retriever checked `_run_fillers_simple`'s own docstring — there is no Observer/retry logic today ("NO Observer — no confidence check, no retry to later rungs on a weak result"). Before this fix, vector always returned *something* (even if silently wrong). After, a slot can now come back honestly empty, and without Observer, nothing automatically retries a later rung — even when, as verified above, `tag_select` had real content available for the exact same query. This was already a known, tracked gap (Observer build-blocked pending Fillers+Synthesis), but this fix makes it a live operational risk for the first time rather than theoretical. Flagged to Router/whoever owns the Observer timeline.

## Final calibration (2026-07-23, post-stopgap-fix) — real numbers

Full 22-query live run, `eval/calibration/filler_b_vector_metrics.json`:
- 20/20 scored queries, 0 errors.
- `mean_junk_contamination_rate`: **0.0 — now genuinely true** (junk is filtered, not silently served; the earlier 0.0 claim was a detector blind spot, this one reflects the actual fix).
- `mean_under_filled_slots`: **0.35** — the honest cost of the fix. 7/20 scored queries (35%) hit vector-arm under-fill:
  - 6 queries totally empty (0/10): cmhc001, cmhc007, cmhc012, cmhc017, cmhc019, cmhc020.
  - 1 query severely partial (1/10): cmhc009.
- Confirmed the junk is a **broad class**, not one isolated cluster — checked 3 of the 6 zero-occupancy queries directly: cmhc007's vector pool (458 candidates) was 2 distinct junk texts (`"How to Set Up an Appointment"`, `"How to Ask for Help"` — navigational/UI boilerplate); cmhc009's was a mix including `"Florida Medicaid"` variants; cmhc012's was 191/191 `"Florida Medicaid o CHIP"`. Additional, concrete evidence for the corpus-cleanup task already flagged to Curation/Maintaining.

## Remaining before Eval sign-off

- Cross-agent sign-off (Chat/Eval/DB/TECH) — not yet requested.
- Filler b's own code is ready. Production-readiness for routing "b" as an early/only ladder rung depends on Observer landing first (see above) — a real dependency this fix surfaces, not a defect in Filler b itself.
