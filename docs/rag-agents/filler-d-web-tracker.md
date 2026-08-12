# Filler d (Web Search) — Progress Tracker

**Status:** Design phase. Kickoff spec written (`filler-d-web-kickoff.md`). No code written yet — deliberately, per handoff instructions: design doc + open questions surfaced before any `filler_d.py`.

---

## What was done

- Read and verified the real prior art in full: `corpus_search_strategy_d.py` (980 lines — search/fetch/synthesize pipeline, Vertex Grounding primary + DuckDuckGo fallback), the legacy `_Passage`→chunk-dict conversion in `corpus_search_agent.py:4627-4670`, the real `FilledChunk`/`FilledSlot`/`FilledShape` contracts, and both existing fillers' real code (`filler_a.py`, `filler_b.py`).
- Confirmed the Google CSE-closed claim independently (code comments + memory agree).
- Found Filler c's session ("4d - LLM Retrieval", `local_ad29acea-4e2b-4265-b7df-c067197d718d`) via cross-session search — no kickoff doc there yet either, so no prior art to build on for the shared facts-vs-narrative problem; coordinating directly instead.
- Confirmed no bandit code exists anywhere under `app/services/retriever/` yet — `RoutingLadder`'s `dispatch_path` (forced/greedy/optimizer/bayesian) in `router/decision.py` is the fleet's one real bandit mechanism so far, one layer above Fillers.
- Wrote `filler-d-web-kickoff.md`: architectural fork (Pool-consumer vs. live-trigger — concluded live-trigger is the correct read, matching the handoff's c/d/s exception), facts-reshaping table (`_Passage`→`FilledChunk`), a real contract gap (`FilledChunk` has no `source_url` field despite the whole point of external chunks being citable URLs), a proposal to drop the `_synthesize()` LLM-narrative step entirely in v1 (facts-only, cuts ~3-6s + one LLM call), and a bandit-scope conclusion (no within-filler bandit needed for v1 — Router's `RoutingLadder` already owns that layer).

## Verified-before-trust notes

- Did not assume `FilledChunk` had a URL field — read `contracts.py` directly, confirmed it doesn't. This is a real gap, not an oversight to route around silently.
- Did not assume Filler d should mirror `filler_a`/`filler_b`'s pure-function-over-`PoolResult` shape just because they're the "structural template" — read the handoff's explicit c/d/s exception, and the legacy code (which does live I/O), and reasoned from there that the live-trigger design is the one that matches reality, not habit.
- Did not invent a `chunk_id`/`document_id` scheme without flagging it as synthetic (no real DB row backs an externally-fetched passage) — proposed a URL-hash approach but left it as an open question pending Filler c coordination.

## Round 2 (2026-07-23) — most blockers cleared

Resolved since round 1, all verified in real code before accepting:
1. **Fork point** — CONFIRMED by Retriever: per-slot, per-attempt, live-triggered on the orchestrator's `RoutingLadder` rung, not a Pool pre-fetch.
2. **`url` contract gap** — name/shape agreed (`url: str | None`, via Chat/Filler c), **DB has not yet landed the field** — verified live in `contracts.py`, still absent as of this check. Real blocker, not resolved yet.
3. **`original_score`** — constant `1.0` for `fetch_status == "ok"` chunks, relying on Observer's percentile-within-pool normalization (verified directly in `observer-bayesian-confidence-spec.md`, which explicitly anticipates external strategies having their own score scale).
4. **Drop `_synthesize()`** — CONFIRMED safe by Eval (verified `confidence_label` has zero references in `app/services/retriever/`). Added a footnote about legacy (old-path) consumers losing that signal at eventual cutover, per Eval's explicit ask.
5. **Bandit scope (strategy-selection)** — CONFIRMED no within-filler bandit needed; Router's `RoutingLadder` is the one mechanism.

**Bandit-stage question — RESOLVED (Eval, independently re-verified in code, Filler c cross-checked):** `rag_strategy_d_external` is a real, live Thompson-sampling bandit stage (`mobius-chat/model_registry.py:862-870`, `mobius-rag/llm_manager_client.py:65-72`), but both files' own comments label it "Strategy (d) External First **synthesis**" — the exact call being dropped. Eval independently confirmed (exact line cites: `model_registry.py:868`, `llm_manager_client.py:72`, invocation only at `corpus_search_strategy_d.py:796`) that Filler d v1 makes zero calls to any bandit-registered stage; nothing else exists to wire. Filler c checked whether the same reasoning applied to their kept `_ask_llm()` call and correctly found it doesn't — their LLM call generates the retrieval content itself, mine only narrated over already-complete content. Retriever separately asked whether any remaining model-routed call in v1 needs its selected-model result preserved for bandit reward plumbing — moot, since v1's only LLM-adjacent call (Vertex Grounding) bypasses the bandit/`llm_manager_client` entirely via a hardcoded-model direct `genai.Client` call.

**New directive (Ananth): port, don't import.** No live dependency on `corpus_search_strategy_d.py` — re-implement the pieces Filler d needs (`_search_web_vertex`, `_search_web`/DDG fallback, `_fetch_and_extract` incl. PDF branch, query-enrichment helpers) into Filler d's own module, verifying each piece fresh as it's ported. Full list in the kickoff doc's new "Port, don't import" section.

**Round 3 (Retriever ruling): payer-context resolution is shared, not ported per-filler.** The live-search fillers all independently need `_extract_payer_slug`/`_resolve_payer_context` — Retriever ruled it becomes one shared utility, not separate re-derivations. `_lookup_sitemap_candidates()` also dropped from my scope — that's the Sitemap filler's own job, not mine.

