# SHAPE / Reformat — Architecture Schematic + Build Spec (Step 1b) — v1

**Status:** DESIGN LOCKED by Shape-Reformat agent, circulating for cross-agent sign-off (same process Shape Gate used). No production code written yet — `reformat.py` is next, after packages below land.
**Owner:** Shape-Reformat Agent (session "4b - Shape:Reformat"), reporting to Retriever.
**Companions:** `shape-reformat-module-spec.md` (original kickoff draft, superseded by this doc for design content) · `project_shape_reformat_agent.md` (memory) · `shape-gate-module-spec.md` + `shape-gate-simulation-tracker.md` (sibling precedent, same process) · `module-sequence.md` (macro 7-module schematic this sits inside, at Step 1 of "shape").

---

## 1. Where Reformat sits (internal schematic)

```
GateResult (from Shape Gate, DONE — contour, d/j/p_codes, probe, fanout_codes[unbounded])
    ↓
┌─ REFORMAT (this module)
│
│  contour == EXACT
│    → posture PRECISE → rewritten_queries = [normalized query]   (pass-through)
│
│  contour == UNDERSPECIFIED, underspecified_kind == explore_siblings
│    → posture FAN_OUT
│      1. embed each fanout_code's lexicon phrases, cluster by vector similarity → themes
│      2. score each theme:  score = w_p·prevalence_norm(theme) + w_l·lexicon_proximity(theme)
│      3. rank descending, take top themes, HARD CAP 4 (MAX_FANOUT_THEMES, target 3)
│      4. rewritten_queries[] = one per selected theme (NOT one per raw code — §3 revision 2026-07-23)
│
│  contour == UNDERSPECIFIED, underspecified_kind in {missing_domain, missing_jurisdiction}
│    → posture CLARIFY
│      surface plausible options (from sibling J/D candidates seen in similar queries),
│      not a blind "which state?"
│
│  contour in {VICINITY, CORPUS_GAP}
│    → posture RELY_ON_EXTERNAL
│      pass-through to Router strategy c/d, external_reason records WHY
│      (vicinity=partial coverage exists / corpus_gap=none exists), no internal query forced
│
│  contour == OUT_OF_SCOPE
│    → posture DECLINE, no fallback
│
│  contour == UNCLEAR
│    → posture CLARIFY_REPHRASE (⚠ not yet confirmed by Ananth — default proposal, see §6)
│
│  ↓
└─ ReformatResult { posture, rewritten_queries[], fanout_ranked[], clarify_questions[],
                    external_reason, decline_reason, reason, reformat_ms }
    ↓
STRUCTURE (Step 1c, next) → POOL (Step 2)
```

## 2. Posture table (LOCKED by Ananth 2026-07-22 — build against this, don't re-derive)

| Gate contour | Reformat posture | Behavior |
|---|---|---|
| `EXACT` | `PRECISE` | One strict query, pass through, minimal work |
| `UNDERSPECIFIED` / `explore_siblings` | `FAN_OUT` | Bounded, ranked fan-out — §3 |
| `UNDERSPECIFIED` / `missing_domain` \| `missing_jurisdiction` | `CLARIFY` | Suggested questions, not a blind ask |
| `VICINITY` | `RELY_ON_EXTERNAL` | Router strategy c/d; partial coverage exists |
| `CORPUS_GAP` | `RELY_ON_EXTERNAL` | Router strategy c/d; zero coverage exists |
| `OUT_OF_SCOPE` | `DECLINE` | Hard boundary, no fallback |
| `UNCLEAR` | `CLARIFY_REPHRASE` | **Proposed default, not yet signed off** — see §6 |

## 3. Design decision — the bounding/ranking function

**REVISED 2026-07-23 by Ananth — supersedes the v1 decision below.** Direct correction: *"we cannot have 80 .. we will use vectors etc to find some themes .. no more than 3-4 question angles at any point."* Raw per-code fan-out (even ranked top-N over individual `fanout_codes`) is the wrong unit — 80 siblings for "eligibility" shouldn't become 3 arbitrary *codes*, they should collapse into 3-4 *themes*.

**Adopted: vector-based theme clustering, capped at `MAX_FANOUT_THEMES = 4`.**

