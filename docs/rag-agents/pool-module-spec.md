# POOL Module Spec (Step 2) — v1

**Status:** DRAFT — kickoff artifact only. No code written yet. Prepared by Retriever for handoff, following the exact process Shape:Gate/Reformat/Structure used.
**Owner:** to be assigned (new sub-agent under Retriever — "Pool Agent," first sibling module OUTSIDE Shape).
**Scope of this spec:** Pool only — build ONE shared candidate pool, once, for the whole query. Does not touch Shape's locked logic (Gate/Reformat/Structure all closed 2026-07-23, all six architects signed off). Does not do Router's strategy selection or Fillers' slot-filling.

---

## 0. Why Pool exists — the root cause it fixes

Per `docs/rag-target-structure-spec.md` §1 (Technical Review + Eval co-authored, verified in code): strategies a/b/c/d today run as **independent, redundant, non-unioning arms** — each re-embeds and re-scans the DB, building its own candidate pool. No shared pool builder exists today. This is the single structural root cause of both the latency problem (repeat scans) and the accuracy ceiling (non-union caps oracle recall at single-best-arm).

**Pool's whole job:** kill both symptoms with one structure — build the candidate pool ONCE, let every downstream filler read from it.

## 1. Where Pool sits in the chain

```
Query → SHAPE [Gate → Reformat → Structure] (ALL CLOSED) → POOL (THIS MODULE) → ROUTER → FILLERS → SYNTHESIS → CONTRACT → TIMING
```

