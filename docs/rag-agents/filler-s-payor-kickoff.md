# Filler s (Payor Platform Fact Store) — Kickoff

**Status:** Handoff from Retriever. Fifth of the 8-filler family (a/b built, c/d in progress on design), building one at a time.

---

## Real prior art, verified directly — this is a live cross-service call, not a local function

Legacy's strategy-s (`corpus_search_agent.py:3850-3965`) makes a real HTTP call (`httpx`) to an external **Payor Fact Store service** (mobius-payor's own service — see project memory `project_payor_fact_store.md`/`project_payor_fact_store_persistence.md`: "certified fact store (tags+vector) replacing payor_lookup RPC, Eval owns spec+cert, payor builds"). This is squarely in the c/d/s category flagged earlier for the whole 8-filler family: a live external call, **NOT pure-over-the-pool** like Fillers a/b.

## The real logic — read the actual code before assuming

- **Gate condition (line 3855):** only consult the fact store when the query has a `j:payor.*` tag AND isn't a "conceptual" query AND isn't forced to another strategy. Without a payor tag, the store's d-tag blend can still match and hijack a query that belongs to a/b — this guard is important, don't drop it.
- **Request payload (line 3859-3864):** `{query, d_tags, p_tags, j_tags, intent_scope: None, k: 5}` — sent to `_fact_url` (check where this URL comes from — likely an env var/config, verify directly, don't assume).
- **Response handling:**
  - `hit` (bool) → if true, `served` dict has `answer_text`, `score`, `payer_key`, `authority_level`, `predicate`, `source_ref`, `freshness`; a fast-exit response is built with `confidence="high"`, ONE synthesized chunk (`source_type="fact_store"`, `confidence_label="high"`).
  - If `hit=false` and mode was forced to `s`, it's a clean miss (empty chunks, `confidence="low"`) — does **NOT** fall through to a/b/c/d.
  - On error, same clean-miss behavior — don't crash.
- **This maps naturally to `FilledChunk` output** — `served`'s fields already look chunk-shaped (a single high-confidence synthetic "chunk" representing the fact-store hit), much more directly than Fillers c/d's reshaping problem.

## Port, don't import (same directive as everyone else)

Re-implement this HTTP-call + response-handling logic in Filler s's own module, don't leave a live dependency on `corpus_search_agent.py`. Verify the actual `_fact_url` config/env var and the Payor Fact Store's real request/response contract directly — don't assume the shape above is complete, it's what was found reading the response-construction code, not the fact-store service's own API contract.

## Read first, in order

1. `docs/rag-agents/fillers-schematic-spec.md` — parent contract, though note (same as c/d) you're a live external call, not pure-over-the-pool.
2. `app/services/corpus_search_agent.py:3850-3965` in full — the real legacy code.
3. `docs/rag-agents/pool-schematic-spec.md` §"AHCA authority"/inherited strategy — related but distinct (Pool's `inherited` arm does something similar for corpus-level authority inheritance; Filler s's fact-store is a different, external, higher-confidence source — understand the distinction before assuming overlap).
4. `app/services/retriever/fillers/filler_a.py` — output-shape pattern to match.
5. Check memory/docs on `project_payor_fact_store.md`/`project_payor_fact_store_persistence.md` if accessible for the service's real API contract, since Payor owns that service, not RAG.

## Process — same as every module in this fleet

Verify-before-trust on every claim (a filler's calibration report was fabricated once already this session and caught — never repeat that). Coordinate directly with whoever owns the Payor Fact Store service (check for a "Payor"/"3a - Payor platform" session) on the real API contract rather than guessing from legacy's HTTP call shape. Build with tests. Real calibration run with a real artifact before any sign-off claim. Track in `filler-s-payor-tracker.md`. First deliverable: a kickoff spec doc, same pattern as the others, before code.

---

## Round 2 (2026-07-23) — read the real prior art, verified directly, not taken on faith

Read, in order: `fillers-schematic-spec.md`, `corpus_search_agent.py:3820-3965` in full, `pool-schematic-spec.md` §3.3 (inherited/AHCA), `filler_a.py` + `fillers/contracts.py`, and — since this doc's own "read first" list pointed at Filler c/d as the other live-external-call fillers — `filler-c-llm-retrieval-kickoff.md` + `filler-d-web-kickoff.md`/`filler-d-web-tracker.md` in full, since they already resolved several problems this filler shares. Also read the payor service's own code (`mobius-payor/app/fact_store.py`, `app/routers/payor_skills.py`) directly rather than trusting the legacy caller's read of the contract — found a real, verified divergence between what payor's service documents as its contract and what legacy RAG code actually sends (see below).

### Architectural fork — same question Filler d already got resolved, applies identically here

**Confirmed live-trigger, per-slot, per-attempt** — same resolution Retriever already gave Filler d, and it applies to `s` for the identical reason: `PoolResult` is corpus-only (Pool's own spec, §2: "PUBLIC-only v1... reused strategies tag_select/vector/inherited"), and the fact store is an external HTTP service with no upstream step that pre-populates `PoolResult` with fact-store hits. Filler s fires when a slot's current `RoutingLadder` rung is `"s"`, not as a query-wide pre-fetch. Real signature, following Filler d's precedent:

```python
async def fill_shape_fact_store(
    pool_result: PoolResult,        # slots NOT on this rung pass through untouched
    shape_result: AnswerShapeResult,
    raw_query: str,
    *,
    tag_matches: list[str] | None,
    query_embedding: list[float] | None = None,   # see embedding gap below — new, not in legacy's call
    routing_ladders: list[RoutingLadder] | None = None,
) -> FilledShape:
```

No `db` parameter needed (unlike Filler d, which needs a DB session for payer-domain resolution) — the fact store is a pure HTTP call, no local DB access from RAG's side.

### Real request/response contract — verified against the payor service's OWN code, not just the legacy caller

Read `mobius-payor/app/fact_store.py::fact_query()` (lines 346-473) and `mobius-rag/docs/payor-fact-store-spec.md` directly. Full URL: `{MOBIUS_PAYOR_URL}/api/skills/v1/fact_query` (env var `MOBIUS_PAYOR_URL`, default `https://mobius-payor-ortabkknqa-uc.a.run.app`, confirmed at `corpus_search_agent.py:3816`).

**Request** (payor's real parsing, `fact_store.py:346-359`): `{query, d_tags, p_tags, j_tags, embedding?, payer_key?, intent_scope?, k?, tau?, bypass_fact_store?, verify_freshness?, correlation_id?, eval_run_id?, query_id?}` — materially richer than legacy's payload (`{query, d_tags, p_tags, j_tags, intent_scope: None, k: 5}`, `corpus_search_agent.py:3859-3865`), which only ever sends 5 of these fields.

**Response** (`fact_store.py:468-472`, matches `payor-fact-store-spec.md` §2 exactly): `{hit, served, shortlist, gate: {payer_key, applied, excluded_n}, blend: {alpha, beta, tau, version}, verify, telemetry_id}`. `served` (when `hit`): `{record_type, predicate, answer_text, value, source_ref: {doc_id, url, page, quote}, authority_level, scope, freshness: {last_verified_at, valid_until, stale}, cert: {status, grades: {retrieval, synthesis}}, score}`.

**Real, verified divergence — legacy's `served.get("payer_key")` reads a field that does not exist.** The actual `served` dict (`fact_store.py:434-446`) has no `payer_key` key at all — only `authority_level`/`scope`/etc. Legacy's `routing.fact_provenance` therefore silently gets `payer_key=None` always. Not porting this bug forward; Filler s's own code won't read a `served["payer_key"]` that was never real.

### Real, verified gap — the embedding field, root cause of the documented over-serve bug

`fact_store.py`'s own module docstring (lines 17-19) states the contract plainly: **"vec_sim participates only when BOTH sides carry embeddings (RAG passes its query_profile...)."** This confirms the payor service has *always* expected RAG to send a query `embedding` in the request. Legacy's payload (`corpus_search_agent.py:3859-3865`) **never includes an `embedding` key** — verified directly, not assumed. So `q_emb = body.get("embedding")` (`fact_store.py:351`) is `None` on every real call today, `vec` stays `None` (`fact_store.py:391`), and the blend collapses to `base = tag_overlap` regardless of whether fact rows themselves have embeddings populated. This is independently corroborated by `[[project-payor-fact-store]]` memory's documented "over-serve" bug (e.g. "pre-authorization philosophy of sunshine health" scoring 1.00 on tag overlap alone with nothing to separate it from an unrelated same-tag fact) — the memory attributes this to fact-embedding backfill being incomplete, but the *client-side* gap (RAG never sending its own query embedding) is an equally real, independently-broken half of the same root cause, unfixed regardless of backfill progress on the payor side.

**Design decision for Filler s (v1), not a silent copy of legacy:** since `s`/`c`/`d` are already the fleet's carved-out exception to "no embed calls" (all three make live external calls), and the gate condition means this only fires on payor-tagged queries (bounded, not every query), Filler s embeds the query itself (one `gemini-embedding-001` call, `output_dimensionality=1536` — same model/dimensionality the fact store's own `embedding` column is locked to, per `payor-fact-store-spec.md` line 33 and `[[project-answer-cache-service]]`'s output_dimensionality gotcha) and passes it as `embedding` in the request. This closes a real, verified precision gap rather than reproducing it. **Flagging as an open design question below, not deciding unilaterally** — an extra embed call is real latency+cost even if bounded, and Router/Retriever may want it costed against the per-slot `speed_budget` explicitly before this is locked.

### Gate condition — port the logic, but the memory shows it's an already-known-imperfect heuristic

Legacy's `_is_conceptual` check (`corpus_search_agent.py:3825-3831`) is a fixed marker-word list (`"philosophy"`, `"why does"`, `"explain"`, etc.) — a heuristic, not a real intent classification. `[[project-payor-fact-store]]` memory documents this exact gate as a **PARKED, not-fully-fixed** bug ("payer j-tag recognition over-fires" on non-stored payers, payer-agnostic queries, and process/conceptual intent even with the marker-list guard in place). Porting the marker list as a starting point (same words, same behavior as today — not a regression), but **not** treating it as solved just because it's in the legacy code. Real open question: does Shape/Gate's new pipeline already carry a structured intent/posture signal (e.g. `GateResult`'s contour classification) that's a better conceptual-query signal than a hardcoded string list? Worth checking against Gate's real contour vocabulary before assuming the marker list is the best available signal in the new pipeline — not yet checked, flagged for next pass.

Also porting the payor service's own server-side mitigation for the ungated case (`fact_store.py:366-368`: no resolved payer → `tau += TAU_UNGATED_BUMP`) as context — this means even if Filler s's own gate is imperfect, the server compensates by raising its own bar when it can't confirm a payer. Defense-in-depth on both sides, not a single point of failure.

**Checked directly, resolves open question #2 below:** Gate's real `Contour` vocabulary (`shape/contracts.py:15-23`) is `EXACT | VICINITY | UNDERSPECIFIED | CORPUS_GAP | OUT_OF_SCOPE | UNCLEAR` — a tag/document-coverage classification, not a factual-vs-conceptual intent signal. None of these values distinguish "phone number for Sunshine Health" from "philosophy of Sunshine Health's prior-auth process" — both could easily land `EXACT` if the payer tag resolves cleanly. So the new pipeline genuinely has **no better conceptual-intent signal than legacy's marker-word list** — porting it isn't settling for a worse option out of laziness, it's the best signal that exists anywhere in Shape/Gate today. The known over-fire limitation (`[[project-payor-fact-store]]`'s PARKED note) is real and ported as-is, not solved by this move to the new pipeline.

### `FilledChunk` mapping — one synthesized chunk per hit, not per-passage like c/d

| `FilledChunk` field | Source | Notes |
|---|---|---|
| `chunk_id` | `f"fact_{telemetry_id}"` | Own synthetic scheme, not c/d's `"ext:" + sha1(url)[:16]` — different domain (an internal cert-store hit, not an ad-hoc web URL), matches legacy's `fact_store_{telemetry_id}` naming intent. |
| `document_id` | `served.source_ref.doc_id` if present, else same synthetic id as `chunk_id` | Real corpus doc when the fact traces to one; `source_ref` shape confirmed `{doc_id, url, page, quote}` directly in `payor-fact-store-spec.md` line 37. |
| `text` | `served.answer_text` | Matches legacy. |
| `source_type` | `"fact_store"` | Matches legacy. |
| `tags` | `{d,p,j}_tags` from the request (passthrough) or empty — TBD, minor. | |
| `is_neighbor` | `False` | No neighbor concept for a fact-store hit. |
| `original_score` | `served.score` (the real blend score, α·tag_overlap + β·vec_sim × scope × authority × freshness) | **Deliberately not a constant**, unlike c/d — this filler has a genuine calibrated absolute confidence (already τ-gated server-side before `hit=true` is even possible), unlike c/d who had no native per-item signal and used fixed placeholders. It still flows through Observer's percentile-within-pool normalization same as everyone else (`observer-bayesian-confidence-spec.md` §6c) — passing the real number through doesn't skip that, it just gives the normalization real signal to work with instead of an arbitrary constant. |
| `assignment_reason` | `"fact_store_hit"` | New value, documented independently — same "no forced shared enum" agreement Filler c/d already reached. |
| `url` | `served.source_ref.url` if present | **Same open contract gap as c/d**: `FilledChunk` has no `url` field yet in `contracts.py` (checked directly, still absent) — blocks writing chunk-construction code until DB lands it, same blocker they're already waiting on, not a new one. |

**Miss/error behavior — simpler than legacy, because the new architecture already has a place for this decision.** Legacy's monolithic `_force_s`/clean-miss/no-fallthrough logic existed because strategy-s ran as a *query-wide* fast-exit before any other routing happened. In the new pipeline, Filler s only runs when Router's `RoutingLadder` already put `"s"` at the current rung for a specific slot's specific attempt — a miss (`hit=false`) or an error just means that attempt's `FilledSlot` comes back with 0 chunks (`occupancy=0`, `under_filled=True`), and Observer's existing Bayesian per-slot logic decides whether to try the next rung. No `force_s`/fallthrough special-casing needs to be reimplemented — the orchestrator loop already generalizes this. Simpler than legacy by construction, not by omission.

### Open design questions

1. ✅ **Query embedding source — RESOLVED (Retriever's fork, verified directly, 2026-07-23): REUSE Pool's embedding, don't make a second call.** Retriever correctly flagged this needed direct verification, not an assumption from either side. Checked both halves:
   - **Model/provider match:** dev deploy sets `EMBEDDING_PROVIDER=vertex` (`deploy/deploy_cloudrun_dev.sh`), and `config.py:154-155` resolves that to `EMBEDDING_MODEL=gemini-embedding-001` by default (no override present in the deploy script). Payor's own `fact_embed.py` (lines 4-8) explicitly uses Vertex `gemini-embedding-001`, `output_dimensionality=1536` explicit — **same model, same provider.**
   - **Dimension match:** `add_pgvector_columns.py:61` — corpus's `rag_published_embeddings.embedding_vec` is `vector(1536)`. `add_payor_fact_store.py:29` — facts' `embedding` column is `vector(1536)`, with the migration's own comment stating the pin explicitly: **"`vector(1536)` pinned: §7.2 requires vec_sim comparability with the corpus embedder"** — i.e. this was a deliberate, already-verified-elsewhere design decision, not something newly discovered here.
   - **Conclusion: reuse is not just cheaper, it's the semantically-correct choice** — a second embed call with the same model on the same query text would (modulo API non-determinism) produce the same vector, so re-embedding buys nothing but latency+cost.
   - **New real gap this surfaces:** `PoolResult` (per `pool-schematic-spec.md` §5) does **not** currently expose the query embedding it already computed for its own vector-search strategy — only `candidates`/`segment_ms`/`strategy_hint`/`fallback_triggered`/`pool_ms`. This is a genuine, new contract gap, structurally identical to Filler c/d's `url`-field gap: Pool needs to add a field (e.g. `query_embedding: list[float] | None`, populated only when Pool's vector strategy ran) for Filler s to consume. Flagging to Pool/Retriever, not deciding unilaterally — Pool owns its own output contract.
   - **Fallback if Pool doesn't expose it (or a slot's ladder never reaches Pool's vector arm):** Filler s's own bounded `gemini-embedding-001@1536` call remains the correct fallback design, already proposed above — same model/dimension either way, so no downstream semantic difference between reuse and a fresh call, only a latency/cost one.
   - **Task-type compatibility, confirmed by "3a - Payor platform" directly (2026-07-23):** payor's own backfill (`fact_embed.py`) embeds facts with `task_type=RETRIEVAL_DOCUMENT`, and RAG's own Vertex provider (`embedding_provider.py:92`) embeds everything — queries included — as `RETRIEVAL_DOCUMENT` too (no query/document task-type distinction exists in the current provider code). So reusing Pool's already-computed embedding is task-type-consistent by construction, not just model/dimension-consistent — one more reason reuse is the correct default over a fresh call that might (incorrectly) use `RETRIEVAL_QUERY`.

### ⚠️ CRITICAL, NOT YET INCORPORATED INTO SHIP PLAN — sending `embedding` is a real regression risk, confirmed by "3a - Payor platform" directly (2026-07-23), reverses the "just send it" framing above

Payor's own session read `fact_store.py:392` and flagged something I hadn't checked: **the blend formula itself changes shape depending on whether `embedding` is present, not just whether vec_sim participates.**

- **Today (embedding absent):** `base = overlap` — raw tag_overlap at full weight 1.0.
- **Once `embedding` starts arriving:** `base = ALPHA·overlap + BETA·vec` = `0.5·overlap + 0.5·vec` (current `ALPHA=BETA=0.5`).

So a fact serving *today* at `overlap=0.8` (`base=0.8`, clears `τ=0.75`) would, the moment RAG starts sending embeddings, rescale to `base = 0.4 + 0.5·vec` — and only re-clear `τ` if `vec ≥ 0.70`. **Facts with high tag overlap but merely-moderate vec_sim would newly stop serving** — the conceptual-mismatch veto working as designed, but it also silently shifts the store's entire operating point for every currently-good serve, not just the buggy over-serve cases this was meant to fix.

Payor's explicit ask: **this cannot ship as an isolated Filler s change.** It has to be bundled with (a) Eval's α/β/τ re-sweep against a fresh baseline, and (b) RAG dropping the legacy `_CONCEPTUAL_MARKERS` keyword-drop band-aid (redundant once vec_sim vetoes conceptual mismatches directly) — as **one measured, sequenced change**, not three independent ships. Payor is holding their own additive `payer_key` fix for the same reason (a "clean-tree freeze" currently in effect) — this isn't a one-off caution, it's the same discipline applying twice in one exchange.

**Revised v1 scope, pending Retriever/Eval sign-off:** Filler s v1 ships **without** sending `embedding` — tags-only, matching legacy's current (already-calibrated, already-live) operating point exactly, `_CONCEPTUAL_MARKERS` gate stays in place as-is. The embedding-send fix (plus the Pool `query_embedding`-reuse plumbing above) becomes an explicitly-tracked fast-follow, bundled with Eval's re-sweep and the markers-band-aid removal, sequenced together once the freeze lifts. This avoids shipping a silent regression into a freeze window and avoids moving the fact store's operating point out from under a baseline Eval hasn't re-measured yet.
2. ✅ **Gate signal** — checked directly: Gate's real `Contour` vocabulary (tag/doc-coverage classification) has nothing resembling a conceptual-vs-factual intent signal. The ported marker-word list is the best available signal in the new pipeline, not a lesser option chosen out of convenience — and its known over-fire limitation is real and unsolved by anything upstream.
3. ✅ **`url` field** — same pending-DB-landing blocker Filler c/d already have open; not new, just shared.
4. ✅ **`original_score`** — real score passthrough, still normalized by Observer same as everyone else; resolved above, no departure from the locked mechanism, just a different (better-justified) input value than c/d's constants.
5. ✅ **Miss/error shape** — resolved above: no `force_s` port needed, Observer's existing per-slot loop already generalizes it.

## Next steps

1. ~~Coordinate directly with the "3a - Payor platform" session on the embedding-gap finding and the `served.payer_key` non-field.~~ Done — sent 2026-07-23, not yet replied.
2. ~~Get open question #1 (query-embedding source) answered.~~ Done — RESOLVED as reuse-Pool's-embedding, verified directly (model+dimension both match). New follow-on: ask Pool to expose `query_embedding` on `PoolResult` — this is the one real remaining ask before `filler_s.py` can be written against the reuse path.
3. Draft `filler-s-payor-module-spec.md` proper now that the design forks are resolved, same pattern as Filler c/d's kickoff→module-spec progression.
4. Unit tests + characterization test, then a real calibration run with a real artifact (standing artifact-validation requirement) before any sign-off claim.
