# Sitemap Links (Suggested-Link Lookup) — Kickoff

**IDENTITY CORRECTION (Retriever, 2026-07-23, round 8):** this module is NOT "Filler f" and never was, despite the title below and this doc's filename. Router's real strategy `"f"` is a separate, unbuilt, scored bandit arm with its own seeded priors (`router-build-spec.md`'s `PRIORS_SEED_DEFAULTS["f"]`, `router/priors.py:236-241`, `router/allocation.py:80`'s `STRATEGY_PRIORITY_ORDER`) — "external fallback, similar to d." This module was mistakenly labeled with that letter early on. Retriever's words: "it doesn't need a strategy-letter identity at all, since it was already established it doesn't compete for Router's attempts." Kept as "Sitemap"/"Suggested Links" internally going forward, no letter. Doc filename and title below kept as-is only because other sessions (Filler d) already link to this exact path — see "Round 8" further down for the full trail. Code module is `sitemap_links.py`, not `filler_f_sitemap.py` (renamed).

**Status:** Handoff from Retriever, received in-session (title "4d - Sitemap"). Design-only doc initially — **core logic now built and tested** (see "Build status" below), still not wired into any orchestrator.

Ananth's framing (relayed by Retriever): "looking at the sitemap of sourcing, seeing if we can point to documents or links that may have the answer" — deliberately lightweight, **NOT** full content retrieval.

---

## Real prior art, verified directly

`_lookup_sitemap_candidates()` — `mobius-rag/app/services/corpus_search_strategy_d.py:413-450`:

```python
async def _lookup_sitemap_candidates(
    db: AsyncSession, tag_matches: list[str] | None, display_name: str | None, *, limit: int = 3,
) -> list[str]:
```

- Maps `d:`-prefixed tags in `tag_matches` to URL-path keyword sets via a static table (`_D_TAG_URL_KEYWORDS`, lines 127-135 — real contents, not paraphrased):
  ```
  claims.timely_filing                          -> ["timely", "filing"]
  utilization_management.prior_authorization     -> ["preauth", "prior-auth", "authorization"]
  utilization_management (any other leaf)        -> ["preauth", "prior-auth", "authorization"]
  pharmacy                                       -> ["pharmacy"]
  eligibility                                    -> ["eligib"]
  disputes                                       -> ["appeal", "grievance"]
  claims (any other leaf)                        -> ["claims"]
  ```
  No match against any of these prefixes -> returns `[]` immediately (no keywords to filter on).
- Queries `discovered_sources` (real schema, verified against `app/models.py:637-696` — not assumed):
  ```sql
  SELECT url FROM discovered_sources
  WHERE payer = :payer
    AND last_fetch_status = 200
    AND curation_status NOT IN ('noise', 'stale')
    AND (url ILIKE '%kw0%' OR url ILIKE '%kw1%' ...)
  ORDER BY ingested DESC, last_seen_at DESC
  LIMIT :limit   -- default 3
  ```
- Returns **bare URL strings only** — no fetch, no extraction, no LLM call, no `title` (the table has no title column — confirmed columns: `url, host, path, payer, state, program, inferred_authority_level, curated_authority_level, topic_tags, content_kind, extension, first_seen_at, last_seen_at, last_fetch_status, last_fetch_at, fetch_attempt_count, content_type, content_length, content_hash, content_changed_at, ingested, ingested_doc_id, ingested_at, discovered_via, seed_url, depth_from_seed, scrape_job_id, curation_status, curated_by, curation_notes, curated_at`). Any "title" for display would have to come from `path`/`url` itself, or a downstream fetch — not from this table.

**Correction to the handoff's framing:** this is not an existing standalone legacy strategy being ported 1:1 — it's a genuinely new decomposition. Confirmed by grep: `_lookup_sitemap_candidates` has exactly **one call site in the entire repo**, inline inside `strategy_d_external()` (`corpus_search_strategy_d.py:872`), where its output (`sitemap_urls`) is merged ahead of live web-search hits ("Sitemap candidates first (highest trust), then web hits, deduped by URL" — line 917) and then fed into the *same* fetch-and-extract pipeline as the web search results, before synthesis. Legacy never treats "check our own sitemap crawl" as a self-contained answer path — it's a priority-ordering step inside Strategy d's search phase. Pulling it out as an independent Filler f is Ananth/Retriever's new call, not a preexisting seam. Flagging this up front because it changes what "done" looks like: legacy has no reference implementation of a sitemap-only result being returned to a user without ever being fetched.

## Real, non-trivial dependency the handoff undersold: payer-context resolution

