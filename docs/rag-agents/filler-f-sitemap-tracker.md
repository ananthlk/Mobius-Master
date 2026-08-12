# Sitemap Links (Suggested-Link Lookup) — Progress Tracker

**IDENTITY CORRECTION (round 8):** not "Filler f" — see kickoff doc's header banner and Round 8 below for the full trail. Code lives in `sitemap_links.py` (renamed from `filler_f_sitemap.py`). Doc filenames kept stable for link continuity.

**Status:** Core logic built and independently verified (`sitemap_links.py`, `payer_context.py`, 71 passing tests). Not wired into any orchestrator yet.

---

## What was done

- Read and verified the real prior art directly: `_lookup_sitemap_candidates()` (`corpus_search_strategy_d.py:413-450`), its one and only call site (`:872`, inline inside `strategy_d_external`), `_D_TAG_URL_KEYWORDS` (`:127-135`, full contents transcribed, not paraphrased), and `_resolve_payer_context()` (`:188-264`, including the live Payor Platform HTTP dependency).
- Verified `discovered_sources`' real schema against `app/models.py:637-696` — confirmed no `title` column exists, correcting the handoff's "maybe title from discovered_sources" suggestion.
- Verified `contracts.py` directly — `FilledChunk.url` has not landed yet (matches Filler d's own tracker note; same still-open blocker, not re-verified stale from memory).
- Grepped `app/services/retriever/` for any existing payer-slug/display-name plumbing — found none. This means Filler f cannot assume payer context arrives upstream; it's a real, undecided dependency question, not a formality.
- Checked `fillers-schematic-spec.md`'s Input Contract — confirmed `tag_matches`/`db` are absent from it, same gap Filler d's kickoff doc already flagged independently. This is now a 3-filler-wide (c/d/f, plus s) shared gap, not filler-specific.
- Read `filler-s-payor-kickoff.md` for pattern/precedent (another live-external filler with its own gate condition and cross-service dependency) before writing this doc.
- Pinged Filler c (`local_ad29acea-4e2b-4265-b7df-c067197d718d`) and Filler d (`local_e2e86c4c-075a-4a7a-80fb-cd04497de27e`) directly, per Retriever's explicit instruction to coordinate rather than re-derive the `url`/`FilledChunk` shape question solo — asked specifically about the text-less-chunk case, which is new (neither of their chunks are ever fully textless).
- Wrote `filler-f-sitemap-kickoff.md`: real prior-art table, the payer-context dependency flag, the shared parent-spec input-contract gap, the open text-less-chunk question, a provisional field mapping, and the central architectural question (is this filler's output answerable content for Synthesis, or a suggested-link affordance for Chat/UX — genuinely unresolved, not assumed either way).

## Verified-before-trust notes

- Did not accept the handoff's framing that this is "the simplest of the c/d/s/f live-external strategies to port" at face value — traced the real dependency chain (`_lookup_sitemap_candidates` needs `payer_display_name`, which needs `_resolve_payer_context`, which makes a live HTTP call to mobius-payor) and found it's not simpler than d's dependencies, just narrower in output shape.
- Did not assume `_lookup_sitemap_candidates` was already an independent legacy strategy — grepped for all call sites, found exactly one, inline inside `strategy_d_external`. This is a new decomposition, not a straight port of an existing standalone path.
- Did not assume a `title` field exists on `discovered_sources` just because the handoff suggested it might — read `models.py` directly, confirmed it doesn't.
- Did not answer the text-less-`FilledChunk` question by extrapolating from c/d's resolved `url` field alone — recognized it's a genuinely new case (zero text, not just an added field) and pinged both sessions directly instead of guessing.

## Round 2 — c/d replies confirm this is a real, unresolved tension, not a solved case

Both Filler c and Filler d replied to the text-less-`FilledChunk` ping, independently, and both concluded the same thing: my case is genuinely new, not covered by their already-resolved `url` field work.

- **Filler c:** their `retrieved_external` status always pairs `matched_chunk_text` with `url` by construction (no-text citations get no `FilledChunk` at all, not an empty one). Flagged that `FilledChunk.text: str` is non-optional/no-default in `contracts.py` today — may need an actual contract relaxation (DB's call), not just a semantics answer.
- **Filler d:** confirmed `text=""` is mechanically legal but conflicts with the field's documented purpose (`fillers-schematic-spec.md:65`: "Synthesis needs actual chunk content, not just an id"). Flagged that Observer's fill-quality proxy is score-only and blind to `text` — a link-only chunk could read as "filled/high-confidence" while giving Synthesis nothing. Proposed a cheaper alternative to a contract change: a distinct `assignment_reason` (e.g. `"sitemap_candidate_unverified"`) instead of a new field.

**Escalated directly to DB (contract), Eval (Observer proxy blind spot), and Chat (grounding-badge UI rendering)** rather than three filler sessions guessing at an answer none of us owns.

## Round 3 — Chat RULED, questions 3 and 4 resolved (in shape, not in wiring)

Chat (`local_a22ef2b9`) answered decisively: link-only results must never become a `FilledChunk` / enter `cited_source_indices` — the LLM consolidator treats every chunk as synthesizable text and would cite a source it never read, a grounding lie. Correct output: a new field, `suggested_links: list[{url: str, title: str | None}]`, a non-grounded "you might also check" affordance — no citation number, no grounding-badge contribution. Confirmed with Chat that `discovered_sources`' bare-URL-only schema (verified earlier) means there's no partial case — every Filler f result goes through `suggested_links`, none through the normal chunk path.

Closed the loop with Eval: the blind-spot concern they were asked about doesn't materialize, since link-only results never get a real `original_score` at all now. Told them so explicitly rather than leaving it hanging.

**New question this creates, escalated to DB + Retriever:** `FilledShape` has no field for `suggested_links` today — its shape is entirely `slots[].chunks[]`. Does Filler f add a new top-level field to `FilledShape` (passed through untouched by Router/Synthesis/Contract), or does its output skip the normal Fillers chain and land directly at Contract (Step 6)? Also raises whether Filler f is really part of the uniform 8-filler contract or a structurally different module. Not deciding solo.

## Round 4 — Eval/Chat/Retriever all replied; most open questions closed

- **Eval:** confirmed both concerns real (checked `observer-bayesian-confidence-spec.md` §6c directly — pure score-count formula, zero content-awareness, a second instance of the corpus-junk-confound failure class). Proposed a binding fix (`FilledChunk.has_content: bool`, `text: str | None`), then **deprioritized it** once Chat's routing made it unnecessary — kept as documented fallback insurance only. No action needed here.
- **Chat:** ruled Option A — `suggested_links` as a new top-level field on `FilledShape`, sibling to `slots`, passed through Router/Synthesis/Contract unchanged. Only hard constraint: a stable key in the final envelope. Also gave the title-derivation rule (path-slug → title-cased). Flagged this touches Synthesis's (unbuilt) passthrough contract too — looped Retriever, not just DB.
- **Retriever:** fixed the parent-spec gap directly (`tag_matches`/`db` now in `fillers-schematic-spec.md`'s Input Contract, scoped to live-external fillers c/d/f/s). Ruled on payer-context: one shared utility, not four re-derivations, not a Shape reopen — coordinate build ownership with whichever of c/d/s gets there first (Filler d already independently flagged needing the same port). Routed the content-vs-affordance question to UX — but Chat already ruled on it; flagging that to Retriever to avoid a redundant/conflicting second answer.

## Round 5 — Retriever's architectural correction + Filler d green-light; core logic built

- **Retriever:** initially ruled Filler f is NOT a per-slot filler — bypasses Router/Synthesis entirely, output lands directly at Contract (Step 6) as a side-channel. **Superseded in round 6, see below.**
- **Filler d:** confirmed not started (still blocked on their own `url` field landing in `contracts.py`), green-lit building the shared `payer_context.py` now, will import once it lands. Updated their own kickoff doc to drop `_resolve_payer_context`/`_extract_payer_slug` from their port-list (shared infra now, imported not re-implemented) and dropped `_lookup_sitemap_candidates()` entirely (confirmed it's squarely Filler f's).

## Round 6 — Retriever retracted its own bypass ruling, deferred to Chat's Option A

Retriever corrected itself: "Chat's ruling is right, mine was wrong." `suggested_links[{url,title}]` is a **top-level field on `FilledShape`**, riding inert through the normal Fillers -> Router -> Synthesis -> Contract pipeline (not scored/gated, just passed through unchanged), NOT a separate side-channel bypassing to Contract directly. Simpler than the round-5 framing. **No code changes needed** — `lookup_sitemap_links()` returning `list[SuggestedLink]` is still correct; only the orchestrator-wiring destination changes (attaches to `FilledShape.suggested_links` instead of a bypass channel). UX's remaining ask narrowed to the visual "you might also check" rendering treatment only — schema/placement is settled.

**Built and verified (not just designed):**
- `app/services/retriever/fillers/payer_context.py` — shared `extract_payer_slug`/`resolve_payer_context`, ported fresh.
- `app/services/retriever/fillers/sitemap_links.py` (renamed from `filler_f_sitemap.py`, round 8) — `SuggestedLink`, `_D_TAG_URL_KEYWORDS`, `_derive_title_from_url` (Chat's rule), `lookup_sitemap_links` (both legacy gate conditions preserved).
- `test_payer_context.py` (13 tests as of round 10) + `test_sitemap_links.py` (16 tests) — ran via pytest, all pass, confirmed real (not asserted from reading code).

## Round 7 — independent verification, not just self-report

- **Filler d:** ran `test_payer_context.py` themselves rather than trusting my "9/9 passed" claim — confirmed matching output, function names/signatures check out. Cleared that blocker on their end; still separately blocked on DB landing their own `url` field before they start building.
- **Retriever:** ran both test files themselves — confirmed 25/25 real. Explicitly noted the discipline of holding off on orchestrator wiring/contracts.py/calibration until the genuinely-open items land, rather than building speculatively on unresolved decisions.
- **Filler s:** found `payer_context.py` independently while writing their own test suite (saw the docstring naming c/d/f/s as intended consumers), swapped an inline `_has_payor_tag` check for `extract_payer_slug()`, full suite (67 passed, 2 skipped) still green after the swap. Not using `resolve_payer_context()` — their fact-store gate only needs the tag-match boolean, not a resolved site domain. Third real (not just anticipated) consumer of the shared utility now. No action needed — informational close-the-loop per direct-connect-peer-sessions convention.

## Round 8 — identity collision found, then CONFIRMED by Retriever against real code

Retriever asked me to coordinate with Filler d + Structure/Slots on a new question: Router's crawl-gate for strategy `d` needs `payer_context`'s `crawlable` verdict resolved BEFORE chain-planning, not lazily at execution time. Before answering, checked Router's own LOCKED specs directly (not assumed applicable):

- `router-eval-codesign-brief.md:23` lists strategies as `a/b/c/d/f/s/sitemap` — **seven** entries. Lines 33-34 describe `f: fallback/external (similar to d)` and `sitemap: direct lookup cost/benefit` as **two separate strategies**.
- `router-build-spec.md`'s actual seeded `PRIORS_SEED_DEFAULTS` (LOCKED, co-designed with Eval) has a real bandit profile for `"f"` — recall_lift/latency/cost/accuracy curves nearly identical to `"d"`'s, prose-grouped with c/d as "external, high recall, variable accuracy." `"sitemap"` never appears in the actual seeded dict, only in prose — unseeded.

Escalated to Retriever rather than assume. **Retriever independently re-verified against the real (not prose) code: `priors.py:236-241` seeds a real `"f"` profile, `allocation.py:80`'s `STRATEGY_PRIORITY_ORDER` includes `"f"` as a genuine scored, competing strategy — confirmed fundamentally incompatible with this module.** Retriever's ruling: this module was never actually Router's `"f"`; Router's real `"f"` is a separate, unbuilt, unowned scored strategy (a genuine roster gap, now flagged to Router/Eval separately). This module doesn't need a strategy-letter identity at all. **Renamed `filler_f_sitemap.py` -> `sitemap_links.py`** to stop carrying the wrong name forward (zero blast radius, no external callers existed).

Separately, narrower point relevant to the actual crawl-gate ask: `lookup_sitemap_links()` never consumes `crawlable`/`site_domain` from `resolve_payer_context()` — only `display_name`. `discovered_sources` rows are already-fetched (`last_fetch_status=200`); live crawlability is orthogonal to querying our own crawl DB. **Confirmed by Retriever: "doesn't apply to you."** Filler d separately confirmed (checked `corpus_search_strategy_c.py` directly) that Filler c doesn't need this either — squarely Filler d's problem alone.

## Round 9 — real bug found and fixed in payer_context.py's tri-state handling

Filler d, working the crawl-gate coordination Retriever asked for, found a real gap: `resolve_payer_context()` collapsed `crawlable=False` (explicit robots-disallow) and "no registry opinion" into the identical `(None, None)` return — faithful to legacy's own behavior (legacy never needed the distinction, both meant "don't site:-restrict"), but insufficient for Router's new `RoutingContext.payer_crawlable` tri-state gate (`False` disqualifies strategy d, `None` fails open — these must stay distinguishable).

Verified the claim against the actual code before agreeing, then fixed it (zero blast radius — no production callers existed yet, only my own tests):
- `resolve_payer_context()` now returns `PayerContext(site_domain, display_name, crawlable: bool | None)` instead of a bare tuple.
- Also fixed a related issue: legacy discarded `display_name` too whenever `crawlable=False` — now preserved, since it's derived from the slug independent of crawlability.
- 4 new tests exercising the registry HTTP layer directly (fake `httpx` module, not just the DB-fallback path already tested) — `crawlable=True`, `crawlable=False`-preserves-display_name, null-falls-through, non-200-falls-through. 13/13 pass in `test_payer_context.py`, 71/71 across the whole `fillers/` directory, no regressions.

**Raised a design point to both Filler d and Router directly** (own the file, wanted a say in the call-site design, not just the return shape): whoever calls `resolve_payer_context()` for chain-planning must thread the resolved `PayerContext` through to whichever filler executes, not have that filler re-call the function independently — otherwise a query pays the ~3s Payor Platform HTTP timeout twice. Same "compute once, thread through" discipline as `gate_j_codes`, extended to this function's *output*.

## Round 10 — crawl-gate call-site resolved (orchestrator, TTL-cached); PayerContext finalized

Filler d clarified their actual proposal was never "Structure/Slots resolves it" (both correctly ruled out — zero-DB, signed-off, wrong layer) but "**Router** resolves it itself" (same precedent as `gate_j_codes`: computed upstream, threaded through). **Router vetoed this** — verified against real code, TECH gate (b) "No DB access during optimization" is real and word-for-word in `router/__init__.py`, plus determinism/latency concerns. **Accepted counter-proposal: the orchestrator resolves it**, concurrent with Pool's fetch, TTL-cached, skip-and-fail-open on a real_time cache miss — Retriever owns that wiring, not this module.

Router also asked (relayed via Filler d) for `resolve_payer_context()`'s return shape to become a dataclass carrying `slug`, `display_name`, `site_domain`, `crawlable`, and `source` ("metafact" | "crawl_history" | "none") — the last for Eval to weight a registry-confirmed verdict differently from a crawl-history-inferred one. **Shipped**, adopting Router's shape with one honest correction: the `discovered_sources` fallback layer has no robots signal at all, so it can only ever produce `crawlable=None`/`source="crawl_history"` — it never infers a `False`. Noted this limit explicitly in the dataclass docstring rather than over-promising a distinction the code doesn't actually make. Updated all existing tests to the new fields + added coverage for `slug`/`source` correctness. 13/13 `test_payer_context.py`, 71/73 total (2 pre-existing skips) across `fillers/`, all passing, no regressions.

Filler d's use of `payer_context.py` is unaffected either way — they only ever read `site_domain`/`display_name`, confirmed a non-event on their end.

## Round 11 — Router/Filler d close out the crawl-gate thread; PayerContext.source simplified

- **Filler d:** independently re-verified the round-9 fix (read the code, ran pytest themselves — 71/2, matched exactly). Added `payer_context: PayerContext | None` to their proposed `fill_shape_external()` signature so a threaded-through resolution can be reused, falling back to self-resolving only if genuinely absent.
- **Router:** three things. (1) Accepted the `PayerContext` shape, but pointed out the `source` field they'd asked for is fully derivable from `crawlable`/`site_domain` given this module's actual registry-vs-fallback semantics — withdrew the ask, suggested documenting the derivation instead of storing it. (2) Ruled definitively on threading: the orchestrator's per-query state carries the FULL `PayerContext`; `RoutingContext` carries only the derived `payer_crawlable` tri-state Router itself consumes. Orchestrator resolves once post-Gate, sets Router's field, hands the same object to Fillers at execution — symmetric with Router's own veto of resolving it themselves. (3) Confirmed the placeholder `"f"` priors cell was retired today (Eval-ratified) — it predated this module's real unscored shape and structurally couldn't produce a recall_lift contribution anyway. This module needs zero priors treatment from Router, permanently.

**Acted on (1) rather than just noting it:** `PayerContext.source` is now a derived `@property`, not a stored constructor field — removes the risk of it drifting out of sync with `crawlable`/`site_domain` that a separately-set field would carry. Docstring documents the exact derivation rule Router described. 4 new direct unit tests of the property (independent of `resolve_payer_context`'s own branches). 75/77 `fillers/`-wide (2 pre-existing unrelated skips), no regressions.

**This closes every open cross-agent thread from rounds 8-11** except the two structurally-separate blockers this module was always going to wait on (orchestrator trigger condition, DB's `suggested_links` contract sign-off) — see below.

## Round 12 — role upgrade: planned helper in Router's recall-failure path

Ananth-directed, relayed by Router: this module is now a **planned helper in Router's recall-failure path**, not only a standalone module. When the scored recall loop fails on a payor-identified query (`UNDER_CONFIDENT`/`NO_VIABLE`), Router's plan emits `helpers: ["sitemap_links", ...]`, and the orchestrator dispatches this module to produce `suggested_links[]` as a "here's where this likely lives" aid. Confirmed: stays outside Router's allocation loop entirely (no priors, no chain math — the retired-`"f"` boundary holds; helpers are zero-priors by design). Gating: Router only plans this helper when a payor `j_code` exists.

Router asked two questions; checked both against real code before answering, not assuming:

1. **Payer identification alone isn't enough for my lookup.** `lookup_sitemap_links()` has TWO independent gate conditions: no `payer_display_name` -> `[]`, AND separately no matching `d:`-tag prefix in `tag_matches` -> `[]`. A payer-identified query with no matching d-tag topic returns `[]` even if dispatched. Told Router to pass `tag_matches` (the query's `d:` tags) alongside the payer slug, not just payer identification. Also honestly flagged: `slot_semantics`/`rewritten_query` (offered by Router as optional extra context) aren't consumed by any code I've built — no per-failed-slot topic-biasing exists today; that would be new logic, not something passing the context would already unlock.
2. **My own lookup is cheap (one DB query, no fetch/HTTP), but it depends on `payer_display_name` — and `resolve_payer_context()` (which produces that) can make a live ~3s HTTP call when not already resolved.** Flagged explicitly, not assumed away: the recall-failure dispatch MUST reuse the orchestrator's already-threaded `PayerContext` (per round 10-11's design) rather than re-resolving fresh, or Router's "cheap enough to run unconditionally" assumption breaks. Asked for explicit confirmation with Retriever's actual orchestrator wiring rather than assuming it's automatically reused.

## Round 13 — Router closed both round-12 questions, pinned into the build-spec

- **d-tags:** `RoutingContext.gate_d_codes` (from `GateResult.d_codes`, same seam as `j_codes`) now feeds Router's helper gate — Router plans `sitemap_links` only when a payor `j_code` AND at least one `d_code` are present, mirroring my two gate conditions as Router's own cheap pre-filter. The keyword-table match (`_D_TAG_URL_KEYWORDS`) stays mine, since a d-code can exist without matching it. **Reconciliation named explicitly in the build-spec:** the orchestrator drops `sitemap_links` from the final verdict when my lookup returns `[]`; Chat includes the suggested-links block iff `suggested_links` is non-empty. My cheap-`[]` path is the safety net, not the plan.
- **Per-slot topic-biasing:** recorded as a known future increment requiring new logic on my side — Router won't pass slot context (`slot_semantics`/`rewritten_query`) until that exists.
- **Latency:** the "reuse the orchestrator's already-resolved `PayerContext`, never re-call `resolve_payer_context()`" rule is now **pinned into the build-spec**, not just an assumption — flagged to Retriever as an explicit orchestrator-wiring requirement.

Both round-12 questions fully closed. No further action needed on this thread.

## Open — blocking full sign-off (not blocking the code that exists)

1. **Orchestrator trigger condition** — when does this module actually run relative to Pool/slots? Now TWO trigger paths to design against: the original standalone flow (Chat's ruling) and the new recall-failure helper dispatch (round 12). Not decided yet, tied to the Observer redesign. Nothing to build against yet.
2. **`contracts.py`/final field shape for `suggested_links`** — DB's call, not yet landed; `SuggestedLink` here is local/provisional.
3. Confirm with Retriever whether Chat's ruling on the content-vs-affordance question supersedes the UX routing they initiated, or whether formal UX sign-off is still wanted.
4. ~~Round 12 — awaiting Router's reply~~ — RESOLVED (round 13): `gate_d_codes` threaded, PayerContext-reuse pinned into Router's build-spec.
4. No live calibration run yet — meaningless without real orchestrator wiring and a real `tag_matches`/payer-context source feeding it.

## Done / not started

- **Done:** `payer_context.py` (shared, real consumers: Filler s (`extract_payer_slug`), Filler d (planned, `PayerContext | None` already in their proposed signature), this module — none currently need `resolve_payer_context` in production code except tests), `sitemap_links.py` (`SuggestedLink`, keyword table, title derivation, `lookup_sitemap_links`), 75 passing tests total across both files, independently verified by Filler d and Retriever (not just self-reported). Identity corrected (not "Filler f"), files renamed accordingly. Crawl-gate call-site design fully resolved (orchestrator owns it, TTL-cached, threads the full object through to Fillers). `PayerContext.source` simplified to a derived property per Router's own withdrawal.
- **Not started, deliberately:** orchestrator wiring (trigger condition undecided — the only remaining structural blocker), `contracts.py` changes (DB's call), calibration run against real `discovered_sources` rows (meaningless without real wiring), cross-agent formal sign-off (Chat/Eval/DB/Retriever/Router have all given informal rulings; no one has done a formal closing sign-off pass yet since the module itself isn't wired in).
