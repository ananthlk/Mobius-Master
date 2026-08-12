# SHAPE Reformat — Simulation & Sign-Off Tracker

**STATUS 2026-07-23: 6/6 packages fully signed off (UX, Chat, Eval, DB, plus Retriever+Shape-Gate structural sign-offs). TECH engaged by Retriever — last gate before CLOSED, same as Gate's precedent.**

## RESOLVED — thinking_trace wiring conflict (2026-07-23)

Retriever's cross-module registry caught it, UX ruled: **both narrate() outputs feed `thinking_trace`, but posture-conditional** — FAN_OUT/RELY_ON_EXTERNAL/CLARIFY combine Gate's + Reformat's narration (Reformat adds real new information for these); PRECISE/DECLINE/CLARIFY_REPHRASE use Gate's narration alone (Reformat's would be redundant — nothing new to say once Gate's already precise/declined/unclear). Implemented in `orchestrator.py` (Retriever, commit `28b98d0`), verified live. No changes needed to `reformat_narrate.py`/`reformat.py` — only how the orchestrator composes the two outputs. Was blocking Structure (Step 1c); no longer blocking.

**Purpose:** track real simulated end-to-end outputs (not abstract spec review) against the actual `reformat.py` output, with per-agent sign-off status and telemetry per test case. Mirrors `shape-gate-simulation-tracker.md`'s pattern — kept current in real time (Gate's tracker went stale once and TECH caught it; don't repeat that here).

**Method (once `reformat.py` exists):** each test case runs the real `run_reformat(gate_result)` against the live DB (prevalence probes), producing the actual `ReformatResult` + trace. Agents review the REAL OUTPUT, not the design doc, and sign off per case.

---

## Status: BUILT + TESTED, 2 known blockers before sign-off (2026-07-23)

`reformat.py` exists (`mobius-rag/app/services/retriever/shape/reformat.py`), runnable end-to-end against live Gate output. Ran the full `queries_reformat_postures.yaml` bank (13 cases) via `scripts/run_reformat_on_postures_bank.py`: **12/13 fully matched** (gate contour + posture). The one mismatch is a bank-authoring gap, not a Reformat bug — see below.

## Test cases run — REAL, live Gate + Reformat, 2026-07-23