`_lookup_sitemap_candidates` takes `display_name` as an argument — it does not resolve it itself. The real resolution is `_resolve_payer_context()` (`corpus_search_strategy_d.py:188-264`), and it is **not simple**:

1. Extracts a payer slug from `tag_matches` via `_extract_payer_slug()` (looks for a `j:payor.<slug>` tag).
2. Tries the **Payor Platform registry** first — a live HTTP call (`httpx`, 3s timeout) to `{MOBIUS_PAYOR_URL}/api/registry/payors/{name}/web-domain`, returning a tri-state `crawlable` verdict.
3. Falls back to querying `discovered_sources` itself (`payer`/`url` grouped by dominant host, requires >= 3 matching rows to avoid false-confidence).

**Verified via grep across `app/services/retriever/`: nothing in the new Retriever chain (Gate/Reformat/Structure/Slots/Pool) resolves or threads a payer display name or slug today.** So Filler f cannot assume this arrives upstream — it would need to replicate `_extract_payer_slug` + `_resolve_payer_context` itself (port, don't import), including the live cross-service HTTP dependency on mobius-payor. That is a materially bigger dependency than "the simplest of the c/d/s/f strategies" framing suggested, and worth explicit sign-off before treating it as a given, not something to quietly absorb. **Open question for Retriever/DB:** should Filler f make its own Payor Platform call (duplicate cost + failure mode already paid by whichever of c/d also needs payer context), or should payer slug/display-name resolution be hoisted into Shape/Slots once, shared by all of c/d/f? Not deciding this unilaterally.

## Real cross-filler gap: `tag_matches` / `db` are not in the Fillers parent input contract

`fillers-schematic-spec.md`'s Input Contract lists exactly three inputs: `PoolResult`, `AnswerShapeResult`, `RoutingLadder`. No `tag_matches`, no `db` session, no `raw_query`. Filler d's own kickoff doc independently hit this (proposed a materially different signature with `db`/`agent_id`/`tag_matches`/`partition` for exactly this reason). Filler f needs the same extras (`db` for the two live queries above, `tag_matches` for the d-tag keyword mapping) — this is now the **third** live-external filler (c, d, now f — plus s) that needs inputs the parent spec doesn't define. Flagging this as a shared, one-time fix rather than four separate per-filler patches: whoever owns `fillers-schematic-spec.md` (UX, per its own header) should add a documented exception block for live-external fillers' real signature, not leave each filler to invent its own ad hoc extension.

## FilledChunk shape for a URL-only result — CONFIRMED genuinely new, not covered by c/d's resolution

Filler c and Filler d already resolved `FilledChunk.url: str | None` (not `source_url`) with Chat/DB — confirmed still pending actual landing in `contracts.py` (checked directly: not present as of this doc). Pinged both sessions on the text-less case rather than assuming it generalizes. **Both independently confirmed this is a real, distinct third shape, not a variant of what they already resolved:**

- **Filler c:** their `retrieved_external` status always has non-empty `matched_chunk_text` alongside `url` by construction — "retrieved" means the LLM's quote was found and verified inside a fetched page. For citations where no text was found, their design **skips emitting a `FilledChunk` at all** rather than emitting one with empty text. They've never hit "url present, text absent." Also flagged a sharper mechanical point: `contracts.py`'s `FilledChunk.text: str` is currently **non-optional with no default** — the same state `document_id`/`url` were in before those got relaxed. This may need an actual contract change (DB's call), not just a semantics decision.
- **Filler d:** confirmed the dataclass type doesn't forbid `text=""` mechanically, but `fillers-schematic-spec.md:65` has an explicit comment on why the field exists: *"CORRECTED 2026-07-23 — dropped in earlier draft; Synthesis needs actual chunk content, not just an id."* A `text=""` chunk runs directly against that documented purpose — it would occupy slot capacity/occupancy (`FilledSlot.occupancy`, `under_filled` computed off it) without giving Synthesis anything to actually synthesize from. Also flagged that Observer's fill-quality proxy (`observer-bayesian-confidence-spec.md`, percentile-of-`original_score`) **doesn't look at `text` at all** — a link-only chunk with a real score could make a slot look "filled" and "high-confidence" while contributing zero synthesizable content. Proposed a lighter-weight alternative to a contract change: a distinct `assignment_reason` (e.g. `"sitemap_candidate_unverified"`) so downstream can filter on that instead of needing a new field/flag.