1. Embed each `fanout_code`'s `policy_lexicon_entries` phrases (same embedding pipeline as `rag_published_embeddings` — no new model to stand up).
2. Cluster by vector similarity into a small number of themes (mechanism — k-means vs. similarity-threshold agglomeration — is a build-time decision, not fixed in this spec; either must produce ≤4 clusters by construction, not by post-hoc truncation).
3. Rank themes (not raw codes) by the same hybrid intuition as before — `score = w_p · prevalence_norm(theme) + w_l · lexicon_proximity(theme, query_tokens)`, prevalence/proximity now computed at the theme level (summed/representative across member codes).
4. Take top themes descending, hard-capped at **4**, target **3** typical (Eval's proposed starting point, still tunable) — one rewritten query per theme.
5. Same graceful-degradation rule as before: if the query has no lexicon-proximity signal at all, ranking falls back to pure theme prevalence.

**`FanoutCandidate` (per-code scoring) still exists in `contracts.py` but is now an intermediate/pre-clustering unit** — `FanoutTheme.member_codes` references the codes folded into it; individual candidates are no longer emitted as rewritten queries directly. `ReformatResult.fanout_themes: list[FanoutTheme]` replaces the earlier `fanout_ranked: list[FanoutCandidate]` field.

**Why themes, not codes:** the earlier "hybrid, no clustering" decision (kept below for the record) optimized *which codes* to search, but never questioned whether individual codes were the right *granularity* to fan out over. For a domain like eligibility, three individual sibling codes (e.g. `eligibility.aged`, `eligibility.blind`, `eligibility.disability`) may all be facets of the same real user question angle ("disability-related eligibility") — fanning out 3 near-duplicate codes wastes Pool's N× cost on redundant queries instead of covering 3 *actually distinct* angles.

**Consequence for already-landed work:** Eval's `queries_reformat_postures.yaml` (landed 2026-07-23) was authored against the pre-clustering per-code design — `expected_rewritten_query_count: 3` for FAN_OUT cases still holds (themes still cap at 3-4), but `reformat003`'s framing ("Reformat scores each code ... ranks descending, takes top-3") needs a pass to reflect clustering into themes rather than raw code ranking. Flagging to Eval directly, not silently reinterpreting their bank.

<details>
<summary>Superseded v1 decision (kept for the record, not the design to build against)</summary>

Four candidates were on the table (`shape-reformat-module-spec.md` §4): top-K by prevalence, top-K by lexicon proximity, aspect clustering, hybrid. Original decision was **hybrid, no clustering in v1** — `score(sibling_code) = w_p · prevalence_norm(sibling_code) + w_l · lexicon_proximity(sibling_code, query_tokens)`, top-N over individual codes, aspect clustering explicitly rejected as "real complexity for unproven benefit." Ananth's 2026-07-23 correction reverses the clustering call — see above.
</details>

## 4. Output contract — `ReformatResult` (drafted, see `contracts.py` addition)

```python
class ReformatPosture(str, Enum):
    PRECISE = "precise"
    FAN_OUT = "fan_out"
    CLARIFY = "clarify"
    RELY_ON_EXTERNAL = "rely_on_external"
    DECLINE = "decline"
    CLARIFY_REPHRASE = "clarify_rephrase"   # UNCLEAR passthrough, tentative

@dataclass
class FanoutCandidate:
    code: str
    prevalence_docs: int
    prevalence_norm: float
    lexicon_proximity: float
    score: float

@dataclass
class ReformatResult:
    query: str
    posture: ReformatPosture
    rewritten_queries: list[str]            # what Pool actually runs
    fanout_ranked: list[FanoutCandidate]     # full ranked list, top-N is what's in rewritten_queries
    clarify_questions: list[str]             # CLARIFY posture only
    external_reason: str | None              # RELY_ON_EXTERNAL posture only (vicinity vs corpus_gap)
    decline_reason: str | None                # DECLINE posture only
    reason: str                               # human-readable trace string
    reformat_ms: int
```

Mirrors `GateResult`'s style deliberately (same dataclass conventions, same "reason" trace-string pattern, same `_ms` timing field per `module-gates.md`/`timing` cross-cut requirement).

## 4b. Literal-entity expansion — RESOLVED OUT OF SCOPE, moved to Gate (2026-07-23)

Originally scoped here as a PRECISE-path stub (query has a literal HCPCS/ICD/CPT code or org name, lexicon doesn't decode it, pass-through misses docs phrased differently). **Placement question raised to Retriever + Shape-Gate; Retriever verified live and resolved it: the HCPCS/ICD half of this is a Gate correctness bug, not a Reformat optimization, and belongs in Gate.**

**Why it's Gate's, verified live, not reasoned about abstractly:**
- `"Does Sunshine Health cover H0019 for Medicaid patients?"` → `UNDERSPECIFIED/missing_domain`, `d_codes=[]` entirely. The lexicon has zero mechanism to recognize a literal code as domain evidence, so a code-bearing query can get contour'd wrong (dead end, not even explorable) before Reformat ever sees it. Reformat can't rescue a contour Gate already got wrong — this has to be fixed upstream of classification.
- `"Is ICD-10 F10.10 covered under Florida Medicaid?"` → happened to land `EXACT` only because surrounding phrasing matched `d:billing_codes.diagnosis_code` by luck, not code recognition. A bare code wouldn't.
- **No reopening of Gate's locked sign-off required**: `_classify()` operates purely on already-matched d/j/p codes, never the raw query. The fix is a **pre-processing stage before `expand_query_via_lexicon()`**: detect a literal code, decode it (HCPCS via `mobius-dbt/seeds/fl_bh_code_reference.csv`, ICD-10 via `mobius-skills/healthcare/app/clients/icd10.py`, both verified live), feed the decoded text into the same existing lexicon pipeline. `_classify`'s branches/33 tests/6 sign-offs untouched — additive increment to Gate, its own scoped sign-off round, not a re-litigation.
- **CPT**: still no translation anywhere in the fleet (AMA-licensed, unlike public-domain ICD-10/HCPCS) — gap persists regardless of which module ends up owning code-decode.

**What stays with Reformat:** org-name resolution (`_resolve_payor()` in `mobius-payor/app/skills.py`, j-tag-anchored alias resolution, call via payor RPC) — this was never a Gate-classification-correctness issue (org names largely already resolve via J-tags), so it stays a genuine Reformat-side stub, not moved.

**Shape-Gate independently confirmed, live, 2026-07-23** (not just agreeing with Retriever's read): "What do you know about H0019?" → `OUT_OF_SCOPE` (wrongly declines an in-scope question). Bare "H0019" alone → `UNCLEAR`. "Does Sunshine Health cover H0019?" → `UNDERSPECIFIED/missing_domain` — J resolves, D stays empty because the code itself carries zero lexicon signal. Confirmed the pre-`_classify` decode step is additive as scoped (doesn't touch `_classify`, `_is_general_only_match`, `_detect_process_intent`, `_is_malformed`), with one implementation note for whoever builds it: **don't decode-and-replace the query text that flows into `GateResult.query`/`.normalized`** — those feed `narrate_full()`'s "You asked: ..." line, and echoing the decoded phrase back would be worse UX than the user's own words. Cleanest shape: a separate "expansion text" input (raw query + decoded phrase) used only for lexicon matching, original query stays what's displayed. Gate plans a lightweight TECH heads-up before landing this (not a full 2-round re-signoff, but not silent either).

**Action:** dropped from Reformat's build list entirely for the HCPCS/ICD piece. Gate's own agent picks this up as a new work item when ready — not tracked here beyond this note.

## 5. What's explicitly OUT of scope

Unchanged from kickoff spec: Gate's classification logic (locked), Pool's search/BM25/vector logic, Structure's downstream-contract emission (Step 1c, after Reformat), `_run_with_kofn_cascade` (Pool-side, older mechanism, not to be confused with this fan-out).

## 6. Open items requiring resolution before final sign-off

1. **UNCLEAR contour handling** — proposed `CLARIFY_REPHRASE` default (§2) is not yet confirmed by Ananth; flagging explicitly rather than silently building against an assumption.
2. **N default (3) and weights (w_p, w_l)** — proposed starting values, Eval owns final tuning against the new eval bank (package below).
3. **`lexicon_proximity` scoring function** — token/phrase overlap is the v1 approach; exact implementation (Jaccard vs weighted phrase match) still to be written into `reformat.py`, not blocking this spec's sign-off.

## 7. Cross-agent work packages (this kickoff's ask — mirrors Gate's spec §8)

| Agent | Package | Artifact | Contract back to Shape-Reformat |
|---|---|---|---|
| **UX** | Emit/telemetry schema for `ReformatResult` (new emit key — check for collisions with `shape_gate`, same discipline Gate used) | Emit schema spec | ✅ **Signed off 2026-07-23** — see §8 |
| **Chat** | Does `FAN_OUT` need a visible "exploring options" UI state now that it's real (not Gate's placeholder)? Chat previously deferred this exact question pending Reformat existing | Integration requirements note | ✅ **Signed off 2026-07-23** — see §8 |
| **Eval** | Co-author `queries_reformat_*.yaml` eval bank (mirror `queries_gate_contours.yaml` pattern) covering PRECISE/FAN_OUT/CLARIFY/RELY_ON_EXTERNAL/DECLINE; own final N and (w_p, w_l) tuning | Eval bank + scoring criteria + tuned params | ⏳ Pending |
| **DB** | Sign off on: (1) per-sibling-code doc-count probe for `prevalence_norm` (live `document_tags`, GIN-indexed — same table Gate already probes), now aggregated per theme; (2) **NEW 2026-07-23 per Ananth's clustering correction (§3): embedding lookup pattern for `fanout_codes`' lexicon phrases** — confirm whether `policy_lexicon_entries` phrases already have embeddings to reuse or a new embed-on-the-fly step is needed, and the cost of that at up to ~80 codes per query. **Also carrying UX's recommended `rag_query_decisions` column addition (§8).** | DB sign-off | ⏳ Pending — scope grew 2026-07-23, DB should be aware before reviewing |
| **Curation** | On call only if a new lexicon gap surfaces during build (as happened twice with Gate) | — | — |
| **TECH** | Final structural sign-off, same 2-round rigor as Gate (independent re-run, not report-only) | Sign-off record | ⏳ Pending |

## 8. UX + Chat sign-off decisions (landed 2026-07-23)

**UX — emit key: `shape_reformat`.** Mirrors `shape_gate`'s namespacing, no collisions found. `ReformatResult` fields are backend/Diagnostics instrumentation, not part of the Chat surface contract or the 9 surface-bound fields.

**UX's open question, resolved:** mirrors Gate's §4 pattern exactly (`gate-emit-schema-spec.md` §4) — `reformat_posture` is strategy-relevant (it decides the downstream path the same way `gate_contour` does), so it graduates to a **lean scalar column on `rag_query_decisions`** (plus `reformat_fanout_n`, the count of rewritten queries when posture is FAN_OUT — useful for eval slicing "show me all fan-out queries with N≥3"). The full `ReformatResult` object goes into `rag_query_traces.full_response.shape_reformat` (JSONB, no migration needed there). This is a DB-owned migration — added to DB's work package above, not UX's.

**Chat — FAN_OUT gets a transient status, with conditions.** Emit one SSE status event (`{type:"status", text:"Exploring a few angles...", phase:"fan_out"}`) on the existing `/internal/progress/{cid}` channel; Chat renders it above the streaming draft and auto-clears it on `draft_ready`. No per-branch status noise. Chat asked Shape-Reformat to own the "don't flash it for blink-length gaps" decision.

**Resolved as delayed-emit, not eager-emit-with-suppress:** rather than emitting immediately and trying to retract a flashed status, the emitter should hold the event for ~2000ms from fan-out dispatch and only send it if Pool hasn't returned by then (standard spinner-delay pattern — nothing to un-send). **Handoff RESOLVED by Retriever, 2026-07-23: owner is Pool (Step 2).** Pool is the component that dispatches the N parallel searches for `rewritten_queries[]` and is the only one with real per-branch completion timing — that's the vantage point the 2000ms decision needs. Reformat's contract stays clean: `ReformatResult.posture == FAN_OUT` plus `len(rewritten_queries)` is all downstream needs. Logged by Retriever as an open item for whoever builds Pool next.

---

**Process from here (repeat exactly what Gate did):** packages above → build `reformat.py` with live-DB verification → unit + DB-integration tests + eval bank → sign-offs land in `shape-reformat-simulation-tracker.md` (kept current in real time) → commit incrementally → report back to Retriever once TECH signs off.
