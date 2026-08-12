# SHAPE / Structure — Schematic Spec (Step 1c) — v1

**Status:** DRAFT — design doc, no code written. Follows the same process Gate (`gate-emit-schema-spec.md`) and Reformat (`shape-reformat-schematic-spec.md`) used: spec → cross-agent sign-off → build.
**Owner:** Shape:Structure agent, reports to Retriever.
**Companions:** `shape-structure-module-spec.md` (Retriever's original kickoff doc), `retriever-meet-old-plan.md` §1c, `retriever-emit-telemetry-registry.md`.

---

## 1. Resolved before this spec was written

- **Scope/auth context assembly does NOT belong to Structure.** Resolved directly with Ananth: `orchestrator.py` owns it, threads it through the chain if/when needed. Structure only ever *consumes*, never assembles, request-level context. (Same principle applied again in §4 below.)
- **`GateResult` carries no PHI/freshness/scope-overlay fields.** Verified live in code — nothing to pass through from Gate on that front.
- **The `thinking_trace` narrate() wiring question is resolved** (via Retriever, commit `28b98d0`): Gate+Reformat narration concatenates into `thinking_trace` for FAN_OUT/RELY_ON_EXTERNAL/CLARIFY postures only; PRECISE/DECLINE/CLARIFY_REPHRASE use Gate's alone. Structure does not currently plan its own narrate() layer — no user-facing narrative need identified yet for a resourcing decision.

## 2. Reframing `answer_shape` + `slots` — what this spec actually proposes

The original kickoff spec (§3/§4) framed Structure's job as producing `answer_shape` + an undesigned `slots` concept, modeled on the legacy bare-string field (`corpus_search_agent.py:2939`: `"essay"|"structured"|"binary"|"any"`).

**Working through this with Ananth surfaced a scope correction: `answer_shape` describes the FORM of the final answer text (essay vs table vs yes/no) — that's Synthesis's/Chat's concern, not Retriever's.** Retriever's actual job ends at "here is the best evidence, at this confidence, this fast." Conflating retrieval effort with answer formatting was the original design's error, inherited from the legacy field's dual role.

**Correction:** leave legacy `answer_shape` completely alone — untouched, still read by `corpus_search_router.py`'s `_shape_match()` (live, 0.30 weight in the linear routing formula). Structure's real, new output is a **`ResourcePosture`**: how much retrieval effort to spend on this specific query, not how to format the eventual answer.

## 3. `ResourcePosture` — four fields, not invented from nothing

Two independent inputs already exist in the codebase, just scattered and never combined:

- **"What we have" (internal)** — posture (`ReformatPosture`, from Reformat) + `fanout_themes` (from Reformat) describe how *hard/ambiguous* the query is.
- **"What the user asked for" (external)** — `caller_mode` already exists as a real concept: `CALLER_MODE_PRESETS` (`corpus_search_router.py:118-159`) keys `chat.copilot`/`chat.default`/`chat.thinking`/`auth_agent`/`research`/`batch` to real `accuracy_need` (0.70–1.00), `recall_demand`, and `speed_budget` (`real_time`/`interactive`/`background`/`none`) values. `chat.thinking` already *is* "think mode"; `chat.copilot` already *is* "fast mode." This is not a new signal — it's an existing one Shape has never had access to (it lives downstream, inside Router, which Gate/Reformat/Structure never see).

**So `ResourcePosture` is a consolidation, not new invention** — three existing-but-scattered signals (`accuracy_need`, `k`/`recall_demand`, `_get_escalation_budget()`) plus direct reuse of the existing `speed_budget` label, cross-referenced against `posture`/`fanout_themes` (which none of those existing computations can see today, since they run after Router, not in Shape).

```python
@dataclass
class ResourcePosture:
    breadth: int                 # target chunk count / pool depth
    confidence_bar: float        # convergence threshold — same 0-1 scale as existing accuracy_need
    max_attempts: int            # escalation loop ceiling — extends existing _get_escalation_budget()
    speed_budget: str            # reuse existing Literal["real_time","interactive","background","none"] AS-IS
```

`speed_budget` is deliberately NOT a new `latency_budget_ms` field. Verified live: **no wall-clock ms latency budget exists anywhere in this codebase** — `speed_budget` is a qualitative label feeding a router scoring weight (`_SPEED_WEIGHT`), and the one `cost_budget` field that exists is explicitly commented "not enforced in v1." Inventing an ms number nothing would enforce is less honest than reusing the real existing type.

## 4. New input Structure needs: `caller_mode`

`caller_mode` is real (`CALLER_MODE_PRESETS` keys) but today only reaches Router, not Shape. Structure needs it threaded in from whatever calls the chain (chat, most likely) — **same "orchestrator threads it, Structure consumes, never assembles" pattern already resolved for scope/auth in §1.** Not a new architectural question, just the same resolved principle applied to a second concrete field.

**Open sub-question for Chat specifically:** does chat's real request path actually send something equivalent to `caller_mode` today, or does `CALLER_MODE_PRESETS` only serve programmatic callers (`auth_agent`, `research`, `batch`) with chat traffic silently defaulting to `chat.default`/`DEFAULT_CALLER_MODE`? If chat has no real per-request "think vs fast" toggle today, Structure's `ResourcePosture` will default correctly but won't reflect genuine user intent until chat adds one — worth knowing before, not after, this ships.

## 5. Proposed grounded anchors (verified live, not guessed)

| Constant | Value | Source |
|---|---|---|
| Default `k` | 10 | `corpus_search.py:81-83`, `corpus_search_agent.py:2915,2924` |
| Strategy-b breadth floor | `max(k, 15)` | `corpus_search_agent.py:4441` |
| `MAX_FANOUT_THEMES` | 4 (≤3 real themes + 1 catchall) | `shape/contracts.py:128`, Ananth's own comment: "no more than 3-4 question angles" |
| `accuracy_need` range | 0.70 (copilot) – 1.00 (auth_agent) | `CALLER_MODE_PRESETS` |
| `_get_escalation_budget()` pattern | 0 attempts (real_time/fast/copilot) · 2 (thinking/research) · 1 (else) | `corpus_search_agent.py:2321-2328` |
| Global escalation ceiling | `_MAX_TRIES = 4` | `retriever-meet-old-plan.md:19` |

**Real inconsistency found, flagged not fixed:** `_get_escalation_budget()` checks `caller_mode in ("fast","copilot")`; `CALLER_MODE_PRESETS` keys are `"chat.copilot"` etc. — two different mode vocabularies already coexist in production. Structure should not silently inherit whichever one is broken — needs an explicit answer from whoever owns that code (DB/TECH), not a guess.

**Not yet verified — do not assume:** `RELY_ON_EXTERNAL`'s "breadth" is a different unit entirely (external result count from strategy d, not corpus chunk count) — I have not checked strategy d's code for what a comparable resourcing number would even mean there. Flagging as open rather than inventing a number.

## 6. Architecture: lookup table, not a weighted formula — v1

Recommendation: `ResourcePosture` resolves via a small discrete table indexed by `(ReformatPosture, caller_mode)`, not a linear/weighted formula. Reasoning:

1. **Input space is small and discrete** — only 3 postures reach retrieval (PRECISE/FAN_OUT/RELY_ON_EXTERNAL) × 6 caller_mode presets = 18 cells max, same shape as Gate's contour taxonomy table (which shipped as a table, not a formula).
2. **No calibration data exists yet.** Router's own linear formula only earned trust after `decide_override()` forced-calibration produced real outcome data (`retriever-meet-old-plan.md` §"Final Decisions"). Structure has zero production traffic — hand-set table cells now, Eval-gated graduation to learned weights later (`retriever-meet-old-plan.md`'s own "Bandit feedback loop [⋯exceed]" is the documented path for this, not a new pattern).
3. **Debuggability** — each cell is independently auditable and independently Eval-tunable without perturbing the others.