**This is now confirmed to need escalation beyond c/d/f** — DB (contract: does `text` need to become optional, or is a distinct `assignment_reason`/flag enough), Eval (Observer's fill-quality proxy currently can't distinguish verified content from an unverified bare link — a real blind spot if link-only chunks enter `FilledShape.chunks` at all), and Chat (does the grounding-badge/citation UI render sensibly with a url but no preview text). **Escalated directly to DB/Eval/Chat** rather than three of us guessing at an answer none of us owns.

**Do not start writing `fill_shape_sitemap()` chunk-construction code until this resolves** — the answer changes whether `FilledChunk.text` becomes optional, whether link-only chunks get a distinct shape/flag entirely, or whether they belong in `FilledShape.chunks` at all vs. some other output the Fillers contract doesn't have yet (a separate "suggested_links" list, say, that Router/Synthesis explicitly know not to treat as content).

**RESOLVED by Chat (2026-07-23, `local_a22ef2b9`): link-only results must NEVER become a `FilledChunk`.** Chat's reasoning, verified against real behavior, not asserted: every chunk that reaches the LLM consolidator is treated as text the LLM can synthesize from — it quotes/paraphrases it and emits a citation number. A chunk with empty `text` gets a citation number pointing at a source the LLM never actually read — a grounding lie to the user. `cited_source_indices` means "sources the LLM synthesized from," which a bare URL categorically isn't.

**Correct shape: a new field, `suggested_links: list[{url: str, title: str | None}]`**, surfaced as a "you might also check" affordance below the answer card — visually distinct from the Citations tab, no citation number, **no grounding-badge contribution** (a turn with only link-only results stays badge=`gap`, not inflated). Confirmed with Chat: `discovered_sources` genuinely has no text/title/description of any kind (verified schema, see above) — there is no partial case where Filler f sometimes produces a normal text-bearing `FilledChunk` instead. Every result goes through the `suggested_links` path in v1.

**New real question this creates — RESOLVED (Chat, round 4): Option A, top-level field on `FilledShape`, sibling to `slots`.** Chat's reasoning: keeps everything flowing through one chain; Synthesis/Router just pass `suggested_links` through unchanged (nothing to synthesize, not a rankable slot) rather than introducing a second out-of-band channel to Contract that complicates the emit contract for no real benefit. Chat's only hard constraint: `suggested_links: [{url: str, title: str | None}]` appears under a stable key somewhere in the final response envelope — doesn't prescribe internal routing beyond that. Chat also flagged this touches **Synthesis's** passthrough contract (a currently-unbuilt module, owned directly by Retriever until forked) — not just DB's — so looped Retriever in on that specifically, not just the contracts.py mechanics. DB's actual open question is narrower per Chat: does `suggested_links` need persistence anywhere (probably not — transient, per-turn) or a `rag_query_decisions` link-count column (also probably not) — DB's call, not blocking.

**Title-derivation for `suggested_links[].title` — RESOLVED (Chat):** extract the last non-empty path segment from the URL, replace hyphens/underscores with spaces, title-case it (`/providers/prior-authorization-requirements` → "Prior Authorization Requirements"). Not real content, but scannable — better than a bare URL for a user deciding whether to click. `title: None` falling back to the raw URL is acceptable too if this is skipped, but adopt the slug-derivation since it's cheap.

**Eval's proxy-blind-spot fix — proposed then deprioritized (Eval, round 4):** Eval's first read proposed a binding `has_content: bool` field on `FilledChunk` + relaxing `text` to `str | None`, with the Observer proxy gated on `has_content`. After Chat's ruling routed link-only results around the scored-chunk flow entirely (`suggested_links`, no `original_score` ever attached), Eval confirmed that's cleaner and **deprioritized the `has_content`/`contracts.py` change** — kept only as documented (not built) fallback insurance for a future filler that hits a content-less-but-scored case it can't dodge as cleanly. No action needed from Filler f on this.

**Payer-context resolution — Retriever's ruling (round 4): build ONE shared utility, don't reopen Shape.** Since c/d/f/s all independently need `payer_display_name`/`payer_slug` and nothing upstream resolves it today, the fix is a shared helper (e.g. `app/services/retriever/fillers/payer_context.py`), not four re-derivations and not a Structure/Shape reopen. Coordinate directly with whichever of c/d/s gets there first; Filler d's own kickoff doc independently already flagged needing to port the exact same `_resolve_payer_context()` — pinging them directly to avoid duplicate build effort (shared-directory file-collision convention: ping before creating a new shared file).

**Parent-spec gap — FIXED by Retriever directly (round 4):** `fillers-schematic-spec.md`'s Input Contract now includes `tag_matches: list[str]` and `db: AsyncSession`, explicitly scoped to the live-external fillers (c/d/f/s) — a/b remain strictly pure-over-the-pool. This is the confirmed, documented contract going forward; no longer an open question.

