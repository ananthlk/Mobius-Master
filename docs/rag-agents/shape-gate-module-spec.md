# SHAPE / Gate Module Spec (Step 1a) — v1

**Status:** DRAFT — built + unit/integration tested by Retriever, circulating for cross-agent sign-off before Reformat (Step 1b) is built.
**Owner:** Retriever agent. **File:** `mobius-rag/app/services/retriever/shape/gate.py` + `contracts.py`.
**Scope of this spec:** the gate ONLY (classify intent → contour). Reformat (fan-out execution), structure (downstream contract), POOL, and everything after are separate specs, not covered here.

---

## 1. What it does

Given a raw user query, classify it into one of 6 contours using J/P/D lexicon expansion + a cheap `document_tags` corpus probe (doc-grain, GIN-indexed, never touches the 1.94M-row chunk index). No LLM call. No chunk-level DB access. Deterministic — same query always produces the same contour.

## 2. Input / Output contract

**Input:** `(db: AsyncSession, query: str)` → `run_gate(db, query)`

**Output (`GateResult`):**
```python
@dataclass
class GateResult:
    query: str
    normalized: str
    d_codes: list[str]              # matched domain tags
    j_codes: list[str]              # matched jurisdiction tags
    p_codes: list[str]              # matched process tags
    expansion_phrases: list[str]    # raw lexicon phrases that fired
    probe: CorpusProbe              # union/intersection doc counts
    process_intent: bool            # structural "how do I..." signal
    contour: Contour                # the 6-way classification (see §3)
    missing_kinds: list[str]        # which of d/j/p had zero matches
    underspecified_kind: str | None # only set when contour==UNDERSPECIFIED (see §4)
    fanout_codes: list[str]         # only set when underspecified_kind=="explore_siblings"
    reason: str                     # human-readable trace string
    gate_ms: int                    # total gate latency
```

```python
@dataclass
class CorpusProbe:
    d_docs: int; j_docs: int; p_docs: int
    union_docs: int            # docs matching ANY matched tag
    intersection_docs: int     # docs matching ALL matched kinds
    probe_ms: int
```

## 3. Contour taxonomy (6-way)

| Contour | Trigger | Response posture (downstream) |
|---|---|---|
| `EXACT` | D+J matched (specific leaf, or general-only resolved by P/process_intent), intersection > 0; or one slot missing but corpus already narrow | Answer directly, lean/fast path |
| `VICINITY` | D+J matched but zero docs cover the full combination (union > 0) | Right area, no single doc nails it — needs synthesis across neighbors |
| `UNDERSPECIFIED` | Missing D or J with broad corpus, OR D matched only a general/umbrella bucket with unresolved siblings | Two sub-kinds — see §4, downstream strategy differs |
| `CORPUS_GAP` | Tags matched, union_docs == 0 | Honest gap — log for Sourcing, don't hallucinate |
| `OUT_OF_SCOPE` | Zero tags matched, query IS well-formed | Decline/redirect — not this corpus's domain |
| `UNCLEAR` | Zero tags matched, query is malformed/too short/non-alphabetic | Ask for clarification — couldn't parse it |

## 4. UNDERSPECIFIED sub-kinds (strategy-relevant, added 2026-07-22)

| `underspecified_kind` | Meaning | `fanout_codes` | Downstream strategy |
|---|---|---|---|
| `explore_siblings` | D matched only the general bucket for a domain (e.g. `eligibility`) that has a KNOWN, ENUMERABLE set of unmatched specific siblings in the lexicon | Populated — the sibling code list | **Explore, not clarify.** We know D+J are valid and the corpus has content; reformat should proactively fan out across (a bounded subset of) `fanout_codes`, probe each, and only ask the user if results genuinely diverge |
| `missing_domain` / `missing_jurisdiction` | D or J matched nothing at all | Empty — no root to enumerate siblings under | **Not explorable.** Different handling: relax scope, escalate, or flag as a lexicon coverage gap |

**Important boundary:** the gate only *detects* explorability and *enumerates* candidates (a lexicon-catalog lookup). It does **not** probe `document_tags` for any sibling code, does **not** bound the list, and does **not** run any fan-out queries. That execution is Reformat's job (Step 1b, not yet built) — this spec covers classification only.

## 5. Key heuristics (grounded, not vibes — see gate.py docstrings for full detail)

