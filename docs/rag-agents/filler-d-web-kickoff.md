# Filler d (Web Search) — Kickoff

**Status:** Handoff from Retriever, received in-session. Fourth of the 8-filler family (a/b built, c in progress as "4d - LLM Retrieval" — `local_ad29acea-4e2b-4265-b7df-c067197d718d`). Design-only doc — **no code written yet**, per process (design doc first, sign-off, then build).

**Round 2 update (2026-07-23):** all 5 original open questions resolved or confirmed except the `url` field's actual landing in `contracts.py` (name/shape agreed, DB still needs to add it). New directive from Ananth: **port legacy `corpus_search_strategy_d.py` logic into Filler d's own module — do not import it.** See "Port, don't import" section below. Also confirmed directly in code: `rag_strategy_d_external` is a real, live Thompson-sampling bandit stage in mobius-chat's `model_registry.py`, but it maps specifically to the *synthesis* call this doc proposes dropping — flagging that reasoning to Filler c + Eval rather than assuming it unilaterally (see Bandit section).

---

## Context verified directly (not taken on faith)

- Google Custom Search JSON API is permanently closed to new customers (403) — confirmed both in `project_google_cse_closed_new_customers` memory and in `corpus_search_strategy_d.py`'s own comments (lines 465-470, 899-902). Not the path to build on.
- The working search path is **Vertex AI's "Grounding with Google Search"** — `_search_web_vertex()` in `mobius-rag/app/services/corpus_search_strategy_d.py:461-531`. A DuckDuckGo fallback (`_search_web()`, same file, lines 534-593) is called only if Vertex grounding returns nothing.
- Real prior art, read in full (980 lines): `_Passage` (lines 82-89) and `StrategyDResult` (lines 92-97) dataclasses, and the legacy conversion at `corpus_search_agent.py:4627-4670` that filters `passages` to `fetch_status == "ok"` and non-empty `text`, building chunk-shaped dicts explicitly marked `source_type: "external"` for "external — verify" UI framing, with confidence floored to `"low"` when `n_ok == 0`.
- Confirmed the real `FilledChunk`/`FilledSlot`/`FilledShape` contracts in `app/services/retriever/fillers/contracts.py`, and both existing fillers' real code (`filler_a.py` — BM25, `filler_b.py` — vector). Both are **pure functions over an already-fetched `PoolResult`** — no I/O, no async, no live calls.
- Confirmed via `router/decision.py` that `RoutingLadder`/`RouterDecision` (dispatch_path: forced/greedy/optimizer/**bayesian**) is Router's own bandit-driven strategy-sequence decision. No bandit code exists yet anywhere under `app/services/retriever/` — filler_a/b's docstring mentions of `RoutingLadder` are just a locally-defined dataclass placeholder ("unused v1"), not a real bandit integration.
- Found Filler c's session (title "4d - LLM Retrieval") via cross-session search. No kickoff/tracker doc exists there yet — it appears to still be in its own discovery phase, same as this one. No prior-art file to build on yet for the facts-vs-narrative pattern; will coordinate directly (see Coordination section) rather than duplicate the discovery independently.

---

## Central architectural fork: is Filler d a Pool-consumer or a live trigger?

**RESOLVED (Retriever, 2026-07-23): confirmed live-trigger, per-slot, per-attempt.** Retriever's own words: "External strategies (c/d/s) fire per-slot, per-attempt, when that slot's current `RoutingLadder` rung is that strategy — NOT a query-wide pre-fetch into Pool. Pool stays corpus-only, always fetched once upfront regardless of what strategy gets tried later (that's the whole 'single-pool' principle)." The per-attempt orchestrator loop (in design alongside the Observer redesign) will trigger Filler d live, on-demand, exactly as described below. Build against this model — the reasoning that follows is now confirmed, not speculative.

This was the first thing that needed cross-agent resolution — it changes the function signature entirely, and wasn't mine to decide unilaterally.

**Fillers' parent spec** (`fillers-schematic-spec.md`) describes Fillers generically as "read-only over Pool + `AnswerShapeResult`; zero DB/embed side effects" — implying `external_context` slots get filled from `PoolResult.candidates` already-tagged `source_type in (web, external)`, the same shape as Filler a/b (pure rank-and-assign, no I/O).

**But** the Retriever handoff explicitly flags c/d/s as an exception: "you are NOT purely read-only, zero DB/embed... you make live external web calls... a correctly-flagged exception (c/d/s are live external strategies, not pure-over-the-pool like a/b)." And the legacy code this is meant to build on (`strategy_d_external`) *is* a live search+fetch+synthesize call, not a pool read — there's no upstream step in the current pipeline that pre-populates `PoolResult` with web-sourced candidates.

That maps cleanly onto how `RoutingLadder.strategy_sequence` already works: Router assigns a per-slot attempt sequence like `["a", "b", "d"]`, and when a slot's current rung is `"d"`, **that's the trigger to run the live external search for that slot, on that attempt** — not a pre-fetch. Filler d's real signature is closer to:

```python
async def fill_shape_external(
    pool_result: PoolResult,        # for slots NOT on this rung — pass through unfilled/untouched
    shape_result: AnswerShapeResult,
    raw_query: str,
    *,
    db: AsyncSession,
    agent_id: str,
    tag_matches: list[str] | None,
    partition: Any = None,
    routing_ladders: list[RoutingLadder] | None = None,
    payer_context: PayerContext | None = None,   # UPDATED, see below
) -> FilledShape:
```

i.e. it only fires `strategy_d_external()` for the specific slot(s) whose current ladder rung is `"d"`, and needs `db`/`agent_id`/`tag_matches`/`partition` as real live-call inputs that `filler_a`/`filler_b` never needed. This is a **materially different filler shape** than a/b, and worth flagging loudly for sign-off rather than silently reusing the a/b function signature and pretending it's the same pattern.

**`payer_context` param — RESOLVED (Retriever, 2026-07-23): confirmed as one coherent data-flow decision, not two.** `PayerContext` gets resolved once, post-Gate, threaded through both consumption points — Router's crawl-gate at plan time, and whichever filler (d/f/s) executes at attempt time. My shape (accept it as a param, self-resolve only if genuinely absent) is confirmed correct — "same defensive pattern as everything else in this fleet," Retriever's words. Exact threading mechanism (rides on `RoutingLadder` vs. a separate orchestrator-level context object) is still Retriever's to settle with Router; doesn't block my own design further. Original catch, for context: if Router resolves `PayerContext` once at chain-planning time (to populate `RoutingContext.payer_crawlable` for the crawl-gate — see the fleet-wide finding below), and Filler d *also* independently re-calls `resolve_payer_context()` at execution time for `site_domain`/`display_name`, the query pays the ~3s Payor Platform timeout **twice** for the same slug — once for planning, once for execution. Same "compute once, thread through" discipline `gate_j_codes` already established, just applied to the *result* of a resolution instead of only an input. Proposed fix: Router's resolved `PayerContext` threads through the orchestrator into Filler d's execution call as this new parameter; Filler d only falls back to calling `resolve_payer_context()` itself if it's genuinely absent (e.g. a slot where Router's crawl-gate never fired, or a standalone/test invocation) — not as the default path. **Not deciding this alone** — it changes what the orchestrator needs to thread through, which is Retriever's territory (they already claimed ownership of the orchestrator wiring for `payer_crawlable` itself); flagging that this is one data flow, not two separate ones, before that wiring gets built.

**Open question for Router/Retriever:** does the per-attempt orchestrator call Filler d once per slot-on-rung-d (my read), or does Filler d get invoked once per query and internally scan all slots for rung `"d"`? Affects whether `fill_shape_external` takes one slot or the whole `AnswerShapeResult`. Not resolving this myself — flagging for the orchestrator-loop owner (Router / Retriever).

---

## Facts-reshaping design (`_Passage` → `FilledChunk`)

Confirmed the legacy conversion (`corpus_search_agent.py:4627-4670`) already does almost exactly this — filters to `fetch_status == "ok"` and non-empty `text`, and explicitly does NOT surface the synthesized narrative as the chunk content. Proposed mapping, one `FilledChunk` per qualifying `_Passage`:

| `FilledChunk` field | Source | Notes |
|---|---|---|
| `chunk_id` | synthetic, derived from URL (e.g. `"ext:" + sha1(url)[:16]`) | No real chunk row exists for external content — needs a stable synthetic id so the same URL dedupes/traces consistently across attempts. |
| `document_id` | same synthetic scheme, or left `""` | Legacy just uses `""` (line ~4658). A synthetic id is more useful for tracing/dedup than an empty string — open question, see below. |
| `text` | `p.text` (already capped at `_MAX_PASSAGE_CHARS`=2000 by `_Passage`) | Legacy additionally truncates to 1500 chars at the dict-building step (line ~4653) — redundant with `_Passage`'s own 2000 cap; propose keeping the full up-to-2000 chars since `FilledChunk.text` has no separate size constraint documented. |
| `document_status` | `None` | No document row / no Product-Awareness reality-gating applies to external pages — explicitly not the "planned/live" concept that field exists for. |
| `content_sha` | hash of `p.text`, or `None` | Could enable cross-attempt dedup if the same URL is fetched twice; not load-bearing for v1. |
| `source_type` | `"external"` | Matches legacy exactly. |
| `tags` | `{}`  — **NOT** where the URL goes, see gap below | |
| `is_neighbor` | `False` | No neighbor concept for external content. |
| `original_score` | `1.0` constant for every chunk with `fetch_status == "ok"` | **RESOLVED**, see below. |
| `assignment_reason` | `"external_fetch"` | New value, distinct from a/b's `"score_rank"`. Vocabulary coordination with Filler c resolved — see Coordination section: no forced shared enum, each filler documents its own value set. |

**Real contract gap, RESOLVED (Chat, via Filler c, 2026-07-23):** `FilledChunk` gets a new field **`url: str | None`** — named `url`, **not** `source_url` (my original proposal). Chat's reasoning: its pipeline already uses `url` everywhere (`SourceRef.url`, `integrate.py:196/710/374` reads `s.get("url")` and checks `s.get("url") or source_type == "web"` to identify web sources) — naming it `url` means zero rename/mapping step when translating `FilledChunk` → `SourceRef`; `source_url` would need one. Shared resolution with Filler c (their `retrieved_external` status has the identical problem). **Still open:** DB (contract owner) has not yet landed the field in `contracts.py` — confirmed live, not yet present as of this doc's last check. Do not write `filler_d.py` chunk-construction code until it lands (constructing `FilledChunk(url=...)` before the field exists will just fail).

**`original_score` — RESOLVED**, using the same guidance Eval already established for Filler c's identical problem (`observer-bayesian-confidence-spec.md` lines 116-126, confirmed in the actual spec file): `FilledChunk.original_score` is never compared as a raw number anywhere downstream — Observer's fill-quality proxy uses **percentile-within-pool** normalization (`pool_percentile(chunk.original_score) >= 0.8`) specifically *because* raw scores aren't scale-comparable across strategies (BM25 unbounded, vector cosine [0,1], and the spec explicitly anticipates "future external strategies (d/f) will have their own scales"). Since percentile normalization absorbs the scale question, and Filler d has no better per-passage relevance signal without the dropped synthesis step (see below), the simplest correct choice is a **constant `1.0`** for every successfully-fetched chunk (`fetch_status == "ok"`) — ties are fine, same reasoning Eval gave Filler c for its own ties-at-1.0 case ("expected behavior of percentile normalization, not a bug"). Do not artificially manufacture per-chunk score variation that doesn't reflect a real signal.

**Narrative is explicitly excluded, matching the handoff's framing:** `StrategyDResult.llm_answer` (the 3-sentence synthesized narrative) is **not** proposed as a `FilledChunk` field or a `FilledShape`-level field. Slots/Fillers deal in facts; a future Synthesis module (not yet started, no owner) is presumably where a final narrative gets composed once, from all filled slots together — not per-filler, per-attempt. This mirrors the same facts-not-narrative issue flagged for Filler c.

---

## Whether synthesis (`_synthesize()`) should run at all

**RESOLVED (Eval, 2026-07-23, verified against code, relayed by Retriever): dropping `_synthesize()` is confirmed safe.** Eval verified `confidence_label` has zero references anywhere in `app/services/retriever/` — nothing in the new Fillers/Router/Observer chain reads it; confidence there is built entirely from `FilledChunk.original_score` + slot occupancy instead. Clean for the v1 build described below.

**Footnote for whoever eventually cuts legacy strategy_d over to Filler d (not a v1 blocker, but don't let it be a surprise later):** `confidence_label` IS still actively consumed by the OLD path today — `corpus_search_agent.py`, `corpus_search.py`, and several mobius-chat stages (`resolve.py`, `integrate.py`, `retrieval_persistence.py`, the `web_search.py` skill, the `corpus_search.py` skill). Those consumers lose that signal whenever legacy strategy_d gets retired in favor of Filler d — someone will need to either backfill an equivalent signal for them or confirm they're being retired in the same cutover. Flagged per Eval's explicit ask.

Original reasoning below, now confirmed rather than proposed:

`strategy_d_external()`'s step 3 (`_synthesize`) is an LLM call whose entire output — the narrative answer with `[N]`-citations — is exactly the thing the new architecture says NOT to pass through. Per the docstring's own cost breakdown, synthesis is ~3-6s of the total ~7-15s per call — **roughly a third to half of Filler d's latency, for output nothing downstream will use.**

If Filler d's job is purely "fetch passages, hand back facts," the cheapest correct design **skips `_synthesize()` entirely** and calls only `_search_web_vertex()`/`_search_web()` + `_fetch_and_extract()` (steps 1-2 of the legacy pipeline), cutting real latency and one LLM call per invocation. This is now the confirmed v1 design, per Eval's sign-off above.

---

## Bandit-selection design

**RESOLVED for the strategy-selection question, no within-filler bandit needed — confirmed by Eval (2026-07-23, relayed by Retriever).** Eval called out the reasoning below as correct: Vertex-vs-DDG is a documented reliability fallback ("safer failure mode" per the legacy file's own comments), not a probabilistic explore/exploit choice — nothing to learn since DDG is strictly worse, not uncertain. Router's `RoutingLadder`/`dispatch_path` (forced/greedy/optimizer/bayesian) is correctly the one strategy-selection bandit in the system, one level up from any individual filler.

**New finding, verified directly in both repos (2026-07-23) — the *model*-selection bandit is real, and it's specifically the synthesis call this doc just dropped:**

- `mobius-chat/app/services/model_registry.py:862-870` — `RAG_ROUTED_STAGES` includes `"rag_strategy_d_external"` verbatim, comment-labeled `"Strategy (d) External First synthesis"`. It competes only among Vertex `gemini-2.5-pro`/`gemini-2.5-flash` (comment: multi-page-chunk prompts need 1M context — may not actually apply to Filler d's short synthesis prompt, same observation Filler c made for their own stage). Selection runs through `ModelRouter.select(stage, ...)` — real Thompson sampling over a `BanditState` (Beta distribution, benchmark priors blended with observed quality/reliability/latency/cost), same mechanism Filler c independently found for `rag_strategy_c_validate`.
- `mobius-rag/app/services/llm_manager_client.py:65-72` — `RAG_STAGES` frozenset also lists `"rag_strategy_d_external"` with the identical `# Strategy (d) External First synthesis` comment, confirming both sides of the cross-service contract agree on what this stage covers: **the `_synthesize()` call specifically**, not the Vertex Grounding search call (which is a direct `genai.Client` call in `_search_web_vertex()`, bypassing `llm_manager_client`/the bandit entirely, hardcoded to `gemini-2.5-flash`).

**RESOLVED (Eval, 2026-07-23, independently re-verified in code — not just re-asserted):** Eval confirmed directly, citing exact lines: `model_registry.py:868` and `llm_manager_client.py:72` both label the stage "Strategy (d) External First synthesis"; in the legacy file the stage is invoked only inside `_synthesize()` (line 796, called from 765/957) — exactly the call being dropped; the Vertex Grounding search itself (`genai.Client`, line 507) never touches `llm_manager_client` at all (confirmed by grep). **Filler d v1 makes zero calls to any bandit-registered stage — there is no other `rag_strategy_d_*` stage in either file.** Eval's words: "you're not missing bandit integration, there's genuinely nothing left for it to apply to once the LLM-synthesis step is gone." Clear to build without any bandit wiring in v1.

**Filler c cross-check (2026-07-23):** confirmed their `rag_strategy_c_validate` stage does NOT generalize the same way — their `_ask_llm()` call **is** the retrieval step (it generates the citations that then get validated), not a narrative layer on top of an already-complete retrieval step the way my `_synthesize()` was. So Filler c correctly keeps their bandit-routed call; the two fillers reached different, structurally-correct outcomes rather than one pattern with an exception. Worth remembering if Filler e/f/s ever face the same question — "does this LLM call generate the content, or just narrate over content that already exists" is the actual test, not "is there an LLM call."

**Separate requirement from Retriever, now moot for v1 but worth recording:** whoever fires a bandit reward update needs the actual selected-model result to survive into emit/telemetry, not just a final score — applies to any design that keeps a model-routed LLM call. Since Filler d v1 has none (the only remaining LLM-adjacent call, Vertex Grounding, is a direct hardcoded-model `genai.Client` call bypassing `llm_manager_client` entirely — no model *selection* happens for it to preserve), there's nothing to wire for this in v1. Revisit only if a future version reintroduces a bandit-routed call.

**Net status:** no bandit code inside Filler d, and no cross-service bandit call either — confirmed, not just proposed.

---

## Coordination with Filler c ("4d - LLM Retrieval") — round 1 resolved

Sent Filler c the `url`-field gap, the synthetic-id problem, and the `assignment_reason` vocabulary question. They confirmed hitting the identical problem (their `retrieved_external` status — LLM-cited content validated against the web, no internal doc row — vs. Filler d's *every* chunk), and responded with:

- **`url` field, RESOLVED via Chat:** `url: str | None`, not `source_url` — see the contract-gap resolution above. Filler c relayed this to me first; I don't need to re-ask Chat separately.
- **Synthetic id scheme:** Filler c adopted my `"ext:" + sha1(url)[:16]` for their one affected status, rather than inventing a second convention. One scheme across both fillers now.
- **`assignment_reason` vocabulary — Filler c pushed back on forcing a shared enum, and their reasoning is right:** `"external_fetch"` (mine) and `"llm_retrieved"`/`"llm_partial_match"` (theirs) carry genuinely different meaning that a forced-common string would lose. Agreed approach instead: each filler documents its own value set in one shared reference location (`fillers-schematic-spec.md` or an appendix) so Router/Synthesis has one place to look instead of reverse-engineering per-filler strings — not a unified enum. Adopting `"external_fetch"` as Filler d's value, documented rather than homogenized.
- Filler c independently found the same `model_registry.py` bandit infra (for their `rag_strategy_c_validate` stage) and asked me to make sure Eval sees my `RoutingLadder`-is-the-one-strategy-bandit finding too, so Eval reasons about the full picture rather than two partial ones — already covered, since Eval's confirmation (above) came from directly reviewing this doc's open questions, not a secondhand relay.

Per standing guidance (direct-connect peer sessions): coordinated directly, looping in Retriever/Eval only for the parts that were actually cross-cutting decisions (the bandit-stage-moot-for-v1 question above still needs that same direct-confirmation treatment, not an assumption).

---

## Port, don't import — new directive (Ananth, 2026-07-23)

**Do not add a live `from app.services.corpus_search_strategy_d import ...` dependency in Filler d's code.** Read the legacy file as reference material — same as before — but re-implement each piece into Filler d's own module(s), verifying it fresh as it's ported rather than copy-pasting and assuming correctness. Same fleet-wide reasoning Filler c got for their equivalent directive: don't silently inherit an old file's latent bugs, and don't create a dependency on a file that could change or get deleted out from under this module later.

Concretely, the pieces to port (not the ones already cut in the drop-synthesis decision above):

- `_search_web_vertex()` — Vertex AI Grounding-with-Google-Search call, the primary search path.
- `_search_web()` — the mobius-skills/DuckDuckGo fallback, used only when Vertex grounding returns nothing.
- `_fetch_and_extract()` — per-URL fetch with timeout, HTML section extraction (`html_extractor.extract_sections`), and the PDF branch (PyMuPDF page-text extraction) — this PDF handling exists because DuckDuckGo's top hit was once a real authoritative PDF the plain HTML extractor mangled into binary garbage; worth re-verifying that failure mode still reproduces before assuming the fix is still needed as written.
- Query-enrichment helpers: `build_authoritative_query()`, `_embed_search_operators()`, `_rerank_hits()`. These carry real, hard-won calibration history (documented inline in the legacy file — e.g. the `_WEB_QUOTE_SELECTIVITY_MIN = 0.95` threshold, derived from a real distribution analysis over 1,612 tags) that's worth preserving, not just the code shape.
- **`_extract_payer_slug()`/`_resolve_payer_context()` — UPDATED (Retriever ruling, round 4): NOT ported into Filler d's own module.** Payer-context resolution is needed identically by the fillers that live-search (this one, plus the LLM-retrieval and sitemap-lookup fillers), so Retriever ruled it becomes **one shared utility**, `app/services/retriever/fillers/payer_context.py`, not separate re-derivations per filler. The Sitemap filler (session "4d - Sitemap" — **correction, 2026-07-23: NOT "Filler f"; that was Retriever's own mislabeling, caught by that session itself — Router's real, unbuilt strategy `"f"` is a completely separate, scored external-fallback thing**) characterized it first (verified against `corpus_search_strategy_d.py:138-142`/`188-264`) and built it since I hadn't started (still blocked on the `url` field). Filler d imports from that shared file once it lands, rather than porting its own copy — this is the one piece of "port, don't import" that's actually "import, don't port," because the thing being imported is fleet-shared infra, not a single legacy file with unknown-quality latent bugs. `_lookup_sitemap_candidates()` also moves out of scope entirely — that's the Sitemap filler's own job, not something Filler d needs.

**Explicitly NOT ported:** `_synthesize()` and the `_SYNTHESIS_SYSTEM` prompt — cut per the drop-synthesis decision above, not carried into the new module at all.

**Process implication:** this is real re-implementation work, not a thin adapter — each ported piece gets its own verification pass (unit test against real behavior, not just "it looks like the original") before being trusted, per the fleet's verify-before-trust discipline.

---

## Open design questions

1. ✅ **Fork point** — RESOLVED (Retriever): per-slot-on-rung-d, orchestrator-triggered, live.
2. **`url` contract gap** — RESOLVED in name/shape (`url: str | None`, Chat), **still pending DB actually landing it in `contracts.py`.** Blocks writing any `FilledChunk`-constructing code.
3. ✅ **`original_score` for external chunks** — RESOLVED: constant `1.0` for `fetch_status == "ok"` chunks, relying on Observer's percentile-within-pool normalization to make the scale meaningless (same pattern Eval gave Filler c).
4. ✅ **Drop `_synthesize()` in v1** — RESOLVED (Eval): confirmed safe, `confidence_label` has zero downstream references in the new chain. Legacy-consumer footnote added for whoever cuts over later.
5. ✅ **Bandit scope (strategy-selection)** — RESOLVED (Eval): no within-filler bandit; Router's `RoutingLadder` is the one strategy-selection bandit layer.
6. ✅ **`chunk_id`/`document_id` synthetic scheme** — RESOLVED: `"ext:" + sha1(url)[:16]`, adopted by Filler c too for their equivalent case.
7. ✅ **Bandit *model-selection* stage moot for v1** — RESOLVED (Eval, independently re-verified in code): `rag_strategy_d_external` maps only to the dropped `_synthesize()` call; zero bandit-registered calls remain in Filler d v1. Filler c cross-checked and confirmed their own case doesn't generalize the same way (their LLM call generates content, mine only narrated over already-complete content).

## What's explicitly NOT being decided in this doc

No code has been written yet. This doc surfaces the fork points and decisions that came from reading the real prior art directly and from cross-agent responses — it isn't a substitute for the actual cross-agent sign-off Fillers' parent spec requires (Chat/Eval/DB/TECH), same as every other module in this fleet.

## Next steps

1. ~~Send coordination message to Filler c session.~~ Done — round 1 resolved (see Coordination section).
2. ~~Surface open questions 1-5 to Retriever for routing to the right owners.~~ Done — all but the `url`-field landing and the new bandit-moot question (#7) came back resolved.
3. ~~Get explicit confirmation on open question #7 (bandit-stage-moot) from Eval/Filler c.~~ Done — confirmed by Eval, cross-checked by Filler c.
4. **Only remaining blocker:** DB landing the `url` field in `contracts.py` (open question #2). Once that lands, start porting the legacy pieces listed in "Port, don't import" into Filler d's own module(s), verifying each piece fresh as it's ported.
5. Unit tests + characterization test, then a real calibration run with a real artifact (per the fleet's standing artifact-validation requirement) before any Eval sign-off claim.