| ID | Query | Live gate contour | Live posture | Expected posture | Result |
|---|---|---|---|---|---|
| reformat001 | "How do I confirm eligibility for Medicaid" | exact | precise | precise | PASS |
| reformat002 | "What's the process to resubmit a denied claim with Molina" | exact | precise | precise | PASS |
| reformat003 | "Eligibility for Medicaid" | underspecified/explore_siblings | fan_out (3 themes+catchall) | fan_out | PASS |
| reformat004 | "Behavioral health services for Medicaid" | exact | precise | precise | PASS |
| **reformat005** | "How do I get hospice services" | underspecified/**missing_jurisdiction** | **clarify** | fan_out | **FAIL — bank assumption wrong, not a code bug (see below)** |
| reformat006 | "What's the process to resubmit a denied claim" | underspecified/missing_jurisdiction | clarify | clarify | PASS |
| reformat007 | "What documentation is required to enroll a new pediatric patient" | underspecified/missing_domain | clarify | clarify | PASS |
| reformat008 | "What is the prior authorization process in Clarendon, AR" | vicinity | rely_on_external | rely_on_external | PASS |
| reformat009 | "What are the drug counselor requirements for Sunshine Health" | vicinity | rely_on_external | rely_on_external | PASS |
| reformat010 | "What is our policy on gifts and business courtesies" | corpus_gap | rely_on_external | rely_on_external | PASS |
| reformat011 | "What's the weather forecast for tomorrow?" | out_of_scope | decline | decline | PASS |
| reformat012 | "Does my auto insurance cover a rental car?" | out_of_scope | decline | decline | PASS |
| reformat013 | "asdkfjqwoeiru" | unclear | clarify_rephrase (tentative) | clarify_rephrase | PASS |

**reformat005 root cause, verified live:** the bank assumed D would match the bare `health_care_services` umbrella (631+ siblings) for "hospice services," triggering `explore_siblings`. Live Gate instead resolves D directly to the specific leaf `d:health_care_services.hospice` — the lexicon phrase "hospice" is specific enough to match a leaf, not the parent. With D resolved and J empty, the real (correct) contour is `underspecified/missing_jurisdiction`, and Reformat's `clarify` output is the right behavior for that real result. **This is a bank-authoring correction needed on Eval's side, not a Reformat defect** — reported to Eval below.

**FAN_OUT theme quality (reformat003, "Eligibility for Medicaid," 80 real siblings):**
- Clustering: k-means (spherical, cosine similarity) — **replaced average-linkage agglomerative after it failed live** (78/80 codes collapsed into one cluster, a known chaining failure mode on same-domain text embeddings). k-means gives a real, balanced split: 31/32/17 members across 3 themes, semantically distinct (enrollment-status, income, age-range).
- Themes produced: "newly enrolled non-participants" (n=31, 3307 docs), "gross income for eligibility" (n=32, 1487 docs), "individuals aged 10-18" (n=17, 154 docs), + 1 catch-all (not corpus-derived).

**Latency — 3 of 3 known bottlenecks addressed (2026-07-23), see caveat below:**
- PRECISE/CLARIFY/RELY_ON_EXTERNAL/DECLINE: 10ms–1.5s (DB-only, no embedding calls) — fine.
- FAN_OUT: was ~18.8s (reformat003). Three independent bottlenecks found and fixed:
  1. **Prevalence-count seq scan — FIXED.** OR-chain of `d_tags ? :code` (up to 32 codes) was a genuine 3735-4557ms Seq Scan (independently reproduced by Retriever). Replaced with ONE `UNION ALL` of single-key GIN lookups + Python set-union (exact semantics, not sum). ~903ms-1.06s for 80 codes.
  2. **Embedding model — improved but not the real fix.** Swapped from `gemini-embedding-001` (1 input/call, forced) to `text-embedding-004` (batchable). ~9.2s for 81 texts at that point.
  3. **Embedding BATCH SIZE — FIXED, the actual big lever.** The shared `app/services/embedding_provider.py`'s `_vertex_embed()` hard-codes `batch_size=5` for any non-gemini model — turns out NOT a real API limit, just an overly conservative default (discovered by testing directly against Vertex, not assumed). Confirmed live: 81 texts at batch_size=5 = 5.28s/17 calls; ONE call of all 81 = 1.37s. Real API ceiling tested directly: **250 instances per prediction** (confirmed via the actual `InvalidArgument` error at 294). Reformat now calls Vertex directly (bypasses the shared abstraction's hard-coded 5, doesn't touch/risk the shared corpus-ingestion embedding path), chunking at the real 250-instance ceiling — 1 call for domains ≤250 codes, 2 calls for the largest seen live (health_care_services, 293).

  **CORRECTION (Retriever's independent re-verification caught this, 2026-07-23): the earlier "n=5/n=7, median ~11.67-12.15s" numbers reported in this section minutes earlier were NOT warm-state variance — they were ALL cold-start.** `scripts/run_reformat_on_postures_bank.py` launches a fresh Python process every invocation, so every bank-runner-based sample (mine and Retriever's) was independently paying the cold-start cost. This was a real mischaracterization, not just a stale number — corrected here, not just noted.

  **Two real regimes, now measured properly (same-process loops, not bank-runner):**
  - **Warm** (`reformat_ms`, steady-state within one long-lived process): mine — n=7, 2277/2379/2409/2422/2549/2591/2629ms, median 2422ms. Retriever's independent — n=2 (after discarding their own cold call), 4143ms and 3885ms. **These don't tightly match (2.4s vs ~4s) — flagging honestly rather than calling it "same ballpark" and moving on.** Plausible causes not yet isolated: network/environment variance between our two sessions, DB-proxy-adjacent variance (documented elsewhere as a real, recurring source of noise in this dev environment), or something structurally different between the two test harnesses. Not resolved — don't treat either number as final.
  - **Cold** (first call in a fresh process): mine — one observation, 7538ms. Retriever's independent — two observations, 10398ms and 14398ms. **Range ~7.5-14.4s across 3 independent cold observations, real and recurring per Cloud Run instance spin-up, not a one-time artifact.**

  **Batch-size fix is still real and still large** (removed ~80 items' worth of embedding payload from every FAN_OUT call, warm or cold) — just don't cite the old "~11.67s → ~2.4s, 4.8x" framing, since that compared cold-start-mislabeled-as-warm against genuinely-warm. The honest comparison is cold-vs-cold (pre-fix ~18.8s vs post-fix ~7.5-14.4s) and warm-vs-warm (post-fix only, ~2.4-4s, no pre-fix warm baseline exists since the fix changed the code before warm-state was ever cleanly isolated).

  **Caching re-scoped, NOT dropped (Ananth, 2026-07-23): no longer a shipping blocker (batch-fix already gets warm-state to shippable), but still the correct long-term architecture** — reduces the redundant re-embedding of static lexicon-code text on every query, keeps latency domain-size-independent, reduces hot-path dependency on an external API. **Cold-start nuance (Retriever raised, worth stating precisely, not overclaiming): caching removes the 80-sibling-code payload from the cold-start path too, so it should help cold-start, not just warm — but the query itself still needs ONE live embed call regardless of caching, and if the Vertex auth handshake (not payload size) is what actually dominates cold-start — a real, unverified possibility already flagged to DB — caching would reduce cold-start, not eliminate it.** Don't let "caching fixes cold-start" become an assumed fact before it's measured.

**Test coverage — CLOSED 2026-07-23.** `tests/test_shape_reformat.py`: 30 tests (dispatch pure-unit, cosine/clustering/union-prevalence math, narration helpers, DB-integration). 28/30 pass as a full batch; the 2 "failures" are the same pytest-asyncio event-loop/connection-pool-scoping flakiness `test_shape_gate.py`'s memory already documents (confirmed order-dependent — whichever test runs right after the FAN_OUT case fails; every test passes individually). Documented in the test file's class docstring, not chased further, same judgment call Gate's build made.

## TRACKED FOLLOW-UP — lexicon-embeddings caching (Ananth, 2026-07-23)

**DB's decision:** caching bundled with the Curation refactor, no separate standalone effort. **No ETA given yet.** Both Shape-Reformat and Retriever are to track this and revisit when that refactor actually happens — not a fire-and-forget ask.

**Two things flagged back to DB, not yet resolved, don't harden into planning assumptions:**
1. DB claimed `reformat.py` already has "a placeholder for lexicon_embeddings JOINs" — checked, **false**, no such placeholder exists anywhere in the file. The UNION ALL prevalence pattern is real; the embeddings-cache lookup will be genuinely new code when the cache lands, not "add the lookup" to existing scaffolding.
2. DB's cold-start projection (7.5s → 3.5-4s after caching) assumes the ~7.5s is dominated by embedding-payload size (81 items), when it may actually be dominated by the Vertex auth-handshake itself (a likely fixed cost independent of batch size) — the single query-embedding call still needed live even after caching sibling codes would still pay most of that fixed cost. Untested extrapolation, not a measurement. Re-test once the cache actually exists before trusting these numbers for monitoring thresholds.

**When the Curation refactor lands:** revisit this section, re-run the latency comparison for real (not projected), and update the numbers above.

**CRUX DECISION, answered 2026-07-23 (Curation asked, blocks the cache table's model/dimension choice):** FAN_OUT compares BOTH code-vs-code (clustering, `reformat.py:195`) AND code-vs-query (`_cosine(query_vec, centroid)`, `reformat.py:207`) — so cached code embeddings and the live query embedding MUST share one embedding space. This does NOT have to be the corpus model (`gemini-embedding-001` @ 1536) — FAN_OUT never compares against corpus chunks, only against the query and other codes. Recommended: pin the cache to `text-embedding-004` (batchable, 250/call), and Reformat's live query-embedding call matches it exactly. **Real risk if this isn't coordinated as one explicit decision: a model mismatch between the cache and the live query embed would silently produce garbage `lexicon_proximity` scores — no error, no crash, just wrong ranking.**

**RESOLVED 2026-07-23 — Curation confirmed:** model = `text-embedding-004`, dim = **768** (confirmed live from the actual `_embed_for_clustering()` function, not assumed — plain native default, no `output_dimensionality` override). Curation's safety design, better than what either of us proposed alone: the cache table's `embedding_model` column is a **read-time fail-closed guard** — assert `cache.embedding_model == query-embedding model` before computing cosine similarity, error or live-embed-fallback on mismatch, never silently compute garbage. A future model change is a **coordinated breaking change**, not something either side flips unilaterally — model-keyed PK allows old+new to coexist during a transition. Curation relaying model+dim to DB to correct the cache table spec (`vector(768)`, not 1536) and folding into the refresh mini-contract (TECH gates it, builds in the code-move window). No changes needed on Reformat's side — stays pinned to text-embedding-004/768 until a coordinated change happens.

---

## Per-agent sign-off status

| Agent | Package sent | Reviewed real output? | Sign-off | Notes |
|---|---|---|---|---|
| UX | Emit/telemetry schema for `ReformatResult` | N/A — design review, no code to run yet | ✅ **Signed off 2026-07-23** | Emit key `shape_reformat` (mirrors `shape_gate`). Backend/Diagnostics only, not a Chat surface field. Recommended `reformat_posture` + `reformat_fanout_n` graduate to lean scalar columns on `rag_query_decisions` (mirrors `gate_contour`) — added to DB's package. Full detail in `shape-reformat-schematic-spec.md` §8. |
| Chat | FAN_OUT visible UI state question | N/A — design review | ✅ **Signed off 2026-07-23** | FAN_OUT gets a transient SSE status (`phase:"fan_out"`, "Exploring a few angles..."), auto-clears on `draft_ready`. Delayed-emit (~2000ms, arm-if-still-pending), not eager-emit-with-suppress. **Handoff RESOLVED by Retriever 2026-07-23: owner is Pool (Step 2)** — Pool dispatches the N parallel searches for `rewritten_queries[]` and is the only component that sees real per-branch completion timing, so the 2000ms delayed-emit decision lives there, not in Reformat or a new orchestration layer. Logged as an open item for whoever builds Pool next. |
| **Eval** | **Co-author `queries_reformat_postures.yaml` + N/(w_p, w_l) guidance** | **Yes — 13/13 cases run live 2026-07-23, 12 PASS** | **✅ DESIGN SIGNED, 1 bank correction requested** | reformat005 needs updating: bank assumed D matches the bare `health_care_services` umbrella for "hospice services," live Gate resolves it to the specific leaf `health_care_services.hospice` instead — real contour is `missing_jurisdiction`, not `explore_siblings`. Either fix the test case's expected values or swap in a different FAN_OUT example. Proposed weights (w_p=0.4, w_l=0.6) used as-is in the live run, not yet re-tuned against real theme scores. |
| DB | Gate-(i) query pattern + Gate-(f) schema (nullable columns, timing, ONE-WRITER deferral) | Yes — independently verified against real artifacts (EXPLAIN ANALYZE, live schema check, re-ran timing) | ✅ **FULLY SIGNED OFF 2026-07-23** | **FINAL: APPROVED.** Gate-(i) SAFE (663ms/80 codes, zero seq-scan). Gate-(f) fully closed: schema sound, timing instrumented+verified (`segment_ms`, 8140/8145ms), ONE-WRITER coordinated with Router (DB committing to no DDL until Router's ready to wire read+write together in one pass, will verify combined DDL then). **Shape-Reformat ready for TECH review per DB.** |
| Curation | On call for lexicon gaps — **channel confirmed 2026-07-23** | — | — | File gaps to **Lexicon agent (`local_dbf9f2eb`)**, not Curation directly — same intake Gate used. Lexicon is under a clean-tree FREEZE: gaps filed now are captured/queued immediately, but the leaf-mining/retag that fixes them lands POST-BASELINE (after Eval pins the refactor baseline), batched into one sequenced pass with Gate's 2 existing gaps — not per-gap turnaround. Curation flagged a real connection: my unbounded-fanout domains (eligibility=80, health_care_services=631) are literally "split broad tags into finer leaves" — exactly what their tag-selectivity/leaf-mining loop already owns. My prevalence/lexicon-proximity ranking findings are candidate fuel for that backlog once I have real data. |
| TECH | Final structural sign-off | No | ⏳ Pending | Announced 2026-07-23 — expect 2-round independent re-run per Gate's precedent |

---

## Telemetry tracking (running log — append per test round)

| Date | Test round | Cases run | reformat_ms range | Bugs found | Fixed? | Notes |
|---|---|---|---|---|---|---|
| 2026-07-23 | live + eval bank | 13/13 | 10ms–18.8s | 1 bank correction (reformat005: live Gate resolves "hospice" to leaf, not umbrella) | N/A (bank issue, not code) | 12 PASS. **CRITICAL: FAN_OUT latency ~18.8s (embed-on-fly not viable); cache req'd** |

---

---

## §3 Bounding analysis: N=3 for large fanout sets (80+ siblings)

**⚠ Correction (2026-07-23, after this analysis was written):** Ananth ruled that fan-out ranks THEMES (vector-clustered groups of fanout_codes), not raw individual codes — "no more than 3-4 question angles at any point." Everywhere below that says "code" for the ranking unit should be read as "theme" (a cluster of codes); N=3/N=4 as a count of themes still holds, the analysis logic (prevalence vs. lexicon_proximity tradeoffs, graceful degradation, empirical tuning approach) carries over unchanged, just one level up. Full detail: `shape-reformat-schematic-spec.md` §3.

**Question from Shape-Reformat:** "For cases like eligibility's 80 siblings, is top-3 too narrow? How would we know?"

**Answer (EVAL analysis, 2026-07-23):**

### Hypothesis: N=3 is a deliberate *exploration constraint*, not a bug

The goal of FAN_OUT is to offer user-meaningful alternatives without exploding Pool cost. From module-gates.md §1, Pool must stay <5s per-query; FAN_OUT forces N parallel Pool calls. If N=3, that's 3× Pool latency (plus routing overhead). If N=10, that's 10×. The N=3 default is not random; it's bounded exploration.

### Real-world tuning surface: 4 cases that matter

1. **Rare + low-doc codes get buried by prevalence** (query signal is ignored)
   - Example: "Medicaid eligibility for pregnant applicants" lands on a general "eligibility" contour.
   - Fanout_codes include both "eligibility.pregnancy" (rarely mentioned, maybe 50 docs) and "eligibility.income" (always mentioned, 2000 docs).
   - Pure prevalence (w_p=1.0): income ranks top, pregnancy never seen. User needs pregnancy answer, frustration.
   - Hybrid (w_p=0.4, w_l=0.6): "pregnant" token matches lexicon entry for eligibility.pregnancy, boosts score despite low prevalence.
   - **Measure:** does top-3 include eligibility.pregnancy? If not, raise w_l or lower w_p. Acceptable if it lands top-3 or top-4 and user can see alternatives.

2. **Generic services absorb all fanout for huge umbrellas** (query is too broad to constrain)
   - Example: Query "behavioral health services" but it's genuinely ambiguous (could be mental health, substance abuse, crisis intervention, peer support, etc.).
   - Fanout_codes = 50+ health_care_services subcategories.
   - N=3 picks behavioral_health, telehealth, pharmacy (by prevalence + lexicon).
   - But there are 47 other legitimate answers; is top-3 enough?
   - **Empirical measure:** if users asking "behavioral health" consistently pick options outside top-3, raise N to 4–5. If they pick from top-3 or say "none of these", N=3 is correct (umbrella is just too broad, not fixable by more options).
   - **Proposal:** ship N=3, measure via downstream user behavior (picking, bouncing back, escalating). Don't guess.

3. **Lexicon_proximity gives wrong signal when query has generic domain terms**
   - Example: Query "eligibility" (bare noun, no hints). All 80 siblings have equal lexicon_proximity=0.
   - Ranking falls back to pure prevalence: eligibility.income, eligibility.aged, eligibility.categorical (always mentioned).
   - But user might mean something rare like eligibility.immigrant_status.
   - **Result:** N=3 can never help here because the query *is* genuinely ambiguous. That's when posture=CLARIFY should fire, not FAN_OUT.
   - **Check:** Gate should classify bare "eligibility" as underspecified→explore_siblings only if there are some hints (e.g., "eligibility requirements for disabled applicants" has "disabled" hint). Bare "eligibility" alone should be underspecified→missing_jurisdiction or missing_domain, triggering CLARIFY instead of FAN_OUT.
   - If that's not happening, the issue is in Gate, not Reformat's N.

4. **Graceful degradation when fanout_codes < N**
   - Example: Query matches only 2 sibling codes.
   - Reformat should return top-2 (not pad with empties), posture still FAN_OUT.
   - **Implement:** N is a ceiling, not a floor. Top-min(N, len(fanout_codes)).

### Recommendation for build phase

- **Start with N=3, w_p=0.4, w_l=0.6** (proposed defaults in eval bank).
- **Run all 13 test cases in queries_reformat_postures.yaml** against live corpus once reformat.py exists.
- **For test case reformat003 (eligibility, 80 siblings):** inspect the top-3 ranking. If you see an obvious gap (e.g., "pregnancy" is missing but corpus has pregnancy docs), note it and adjust weights.
- **Log downstream metrics:** once Shape feeds into Pool feeds into answers, track whether users ask follow-up clarifications on FAN_OUT results. If N=3 is too narrow, they'll say "none of these help" more often.
- **Gate on empirical signal, not intuition.** If Gate+Reformat together produce good top-3 exploration 80%+ of the time (measured via feedback), N=3 is right. If <60%, consider N=4 or adding a "show more options" escalation.

### UNCLEAR handling (tentative, pending Ananth)

Test case reformat013 ("asdkfjqwoeiru") proposes CLARIFY_REPHRASE posture. This is a **placeholder pending Ananth's decision.**
- Option A (proposed): CLARIFY_REPHRASE → emit a generic "could you rephrase?" prompt, escalate to user clarification.
- Option B: DECLINE → hard boundary, same as OUT_OF_SCOPE. Cleaner, but less helpful.
- **Awaiting Ananth's judgment** on whether UNCLEAR should get a clarification attempt or just fail closed.

---

**Design update (2026-07-23):** Ananth corrected the FAN_OUT mechanism from "top-N individual codes" to "embed + cluster codes into themes, rank themes, one query per theme." This avoids redundant near-duplicate queries for large fanoust (e.g., eligibility.aged + eligibility.blind both in "disability-related" theme → one query, not two). **Eval bank updated:** test cases reformat003/reformat005 now describe theme-level ranking instead of per-code ranking. Scoring formula (w_p, w_l) stays the same, applies at theme level. Tuning questions updated to reflect theme validation (clustering quality, theme-level ranking).

**Open design items carried from schematic spec §6** (resolved or in-flight): 
- ✅ Theme clustering + tuning guidance drafted; empirical validation after build
- ✅ Eval bank (queries_reformat_postures.yaml) co-authored + revised for theme-level design
- ⏳ UNCLEAR→CLARIFY_REPHRASE default unconfirmed by Ananth
- ⏳ Theme clustering mechanism (k-means vs. similarity-threshold) TBD in reformat.py build
- ⏳ `lexicon_proximity` aggregation at theme level (sum? representative?) TBD in reformat.py

**Next:** build `reformat.py` once UX/Chat/Eval/DB packages land (or in parallel where independent), same discipline as Gate — real DB verification at every step. **Key difference from Gate:** Shape-Reformat must also produce theme clusters (embedding + clustering step), not just scoring. DB should note this new infrastructure ask (embedding lookup for fanout_codes' lexicon_entries phrases).
**UX/Chat/DB:** expected to receive updated packages for independent review; Eval ready on design + scoring guidance.