- **D+J required, P is enrichment** — except the general-only-match exception below. Verified against cmhc 22-query bank: requiring P pushed 17/22 to underspecified incorrectly; dropping it to enrichment-only correctly reads 20/22 exact.
- **General-only-match detection** (`_is_general_only_match`) — if every matched D-code for a domain is the bare root or `.general`, AND the lexicon has other specific leaves under that root that didn't fire, P becomes the disambiguator (satisfied by a lexicon p-code OR the `process_intent` structural signal).
- **`process_intent` regex** — catches "how do I / how to / what's the process for" phrasing as a generic disambiguator, avoiding the need to enumerate every action-verb synonym as a lexicon alias (e.g. resolves "check" without any lexicon change, since only "verify" was an alias).
- **Malformed vs out-of-scope split** — zero tag matches alone can't distinguish "gibberish" from "clear question, wrong domain"; a cheap word-count/alpha-ratio check does, with a documented limitation (multi-word "fake English" gibberish isn't reliably caught — accepted trade-off, not hidden).

## 6. Known limitations / open backlog (not blocking this spec, tracked separately)

- **Lexicon D-tag gaps:** "credentialed" and "enroll a pediatric patient" have no matching D-tag at all → `missing_domain`. See `lexicon-p-tag-gaps-log.md` (held, not yet filed to Curation).
- **Malformed-query heuristic gap:** multi-word alphabetic gibberish isn't caught, falls through to `OUT_OF_SCOPE`. Accepted default (real traffic skews toward legitimate off-topic questions over gibberish).
- **`fanout_codes` unbounded:** currently returns ALL siblings (e.g. 80 for eligibility) with no relevance ranking or top-K cap. Reformat must add bounding before executing fan-out.

## 7. Verified performance (DB-checked, not estimated)

- Typical 2-3 code probe: Bitmap Index Scan + BitmapOr on `document_tags` GIN indexes, ~630-715ms server-side (cache-hit, no I/O issue — inherent per-row JSONB evaluation cost).
- Near the lexicon's 12-entry cap with several broad `*.general` tags: correctly falls back to Seq Scan (~900ms-1.5s) once combined selectivity crosses ~50-60% — the planner's cost call is right, not a bug.
- **Gate does NOT currently meet the <500ms p50 target** from `module-gates.md` §1. This is a known, DB-verified gap to resolve with TECH/DB before final sign-off (see §9).

---

## 8. Cross-agent work packages (this session's ask)

Each agent below gets a scoped ask against this spec, and owns a concrete artifact + a defined contract back to Retriever.

| Agent | Package | Artifact | Contract with Retriever |
|---|---|---|---|
| **UX (emits/telemetry)** | Design the telemetry/emit schema for gate decisions (contour, timing, trace fields for the 9-tab chat bubble / diagnostics view) | Emit schema spec | Retriever wires `GateResult` fields into agreed emit format |
| **Chat** | Confirm no special integration requirements — does chat need anything beyond the 12-field contract eventually, any gate-specific UI hooks (e.g. surfacing `explore_siblings` as a visible "exploring options" state)? | Integration confirmation note (or requirements list) | Retriever adjusts GateResult/contract if Chat has needs |
| **Eval** | Co-author the QA test script + scenarios for the gate — beyond the cmhc 22-query bank, what edge cases/scenarios should be covered before sign-off? | QA test script + scenario list (co-authored) | Retriever implements agreed test cases |
| **DB** | Sign off on the `document_tags` query pattern (GIN usage, seq-scan fallback conditions) and co-lead the <500ms latency gap resolution | DB sign-off + latency remediation plan | Retriever implements agreed query changes |
| **TECH (architects)** | Final structural sign-off on the full spec | Sign-off record | Gate is cleared to be the locked Step 1a contract |
| **Product Awareness** | Hold this spec as the canonical reference doc post-signoff | — | Spec stays discoverable/current for future queries about the gate |

## 9. Open items requiring resolution before final sign-off

1. Gate latency (630-1500ms) vs the <500ms target in `module-gates.md` §1 — needs DB/TECH input on whether to relax the gate, optimize the probe further, or accept a revised target.
2. `fanout_codes` bounding strategy — not blocking gate sign-off (Reformat's problem), but flagging so Eval/TECH know it's explicitly out of scope here.
3. Lexicon D-tag backlog (§6) — held per Ananth, not filed yet; noting for Product Awareness's record so it isn't lost.

---

**Companions:** `retriever-meet-old-plan.md` (full 7-step chain design) · `retriever-current-state.md` (legacy code anchors) · `lexicon-p-tag-gaps-log.md` (held lexicon backlog) · `tests/test_shape_gate.py` (25 pure unit tests + 6 DB integration tests, all passing).
