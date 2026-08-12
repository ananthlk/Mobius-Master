# Filler c — LLM Retrieval — Kickoff Spec (Step 3c) — v1

**Status:** BUILT, v1, 2026-07-23 — `filler_c.py` + `test_filler_c.py` (23/23 unit tests passing), wired into `orchestrator.py`'s `_IMPLEMENTED_FILLERS`. Independently re-verified by Retriever (not just self-reported): re-ran the test suite (matched, no discrepancy) and the full retriever suite (157 passed/2 skipped at that point), plus their own independent live-call runs (real DB, real LLM, ~8.3s avg across 3 queries, same LLM-dominated/truncation-risk shape as my own numbers). Two of my own real end-to-end runs against this environment's real DB + real LLM (dev-fallback path, see below): 18.3s (1 chunk retrieved, `retrieved` status) and 14.4s (0 chunks — real JSON truncation at `max_tokens=2048`, see "Known v1 risk" below, not a code bug).

**Real gap caught by Retriever's independent re-verification, fixed 2026-07-23:** DB landed `contracts.py`'s `url`/`document_id` changes (`document_id: str | None`, new `url: str | None`, docstring stating internal-vs-external chunks are mutually exclusive on those two fields) while this module's `_chunk_from_citation` was still using the pre-landing workaround (`document_id=""`, `url` omitted entirely) — passed all 22 unit tests at the time because none of them asserted on `url`/`document_id`'s new convention, so it was a real silent gap, not a test failure. Fixed: `document_id=None` (not `""`) for `retrieved_external`, `url=v.discovered_source_url` populated for that case, `page_number` now a real field instead of buried in `tags`. Two new tests added asserting the corrected convention; 23/23 passing, 162 passed across the full retriever suite (up from 157, reflecting the new tests).