Only PRECISE/FAN_OUT/RELY_ON_EXTERNAL get real `ResourcePosture` values. CLARIFY/CLARIFY_REPHRASE/DECLINE don't reach retrieval this turn — proposing `resolve_resource_posture()` returns `None` for those (open question for sign-off: `None` vs an explicit all-zero object — leaning `None`, less "is it real" ambiguity downstream, but want TECH/DB's read on which is easier to consume).

## 7. Explicitly NOT proposed here

- **Not proposing Structure's `ResourcePosture` replace or feed into Router's existing `accuracy_need`/`_get_escalation_budget()` computation.** That would be a bigger, riskier change (Router doesn't currently see posture/fanout_themes at all) requiring Router-owning-agent coordination — out of scope for this spec, flagged as a future `[⋯exceed]` unification question, not something I'm doing unilaterally.
- **Not touching `CALLER_MODE_PRESETS` or `_get_escalation_budget()` themselves** — read-only consolidation into a new, additive, Structure-owned field.

## 8. Asks per collaborator

- **UX** — new emit key `shape_structure` (proposed, avoiding collision with `gate`/`shape_gate`/`shape_reformat`) — does `ResourcePosture`'s 4 fields make sense as Diagnostics-surface content? Any Chat-bubble-visible need, or backend-only like `shape_reformat`?
- **Chat** — does chat's real request path send anything like `caller_mode` today (§4's open sub-question)? Does the final Shape→Pool contract need anything Chat-specific?
- **Eval** — is the lookup-table approach (§6) acceptable for v1, or is there a reason to prefer forced-calibration before shipping any real cell values? What would a resourcing eval bank need to look like?
- **DB** — Structure makes zero DB calls (pure compute over `GateResult`/`ReformatResult`/`caller_mode`) — confirming that's actually true and not a gap. Also: the `caller_mode` vocabulary inconsistency (§5) — real bug or intentional, and who should fix it?
- **TECH** — overall structural review, same 2-round rigor as Gate/Reformat.

