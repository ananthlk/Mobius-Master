# SHAPE / Reformat Module Spec (Step 1b) — v1

**Status:** DRAFT — kickoff artifact only. No code written yet. Prepared by Retriever (acting as Shape's manager) for handoff to a forked session/sub-agent, following the exact process Shape Gate (Step 1a) used.
**Owner:** to be assigned (a new sub-agent under Retriever, e.g. "Shape-Reformat Agent" — mirrors how "Shape-Gate Agent" was named).
**Scope of this spec:** Reformat only — takes a `GateResult` (already built, tested, signed off) and decides HOW to translate it into what Pool will search. Does not touch Gate's classification logic (locked), does not do Pool's actual corpus search (Step 2, separate module), does not do Structure (Step 1c, the final downstream-contract emitter — comes after Reformat).

---

## 1. Where Reformat sits in the chain

```
Query → SHAPE [ Gate (DONE) → Reformat (THIS MODULE) → Structure (next) ] → POOL → ROUTER → FILLERS → SYNTHESIS → CONTRACT → TIMING
```

Gate already answers "can/should we answer, and what posture?" (6 contours). Reformat answers **"how do we translate this into the best query/queries to actually run?"** — the piece the original design doc calls "the tricky piece."

## 2. Input — what Reformat receives

The full `GateResult` from Shape Gate (already built): `contour`, `d_codes`/`j_codes`/`p_codes`, `probe` (union/intersection counts), `process_intent`, `missing_kinds`, `underspecified_kind`, **`fanout_codes`** (populated only when `underspecified_kind == "explore_siblings"` — currently unbounded, e.g. 80 for eligibility, 631 for health_care_services), `reason`, `expectation()` (label + text).

**Reformat's job starts exactly where Gate's stops:** Gate enumerates *what could be explored* (`fanout_codes`); Reformat decides *what actually gets explored* (bounded, ranked) and *how* (one query vs. a fan-out set).

## 3. Core design questions (from the original meet-old plan, §1b — re-read before building)

Per `retriever-meet-old-plan.md` §1b, three postures based on tag-completeness — **REFINED by Ananth 2026-07-22 with explicit per-contour routing, including when to fall back to external sources (Google/LLM = strategies c/d in the Router's 7-strategy set):**

| Gate contour | Reformat posture | Behavior |
|---|---|---|
| **EXACT** | **PRECISE** | One strict query — pass through, minimal work. Agreed as-is. |
| **UNDERSPECIFIED (explore_siblings)** | **FAN-OUT** | Bounded, ranked fan-out across candidate facets → `rewritten_queries[]`. Agreed as-is — this is Reformat's core new logic (§4 below). |
| **UNDERSPECIFIED (missing_domain / missing_jurisdiction)** | **CLARIFY, with suggested questions** | NOT a blind "please clarify" — proactively suggest the likely clarifying question(s) (e.g. "did you mean Florida or Texas Medicaid?" rather than "which state?"). Gate already knows what's missing (`underspecified_kind`); Reformat should surface plausible options if any exist (e.g. from J-code candidates seen in similar queries), not just name the gap. |
| **VICINITY** | **RELY ON EXTERNAL** | Internal docs exist in the area but don't cover the exact combination — route to external (strategy c/d: LLM synthesis or Google) rather than force an internal answer from partial coverage. |
| **CORPUS_GAP** | **RELY ON EXTERNAL** | Tags matched (we know what's being asked), but zero internal documents cover it — same external fallback as VICINITY, for a different reason (VICINITY = partial coverage exists but doesn't align; CORPUS_GAP = no coverage exists at all). |
| **OUT_OF_SCOPE** | **DON'T ANSWER** | Decline. Not this corpus's domain — no external fallback attempted, this is a hard boundary, not a coverage gap. |
| **UNCLEAR** | (not yet specified — presumably ask to rephrase, consistent with Gate's original framing; confirm with Ananth when this comes up) | |

**This table is the single most important design decision Reformat implements** — it's what decides whether the eventual answer comes from internal retrieval (a/b), external synthesis (c/d), a clarifying question, or a decline. Build against this table; don't re-derive it from first principles.

**Explore-before-clarify (the key design principle, already established in prose — now needs real bounding logic):** for the FAN-OUT case, run the fan-out and explore *first*; only clarify with the user if results genuinely **diverge**. Two distinct clarify triggers:
- **gate-time** — can't even form a fan-out (Reformat itself fails to bound anything sensible) → ask up front
- **observe-time** — explored, results genuinely split by the missing axis → **informed** aperture ("depends on your state — FL vs TX"), which beats a blind "which state?" — this observation happens downstream (at Observe, not yet built), but Reformat's fan-out output is what makes it possible

**Fan-out width is a cross-module knob:** *Reformat sets N* (how many rewritten queries), *Pool pays N×* (parallel builds — cost), *Observe reaps convergence* (does the fan-out actually resolve). This is explicitly the recall/latency tradeoff — Eval-tuned, not guessed.

## 4. The concrete problem Reformat must solve (not yet designed)

Gate's `fanout_codes` is currently **unbounded and unranked** — flagged repeatedly during Shape Gate's build as explicitly out of scope for Gate. Concretely:

- "Eligibility for Medicaid" → 80 candidate sibling codes (age bands, income tests, immigration status, verification, work requirements, ...)
- "Behavioral health services" (hypothetically, if it ever lands general-only) → up to 631 candidates under `health_care_services`

**Reformat must answer:** how do we go from "80 possible facets" to "a bounded, sensible set of rewritten queries"? Candidate approaches to design (not decided yet):
1. **Top-K by corpus prevalence** — rank siblings by document count (most-represented facets first), take top-K.
2. **Top-K by lexicon signal** — if the query has partial hints (e.g. an age mentioned but not matched precisely), weight siblings whose phrases are "closest" to query tokens.
3. **Aspect clustering** — group siblings into a small number of meaningful aspect buckets (e.g. all age-band codes → one "age eligibility" aspect) rather than fanning out to every individual leaf.
4. **Hybrid** — cap at some N (Eval-tuned), combine prevalence + lexicon proximity.

This is genuinely undesigned — the original meet-old doc flags fan-out width as "one knob across three modules" but doesn't specify the ranking function. **This is the first real design decision for whoever picks up Reformat.**

## 5. Output — what Reformat must emit

Per the original design (§1b/§1c boundary): `rewritten_queries[]` (bounded list of concrete queries to hand to Pool), plus whatever slot/aperture metadata Structure (Step 1c) will need downstream. Exact schema TBD — first task for the new owner is to draft this contract (mirroring how Shape Gate's `contracts.py` was the first file written).

## 6. What's explicitly OUT of scope for Reformat

- Gate's classification logic (locked, tested, signed off — do not modify `gate.py`'s `_classify`)
- Pool's actual corpus search/BM25/vector logic (Step 2, separate module)
- Structure's final downstream-contract emission (Step 1c, comes after Reformat)
- The `_run_with_kofn_cascade` strict→relaxed tag cascade (`corpus_search.py:1225`) — this is Pool-side, a different (older) mechanism; don't confuse it with Reformat's fan-out (new, Shape-side)

## 7. Process — repeat exactly what Shape Gate did

1. **Design/ground the approach** — read this spec + the original meet-old doc §1b, decide the bounding/ranking mechanism (§4), draft `contracts.py` equivalent for Reformat's output shape.
2. **Build with real DB verification at every step** — same discipline as Gate: no guessed numbers, run live queries, verify against the actual lexicon/corpus, restart the dev proxy if latency looks suspicious before trusting any number.
3. **Test:** unit tests on pure logic (bounding/ranking functions) + DB-integration tests + an eval bank (mirror `queries_gate_contours.yaml`'s pattern — a `queries_reformat_*.yaml` covering PRECISE/FAN-OUT/exit cases with real, verified expected outputs).
4. **Cross-agent sign-off, same process:**
   - **UX** — telemetry/emit schema for Reformat's output (new emit key, avoid collisions — check what already exists, same discipline as Gate found `gate` vs `shape_gate`)
   - **Chat** — integration requirements check (does the fan-out need a visible "exploring options" state now that it's REAL, unlike Gate's placeholder? Chat previously deferred this exact question pending Reformat existing)
   - **Eval** — co-author test scenarios + scoring criteria for the bounding/ranking decision (this is the one genuinely new judgment call — Eval should have real input on what "good bounding" looks like)
   - **DB** — sign off on any new query patterns Reformat introduces (e.g. probing doc-counts per sibling code for ranking)
   - **Curation** — only if a new lexicon gap surfaces during build (as happened twice with Gate)
   - **TECH** — final structural sign-off, same rigor as Gate's 2-round review (expect them to independently re-run everything, not take reports at face value)
5. **Track everything in a live scoreboard** (`shape-reformat-simulation-tracker.md`, mirroring the Gate tracker) — telemetry + narrative examples per test case, sign-off status table, kept UP TO DATE (Gate's tracker went stale once and TECH caught it — don't repeat that).
6. **Commit to git** incrementally, not all at the end.
7. **Report back to Retriever (Shape's manager)** once TECH signs off, for the next module (Structure, or straight to Pool if Structure is folded in — check current chain sequencing before assuming).

## 8. Key lessons from Shape Gate's build (apply here too)

- **Verify-before-trust, every number.** The dev cloud-sql-proxy degrades after long uptime and produces wildly misleading latency numbers — restart it and re-measure with `EXPLAIN ANALYZE` before believing anything looks slow.
- **Don't guess at lexicon facts** (sibling counts, doc counts) — query the live `policy_lexicon_entries` / `document_tags` tables directly. A stale seed file (`policy_lexicon.yaml`) caused a real cross-agent conflict during Gate's build; it's been deleted.
- **User-facing text should never leak internal names** (enum values, code names) — collaborative, first-person language instead.
- **Land test-suite additions immediately when another agent drafts them** — don't build a parallel eval bank and forget the unit tests (this exact miss happened during Gate's TECH review).
- **Keep the sign-off tracker doc current in real time**, not just at the end — it went stale once already in this exact workflow.
- **PHI discipline:** anything echoing raw query text must be fail-closed (never persisted), not just "redact before persisting."