Cross-agent sign-off (Chat/Eval/DB/TECH per Fillers' parent spec) still pending before this is "done" — design-level sign-off from Chat/Eval is in, DB's remaining three questions (Pool dedup, content_sha, document_status lookup) are still open.

**Grounding-integrity fix, 2026-07-23 (Eval-verified):** found via a live call that `_retrieve_in_doc_by_query` could accept a topically-wrong-but-non-empty BM25 hit and silently claim `status=retrieved`. Fixed with `_quote_present()` — verify the fetched chunk actually contains the LLM's cited quote before accepting `retrieved`; downgrade to `doc_found_section_missing` otherwise. Traced the specific repro case to ground truth via real SQL: the LLM had hallucinated the section name and quote (real doc/page, fabricated specifics — confirmed zero `plainto_tsquery` hits on the exact quote anywhere in the corpus). Eval independently verified the fix (code + isolated test run) and confirmed real.

**Open question, Eval-owned, NOT resolved (2026-07-23):** `doc_found_section_missing`/`original_score=0.5` currently conflates two genuinely different failure modes wearing the same status: (a) the LLM's citation was accurate but our corpus indexing just didn't have that exact page (partial evidence, our gap), vs (b) the LLM hallucinated the section/quote entirely (zero corpus evidence, its fabrication). Eval's read: these should not share one confidence bucket — (b) should score lower than (a), likely a distinct status (e.g. `quote_unverifiable`) — but this needs the fact-check/honesty-critic system to formalize properly, not a unilateral patch inside Filler c. **Not implemented pending that design.** Separately, whether "LLM cites title/page with zero quote at all" is common enough to need its own handling is an open empirical question — needs real telemetry once enough live citations have flowed, not a guess.

**Fleet-hygiene note, NOT a Filler c issue (Eval, 2026-07-23):** the "167 passed fleet-wide" number I reported (from Retriever's re-verification) does not hold under Eval's own re-run — `test_filler_d.py::TestFillShapeExternal` shows 3-4 intermittent failures when run as part of the full suite (passes in isolation), consistent with test pollution/shared state leakage between modules, not a functional regression. Eval flagged this directly to Filler d's session and Retriever for fleet-test hygiene — explicitly not something to fold into this doc's own sign-off status, noted here only so this doc doesn't imply a stronger "fleet-wide green" claim than currently holds.

**Known v1 risk, found during testing, not hidden:** `_ask_llm`'s `max_tokens=2048` (same value as the legacy code) can truncate the LLM's JSON output mid-citation for queries producing 3+ citations with a verbose answer — verified directly (raw response inspected, ends mid-string). Truncated JSON fails to parse → `parse_error=True`, zero citations, `under_filled=True` for that slot. This is an inherited legacy limitation, not a regression introduced here. Not fixing unilaterally (raising max_tokens trades cost/latency, worth Eval's input) — flagging for cross-agent awareness before sign-off.

**Superseded status line below (kept for history):** DRAFT — design doc, no code written yet. Drafted by Filler-c session, grounded in real prior-art code (not a summary), per Retriever's handoff.
**Owner:** Filler-c session (new, forked off Retriever 2026-07-23).
**Companions:** `fillers-schematic-spec.md` (parent contract, Step 3), `app/services/corpus_search_strategy_c.py` (legacy prior art, 1139 lines, mobius-rag), `app/services/retriever/fillers/contracts.py` (`FilledChunk`/`FilledSlot`/`FilledShape`), `app/services/retriever/fillers/filler_a.py` (shipped pattern for output shape).

Ananth's framing, verbatim: *"as simple as send the question/slots to an LLM through a bandit (we can vary models here), retrieve as facts and citations — not narrative — so that we can include these the same way as the rest of them, include the same confidence etc."*

It is **not** actually simple — the two real design problems are (1) reshaping legacy prose+citations into the `FilledChunk` contract, and (2) the model-selection bandit turns out to already exist, one layer removed, which changes the question from "build a bandit" to "how does Filler c's own module talk to it."

**Directive from Ananth (2026-07-23):** the legacy citation-location/confidence logic below is reference material to port, not a dependency to import. Filler c gets its own module with the location chain, dataclasses, and confidence mapping re-implemented and verified fresh — no live `from app.services.corpus_search_strategy_c import ...` in Filler c's code. Same fleet-wide reasoning as everywhere else: don't inherit an old file's latent bugs silently, and don't create a dependency on a file that could change or get deleted out from under Filler c later. The bandit (`model_registry.py`) is a different case — see below.

---

## Why Filler c is not like Filler a/b

Fillers a (BM25) and b (Vector) are **pure, read-only, zero-I/O functions over `PoolResult`** — pool candidates already exist; the filler just ranks and assigns them to slots. Filler c is fundamentally different:

- It makes a **live LLM call** (`_ask_llm`, real network I/O, ~seconds of latency) and, in the worst case, a **live web fetch** (Google search + scrape, via strategy (d)'s infra, when a citation isn't in-corpus).
- It does **not primarily consume `PoolResult` candidates** — it generates its own answer+citations from scratch by asking the LLM the query, then validates those citations against the corpus (and optionally the web).
- It is asynchronous and non-deterministic (same query can return different LLM output run to run) — breaks the "deterministic same-input-same-output" constraint the fillers spec states for a/b.

This means Seam α (Pool → Fillers input) does not apply to Filler c the same way, and the "zero DB/embed side effects" constraint in `fillers-schematic-spec.md` §Constraints does not hold for Filler c either. **Open question #4 below** covers whether Filler c should still cross-reference Pool for dedup.

## What already exists (prior art — port into Filler c's own module, don't import)

`app/services/corpus_search_strategy_c.py` (mobius-rag) already implements the full pipeline. This is reference material for Filler c's re-implementation, not a library Filler c calls into — read it, verify it, then write Filler c's own version of the pieces it needs:

- `_ask_llm(query, *, correlation_id) -> (answer_text, parsed_json, llm_telemetry)` — sends a fixed system prompt instructing the LLM to answer in ≤3 sentences and emit strict JSON: `{"answer": str, "citations": [{"document_title", "page", "section", "url", "quote"}]}`. Calls out via `llm_manager_client.generate(system=..., user=query, stage="rag_strategy_c_validate", max_tokens=2048, correlation_id=...)`.
- Citation location chain, `_locate_citation()`: **by title** (token overlap ≥0.65, cross-payer safeguard) → **by URL** (exact match against `documents`/`discovered_sources`) → **by quote** (Postgres full-text search + literal substring ground-truth check) → **by Google** (external web validation via strategy (d)'s `_search_web`/`_fetch_and_extract`, token-overlap ≥0.40 fallback for paraphrase tolerance).
- Real dataclasses:
  ```python
  @dataclass
  class CitationCandidate:
      document_title: str | None = None
      page: int | None = None
      section: str | None = None
      url: str | None = None
      quote: str | None = None

  @dataclass
  class ValidatedCitation:
      candidate: CitationCandidate
      status: str  # "retrieved" | "retrieved_external" | "doc_found_section_missing"
                   # | "doc_in_sitemap_not_ingested" | "doc_robots_blocked" | "doc_not_found"
      document_id: str | None = None
      document_display_name: str | None = None
      document_filename: str | None = None
      matched_chunk_text: str | None = None
      matched_page: int | None = None
      discovered_source_url: str | None = None
      last_fetch_status: int | None = None
      locate_method: str = ""
      notes: str = ""

  @dataclass
  class StrategyCResult:
      llm_answer: str
      citations: list[ValidatedCitation] = field(default_factory=list)
      raw_llm_output: str = ""
      telemetry: dict[str, Any] = field(default_factory=dict)
  ```
  **Correction to the handoff note:** the module docstring's outcome matrix (`validated_correct`/`validated_hallucinated`/`unverified_robots`/`needs_scrape`/`needs_external`/`located_unverified`) is **stale** — the actual `status` values produced by the code today are the six listed above (`retrieved`, `retrieved_external`, `doc_found_section_missing`, `doc_in_sitemap_not_ingested`, `doc_robots_blocked`, `doc_not_found`). Build against the real code, not the docstring.
- A confidence mapping **already implemented** in `corpus_search_agent.py` (lines ~4509–4539), reused verbatim for Filler c (see Reshaping Design below):
  - `high` — any citation is `retrieved` or `retrieved_external`.
  - `medium` — only `doc_found_section_missing` or `doc_in_sitemap_not_ingested`.
  - `low` — only `doc_robots_blocked` or `doc_not_found`.
- A **chunk-reshaping precedent** — `corpus_search_agent.py` already builds `CorpusChunk` dicts from `matched_chunk_text` for citations with status in `(retrieved, retrieved_external, doc_found_section_missing)`, tagging `source_type` as `"external_validated"` (web) or `"llm_hinted_retrieval"` (corpus) and `confidence_label` high/medium. Filler c's `FilledChunk` reshaping (below) is the same idea, targeting the fillers contract instead of the chat planner's contract.

## Reshaping Design: `ValidatedCitation` → `FilledChunk`

This is the core design work the handoff called out. Proposed mapping, one `FilledChunk` per citation with usable text:

| `FilledChunk` field | Source | Notes |
|---|---|---|
| `chunk_id` | For in-corpus citations (`retrieved`/`doc_found_section_missing`/`doc_in_sitemap_not_ingested`): synthesize from the real `document_id`, e.g. `f"llm-{document_id}-{matched_page}-{hash(matched_chunk_text)[:8]}"`. For `retrieved_external` (no doc row): adopt Filler d's URL-hash scheme, `"ext:" + sha1(url)[:16]`, for consistency across fillers rather than inventing a second convention. | **flag to Chat**: does grounding/vault_sources identity need a real chunk_id, or is empty acceptable for LLM-hinted chunks? |
| `document_id` | `v.document_id` | Direct passthrough for in-corpus citations. `None` for `retrieved_external` (web citations have no internal doc row) — same asymmetry Filler d hit for *all* its chunks (it never has a real `document_id`); Filler c only hits it for the `retrieved_external` status. Need a sentinel or `document_id: str` typing relaxation on the contract either way — coordinate with Filler d so both fillers hit the same resolution, not two. |
| `url` | `v.discovered_source_url` for `retrieved_external`; `v.candidate.url` if the LLM supplied one for an in-corpus citation. | ✅ **RESOLVED (Chat, 2026-07-23):** add `url: str \| None` to `FilledChunk` — named `url`, not `source_url`, matching Chat's existing `SourceRef.url` convention (`integrate.py:196/710/374`) so no rename/mapping step is needed when translating `FilledChunk` → `SourceRef`. Shared resolution with Filler d (same field covers their per-passage URL case). |
| `text` | `v.matched_chunk_text` | Only citations with non-null `matched_chunk_text` become chunks at all — same skip behavior as `corpus_search_agent.py` today. |
| `document_status` | *(new lookup)* | Not populated by strategy_c today; needs a `documents.status` lookup if Filler c is to honor Product-Awareness reality-gating like other fillers. |
| `content_sha` | *(new)* | Not computed by strategy_c; compute if dedup/provenance parity with a/b is required — open question #6. |
| `source_type` | Derived from `v.status`: `retrieved`/`doc_found_section_missing` → `"llm_hinted_retrieval"`; `retrieved_external` → `"external_validated"` | Matches existing precedent in `corpus_search_agent.py`. |
| `tags` | *(new)* — `{}` by default, or stash `locate_method`/`notes`/`matched_page` here for diagnostics | Fillers a/b populate this from Pool's tags; Filler c has no Pool tags to pass through. |
| `is_neighbor` | Always `False` | Filler c never derives neighbors. |
| `original_score` | *(new)* — categorical `status` has no numeric score | Need a status→score mapping for Router parity with a/b's numeric ranking — open question #5. |
| `assignment_reason` | `v.locate_method` (e.g., `"title"`/`"url"`/`"quote"`/`"google"`) or the `status` itself | Recommend `status` value directly (e.g., `"llm_retrieved"`, `"llm_partial_match"`) since that's what downstream confidence logic keys off. |

**Citations that produce NO `FilledChunk`:** `doc_robots_blocked` and `doc_not_found` (no `matched_chunk_text`) — same as today's `CorpusChunk` behavior. These still count toward `under_filled`/diagnostic telemetry but contribute zero chunks.

**Where does `llm_answer` (the narrative prose) go? — RESOLVED (Chat, 2026-07-23, verified against code):** diagnostic-only, in `FilledShape.emit.fillers_c.llm_answer`, never consumed by Router/Synthesis. Chat confirmed `llm_answer` is read in exactly one place fleet-wide — `corpus_search.py:631`, inside the legacy strategy "s" (fact store) fast-exit block, gated on `strategy_used == "s"` / `method == "fact_store"`. Strategy c never triggers that path, so nothing today reads Filler c's `llm_answer`. **Asymmetry noted for whoever eventually builds Filler s:** unlike c, strategy s's `llm_answer` IS actively consumed by Chat — not diagnostic-only for that filler. Not Filler c's problem, but worth the fleet remembering before assuming this pattern generalizes.

**Reshaping field questions — RESOLVED (Chat, 2026-07-23, verified against code):**
- Empty/synthesized `chunk_id` is fine — Chat's grounding badge derives from `source_type`, citation pills index by position in `sources[]`, and `vault_sources[]` only covers `instant_rag` sources, never `retrieved_external`. No consumer needs a real `chunk_id`.
- `document_id=None` for `retrieved_external` is safe — `integrate.py:188/702` reads it via `s.get("document_id")` with no required-field assertion; `None` passes through cleanly, and there's nothing to deep-link to for external citations anyway.
- Action item, not Chat's to fix: `FilledChunk.document_id` needs its type relaxed to `str | None` at the contract level (DB owns `contracts.py`) before Filler c builds against it — confirm this lands before writing code.

## Bandit-Based Model Selection — corrected understanding

The handoff's ask was "vary models via a bandit" as if this needs building from scratch. It doesn't, fully — **an LLM-selection bandit already exists**, one service away:

- `mobius-chat/app/services/model_registry.py` — `ModelRouter.select(stage, ...)` (line ~1417) runs **Thompson sampling** over a `BanditState` (Beta distribution, `np.random.beta(alpha, beta)`), blending each model's benchmark prior (`ModelSpec.beta_prior`) with observed quality/reliability/latency/cost stats (¼ weight each by default). Includes circuit breakers, forced exploration every 20 calls/stage, and live-health degradation detection.
- The stage `"rag_strategy_c_validate"` (which `_ask_llm` already uses) is **already in this router's roster** (`RAG_ROUTED_STAGES`) — but **only `gemini-2.5-pro` and `gemini-2.5-flash` compete for it today** (comment: Vertex-only because "extraction/synthesis prompts carry multi-page chunks → need the 1M-context models" — Filler c's prompt is short, so that constraint may not actually apply here). Confirmed real by Retriever/Ananth (2026-07-23) — this genuinely is a working bandit, not an aspirational comment.

**Verified, but this is a *different kind* of reuse question than the location-chain logic above.** `model_registry.py` lives in **mobius-chat**, a separate service/repo — this is real, shared, cross-service infrastructure other RAG stages (including `rag_strategy_d_external`, which Filler d will also need) already depend on, not a same-repo legacy file with latent bugs to avoid inheriting. So the "port, don't import" directive does **not** apply here.

**RESOLVED (Eval, 2026-07-23, verified against code):**

1. **Integration pattern:** call the existing bandit as-is, widen the roster. `ModelRouter` picks *which model* executes a stage; Router's own bandit picks *which strategy* (a/b/c/d/s/f) to use — orthogonal axes. Building a second model-selection bandit inside Filler c would be duplicate infrastructure competing with itself. Widening `eligible_stages` for `rag_strategy_c_validate` (if the short prompt really doesn't need 1M-context) is an engineering call for whoever owns that roster in mobius-chat, not a policy question.

2. **Reward signal plumbing — bigger finding, fleet-wide, not Filler-c-specific:** Eval grepped mobius-rag for `update_ema`/`quality_score` — **zero hits, anywhere.** None of the four `rag_strategy_*` stages (a_synth, b_synth, c_validate, d_external) feed quality back to the bandit today — all run on priors/latency/cost only. There is no existing pattern to extend, and building bespoke cross-repo plumbing (mobius-rag calling `update_ema` directly) just for Filler c would be solving a fleet-wide gap with a one-off wire across a service boundary that should go through a real integration point instead.
   **Decision for Filler c v1:** record citation-validation outcome (`n_retrieved`/`n_total`, per-citation status) as RAG-side telemetry only, using the existing persistence discipline (`rag_query_decisions`-style, same pattern Router already uses). Treat "does this feed mobius-chat's bandit" as a separate, larger cross-repo integration question affecting all four `rag_strategy_*` stages — flagged to Retriever as a fleet-wide follow-up, not something Filler c blocks its build on.

3. **`original_score` mapping — RESOLVED with a real constraint, not a free choice:** the categorical scale (retrieved→1.0/retrieved_external→0.9/doc_found_section_missing→0.5/others→no chunk) is fine *in principle*, but only if it feeds the same **percentile-within-pool normalization** Router/Observer already rely on (`observer-bayesian-confidence-spec.md` §6c, locked 2026-07-23: `s = min(1, #{chunks : pool_percentile(chunk.original_score) >= 0.8} / capacity)`). Raw absolute scores are **not** comparable across strategies — this exact trap already got caught once (BM25 unbounded vs. vector cosine [0,1]) — so Filler c's `original_score` must never be compared as a raw number anywhere downstream, only through percentile normalization. Since Filler c's values will cluster at a few fixed points (lots of ties at 1.0 for "retrieved"), expect them to land at extreme percentiles within a c-heavy pool — that's expected behavior of percentile normalization, not a bug. **Do not** artificially spread the categorical values out to avoid ties.

## Async / Live-Call Handling in the Filler/Router Loop

Fillers a/b are synchronous, pure functions. Filler c is an `async def` making a real network call (LLM + possible Google fetch). Three things need resolving before code, not after:

1. **Fan-out cost:** if multiple slots (e.g., several `thematic_exploration` slots from FAN_OUT) each have `"c"` in their `RoutingLadder.strategy_sequence`, does Filler c get invoked once per slot (N real LLM calls) or once per distinct `rewritten_query` (dedup across slots sharing the same query text)? Recommend dedup by query text — re-asking the LLM the identical question per slot is pure waste.
2. **Timeout/failure fallthrough:** strategy (c) can fail (LLM error, timeout, Google fetch failure). Router's ladder is presumably built to fall through to the next strategy in `strategy_sequence` on failure — confirm this is already true for the orchestrator loop, since a/b never had a failure mode to design for.
3. **Orchestrator interface:** does the Router/Fillers calling convention already support an async filler function, or do a/b's synchronous signatures mean the orchestrator needs a signature change to await Filler c? Check before assuming.

## Emit Contract Extension

The parent `emit.fillers` shape (`slots_filled`/`empty_slots`/`under_filled`/`over_filled`/`total_overflow`/`filling_strategy`/`filling_ms`/`per_slot_details`) has no room for LLM-specific telemetry. Extend with an `emit.fillers_c` block, modeled on `corpus_search_strategy_c.py`'s existing telemetry + `corpus_search_agent.py`'s `outcome_counts`:

```
emit.fillers_c:
  llm_ms: int
  validate_ms: int
  model_used: string          # llm_telemetry["llm_meta"]["model"] — see Model Attribution below, thread through, don't discard
  llm_call_id: string         # llm_telemetry["llm_meta"]["llm_call_id"] — join key for eventual reward-update against mobius-chat's llm_calls table
  outcome_counts: {retrieved, doc_found_section_missing, doc_in_sitemap_not_ingested, doc_robots_blocked, doc_not_found}
  parse_error: bool           # from strategy_c's best-effort JSON parse
  llm_answer: string          # diagnostic-only, see Reshaping Design above — never consumed downstream
```

**Model attribution — checked, not assumed (Retriever/Ananth flagged this as a real requirement 2026-07-23):** whoever eventually fires a bandit reward update (Eval's offline calibration, or Chat's live path) needs to know exactly which `(stage, model)` arm to credit, not just the stage — since `ModelRouter` does Thompson sampling, a *different* model can get picked per call even for the same stage. Traced the actual return path rather than assuming: `_ask_llm`'s `llm_telemetry["llm_meta"]` already **is** the `usage` dict `llm_manager_client.generate()` returns, which is `llm_manager.generate()`'s `out_usage` in mobius-chat (`llm_manager.py:247-254`) — confirmed it already sets `out_usage["model"] = model_id` and `out_usage["llm_call_id"] = str(record["call_id"])`, plus latency/provider/stage/router-selection-reason fields. **No gap in `llm_manager_client` itself** — the model id and a real join key already survive all the way to `_ask_llm`'s return value today. The actual risk is Filler c's own reshaping code discarding `llm_meta` when it builds `FilledChunk`/`emit` (since `ValidatedCitation` itself carries none of this — it's a sibling field on `StrategyCResult.telemetry`, not per-citation). Action: thread `llm_telemetry["llm_meta"]["model"]` and `["llm_call_id"]` into `emit.fillers_c` from day one, per the table above.

## Resolved Design Questions

1. ✅ **`chunk_id`** — empty/synthesized is fine, no consumer needs a real one (Chat, verified against `integrate.py`/`vault_sources` logic).
2. ✅ **`document_id=None` for `retrieved_external`** — safe, passes through cleanly; contract's `str` type needs relaxing to `str | None` before build (Chat, DB to action).
3. ✅ **`llm_answer` diagnostic-only** — confirmed genuinely unread by anything for strategy c (Chat, verified against `corpus_search.py:631`).
4. ✅ **Bandit integration pattern** — call the existing mobius-chat bandit as-is, widen `eligible_stages`; no rag-side bandit (Eval, verified against `model_registry.py`).
5. ✅ **Reward signal plumbing (v1)** — RAG-side telemetry only (`rag_query_decisions`-style), no bespoke cross-repo `update_ema` wiring; cross-repo feedback is a fleet-wide follow-up affecting all 4 `rag_strategy_*` stages, not a Filler-c-blocking decision (Eval).
6. ✅ **`original_score` mapping** — categorical scale (retrieved→1.0/retrieved_external→0.9/doc_found_section_missing→0.5) is fine, but MUST flow through Pool's percentile-within-pool normalization (`observer-bayesian-confidence-spec.md` §6c) — never compared as a raw number. Expected clustering at extreme percentiles for a c-heavy pool is correct behavior, not a bug (Eval).
7. ✅ **`FilledSlot.required`** — landed in `contracts.py` (2026-07-23, Eval finding: Synthesis needs required-slot-underfilled="gap" vs optional-slot-underfilled="expected" distinguished, per `AnswerSlot.required`). Verified in code: Filler a already threads `required=slot.required` when building `FilledSlot`; **Filler b does not yet** — flagged directly to that session as a live break (missing required, no-default dataclass field → `TypeError` on any `fill_shape_vector` call). For Filler c: thread `slot.required` the same way when constructing `FilledSlot`, from day one.

## Open Design Questions (still need sign-off input)

1. **Pool cross-reference** — should Filler c check `PoolResult.candidates` for the same `document_id` to avoid Router seeing the same document proposed twice (once via Pool→a/b, once via Filler c), or is duplication acceptable/handled downstream by Router's ranking? (DB — asked, awaiting response)
2. **`content_sha`** — worth computing for dedup/provenance, or skip since Filler c's chunks aren't pool-sourced and dedup may not matter the same way? (DB — asked, awaiting response)
3. **`document_status` lookup** — confirm `documents.status` lookup is the right source for Product-Awareness reality-gating passthrough. (DB — asked, awaiting response)
4. ✅ **`url` contract gap** — RESOLVED (Chat, 2026-07-23): add `url: str | None` to `FilledChunk` (named `url`, matching Chat's `SourceRef.url` convention, not `source_url`). Shared resolution with Filler d. Still needs DB (contract owner) to actually land the field in `contracts.py`.

## Fleet-Wide Follow-Up (flagged to Retriever, not Filler-c's to own)

Eval's grep found **zero** `update_ema`/`quality_score` wiring anywhere in mobius-rag — none of the four `rag_strategy_*` LLM stages (a_synth, b_synth, c_validate, d_external) feed task-outcome quality back to mobius-chat's bandit today. This is a real gap across the whole fleet, not specific to Filler c, and deserves a dedicated owner/task rather than being solved piecemeal per-filler. Surfacing to Retriever to route.

## Coordination with Filler d (Web Search)

Filler d hit the same three problems independently, from the outside (external passages, not corpus citations): (1) `FilledChunk` has no URL field, but the URL *is* the citation for their (and Filler c's `retrieved_external`) content; (2) no real `document_id` exists for non-corpus content, needing a synthetic id; (3) `assignment_reason` values will diverge per-filler with no shared vocabulary.

Resolution, coordinated directly rather than each independently escalating:
- **URL field**: RESOLVED by Chat — `url: str | None` on `FilledChunk`, not `source_url` (matches Chat's existing `SourceRef.url` convention, no rename step needed downstream). Relayed to Filler d.
- **Synthetic id scheme**: adopting Filler d's `"ext:" + sha1(url)[:16]` for Filler c's `retrieved_external` case (no real doc row), rather than inventing a second convention. Filler c's other statuses have a real `document_id` from the location chain, so this only applies to the one status.
- **`assignment_reason` vocabulary**: proposing we *don't* force identical strings across fillers — `"external_fetch"` (d) and `"llm_retrieved"`/`"llm_partial_match"` (c) carry genuinely different meaning worth preserving — but both fillers should document their full value set in one place (`fillers-schematic-spec.md` or a shared appendix) so Router/Synthesis has one reference instead of reverse-engineering each filler's strings.

## What's explicitly OUT of scope for this kickoff

- Redesigning the locate/validate algorithm itself (title/URL/quote/Google chain, thresholds) — port the logic as verified, don't redesign it; this spec only covers the *output reshaping* and *model-selection integration* layers on top.
- Rebuilding strategy (d)'s Google-fetch infra, or the bandit itself in `model_registry.py` — both already exist as real, tested, shared infrastructure; Filler c calls into them, doesn't duplicate them.
- Router's ranking/ordering of Filler c's chunks alongside a/b's — Router's problem, once chunks are in `FilledChunk` shape.

## Process

1. Resolve open questions #1–7 above with Retriever, Eval, Chat, DB before writing code (per fleet's verify-before-trust discipline — a filler's calibration report was fabricated once already this session and caught).
2. Build `filler_c.py`: port the location-chain/dataclasses/confidence-mapping logic from `corpus_search_strategy_c.py` into Filler c's own module (verified fresh, not imported), plus the reshaping layer above. The LLM call and bandit selection still go through the existing `llm_manager_client` → mobius-chat HTTP path — that part is called, not ported (see Bandit section).
3. Test: unit tests on the reshaping function (pure, given a fixed `StrategyCResult`, deterministic `FilledShape` output) + integration test against a real `strategy_c_llm_validate` call (non-deterministic, characterization-style) + eval-bank angle once Eval weighs in on bandit reward design.
4. Track in `filler-c-llm-tracker.md` (per handoff instruction).
5. Cross-agent sign-off: Chat, Eval, DB, TECH — same as every prior module.
6. Report back to Retriever once the open questions are resolved and a real (not self-reported) calibration run exists.