## 10. Addendum 2026-07-23 — `max_attempts` role correction (post-close)

**Architecture correction from Ananth, relayed via Retriever, triggered by a real seam bug**: Router's code reached for a per-slot `max_attempts` on `AnswerSlot` (Slots/Step 1d's contract) that didn't exist there — surfacing that the original design let `max_attempts` be treated as *the* planned attempt count, when Structure was never positioned to know that. Structure has no visibility into per-strategy latency (that's Router/Fillers knowledge) — any fixed attempt count it hands down is a guess dressed as a decision.

**Correction:** `speed_budget` is the primary effort constraint `ResourcePosture` expresses — it's the real thing Structure can reason about (time). `max_attempts` is downgraded to an optional **soft safety ceiling** ("never exceed N regardless of how fast each attempt is" — cost/pathological-retry protection), not the allocation decision. Router's job: derive planned attempts from `speed_budget` (time budget) ÷ its own per-strategy latency estimate, then `min()` against `max_attempts` as an upper bound.

**What changed:** `contracts.py`'s `ResourcePosture` docstrings corrected to state this explicitly (field reordered, `speed_budget` now documented as primary); field itself NOT removed — kept as the escape hatch Ananth explicitly allowed ("if max_attempts still serves some purpose beyond time... keep it as an optional soft cap"), given Eval's existing cost-premium sign-off criteria partially leaned on attempt count as a cost proxy, and removing outright risked a bigger destructive ripple into Slots/Router's already-built code than a semantic correction. 21/21 tests still pass (values unchanged, only documented role changed).

**What did NOT change:** the hand-set table values (1/2/1 for PRECISE/FAN_OUT/RELY_ON_EXTERNAL) — still valid as a safety ceiling, just no longer to be read as "the plan."