**Round 4: `payer_context.py` landed, verified myself before accepting the claim.** The Sitemap filler (session "4d - Sitemap") built `app/services/retriever/fillers/payer_context.py` (`extract_payer_slug()`, `async resolve_payer_context()`) + `test_payer_context.py`. Ran the tests myself rather than trusting the report: `uv run pytest app/services/retriever/fillers/test_payer_context.py -v` → real output, 9/9 passed. Confirmed function names/signatures match by reading the file directly. This blocker is cleared — I import this module, no porting needed.

**Correction (Retriever, 2026-07-23):** this filler is NOT "Filler f" — earlier references in this doc calling it that were Retriever's own mislabeling, caught by the Sitemap session itself. Router's real, unbuilt strategy `"f"` is a separate, scored external-fallback thing. Referring to it as "the Sitemap filler" going forward.

## Fleet-wide finding (not a Filler-d blocker, flagged and routed) — RESOLVED (Router vetoed, counter-proposed)

Router needs `payer_crawlable` (tri-state) resolved before it plans a chain. My first proposal (Router resolves it itself) was **vetoed by Router, correctly** — verified their reasoning against real code: TECH gate (b) "No DB access during optimization" is real (`router/__init__.py` docstring), plus determinism/replayability (byte-identical plans is an enforced characterization property) and latency inversion (allocation costs 0.06-0.31ms; a 3s-timeout HTTP call would eat the entire real_time budget). Same class of reason I used to rule out Structure/Slots — Router correctly applied it to my own proposal.

**Accepted counter-proposal: the orchestrator resolves it**, not Router — matches the real `gate_j_codes` precedent more precisely than my first read did (Gate doesn't hand `j_codes` to Router directly either; the orchestrator threads it). Run concurrently with Pool's fetch (both depend only on Gate output, zero added wall-clock in the common case); TTL cache per payer slug; skip-and-fail-open on a real_time cache miss. Orchestrator wiring is Retriever's to own — routed there.

Router also endorsed the return-shape blocker and specified what it needs: not a wider tuple, a small dataclass — `PayerContext{slug, display_name, site_domain, crawlable: bool|None, source}`. The Sitemap filler owns `payer_context.py`; coordinating the exact shape with them since I'm also a consumer (I only need `site_domain`/`display_name`, unaffected either way by the dataclass switch).

**Round 5: `PayerContext` shipped and independently re-verified.** Sitemap fixed the collapse (verified myself: `resolve_payer_context()` now returns a real `PayerContext(site_domain, display_name, crawlable)` dataclass, ran `uv run pytest app/services/retriever/fillers/ -q` → 71 passed, 2 skipped, matches their report). Sitemap also caught a real design gap I hadn't: if Router resolves `PayerContext` once at plan time and I independently re-resolve at execution time, the ~3s Payor Platform timeout gets paid twice per query. Added a `payer_context: PayerContext | None` param to my proposed `fill_shape_external()` signature so Router's resolution threads through the orchestrator into my execution call instead of me re-deriving it.

**RESOLVED (Retriever):** confirmed as one coherent data-flow decision — resolved once post-Gate, threaded to both Router's plan-time crawl-gate and the executing filler's attempt-time use. My param shape (accept-with-self-resolve-fallback) confirmed correct. Exact threading mechanism (RoutingLadder vs. separate context object) still Retriever's to settle with Router — doesn't block my own design further.

**Round 6: `PayerContext` finalized to Router's exact requested shape, independently re-verified.** `PayerContext(slug, display_name, site_domain, crawlable: bool|None, source: str)`, `source ∈ {"metafact", "crawl_history", "none"}`. Verified myself: `uv run pytest app/services/retriever/fillers/test_payer_context.py -q` → 13 passed (exact match to claim); full `fillers/` suite → 71 passed, 2 skipped (matches "71/73" claim). Sitemap flagged one real correction to Router's own sketch rather than silently absorbing it: the `discovered_sources` fallback layer has no robots signal, so it can only ever produce `crawlable=None`/`source="crawl_history"`, never a `False` — worth remembering if anything downstream assumes the fallback layer can disqualify strategy d on its own. Sitemap's module also renamed `filler_f_sitemap.py`→`sitemap_links.py` (naming correction, not "Filler f" — Router's real `"f"` is separate and unbuilt). Non-event for my own design either way — still reading only `site_domain`/`display_name`.

**Round 7 — threading mechanism settled, whole `payer_context` thread now CLOSED.** Router confirmed with Sitemap directly: full `PayerContext` rides the orchestrator's per-query state (not `RoutingContext`, which only carries the derived `payer_crawlable` tri-state); orchestrator resolves once post-Gate, sets Router's field from it, hands the same object to Fillers at execution — exactly matches the `payer_context: PayerContext | None = None` param already in this doc's `fill_shape_external()` signature. Router also withdrew the `source` field ask once it was clear it's fully derivable; verified myself it's now a `@property`, not stored state (`payer_context.py:62`) — no change on my end. Nothing further to track here; ready to wire in whenever code starts.

## BUILT 2026-07-23 — real code, real tests, real live run

Per Ananth's change of plan (relayed by Retriever): built `filler_d.py` directly rather than staying hands-off, since the design was fully resolved.