Shape hands off a `StructureResult`: `rewritten_queries[]`, `answer_shape`/slots (if Structure ended up owning that — verify against Structure's actual closed contract, don't assume), `ResourcePosture {breadth, confidence_bar, max_attempts, speed_budget}`, scope/auth context (if Structure owns it — also verify, per Structure's own open question in its spec, this may have landed with the orchestrator instead). **First task: read `shape/contracts.py`'s actual closed `StructureResult` dataclass, not this spec's guess at its shape.**

## 2. Input — what Pool receives

Whatever `StructureResult` actually contains post-close (verify, don't assume) — most importantly:
- `rewritten_queries[]` (one query for most postures, up to `MAX_FANOUT_THEMES=4` for FAN_OUT)
- `ResourcePosture.breadth` — how wide the pool should be
- `ResourcePosture.speed_budget` — the timing envelope this build must respect
- scope/auth context — which of the 4 federated pool sources (public/org/instant-rag/cache) this pool is allowed to draw from. **Do not federate across a scope boundary — "federate, never leak" is the P0 principle from the original Pool design.**

## 3. Output — the shared candidate pool contract

One assembled pool object, built once, that Fillers read **purely** (no DB handle, no re-embed, no re-scan — see Gate (b) below). Must include, at minimum:
- The unioned candidate set (vector + keyword + payer-authority contributions, deduped)
- Per-candidate provenance (which source/arm surfaced it, for Router's feature vector and Contract's `source_types[]`/`cited_source_indices[]` downstream)
- Timing per segment (embed pass, vector search, keyword search, tag-filter) — **every DB/retrieval segment timed, untimed = RED per gate (d)**
- `status` (planned/live) and `source_type` passthrough per chunk — required by Product-Awareness's reality-gating condition (target-structure-spec §10) so it survives pool→shape→synthesis→contract

## 4. What's genuinely undesigned (Pool's real work)

1. **Pool DB access pattern — gate (i), DB-owned, MUST be decided explicitly before building:** pool-first (vector/keyword search → apply tag `?` filter on the small pooled id-set) OR GIN-index `chunk_{d,p,j}_tags` (proven 268× speedup on `document_tags` already). **Never seq-scan `rag_published_embeddings` (1.94M rows) on a `?` predicate** — this is the single highest-value non-negotiable from DB's sign-off on the target structure.
2. **Single embed pass for multi-query (FAN_OUT) input** — Reformat may hand Pool up to 4 rewritten queries; does Pool batch-embed them in one call, or is there a real reason to keep them separate? Ties directly to the embedding_provider.py `batch_size=5` hardcode bug Shape:Reformat already found and partially fixed — verify Pool doesn't reintroduce a similar artificial batch ceiling.
3. **Dedup + union logic across vector/keyword/payer-authority contributions** — no design exists yet for how overlapping candidates from different sources get merged into one ranked/unranked pool. This is the actual accuracy lever (§1 above) — get this right, not just "make it compile."
4. **What Fillers actually read** — the pool's shape needs to be exactly what `fillers/fill(pool, shape) -> slots` (target-structure-spec §2) expects. Coordinate the interface with whoever builds Router/Fillers next, don't design Pool's output in isolation.

## 5. What's explicitly OUT of scope for Pool

- Shape's classification/posture/structure logic (Gate/Reformat/Structure — all locked, closed 2026-07-23)
- Router's strategy/arm selection logic (Step 3, separate module — Pool builds the candidates, Router decides how fillers use them)
- Fillers' actual slot-filling (Step 4, separate module — fillers are "pure over the pool," per gate (b): **a filler may not open a DB connection, embed, or build candidates — enforce by signature, no db handle passed in**)
- Synthesis/Contract/Timing (further downstream, separate modules)

## 6. The two gates Pool must clear (from `docs/rag-target-structure-spec.md` §4 — both already-ratified, not new)

**Technical/structural gate (TECH — RED/quarantine = P0):**
- (b) **Single-pool** — no arm opens a DB conn / embeds / builds candidates outside Pool itself. This is the whole fix; get it verified, not assumed.
- (d) **Every DB + retrieval segment timed.** Untimed = RED, non-negotiable per DB's own sign-off.
- (i) **Pool DB access explicitly decided + timed** — pool-first vs GIN-index (see §4.1 above). DB gate, folded into TECH's structural close.
- (e) No reintroduced god-file; Pool stays its own module, doesn't bleed into Router/Fillers.

**Outcomes gate (Eval):**
- New-path per-arm recall ≥ old, behind the `RAG_ANSWER_ENGINE=shape` flag — **NUMBER-MOVING**, per target-structure-spec §7 ("Candidate-pool unification (core)" is explicitly tagged NUMBER-MOVING). Before/after forced-arm calibration required before this can merge, same discipline as Gate/Reformat/Structure.
- Recall 0.65 is the mechanism target, not a guaranteed number (Eval's own caveat, target-structure-spec §10) — a corpus-bound ceiling below 0.65 is a corpus gap, not Pool's miss, IF the structure itself is right.

## 7. Process — same as Gate/Reformat/Structure, don't skip steps

1. **First task before any code:** read Structure's actual closed `StructureResult` contract directly (don't assume this spec's guess), and confirm the pool-DB-access decision (pool-first vs GIN-index) with DB explicitly — this is a named P0 decision point, not a detail to default on.
2. Build with real DB/system verification at every step — restart the dev proxy before trusting any latency number, EXPLAIN ANALYZE before believing a query is slow.
3. Test: unit tests on dedup/union logic (pure), DB-integration tests for the actual pool-build query pattern, an eval bank measuring per-arm recall pre/post (this module is explicitly NUMBER-MOVING — a characterization test alone is not enough).
4. Cross-agent sign-off: Chat (any UI implication), UX (new emit key — avoid collision with `shape_gate`/`shape_reformat`/`shape_structure`, propose `pool` or similar), Eval (before/after calibration, mandatory — this is the number-moving gate), DB (pool DB access pattern, gate (i), MUST sign off on the explicit decision before merge), TECH (structural close, gates (b)/(d)/(e)/(i)).
5. Track in a live scoreboard (`pool-simulation-tracker.md`), same pattern as Shape's three trackers — keep it current in real time, not reconstructed after the fact.
6. Commit incrementally, module-prefixed filenames under `app/services/retriever/pool/` (new package, no shared-directory collision risk with `shape/` — but ping before adding anything to `shape/contracts.py` if Pool needs a new shared dataclass there).
7. Report back to Retriever once TECH + Eval both sign off — next stop is Router (Step 3).

## 8. Lessons from Shape's three builds — apply here too

- **Verify-before-trust, every number** — recurring dev-proxy degradation produced misleading latency more than once; always restart + re-measure with EXPLAIN ANALYZE before trusting a slow-looking number.
- **Don't guess at what fields "should" exist** — check the actual closed `StructureResult` dataclass directly before assuming what Pool receives.
- **This module is explicitly NUMBER-MOVING** — a characterization test alone will not clear Eval's gate; before/after forced-arm recall calibration is mandatory, same as Structure's more numeric siblings would have needed had they touched behavior.
- **PHI discipline: fail-closed, not "redact before persisting"** — if pool contents ever get logged/persisted for debugging, the same never-persist-raw-content rule applies.
- **Module-prefixed filenames, ping before touching shared files** — `shape/contracts.py`'s near-miss (Reformat's `narrate.py` briefly overwriting Gate's) is the cautionary case; Pool gets its own package, but any shared-file touch still needs a heads-up.
- **Keep the sign-off tracker current in real time** — TECH caught this going stale once already during Shape's build; don't repeat it here.
- **The pool-DB-access decision (gate i) is a named, explicit P0 — not a default.** Never seq-scan `rag_published_embeddings` on a `?` predicate; this is the one number DB flagged as highest-value in its own sign-off.

## 9. Open architecture questions to resolve FIRST (before kickoff proceeds)

1. **Does Structure's closed contract actually carry `answer_shape`/slots and scope/auth context, or did that land with the orchestrator instead?** Structure's own spec flagged this as unresolved when it started; verify what actually shipped before Pool assumes an input shape.
2. **Pool-first vs GIN-index (gate i)** — DB flagged this as a required explicit decision, not yet made as of the target-structure-spec. This blocks real design, not just an implementation detail — resolve with DB before writing the pool-build query.
3. **Multi-query embed batching for FAN_OUT** — one call or several? Directly related to the `batch_size=5` hardcode bug Reformat already found; don't reintroduce a similar artificial ceiling here.