**Coordination:** flagged directly to Router's session (theirs is the allocation logic that needs to change — derive-from-time, not read-a-fixed-count) — this section documents Structure's side of the correction, not Router's or Slots' implementation, which are out of scope here same as always.

**Closed 2026-07-23 — Router confirmed, verified not claimed:** the `AnswerSlot` gap was entirely a Router-side drift bug (a local stand-in re-declared with phantom fields instead of importing the real `shape.slots.AnswerSlot` — fixed with an identity assertion in Router's tests so it can't recur), nothing needed from Structure. Router's attempt-derivation already worked incrementally (grow the chain while the next strategy's `latency_p50` fits `speed_budget × (1 + tolerance)`) — more accurate than a flat time÷latency division since strategies have heterogeneous costs. `max_attempts` was already only a loop cap (i.e. already the soft-ceiling model), default loosened to 6 now that time is the explicit binding constraint. `query_class` (a related question that came up) is confirmed dead — fed only a dormant priors-fallback tier, no replacement field needed on either `AnswerSlot` or `ResourcePosture`. No further action on Structure's side.

**REOPENED and re-closed 2026-07-23 — the actual values still needed fixing.** Router's "loosened to 6" note above described Router's OWN internal default; Structure's own `_MAX_ATTEMPTS_BY_POSTURE` table (PRECISE=1, FAN_OUT=2, RELY_ON_EXTERNAL=1) was left untouched and turned out to be a live production bug: `min(time_derived_attempts, 1)` is always `1`, so a "soft ceiling" of 1 functionally became the plan, not a rarely-binding backstop — directly contradicting the addendum above. Real impact: 19/22 bank queries produced 0-occupancy answers, blocking Eval's Observer calibration sign-off, root-caused by Router (with live evidence, not a guess) and traced back to this exact table. Fixed: removed posture-based variation entirely, replaced with one uniform `_MAX_ATTEMPTS_CEILING = 6` — Router independently verified this ceiling never actually binds for real_time (their own allowance naturally settles fallback chains around ~3 strategies), confirming 6 is generous-but-safe, not another guess. 28/28 tests updated and passing. Lesson: "corrected the documented role" (first pass) and "corrected the actual values to match that role" (this pass) are different fixes — don't assume a docstring change alone closes out a design correction with real numeric consequences.

## 11. Addendum 2026-07-23 — `token_budget` added to `ResourcePosture`

**New constraint, from Ananth via Retriever**, triggered by a real correctness gap, not just cost: strategy d (web search/full-page extraction) can hand back whole-document-sized text with no aggregate cap. Only a PER-PASSAGE cap exists (`corpus_search_strategy_d.py`: `_MAX_PASSAGE_CHARS=2000` chars × up to `_MAX_FETCH=5` passages, unbounded in total) — a filler could technically "cover" a query by volume, not relevance. Same class of issue as Eval's citation-trust findings.