**What was built:**
- `app/services/retriever/fillers/filler_d.py` — ported (not imported) `_search_web_vertex`, `_search_web`/DDG fallback, `_fetch_and_extract` (incl. PDF branch via PyMuPDF), `build_authoritative_query`, `_rerank_hits`, `_embed_search_operators` from `corpus_search_strategy_d.py`. `_synthesize()` dropped entirely per the earlier-confirmed decision. `payer_context.py` imported (not ported) for `PayerContext` typing; `resolve_payer_context()` itself never called here — threaded in as a param instead (per the round-7 orchestrator design). `url` still absent from `FilledChunk` (DB hasn't landed it) — omitted from the chunk per Filler s's own precedent, carried instead in `emit.fillers_d.passages[].url` as a documented diagnostic bridge.
- **New (Ananth, mid-build): p:/j: tag boosting in reranking, not the query.** `_boost_phrases()` extracts every matched d:/p:/j: tag into a reranking-only signal — the live query string itself stays narrow (only the one domain-anchored d-tag, unchanged), avoiding the recall risk of over-specifying a live search. Verified end-to-end: a hit matching only boost terms (not embedded in the query) still gets promoted by `_rerank_hits`.
- `app/services/retriever/fillers/test_filler_d.py` — 43 tests, all passing, real execution:
  ```
  $ uv run pytest app/services/retriever/fillers/test_filler_d.py -v
  ============================== 43 passed in 0.36s ===============================
  ```
  Full `app/services/retriever/` suite (no regressions): `142 passed, 2 skipped`.
- Wired into `orchestrator.py`: `_IMPLEMENTED_FILLERS["d"] = "external"`, `_run_fillers_simple()` gained a `payer_context` param (threaded from `run_retriever_partial`, previously computed but never passed to filler execution — a real gap, now closed) and a `"d"` branch calling `fill_shape_external`.

**Two real latent bugs found during porting/re-verification, not silently inherited (per Ananth's explicit ask):**
1. `_tag_to_phrase`: legacy's `full_code.split(".")[-1]` only strips the `"d:"` prefix incidentally when a dot exists; for a bare single-segment tag (`"d:eligibility"`) it left the prefix attached, producing a broken search-quote term (`'"d:eligibility"'`, colon included). Fixed with an explicit prefix strip.
2. `_most_specific_d_tag`'s generic-leaf exclusion (`t.split(".")[-1] not in _GENERIC_D_TAG_LEAVES`) had the identical bug — a single-segment generic tag like `"d:general"` never matched the bare-word exclusion set, so it silently slipped through as a "specific" candidate. Both fixed via a shared `_bare_leaf()` helper; both caught by failing tests, not spotted by inspection.

**Real live smoke test (not a fake/stub number) — two separate real runs, real network calls:**
```
Query: "What is the timely filing deadline for Sunshine Health Medicaid claims in Florida?"
tag_matches=["d:claims.timely_filing", "j:payor.sunshine_health"], no payer_context
→ search_backend=vertex, search_ms=5153, fetch_ms=935, total_ms=6089
→ n_hits=5, n_ok=5 (4/5 from sunshinehealth.com, found by Vertex Grounding's own
  semantic search even without a domain restriction)
→ 3 chunks assigned (capacity=3, fully filled), ~2000 chars each, deterministic chunk_ids

Query: "timely filing deadline for claims", tag_matches=["d:claims.timely_filing"],
payer_context=PayerContext(site_domain="sunshinehealth.com", crawlable=True)
→ search_backend=vertex, search_ms=7121, fetch_ms=1041, total_ms=8163
→ n_hits=5, n_ok=5 (4/5 from sunshinehealth.com -- site: restriction working)
```
Both real end-to-end latencies land at ~6-8s — faster than legacy's documented ~7-15s estimate, consistent with dropping the ~3-6s synthesis step.

**`url` field landed (DB, same session) — resolved during the build, not after.** `contracts.py`'s `FilledChunk` gained `url: str | None`, `document_id` relaxed to `str | None`, plus `page_number`/`paragraph_index`. Convention: external chunks get `url` populated + `document_id=None` (no synthetic id pretending to be real); internal (Pool-sourced) chunks keep `document_id`, `url=None`. Updated `_chunk_from_passage` to match — verified live (real `chunk.url`/`chunk.document_id is None` in a real run). The `emit.fillers_d.passages[].url` diagnostic bridge is kept as extra telemetry, not a replacement.

**Real BM25 reranking added (Ananth's steer): "run bm25 on the retrieved chunks... see how much of the reranking you can inherit from BM25."** `_score_bm25()` scores every fetched passage's FULL body text against the query using Pool's exact ranking function (`ts_rank_cd(..., 32)`) — real, cross-strategy-comparable `original_score`, not a flat `1.0`. Two real bugs caught and fixed via LIVE testing (real DB, real fetched pages), not just unit tests:
1. A straight `plainto_tsquery` (AND semantics, same as Pool's own formula) scored a genuinely correct fetched passage — literally a "Timely filing table: 180 days" page — as a hard **0.0**, because it didn't repeat every query word verbatim ("Sunshine"/"Medicaid"/"Florida" don't all appear on the page that IS the timely-filing table). Fixed by rebuilding an OR-joined `to_tsquery` from `plainto_tsquery`'s safely-stemmed output (`replace(plainto_tsquery(...)::text, ' & ', ' | ')` then re-parsed via `to_tsquery`) — same reasoning `corpus_search.py` already established elsewhere in the fleet for ranking vs. exact-match queries.
2. Ported `corpus_search.py`'s `_normalize_bm25_query`/`_QUESTION_LEAD`/`_BM25_NOISE` (strips lead-phrase/quantifier noise before either tsquery variant sees the raw question) — same fleet-established fix, applied here too.

**Final live verification, real DB + real network, real bug fixed:**
```
Query: "What is the timely filing deadline for Sunshine Health Medicaid claims in Florida?"
→ search_ms=6804, fetch_ms=1169, bm25_ms=1669, total_ms=9644
→ Top-ranked chunk (score=0.7619): "Fact: Timely filing table | Value: Initial Filing:
   180 calendar days of the date of service..." -- literally the correct answer, ranked #1
   by genuine relevance, not arbitrary fetch order.
→ All 3 assigned chunks real url + document_id=None (contract convention verified live)
```

**Distinct from `_rerank_hits`** (title/snippet based, runs BEFORE fetch to prioritize what gets fetched at all) — `_score_bm25` runs AFTER fetch, on real body text, and decides final chunk order + `original_score`. Both stages now real, tested, and live-verified.

## Output QUALITY check (Ananth asked directly, 2026-07-23) — real findings, not a clean bill of health

Prior verification (tests, latency, ranking sanity) checked that the pipeline runs correctly and ranks sensibly — it did NOT check whether the actual chunk *content* is good. Read the full text (not truncated previews) of all 5 ranked chunks for the timely-filing query:

- **3 of 5 chunks are high quality and cross-corroborate**: independently-fetched sources agree on "180 days" (initial, participating) / "90 days" (reconsideration/dispute) — decent internal corroboration, not proof against an authoritative source.
- **Real problem #1 — PDF truncation can surface a table of contents instead of substance.** The PDF branch (`_fetch_and_extract`) takes the first ~2000 chars of page text; for a multi-page "Claims Filing Instructions" PDF, that was cover page + TOC, not the actual deadline section (page 4, per the TOC itself). Topically on-target, doesn't state the answer — a real content-quality gap not caught by BM25 scoring (which just measures topical relevance, not whether the answer is actually present).
- **Real problem #2 — a fetched chunk can be another AI system's output, not primary-source text.** The highest-BM25-ranked chunk was formatted `Fact: ... | Value: ... | Source: Official | Confidence: high` — the output shape of a third-party site's own LLM/RAG extraction over Sunshine Health data, not Sunshine Health's own page. Facts matched the primary-source chunks here, but nothing in this pipeline distinguishes "primary source" from "someone else's AI summary laundered through a search index." Real provenance gap for anything citation-facing.
- **Off-topic content still gets included at wide capacity.** Rank-5 chunk was about prior authorization, not timely filing — correctly ranked last by BM25, but still present in the output.

Flagged both real problems to Eval directly (owns confidence/citation-trust design) rather than deciding a fix myself. **Not done, and shouldn't be mistaken for done:** testing across a diverse query set (only tested variations of one query), fact-checking against an authoritative source independent of what the fetcher itself returns, or running through Eval's actual eval-bank/calibration harness — that's real calibration work, not a substitute for a few manual reads.

**Eval's resolution (2026-07-23) — both findings real, neither blocks v1:**
- **Finding 1 (PDF TOC-not-substance)** is actually two things: a general, structural limitation of ANY score-based evidence proxy (no formula can detect "right document, wrong page") — Eval logged that into `observer-bayesian-confidence-spec.md` as a third known limitation, not a Filler-d fix. Separately, a real scoped improvement IS backlog for this module: **search within a fetched PDF for keyword-relevant pages instead of blindly grabbing the first ~2000 chars.** Not done, not blocking v1.
- **Finding 2 (laundered third-party AI content)** routed to Chat — citation-trust/grounding-badge design question (does "external — verify" framing cover "might not even be a primary source"), not Filler d's or Eval's to decide.

## Backlog (not blocking v1, tracked so it isn't lost)

- PDF extraction: search for keyword-relevant pages instead of a blind first-N-chars prefix (per Eval, above).

## Widened + diversified search funnel (Ananth's steer, 2026-07-23)

Two related asks: "get 15 or 20 to fill 5" instead of pulling exactly N-for-N, and "2 parallel calls, one with the must-haves and one without... we will/may end up with different chunks."

Investigated before changing anything: Vertex Grounding tops out around 5-7 real hits per call regardless of requested `n` (its own internal ceiling, not something raising `n` controls) — reaching 15-20 required combining sources, not just relaxing an early-exit. Implemented: **3 concurrent search calls** (`asyncio.gather`, not sequential) — Vertex constrained (site_domain/exact_terms embedded), Vertex UNconstrained (raw query only, only fired when there's actually something to vary), and DDG/mobius-skills (now a real concurrent contributor, not last-resort-only). Merged + deduped by URL (`_dedup_hits`). `_MAX_FETCH` raised 5→15; `_DEFAULT_N_SEARCH` raised 5→20 (per-call request size; each backend still returns its own real ceiling).

**Real live verification, all three sources contributing, zero URL overlap:**
```
search_backend: vertex+vertex_unconstrained+ddg
n_vertex_hits=5, n_vertex_unconstrained_hits=5, n_ddg_hits=10 -> n_hits (merged/deduped)=20
n_fetched=15, n_ok=15 (100% fetch success at this fan-out)
search_ms=5209, fetch_ms=1981, bm25_ms=2120, total_ms=9322
-- occupancy=5/5 (capacity), all 5 chosen by real BM25 relevance from 20 diverse candidates,
   scores spanning 0.615-0.80, all genuinely on-topic Sunshine Health billing-manual pages
```
Latency stayed reasonable despite 3x the search calls and 3x the fetches (~9.3s vs ~9.1s single-funnel) because everything runs concurrently, not serially — confirmed via real timing, not assumed. 56 tests passing (added `TestDedupHits` + fixed a real test-hermeticity gap: 6 tests only patched Vertex, not DDG, which was silently safe only because `CHAT_SKILLS_GOOGLE_SEARCH_URL` happened to be unset in this test env — now all patched explicitly). Full `retriever/` suite: 170 passed, 2 skipped, no regressions.

**Confirmed root cause with a direct repro (Eval independently found the same symptom via a full-suite flaky run):** temporarily removed one of the 6 DDG mocks, reran with `CHAT_SKILLS_GOOGLE_SEARCH_URL` set — `test_vertex_hit_assigns_chunks` failed exactly as Eval described (extra chunk from a real live search hit; the literal test string "test query" pulled back a real Wikipedia "Testery" page). Restored the mock, verified clean across 5+ repeat runs, both env conditions, both `fillers/` and full `retriever/` scope — 170 passed/2 skipped every time. Not a hypothesis, a proven fix.

## Status check (Retriever, 2026-07-23) — confirmed genuinely not started

Ananth wants real per-filler latency numbers (a/b/s already measured); Retriever asked whether a working (even partial) `filler_d.py` exists to pick up. Answer: no, re-verified live — no such file, `_IMPLEMENTED_FILLERS` has no `"d"`. Corrected Retriever's note that the bandit-moot question was still open — it's resolved (see round 2 above). Pointed Retriever at this doc + the kickoff doc as the source of truth if they build the minimum real version themselves for a latency measurement, rather than re-deriving the design. Flagged that latency measurement (search+fetch) doesn't actually need the `url` field — only `FilledChunk` construction does. **Staying hands-off on `filler_d.py` while Retriever may be building it**, to avoid a file collision — will pick back up once code exists or Retriever confirms it's still mine to build.

## SUPERSEDED — the two sections above/below this note are stale

The "Open — blocking code start" / "Not started" sections that used to follow described the pre-build state (before Ananth said to build it directly). All of it is resolved now: `filler_d.py` exists, `url` field landed and verified live, 56 unit tests + real live smoke tests exist. See "FINAL STATUS" at the bottom of this doc for the current, accurate picture — don't read below this note as current.

## FINAL STATUS (2026-07-23, per Retriever's fleet round-up request)

- **Code**: `app/services/retriever/fillers/filler_d.py` — real, ported (not imported), wired into `orchestrator.py` (`_IMPLEMENTED_FILLERS["d"]`).
- **Tests**: 56/56 (`test_filler_d.py`), 170/170 + 2 skipped fleet-wide (`app/services/retriever/`), verified clean across 5+ repeat runs under both env conditions after the test-pollution fix.
- **Live-verified, not just unit-tested**: real Vertex Grounding + DDG + fetch + BM25 reranking, real DB, real latency numbers, real chunk content read end-to-end (not just previews).
- **`url`/`document_id` contract**: landed, verified live (`chunk.url` populated, `chunk.document_id is None` for external chunks, per `contracts.py`'s documented convention).
- **Known limitations, tracked, NOT blocking**: PDF-TOC-not-substance (backlog, scoped fix identified), third-party-AI-content provenance (routed to Chat, post-v1 bundle), Eval's structural evidence-proxy limitation (logged in `observer-bayesian-confidence-spec.md`, not filler-d-specific).
- **Not my call, not blocking my readiness**: the corpus-junk "confidently wrong" trigger-threshold question (Router's/Eval's dispatch design, forwarded, not mine to resolve).
- **Cross-agent sign-off (Chat/Eval/DB/TECH)**: not yet formally requested — this is the next real step, not something outstanding on my end.
- **Nothing else in flight on my side.** Ready for sign-off.

## Latency investigation (2026-07-23) — leading approach identified, DEFERRED by Ananth

Ananth asked to minimize Filler d's real latency (search dominates at 5-10s per real measurements, not fetch as initially assumed). Explored three ideas in order, with real data at each step:

1. **Percentile cutoff on parallel search completion** — doesn't map cleanly; there are only 3 concurrent search *calls* (vertex-constrained, vertex-unconstrained, DDG), not many small parallel queries to distribute-and-cutoff.
2. **Fetch-module tuning** — ruled out. Fetch is already the *cheapest* phase (~1-2s, 15-way concurrent, real measurements). No slack to give there.
3. **Stage fetch to start as soon as the fastest search backend (DDG, ~1-2s) returns, instead of waiting for all 3 (Vertex dominates at 6-10s per real repeated measurements)** — investigated in depth, **found to save nothing real**. Traced the actual critical path: DDG's search+fetch (~2-4s total) already finishes well inside Vertex's own search window, so DDG was never blocking anything. The unavoidable gate is `vertex_search_time → vertex_fetch_time (can't start until vertex search resolves and returns URLs) → BM25`. Staging DDG's fetch earlier just moves already-idle time around; it doesn't shrink the chain. Caught this by walking through the actual timeline with real numbers rather than assuming "start earlier = faster," and said so directly rather than defending the original claim.

**The one idea with real teeth, per this analysis: fire Filler d's search (the slow, ~6-10s Vertex leg specifically) concurrently with Pool's build, on a separate task from Pool's own work — not staged internal reordering, but genuinely overlapping with an already-dominant cost the query pays regardless (Pool is 5-9s per Retriever's fleet measurements).** This is the only lever that overlaps Filler d's bottleneck with time already being spent, rather than trying to find slack inside Filler d's own ~9-14s total that (per the analysis above) doesn't exist.

**Real complexity flagged before deferring, not glossed over:** a FAN_OUT posture has up to `MAX_FANOUT_THEMES=4` slots, each with its own `rewritten_query` — speculatively pre-searching "in case Router picks d" multiplies to up to 4 concurrent speculative Vertex calls per query, a real cost/quota multiplier on top of the wasted-work risk (Ananth's earlier framing) whenever Router doesn't end up selecting "d" for that slot at all.

**DEFERRED, explicitly, not shelved by inaction (Ananth, 2026-07-23):** don't build this yet. Priority is letting strategies a/b (internal, cheap, no external-API cost) win when they can — only worth paying the speculative-search cost/complexity once we have real data on how often a/b *aren't* winning and d actually gets selected. Once that data exists (from the sign-off round / eval-bank runs already in motion), this can be revisited as either an unconditional speculative fire or a trigger-based one (e.g. gated on Gate's tag-match sparsity, per Eval's earlier suggestion in the same thread).

**Documented here as the leading approach for cutting RAG latency going forward** (Ananth's explicit framing) — flagging to Retriever too, since "fire on a separate task from Pool, threaded through to wherever the filler eventually executes" is an orchestrator-sequencing change with the same shape as the `payer_context` "resolve once, thread through" pattern already built — not something Filler d can do unilaterally when it's time to build it.

## v1 BUILT (2026-07-23) — Ananth green-lit, my piece is ready for orchestrator wiring

Scope (per Retriever's relayed guidance, all verified before building): search-only, not fetch+synthesize; gated on Router's real `authority_requirement` field (`allocation.py`'s `AUTHORITY_CITABLE_REQUIRED` gate, verified live — not the tag-sparsity proxy floated earlier); cache the result so the sunk search cost carries through if Router picks "d".

**What was built** — extracted the search phase (previously inline in `fill_shape_external`) into three reusable pieces, same low-level `_search_web_vertex`/`_search_web` calls underneath, zero behavior change to the default path:
- `PrescreenedSearch` — dataclass holding the search result (hits, backend, site_domain/exact_terms/boost_terms used, timing).
- `prescreen_search(raw_query, *, tag_matches, payer_context, n_search) -> PrescreenedSearch` — the callable orchestrator fires concurrently with Pool.
- `should_prescreen_search(authority_requirement: str) -> bool` — the gate. **Conservative simplification, documented not hidden:** the real per-slot rule (`strategy_authority_eligible`) keeps "d" eligible for OPTIONAL slots even under `citable_required` — this only checks the query-level signal (that per-slot detail isn't known yet at the point this fires, before Router runs), so it can occasionally skip a legitimate optional-slot opportunity. Never fires when it definitely shouldn't; may miss an optimization, never incorrect.
- `fill_shape_external(..., prescreened: PrescreenedSearch | None = None)` — new optional param. `None` (default) = runs search inline exactly as before, fully backward compatible. Given = skips search entirely, uses the cached result.

63 tests passing (7 new: gate logic, `prescreen_search` isolation — verified it never touches fetch/BM25/DB — and both `prescreened`/`None` paths of `fill_shape_external`).

**Real live end-to-end verification, not simulated:**
```
should_prescreen_search("any") = True, should_prescreen_search("citable_required") = False
prescreen_search(): 10071ms, 16 hits, backend=vertex+ddg  <- the cost that gets hidden behind Pool
fill_shape_external(..., prescreened=<that result>): 3165ms  <- fetch+bm25+assignment only
emit["prescreened"] = True, emit["search_ms"] = 10071 (sunk cost, still carried through for observability)
occupancy = 5/5

Old sequential total: ~13236ms of on-critical-path time
New (search hidden behind Pool once wired): ~3165ms of on-critical-path time for this filler's own execution
```

**Handed off to Retriever for the orchestrator half** (per the original ask — "ping me when you have that piece; I'll handle where/how it gets threaded into the real query flow"): calling `prescreen_search()` on a separate task concurrently with Pool's build (same shape as the existing `payer_context` concurrent-resolution pattern), gating with `should_prescreen_search(resource_posture.authority_requirement)`, and threading the resulting `PrescreenedSearch` into whichever `fill_shape_external` call eventually happens if Router picks "d" for a slot. FAN_OUT multi-slot dispatch (whether to fire once or per-theme) is explicitly Retriever's call, not decided here.

## Orchestrator wiring DONE (Retriever, 2026-07-23) — independently re-verified before accepting

Retriever confirmed my API/numbers directly (own timing run: fresh prescreen 4691ms, cached retrieval 1880ms, occupancy=10) before wiring. Real implementation in `run_retriever_partial`: `prescreen_search` fires as a concurrent task alongside Pool's build, chained to wait on `payer_context_task` internally first (so it still gets a real `site_domain` for restriction rather than racing ahead unrestricted — a real improvement over my own spec). Gated on `should_prescreen_search(authority_requirement)` AND non-FAN_OUT posture (FAN_OUT dispatch explicitly scoped out for v1, Retriever's call as expected). Threaded through `_run_fillers_simple` into the `d` branch.

Full pipeline: 430 passed/2 skipped (combined suite), no regressions. **Honest gap flagged by Retriever, not glossed over:** their one live end-to-end run happened to land on a query whose ladder only needed strategy `s`, so `d`'s prescreen cache-hit wasn't actually exercised inside the full pipeline in that specific run — the mechanism itself is independently verified real (direct calls, both sides), but the full-pipeline exercise with `d` actually selected is still open. **Requested a forced-ladder demo** to close that gap before treating this as fully proven for the sign-off round — asked, not yet delivered.

## Forced-ladder demo delivered + independently re-run — real mechanism, noisy magnitude (2026-07-23)

Retriever built `scripts/demo_prescreen_forced_ladder.py` (real pipeline calls — Gate/Reformat/Structure/Slots/Pool/prescreen_search/fill_shape_external, not stubbed) and reported COLD=13444ms vs WARM=6298ms, 7146ms saved (53.2%). **Ran it myself independently before accepting the number** — confirmed the mechanism is real (occupancy=10 both runs, WARM's `fill_ms` dropped 7590ms→1418ms, clearly cache-hitting) but got a different magnitude: COLD=12305ms vs WARM=9823ms, only 2482ms saved (20.2%).

**Root cause, not a bug:** Pool's own latency was similar across both sets of runs (~1.8-1.9s); the actual driver is Vertex Grounding's search latency itself, which varies run-to-run by several seconds (measured 5.4-9.7s range earlier this session, unrelated queries). How much of that gets hidden depends on how it happens to compare to Pool's window that specific run — `prescreen_extra_wait_ms` (search cost that spilled PAST Pool's window) was 3039ms in Retriever's run, 6552ms in mine.

**Recommendation sent to Retriever for the sign-off materials:** report this as a range with the mechanism explained ("savings scale with how much of Vertex's latency fits inside Pool's window that run — observed 20-53% reduction across two independent real runs"), not a single fixed "53.2%" that could be mistaken for a guarantee. Also flagged a minor doc/code mismatch in the demo script (docstring claims it forces "d" via Router's real `forced_strategy` mechanism; the code actually calls `fill_shape_external` directly, bypassing `router_route` entirely — doesn't affect what's being measured, just inaccurate framing). **Both fixed by Retriever, confirmed.**

## Real gap found (2026-07-23): current wiring stalls the WHOLE pipeline on prescreen, not just Filler d's own execution

Ananth asked directly whether prescreen_search holds up Router/the rest of the pipeline, or whether Router can move forward independently. Traced the real `orchestrator.py` code rather than answering from the design description:

`prescreen_search_task` (line 556) does run concurrently with Pool, as designed. But `orchestrator.py:583` — `prescreened_search = await prescreen_search_task if prescreen_search_task else None` — awaits it **unconditionally, before Router runs** (line 591). Verified `_run_router`'s actual signature: it only takes `payer_context`, never `prescreened_search` — Router has zero dependency on this wait. Consequence: every query that fires prescreen (any non-FAN_OUT, non-`citable_required` query) pays the FULL prescreen wait before Router even starts deciding — **including every query where Router ends up NOT picking "d" and the prescreen result goes completely unused.** This also reframes the demo's `prescreen_extra_wait_ms` numbers (3039ms/6552ms) — that's whole-pipeline stall time before Router runs, not just Filler d's own eventual execution being slower.

Real fix (flagged to Retriever, their file): move the `await prescreen_search_task` out of the pre-Router section and into `_run_fillers_simple`'s "d" branch specifically, so it's only waited on if Router actually assigns "d" to a slot. The async-Task mechanism itself (await returns instantly if already done, blocks if not) is correct and needs no change — the bug is purely *where* the await happens, not the underlying concurrency primitive.

**Follow-up ask from Ananth: don't let a slot's first attempt commit to "d" if prescreen isn't ready yet — prioritize an already-ready strategy when time is ticking.** Coordinated with both Retriever and Router directly (spans both domains, didn't decide it myself). Concrete mechanism proposed: `prescreen_search_task.done()` (asyncio Task, non-blocking check) queried right before the execution loop commits to rung "d" — if not ready, try the next rung instead for that attempt. Two possible homes flagged, not decided: Router's plan-time priors (slower, calibration-based) vs. the execution loop checking live readiness at commit time (faster, run-specific) — not mutually exclusive. Real dependency: needs a fallback rung and/or a later attempt for "d" to land in, which depends on whether `_run_fillers_simple`'s current single-rung-per-slot stopgap has grown into a real multi-attempt loop with Observer's `decide_continuation` (imports for it are already in orchestrator.py, so likely in motion) — Retriever's call on sequencing. Not yet resolved, awaiting response from both.

## Stall fix CONFIRMED, independently verified (2026-07-24)

Retriever moved the `await prescreen_search_task` into `_run_fillers_simple`'s "d" branch (unawaited Task threaded through, converted to a real `PrescreenedSearch` only at the point it's actually needed) and added dangling-task cleanup for both the "d" never tried" and "no-slots" paths. **Verified myself before accepting, not taken on the reported numbers alone:** read the actual code — task threading and await placement correct, `.cancel()`-on-already-done-task is a safe no-op, `CancelledError`/`Exception` cleanup handling is technically sound. Ran the fillers/orchestrator-relevant tests myself: 187 passed/2 skipped, clean.

**Separate finding while verifying, flagged to Retriever, not mine to fix:** real test-pollution flakiness in `test_synthesis.py` (different module, recently modified by someone else in this shared checkout) — passes clean in isolation (17/17), fails with a *different* test each time when run as part of the combined `retriever/`+`router/` suite. Same signature Eval caught in my own file earlier this session. Not related to the prescreen fix; flagged so it doesn't silently surface during the sign-off round.

## Readiness-aware prioritization: RESOLVED at the design level, execution now with Retriever

Router formally ruled: **zero Router-side changes needed** for the `.done()`-check-and-reorder mechanism — mathematically justified, not just permitted by convention. Every §2a-enforced quantity (chain LB/mean, worst-case latency, cost, payload) is invariant under permutation of a slot's planned rung order, so the execution loop can freely reorder without touching plan feasibility. Spec'd in `router-build-spec.md` §11, guarded by `TestExecutionReorderingContract` (a real regression test — if any enforced quantity ever becomes order-dependent, this test catches it and the permission gets renegotiated instead of silently breaking). **Independently verified before accepting:** spec section matches claim word for word, ran the contract test myself (passes), confirmed 72/72 `test_allocation.py` and 224/224 full router suite.

Three boundaries specified: (1) reordering stays within the PLANNED rung set — substituting an unplanned strategy remains a plan violation; (2) executed order must be emitted as executed (per-attempt telemetry); (3) **new labeling requirement** — if "d" never runs because prescreen wasn't ready in time, emit that as a distinct `prescreen_not_ready_deferred` label, not folded into generic failure, so Eval's calibration cells for "d" don't absorb readiness noise as performance noise.

Handed the complete, verified spec to Retriever for implementation (their execution loop, `_run_fillers_simple`) — nothing further for Filler d to build here; this was cross-agent design coordination, not a Filler-d code change.

## IMPLEMENTED + independently verified (2026-07-24) — readiness-aware prioritization is real and live

Retriever built it, correcting a premise I'd had: `_run_fillers_simple` had already grown from the single-rung stopgap into a real multi-turn loop (wired to `decide_continuation()`) a couple exchanges earlier — so there was already a "later turn" for a deferred "d" to land in, no separate dependency needed.

**Verified directly against the code, not the report:** `_visible_remaining_rungs()` is real — checks `prescreen_search_task.done()` (non-blocking), reorders "d" behind the next alternative ONLY when it's first-in-line and not ready, correctly falls back to unchanged when "d" is the only rung left (nothing to defer behind). `_pick_and_consume()` picks from this reordered view but removes the actually-chosen rung from the real underlying list — so a deferred "d" stays available for a future turn, never silently dropped. The reordered view (not the raw list) feeds `decide_continuation`'s `remaining_rungs` input, so Router's own math operates on a self-consistent view rather than being overridden after the fact.

Test counts confirmed exactly: 8/8 `test_orchestrator_fillers_dispatch.py`, 456 passed/2 skipped fleet-wide (`app/services`).

**This closes the readiness-aware prioritization thread end-to-end** — Ananth's original ask, Router's mathematical justification + contract test, Retriever's implementation, all independently verified at each step rather than taken on report alone.

## Synthesis sign-off (§4, external chunk shape) — GIVEN, one real backlog finding surfaced

Reviewed `synthesis-module-spec.md` §4 directly (not just Retriever's summary) before signing off. Confirmed accurate for my output: `url`/`document_id` mutually exclusive, no page/paragraph anchor, `content_sha` always `None` (dedup correctly falls to body-text for everything I produce). Prescreen work doesn't touch this contract — `_chunk_from_passage` unchanged.

**Real finding, not a blocker:** Synthesis's humanized-URL-path document-name fallback (`/providers/x` → "X") is genuinely the *correct* choice for Vertex-sourced chunks — verified Vertex Grounding's own `title` metadata is literally just the bare domain by API design, confirmed in both code and real captured titles ("sunshinehealth.com"). But DDG-sourced hits carry real, useful page titles (`_Passage.title`, e.g. "PDF CLAIMS FILING INSTRUCTIONS - Sunshine Health") that get dropped before reaching `FilledChunk` — no `title` field exists on the contract. Flagged as a concrete backlog item for whenever `FilledChunk` next changes: a best-effort `title: str | None` field, populated only when real (not a bare domain), that Synthesis could prefer over URL-humanization when present. Not building unilaterally — same pattern as the `url` field, DB's call.

Also independently re-confirmed the `test_synthesis.py` flakiness I flagged earlier doesn't reproduce now (5/5 clean, matches Synthesizer's own report) — gave them the exact failing test names/tracebacks I saw for their records, consistent with it being transient shared-checkout state at that moment, not a persistent bug.

## Length floor + text-level dedup BUILT (2026-07-24) — the two backlog items closed

Retriever's status check ("is Filler d's stop-signal design blocking Observer") prompted clarifying the actual division of labor (Observer owns the sufficiency-check logic in `observer.py`, already reviewed+signed-off by me — see earlier entries) and closing the two items that WERE genuinely mine and unbuilt: the length floor Eval asked for, and the text-level dedup gap found during Observer's design review.

- `_MIN_PASSAGE_LENGTH = 50` — same threshold as Filler b's `_MIN_CHUNK_LENGTH`, reused not reinvented. Filters genuinely tiny/degenerate extractions before they become chunks. Does NOT solve the PDF-TOC-not-substance finding (different failure mode, already logged separately).
- `_dedup_passages_by_text()` — exact-text match across different URLs (mirror/syndicated pages), first-seen wins. Not fuzzy similarity — no calibration data exists for a threshold, and exact match covers the concrete case raised.
- Both emit new telemetry (`n_below_length_floor`, `n_text_duplicates_dropped`).
- **Real self-inflicted regression caught and fixed during testing, not shipped silently:** the length floor initially broke 10 existing tests because the shared test fixture's default passage text (`_ok_passage`) was below the new 50-char floor — then, after fixing that, a second bug surfaced where multiple tests simulating distinct passages all used the SAME default text, which the new text-dedup correctly (but unexpectedly for the tests) collapsed into one. Fixed the fixture properly (unique-per-URL default text, real margin above the floor, explicit `text=` override for tests that genuinely want duplicates) rather than papering over either symptom.
- 69/69 `test_filler_d.py`, 493 passed/2 skipped fleet-wide (`app/services`), no regressions.
- **Real live verification, not just tests:** ran against real Sunshine Health data — `n_text_duplicates_dropped: 3` (genuine mirror/syndicated duplicate content caught in production data, not a synthetic case), `n_below_length_floor: 0` (no tiny scraps this run, as expected for typical web content), occupancy still 5/5.

## Real warm/cold latency split for priors_bootstrap.yaml (2026-07-24)

Router found `priors_bootstrap.yaml`'s static `latency_p50_ms=3000` for "d" was a placeholder excluding "d" from most interactive-budget plans. Ran fresh real measurements (3 queries, current code, real DB+network) rather than reuse older session numbers:
- **WARM (prescreen already done)**: 4024/4315/3200ms, median ≈4000ms. fetch_ms 1942-2765ms, bm25_ms 704-2081ms.
- **COLD (no prescreen)**: 9961/17015/11019ms, median ≈11000ms. search_ms (6148-11611ms) still the dominant, highly variable cost.
- n=3 per path — real signal confirming the bimodal split, not a rigorous P50; more samples needed before hard-locking a number.
- **Framing flagged to Retriever/Eval**: with readiness-deferral now live, "d" should rarely actually execute cold for single-query PRECISE/EXACT postures (deferred to a later turn instead) — COLD mainly applies to FAN_OUT (prescreen scoped out) or forced-last-rung cases, not the general "d" estimate. WARM is the number that should feed the interactive-budget-relevant prior for the common case.

## Observer's real stop-signal for "d" — SIGNED OFF (2026-07-24)

Observer implemented the decay-floor sufficiency check proposed earlier (`observer.py:258-316`, `_evaluate_web_search`), reusing Filler b's exact `_DECAY_FLOOR_RATIO=0.6` threshold against my real `original_score` (BM25). Verified against the actual file, not the pasted diff: matches exactly, both of my earlier caveats (capacity=1 slots get zero signal; BM25 doesn't cleanly separate off-topic-but-vocabulary-sharing content) are written verbatim into the function's docstring, not just chat-acknowledged. Ran the tests myself: 23/23 `test_observer.py`, all 5 `TestWebSearch` cases correct. Signed off — good to ship as designed, no changes needed on my end. This closes the Observer-design thread entirely; `filler_d.py`'s own scope (search, fetch, BM25, dedup, length floor, prescreen, readiness deferral) is fully independent of and unaffected by this.