## Proposed mapping (provisional — blocked on the two questions above)

| `FilledChunk` field | Source | Notes |
|---|---|---|
| `chunk_id` | `"ext:" + sha1(url)[:16]` | Same synthetic scheme Filler c/d already adopted — one convention across all live-external fillers. |
| `document_id` | same synthetic scheme | Matches c/d's resolution of this same question. |
| `text` | `""` | **Open** — see above; may not be the right answer. |
| `url` | the candidate URL | Depends on c/d's field landing in `contracts.py`. |
| `document_status` | `None` | No document row / no reality-gating for a raw crawl URL. |
| `source_type` | `"sitemap"` or `"external"` | Open — distinct enough from Filler d's fetched-and-synthesized external content to maybe warrant its own value; needs UX input on whether Chat's rendering path branches on `source_type`. |
| `original_score` | provisionally constant, high (matches legacy's "highest trust" framing relative to web search) | Same percentile-normalization reasoning Eval gave Filler c/d — raw scale doesn't matter once Observer normalizes within-pool. Needs Eval confirmation, not assumed. |
| `assignment_reason` | `"sitemap_candidate"` | New value, distinct from d's `"external_fetch"` and c's `"llm_retrieved"`/`"llm_partial_match"` — per the already-agreed convention (each filler documents its own value, no forced shared enum). |

## Gate condition (mirrors Filler s's explicit guard — don't drop it)

Legacy's own function already gates internally: no `display_name` -> `[]`; no matching `d:` tag prefix -> `[]`. Filler f's `fill_shape_sitemap()` should preserve both short-circuits rather than always attempting the query.

## Port, don't import

Same directive as every other filler. Re-implement `_lookup_sitemap_candidates`, `_extract_payer_slug`, and (pending the payer-context open question above) `_resolve_payer_context` into Filler f's own module — no live `from app.services.corpus_search_strategy_d import ...`. Verify `_D_TAG_URL_KEYWORDS` and the `discovered_sources` schema fresh as ported (done above), don't copy-paste and assume correctness.

## Central architectural question — RESOLVED, Retriever retracted its own round-5 ruling in favor of Chat's

Round 5 (above framing, now superseded): Retriever initially ruled Filler f bypasses Router/Synthesis entirely, landing directly at Contract (Step 6) as a side-channel. **Round 6: Retriever retracted that framing, explicitly deferring to Chat's actual decision as simpler and correct** — Chat's Option A stands: `suggested_links: [{url, title}]` is a **new top-level field on `FilledShape`, sibling to `slots`**, and it rides along through the normal Fillers -> Router -> Synthesis -> Contract pipeline **inert** — not scored, not gated, not retried, just passed through unchanged by every scoring/gating step along the way, and arrives intact at Contract. One object flows through the whole pipeline; this field simply isn't touched by any of the machinery that acts on `slots`. Retriever's own words: "my instinct to keep it out of the scored-chunk machinery was right; my instinct to invent a separate side-channel bypassing the pipeline entirely was unnecessary complexity Chat's answer avoids."

**Practical effect on this module's code:** none — `lookup_sitemap_links()` returning `list[SuggestedLink]` directly is still the right shape for the data-producing function itself. What changes is only how the orchestrator wires the result in: instead of shipping it off to a separate Contract-bound channel, whatever assembles `FilledShape` for a query attaches this module's output as `FilledShape.suggested_links` (pending DB's sign-off on that exact field name in `contracts.py`), and Router/Synthesis/Contract pass it through untouched alongside the normal `slots` list.

UX's role narrowed accordingly (per Retriever, round 6): schema/placement is settled (Chat, code-grounded reasoning); the only thing still going to UX is the **visual rendering treatment** for the "you might also check" affordance itself, not the underlying architecture.

## Build status (2026-07-23) — core logic built and tested, NOT wired into any orchestrator

Since the output shape (Chat), routing preference (Chat, Option A), title-derivation rule (Chat), and non-per-slot architecture (Retriever) are all resolved, and Filler d green-lit building the shared payer-context utility now (they haven't started, still blocked on their own `url` field landing), built and verified the parts that don't depend on the still-open items:

- **`app/services/retriever/fillers/payer_context.py`** — shared `extract_payer_slug()` + `resolve_payer_context()`, ported fresh from `_extract_payer_slug`/`_resolve_payer_context` (verified against the real source line-by-line, not copy-pasted). Filler c/d/s can import this once they need it instead of each re-porting the same Payor Platform HTTP call + `discovered_sources` fallback.
- **`app/services/retriever/fillers/sitemap_links.py`** (renamed from `filler_f_sitemap.py` per the identity correction above) — `SuggestedLink` dataclass (`url`, `title`), the ported `_D_TAG_URL_KEYWORDS` table, `_derive_title_from_url()` (Chat's path-slug rule), and `lookup_sitemap_links()` (the ported query, preserving both legacy gate conditions: no payer name -> `[]`, no matching d-tag -> `[]`).
- **Tests:** `test_payer_context.py` (13 tests, incl. tri-state `crawlable`/`source` coverage added round 10) + `test_sitemap_links.py` (16 tests), all passing — verified by actually running pytest, not asserted from reading the code (per the fleet's standing artifact-validation requirement). Payer-context's live-HTTP registry layer is now tested directly (fake `httpx` module) as well as the `discovered_sources`-fallback layer's own filtering logic (dominant-host, min-rows guard) — this module only ever depends on `display_name`, not the registry/crawlable half.

**Deliberately NOT done yet:** no wiring into any orchestrator/dispatch loop (trigger condition still in flux), no `contracts.py` changes (DB's call on `suggested_links`' final field name/shape — this module's `SuggestedLink` is local/provisional until DB signs off), no live calibration run (meaningless without real orchestrator wiring and a real `payer_display_name`/`tag_matches` source feeding it).

## Identity collision with Router's "f" — RESOLVED (Retriever, round 8, confirmed against real code)

Router's LOCKED specs (`router-build-spec.md`, `router-eval-codesign-brief.md`) list strategies as `a/b/c/d/f/s/sitemap` — treating `"f"` (a real seeded bandit strategy, "fallback/external, similar to d," scored/competing for slot attempts) and `"sitemap"` (unseeded, "direct lookup cost/benefit") as **two different things**. Escalated to Retriever, who independently verified against the actual (not just prose-described) code: `priors.py:236-241` has a real seeded profile for `"f"` (recall_lift 0.12→0.65, latency 2500ms, cost 2), and `allocation.py:80`'s `STRATEGY_PRIORITY_ORDER` includes `"f"` as a genuine, scored, competing member of the allocation loop — exactly like a/b/c/d/s. Fundamentally incompatible with what this module is (unscored, no slot competition, inert `suggested_links` passthrough).

**Conclusion (Retriever): this module was never actually Router's `"f"`.** Router's real `"f"` is a separate, unbuilt, unowned scored strategy — a genuine gap, not this module, and Retriever is flagging it to Router/Eval separately to decide whether it gets its own kickoff or drops from the roster if nobody builds it. This module doesn't need a strategy-letter identity at all, matching what was already established about it bypassing Router's scored machinery. Code renamed `filler_f_sitemap.py` -> `sitemap_links.py`; doc title/filename above kept for link stability but corrected in content.

## Open design questions

1. **Payer-context resolution ownership** — does Filler f make its own Payor Platform HTTP call + `discovered_sources` fallback, or does Shape/Slots resolve payer slug/display-name once upstream for all of c/d/f? Not deciding solo.
2. **`tag_matches`/`db` missing from Fillers' parent input contract** — shared gap with c/d/s, needs one fix at the parent-spec level, not four ad hoc ones.
3. **Text-less `FilledChunk` shape** — pinged Filler c/d directly, awaiting reply.
4. **Is Filler f's output answerable content or a suggested-link affordance?** — central architectural question, changes what Synthesis/Chat do with the output. Not assumed.
5. **`source_type` value** (`"sitemap"` vs reusing `"external"`) — needs UX input on whether Chat's rendering branches on it.
6. **`original_score` constant value** — needs Eval confirmation, same pattern as c/d.

## What's explicitly NOT being decided in this doc

No code written. This surfaces fork points from reading the real prior art directly and from direct coordination with Filler c/d — not a substitute for actual cross-agent sign-off (Chat/Eval/DB/UX/TECH), same as every other module in this fleet.

## Next steps

1. ~~Read parent spec, existing filler_a.py pattern, contracts.py, discovered_sources schema.~~ Done.
2. ~~Ping Filler c/d directly on the text-less chunk shape question.~~ Sent, awaiting reply.
3. Raise open questions 1, 2, 4, 5 to Retriever for routing to the right owners (payer-context ownership and the parent-spec gap are cross-filler, not mine to resolve unilaterally).
4. Once questions 3-4 resolve, write `fill_shape_sitemap()` + `contracts.py` additions (if any), unit tests against real `discovered_sources` rows, characterization test.
5. Real calibration run with a real artifact (per the fleet's standing artifact-validation requirement) before any Eval sign-off claim.