**Design, same family as `confidence_bar`/`speed_budget`:** per-`caller_mode` lookup table, Fillers enforce it with their own selection logic (Filler d's own instinct, confirmed via Retriever: rank chunks by existing BM25 scores and keep the best within budget, not a blind truncate) — Structure hands down a target, doesn't dictate how it's met. Same interface pattern already established, no new consumption model needed.

**Grounded, not guessed:** Filler d measured a real full-slot (capacity=5) at ~2,021 tokens live — 4/5 chunks pinned right at the extraction ceiling. Table values (`chat.copilot`=2000, `chat.default`=3000, `chat.thinking`=6000, `auth_agent`=2500, `batch`=12000, `research`=20000) track `speed_budget`'s urgency tier, not `accuracy_need` — real_time modes get tight caps regardless of how much accuracy they demand, background/none modes get room.

**Open question, not resolved here:** `auth_agent` is tentative. Its `accuracy_need=1.00` is about precision on a binary answer, not evidence volume — `token_budget` doesn't cleanly scale with `accuracy_need` the way `confidence_bar` does, and answer_shape (which would disambiguate this) lives on the original request, not `ReformatResult` — Structure has no visibility into it. Flagged, not guessed past.

**Breaking-change catch, fixed same-session:** adding `token_budget` as a required field broke `tests/test_pool.py` and `tests/test_slots.py` (both construct `ResourcePosture` directly, built before this field existed) — 20 failures caught immediately by running the full affected suite, not assumed clean. Fixed by giving `token_budget` a default (`10**9`, "unbounded" — matches the exact pre-field status quo and mirrors Router's own `_SPEED_BUDGET_MS["none"]=10**9` sentinel) rather than requiring every existing caller to update immediately. `run_structure()` always overrides the default with a real per-`caller_mode` value; the default is a compat shim, not a real answer. Verified: `test_shape_structure.py` (24/24) + `test_slots.py` all green; `test_pool.py`'s remaining 4 failures confirmed as pre-existing pytest-asyncio event-loop-reuse flakiness (pass individually in isolation), not caused by this change.

**Closed 2026-07-23 — bridge gap found and fixed, semantics confirmed:** the real end-to-end path had a 3-layer gap independent of anything above — `orchestrator.py`'s `RouterResourcePosture(...)` never threaded either new field to Router at all, and Router's own `decision.py` dataclass didn't declare them either (only their internal dict-based `resolve_constraints()` path could see them, which real production traffic never calls directly — only their own tests did). Found by verifying Router's claim against live code rather than trusting the summary, reported to both Retriever and Router with exact line citations, fixed entirely on their side (Router: dataclass + bridge, 223/223; Retriever: adding the two kwargs to `RouterResourcePosture(...)` once that landed) — Structure's own computation was never the problem. Router adopted `token_budget` as Structure's own field name verbatim, confirmed per-slot semantics (not query-total) matches what Structure actually computes — no translation math needed at the bridge.

## 12. Addendum 2026-07-23 — `authority_requirement` added to `ResourcePosture`

**Second field bundled with `token_budget`'s rollout, per Ananth via Router** — same posture-widening conversation, not a separate one. Unlike every other `ResourcePosture` field, this one is **caller-declared, not Structure-computed** — Router's own module docstring is explicit: "Bifurcation is CALLER-DECLARED, not Router-guessed." Structure's job is purely to thread it through faithfully, same "consume, don't assemble" pattern already applied to scope/auth and `caller_mode`.

**Matched exactly against Router's already-built, already-tested consuming side** (verified live in `allocation.py` before adding anything, not guessed): `authority_requirement: str`, values `"any"` (default, fail-open — zero behavior change until a caller declares) and `"citable_required"` (non-citable strategies like web-search `d` become ineligible for REQUIRED/evidence-bearing slots only; optional/`external_context` slots keep them, since web context is still useful even when it can't serve as citable evidence to a payor). Router: 220/220 tests passing on their side, independently verified by Retriever.

**Implementation:** new `run_structure(reformat, caller_mode=None, authority_requirement=None)` parameter, unrecognized/missing values degrade to `"any"` (fail-open, same defensive pattern as the `caller_mode` vocabulary-bug fallback — never propagate a bad value into eligibility filtering). Field defaulted (`= "any"`) on `ResourcePosture` itself from the start this time — learned from `token_budget`'s breaking-change catch a few messages ago, verified `test_pool.py`/`test_slots.py` still pass before considering this done, not after.

**Genuinely unresolved, not mine to resolve:** whether callers can actually distinguish appeal-vs-casual context at the source to set this meaningfully — Chat is being engaged on that separately (by Router, per Ananth). Structure carries whatever value arrives; it has no way to determine intent itself.

## 9. What's explicitly out of scope for Structure (unchanged from kickoff)

- Gate's classification logic, Reformat's posture/fan-out logic (both locked)
- Pool's actual corpus search, Router/Fillers/Synthesis/Contract/Timing (downstream, don't exist yet)
- `orchestrator.py` itself
- Legacy `answer_shape`'s semantics or Router's consumption of it (untouched, passthrough only)
