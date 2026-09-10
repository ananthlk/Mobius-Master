# Chat refactor — program plan

**Status: ACTIVE. P1 and P2 complete; P3 in progress (`state_load` closed).** The
sign-off table at the end is current as of 2026-09-09 — five of six rows ruled, the
sixth (Prompt Studio) deliberately not yet asked because Phase 4 has not opened.

Tracked in **`docs/chat-refactor-roadmap.md`**, which is generated from the same
findings and **fails the build when a bug is unassigned** — so a new finding is either
sequenced into a phase or given an explicit reason for sitting outside the program.
Phase definitions live in `scripts/platform/refactor_roadmap.py`.

Companion to `docs/chat-schema-findings.md` (73 bugs · 66 checks · 60 verified-ok
across 35 nodes), which is generated and must not be hand-edited. This document is
hand-written: it sequences that inventory into work, and defines the pre-test /
eval / post-test gate every phase has to pass.

---

## 0. The finding that shapes the whole plan

**Most of what we want to change is currently unobservable, so it cannot be
baselined.** This is why instrumentation is P2 and blocks everything after it.

Concretely, from the findings log:

- The governor contains **zero logger calls**. Its only window is the `react_trace`
  envelope, emitted by a different module, wrapped in a `logger.debug` swallow.
- `keep` — which retrieved chunks the curator kept — is **never persisted**. 568
  turns record `gaps_closed`, 701 record `gaps_open`, `keep` appears 0 times.
- `objective_status` is **always `"resolved"`**, for every turn, including refusals
  and the 203 that exhausted their round budget.
- **116 of 187 config knobs** run on invisible code defaults; nothing states the
  effective value.
- **16 of 35 nodes have no test file**, including 2 of the 5 reds.

A refactor measured against a baseline this thin will look successful whether or not
it is. Instrumentation is not preparation for the work; it is the work that makes the
rest provable.

**Why deletion still goes first (Ananth, 2026-09-08).** Two reasons, and the second
is the stronger one. Clearing dead code makes the remaining list legible — you stop
reasoning about code that will not exist. And deletion is the one phase whose gate
needs nothing we do not already emit: I1–I7 are all computable from today's
telemetry, which is how every measurement in the findings log was taken.

**What that ordering costs, stated rather than hidden: P1 cannot claim a latency
win.** The latency baseline does not exist until P2. Deleting unreachable code should
not move latency at all — that is the argument for it being safe to lead, and it is
also exactly why it forfeits the claim. The reference numbers for "better and faster"
are captured at the END of P2, and every phase after that is measured against them.

---

## 1. The test gate — same shape for every phase

Each phase is a loop, not a step. **A phase that cannot state its post-test in
advance does not start.**

```
  PRE   freeze a baseline on the CURRENT code
        └── replay corpus + invariant set + the metric this phase claims to move
  CUT   the change, behind a flag where a flag is possible
  POST  re-run the identical baseline
        └── invariants must hold exactly; the claimed metric must move; nothing else may
  SIGN  the owning seat + Eval both sign, or the phase reverts
```

**The corpus — and what it is NOT.** Frozen in `docs/chat-refactor-baseline.json`:
2,750 turns, fingerprint `7278bebc`. It is a **committed file, not a query** —
Technical Review asked whether the set was frozen or the live table read twice, and
it was the latter: every measurement in the findings log used a moving
`now() - interval '60 days'` window, which is why the DB seat measured 2,744 against
my 2,741. From here PRE is the file.

**It is a DIFFERENTIAL gate, not a replay of production** (DB seat's ruling, adopted
verbatim). `chat_state` holds one row per thread, mutated in place, no history — so
the state a turn actually ran with is not recoverable, only today's value. Both PRE
and POST get the same reconstructed input, so any delta is attributable to the code
change. That is what a refactor gate needs and it is all this claims. Nobody may
describe it as reproducing historical behaviour.

**Stratified on `context_summary`** (DB seat): present on 1,853 turns, absent on 897.
A pooled comparison silently over-weights the 67% carrying context. Both strata are
reported. **Caveat I owe back to the DB seat:** 378 of the 383 integrator bypasses
fall in `no_context`, because a bypassed turn exits before the summary is written —
so this stratum is partly an *effect* of the outcome we are measuring, not an
independent covariate. It still separates the populations usefully; it must not be
read as a control.

**Dependency, flagged by the DB seat:** the gate now depends on 60 days of
`chat_turns` existing. There is no retention path today, so it is safe — but a future
retention change would silently shrink the corpus and break comparability. Any
retention work must trip over this line.

**Invariants — must be identical before and after, every phase.** These are
assertions about the envelope, not about answer text:

| # | Invariant | Why it is the right assertion |
|---|---|---|
| I1 | every turn produces exactly one terminal envelope | catches a refactor that drops a finalize path — there are 12+ `_finalize_response` call sites |
| I2 | the set of turns that bypass the integrator is unchanged | 383 today; a change here is a change in what the user sees |
| I3 | PHI gate verdict per turn is unchanged | fail-closed must stay fail-closed |
| I4 | `rounds_used` / `max_rounds` unchanged — **except** where the extension-writer unification changes the outcome, which gets a named reviewed diff, never a silent pass | the governor's arithmetic is most at risk |
| I5 | floor ran / skipped unchanged, **same carve-out** if floor timing interacts with which round it runs in | 966 ran / 1,784 skipped at baseline |
| I6 | the source set per turn is unchanged | retrieval must not shift under a refactor of control flow |
| I7 | no new swallowed exception | count `log-and-continue` handlers; the number may fall, never rise |

**The I4/I5 carve-out** (Technical Review's amendment, adopted). Unifying the two
extension writers **is in scope** — it is P3. So a blanket "rounds unchanged"
invariant would fail on exactly the 102 turns already identified as past soft target,
and the gate would reject the change it exists to enable. An invariant that cannot
distinguish an unintended change from the specific defect the program exists to fix
is not testing the right thing. The carve-out is scoped, not a weakening: the
expected delta is predicted before the cut and reviewed against after.

**The replay mechanism — the honest answer.** There is no record/replay harness in
`mobius-chat` today: no VCR, no cassettes, no `MOBIUS_LLM_MOCK`, no seed or
determinism switch in `llm_manager`. So a live re-run makes I3 and I5 judgement calls
with real model variance, and a flip could be non-determinism rather than regression.
**Building the deterministic harness is therefore a P1 prerequisite, not an
assumption** — pinned LLM responses so PRE and POST compare identical inputs through
code-only diffs. Until it exists, the only assertable invariants are the ones
computable from persisted telemetry without re-running anything (I1, I2, I4, I6, I7),
which is exactly what the frozen baseline holds. I3 and I5 are **deferred until the
harness lands**; no phase may claim them before then.

**What the metric is, per phase, is named in Section 3.** A phase claiming "cleaner
code" and no metric does not start either.

**The honest limit, stated up front.** Answer *quality* is not in the invariant set,
because we cannot assert it from a replay — that is Eval's judge, and it is a
separate, slower loop. Invariants prove *we did not change behaviour we did not mean
to change*. They do not prove the answer got better, and no phase below claims they
do.

---

## 2. Sequencing rule

Ordered by **what unblocks what**, not by severity:

1. Deletion first — it makes the rest of the list legible, and its gate needs only
   telemetry we already have.
2. Instrumentation second — nothing after this point can be measured without it, and
   "faster" is unprovable until it lands.
3. Unify a decision before moving it — do not build a UX over a policy that lives in
   two places.
4. Split large modules last — the highest-risk, highest-blast-radius work, done when
   the test gate is proven by three earlier phases.

---

## 3. Phases

### P1 — Delete  ·  LEADS  ·  owner: chat  ·  ratifier: DB seat (tables), Tech Review (contract)

Lowest risk in the program and the largest clarity gain. Nothing here changes live
behaviour if the measurements hold.

| Target | Size | Evidence | Caveat that must be cleared first |
|---|---|---|---|
| classic path (`resolve`, `plan`, `classify`, `clarify`, `refined_query`, `clarification`) | **DONE — 2,181 lines** (1,298 app + 883 test), vs my 1,159 estimate | imported by nothing but the branch; 3 user-facing strings, 0 live occurrences in 2,741 turns | `use_react` is a per-request API field — removing the branch is a **contract change**; and `query_refinement.py` looks legacy but `blueprint.py` needs it |
| `credentialing_envelope` — 7 of 8 functions | 177 lines | 7 have zero callers | none; this one is genuinely free |
| credentialing workflow — **code only** | 8,994 lines + 125 refs in shared modules | `provider-roster-credentialing` skill owns the domain and references `provider_roster` directly, so this is **duplication, not disuse** — a stronger argument than emptiness | needs prod counts + the skill owner confirming who writes `provider_roster`; the 125 scattered refs are the real work |
| credentialing tables — **DO NOT DROP** | 11 empty tables | DB seat's ruling: empty tables cost nothing, dropping is the irreversible half, and row counts do not license it | revisit after the code is gone and they have sat empty a quarter |

**Metric:** lines removed; `log-and-continue` handler count down; **zero** invariant
movement. If any invariant moves, the deletion was not dead code. Explicitly NOT a
latency metric — the baseline for that does not exist until P2.

### P2 — Make absent producers detectable  ·  BLOCKING for P3–P5  ·  owner: chat + Eval

**Reframed 2026-09-09**, on Chat Master's argument rather than mine. I had scoped this
as "instrument the known gaps." That fixes twelve instances. The evidence supports a
stronger frame: **nothing in this codebase fails loudly when a producer disappears,
because every consumer has a plausible default.**

`master_objective`'s writer died and four readers quietly returned `"resolved"` on
every turn for five months. `variant_id` was never written and a refresh query matched
nothing for a month while serving a hardcoded seed. `make_tool_failed` has no caller,
so `tool_failed` is not rare — it is impossible, while `tool_invoked` and
`tool_completed` emit normally. `CallManager` is wired in docstrings only. In each
case the absence is invisible precisely because the default is plausible.

So the phase's job is not a list of instruments. It is: **when a producer stops, some
consumer must fail loudly.** Same-change read-backs, emitters that assert a caller,
and defaults that are distinguishable from real values. Latency instrumentation still
lands here — 19 of 25 modules untimed, and "faster" is unprovable without it — but it
is an instance of the rule, not the point of the phase.

Nothing after this can be measured without it.

| Item | From node | Why it blocks |
|---|---|---|
| governor emits its own decisions | `governor` | the round policy is invisible; I4 cannot be asserted from a module that logs nothing |
| `react_trace` emit failure stops being a `logger.debug` swallow | `react_loop` | the single observability window can fail silently |
| persist `keep` | `react_loop` | curation is untestable retrospectively without it |
| effective-config surface | `governor` | 116 knobs on invisible defaults; "what was deployed" is unanswerable at baseline time |
| latency per segment | `orchestrator` | 19 of 25 modules untimed; no phase can claim a latency effect |

**Metric:** every segment timed — 19 of 25 modules are untimed today — and every
invariant I1–I7 computable from emitted telemetry alone, without a DB join written by
hand for the occasion. **The latency numbers at the end of this phase are the
reference every later phase is measured against.**

### P2a — Fallout cleanup  ·  owner: chat  ·  FIRST

P1a orphaned more than its own sweep found, because `planner/__init__.py` re-exports
`parse` and `Plan`/`SubQuestion` — so an "is anything importing this?" check saw the
re-export and not the fact that nothing consumes it. **The import-graph check I
specified is what failed**, which is why this leads P2 rather than sitting in a backlog.

Verified closure, measured 2026-09-09 — importers outside the file itself:

```
  planner/blueprint.py        194   NONE                     ← orphan root
  planner/parser.py           294   only planner/__init__.py ← the masking re-export
  planner/mobius_parse.py     354   only parser.py
  planner/adapter.py          109   only parser.py
  planner/route_triggers.py   120   only blueprint.py
  state/query_refinement.py   128   only blueprint.py
  ------------------------------------------------------------
  1,199 lines + the __init__ re-export
```

**`planner/schemas.py` (199) STAYS** — nine live importers including `react_loop.py`,
`pipeline/context.py` and both responders. It is the one file in the package that is
genuinely load-bearing, and it is the same shape as `query_refinement.py` in P1a: the
file that looks like it goes with the others and does not.

**Gate:** import-graph proof, suite no worse than the 14-failure baseline, zero
invariant movement — and this time the proof must resolve re-exports rather than stop
at the first `import` it finds.

---

### P2b — Latency telemetry across every module  ·  owner: chat + Eval  ·  NEW REQUIREMENT

Ananth, 2026-09-09. This is a standing product requirement, not a phase deliverable:
**every module reports its own timing, the result is displayed in diagnostics AND
stored, and we can re-run it to prove we have not drifted.**

**Why it is more than a stopwatch.** The stated purpose is to find *bad writes, bad DB
calls and loops* — work that is silently repeated or silently slow. Today 19 of 25
modules are untimed, so none of those are visible. Everything this review has found
argues the same way: the system is structurally unable to report its own failures, and
duration is the one signal that exposes repetition without needing anyone to have
anticipated the specific bug.

**What it must produce, per turn:**
- a timing for every module the turn touched — not a total, a breakdown
- **DB call count and cumulative DB time per module**, because a loop that issues the
  same write forty times is the target and a single total hides it
- LLM call count and time per stage, which `llm_calls` already has and nothing joins
  to the turn's module breakdown
- **stored**, not just emitted — a turn's timing must be readable after the fact, or it
  is another producer without a consumer
- **rendered in diagnostics**, so a slow turn is diagnosable by the person who saw it

**The exercise, and why it is the right one.** Eval owns a 22-question bank already
used for overlap calibration. Running that bank in **fast mode** — one question, then
the series — gives a repeatable baseline across a fixed input set rather than a
synthetic benchmark. It answers "what is actually working" and it re-runs, so drift
becomes measurable instead of anecdotal. Same discipline as the refactor gate: a frozen
corpus, compared against itself.


**SPAN IDENTITY IS THE NODE KEY — Ananth, 2026-09-09: "shouldn't the span also map to
our schema in some regards, else what is the point of those modules?"**

He is right, and it is the difference between telemetry and instrumentation. If spans
carry their own ad-hoc names we end up with **two independent decompositions of the
same system** — 36 schema nodes and N arbitrary spans — and neither can check the
other. Span `name` must be the node key from `docs/chat-schema/chat-dev.json`.

**What that buys, beyond tidiness:**

1. **The schema becomes instrumented.** Every node gets real p50/p95 and real call
   counts beside its findings and its rating. A red node stops being a judgement and
   starts carrying a number.
2. **The two artifacts become RECIPROCALLY FALSIFIABLE**, which is the part that
   matters. A span with no matching node means the schema is incomplete — we are
   modelling something that does not exist and missing something that does. A live node
   that never produces a span is dead or mis-modelled. **Today neither error is
   detectable:** the schema is hand-written and nothing contradicts it, which is the
   same "nothing fails loudly" shape as every finding on this page, applied to our own
   map.
3. **The readiness ratings get evidence.** A node rated amber on suspicion can be
   confirmed or refuted.
4. **It closes the loop on the phase's own purpose.** P2b exists to make absent
   producers detectable; a span set that cannot be checked against the model of the
   system is itself an unverifiable producer.

**Concretely:** `span.name ∈ node keys`, with a generator check that fails when a span
name is not a known node, or when a live node produces no span across a corpus run.
That check belongs in `refresh.sh` beside the roadmap's unassigned-bug check — same
rule, same failure mode.

**One honest limit:** some spans are finer than any node — a single tool call inside
`react_loop`, a single DB write inside `state_load`. Those are CHILD spans carrying the
parent's node key plus their own local label. The mapping is node → span *tree*, not
node → span. A child span whose parent is not a node is still a schema gap.

**PROVIDER STATE: CAPTURE NOW AND LABEL IT — Ananth's ruling, 2026-09-09**, in answer
to whether to wait for the Anthropic credit issue to clear. And his aim makes the label
the control rather than a caveat: **lower latency with the SAME provider through the
refactor.** So every later run is compared like-for-like against a Vertex-only fleet,
and a provider change invalidates a comparison rather than explaining it.

**The label must live in the DATA, not in this document.** A note here is not
queryable; a stamp on the row is. `docs/chat-latency-provider-stamp.json` holds the
baseline stamp, and the per-turn telemetry must carry the same fields, or in six weeks
nobody can tell which runs are comparable.

Stamp as captured, 24h to 2026-09-09 — 1,975 calls, 309 failures:

```
  vertex  gemini-2.5-flash   978 calls,  1 fail   avg  5,544ms  p50  4,669  p95 15,608
  vertex  gemini-2.5-pro     691 calls,  9 fail   avg 21,172ms  p50 20,034  p95 38,486
  anthropic  ALL 11 models — 100% failing since 2026-09-07T00:58:43Z
  groq       126 of 133 failing; openai/gpt-oss-20b served 7 of 7
```

Two things I got wrong earlier and corrected in the stamp: groq is **per-model**
failing, not per-provider — I had recorded it as 100% down. And the pro numbers are not
a mean hiding a tail: **p50 is 20.0 seconds and p95 is 38.5.** The whole distribution
is slow. Any per-module breakdown has to explain where a 20-second median call sits
inside a turn, because that is the number a user feels.

**EVAL HAS RULED, 2026-09-09** — full answers in `docs/p2b-latency-telemetry-eval.md`.
The reframing is theirs and it is better than the question I asked.

**Latency here is THREE layers and one instrument cannot serve all three:**

| Layer | Dominated by | Instrument | Owner |
|---|---|---|---|
| 1 · routing — Σ(llm calls × per-model latency) | which stage pins Pro (4× flash) | the 2,750-turn corpus, stratified mode × bypass × per-stage model | chat builds the replay runner, to Eval's spec |
| 2 · code — `wall − llm` | loops, bad DB calls | the 22q, provider-independent | Eval owns the runner (`/eval/bank` exists) |
| 3 · counts — writes/module, calls/model/stage | the 40-write loop, a stray Pro call | either set, **n=1** | chat's span emitters |

So the 22q is the **wrong** instrument for the wall-clock baseline and the **right** one
for the loop hunt. The stratified corpus *is* the routing instrument — don't rebuild
the bank for routing coverage and don't build a third one.

**Signal semantics, which change what the phase optimises for:**
- **Counts are signal at n=1.** A loop is 40 writes every run; a stray Pro call is +1
  every run. Both target bug classes show in a single run, no statistics. This is the
  PRIMARY detector.
- **Per-call LLM latency is stamped once, not re-measured per turn.** Routing latency =
  per-turn counts × stamped per-model latency. That is how a 20s median becomes
  attributable rather than noise.
- **Wall/DB deltas need a noise floor: ≥5 runs first.** Report p50 and p95 per module,
  **never the mean** — the mean is eaten by the tail and the tail is where the loop is.

**Control set to pin:** model mix, input set, caller_mode (never mix quick and
agentic), warm state (discard a warm-up; RAG is min=max=1), serialized runs.

**Four additions to the taken design decisions, all Eval's:**
1. **Label each count by its TARGET** — "40 writes to `chat_state`" is a loop, "40
   writes across 40 tables" is a busy turn, and a bare integer cannot tell them apart.
2. `n` ships in v1, not v2.
3. **Acceptance is a same-turn read-back AGAINST A NAMED ARTIFACT**: one real turn on
   the live path → the stored span row exists → the diagnostics panel renders from that
   row → one test asserts all three. A row in isolation is instance 13.

   **The artifact must be named, not just required** (Chat Master, 2026-09-09, from the
   PHI failure): they performed a read-back on the PHI fix and it PASSED — against a log
   line that carried `correlation_id` because it was the *diagnostics envelope*, while
   the `llm_calls` row the fix was meant to populate stayed NULL. **A read-back of the
   wrong artifact is indistinguishable from a successful one.** So the test asserts
   against the stored span row that diagnostics renders from — not an emitter log, not an
   in-memory object, not the nearest thing that happens to have the field.
4. **Stamp per MODEL, not per provider** (flash and Pro are 4× apart inside Vertex),
   and the stamp needs a READER — a baseline-compare that refuses or red-flags a run
   whose model mix differs. Without that consumer the stamp is a labelled producer
   nobody enforces.

**Still open, put back to us:** Eval is *inferring* "fast mode" means `chat.copilot`.
The concrete config needs confirming — if it is copilot it is a good lens for layers
2–3, but its numbers do not represent agentic latency.

**Eval also answered the two long-open items:**
- **Coverage signal** — replace filename matching with two layers: **reachability**
  (AST-walk each collected test's call graph, does it actually call the node's
  entrypoint) shipped now, and **contract tags** (`@pytest.mark.guards("queue:no_silent_loss")`)
  audited by Eval. Rendered as an enum where only the top state shows a tick: **ABSENT
  · PERIPHERAL · GUARDED · ASSERTS-NOTHING**. Eval starts the Layer-2 audit on the four
  REDs once Layer 1 is wired.
- **Assertability rule:** *a decision is assertable iff the inputs it consumed are
  persisted alongside the outcome.* Outcomes-only tell you what happened, never why.
  Highest-leverage single change is persisting **`terminated_by`** — it unlocks both the
  deterministic critic-required function and the 203-turn budget-exhausted audit.

**And a flag Eval added that I had not:** the NULL `correlation_id` does not block P2b,
but leaving it unmarked is itself a producer-13 — a future consumer will join
`llm_calls` to turns, get 55% of rows and believe it has all of them. Mark the column
**non-joinable** or populate it.

**Two constraints from this program's own findings:**
1. **Instrument before optimising.** No latency claim is admissible until the baseline
   exists — the same rule that made P1 forfeit its own latency claim.
2. **The measurement must not be the thirteenth instance.** A timing emitter with no
   reader, or a stored row nothing queries, reproduces the exact defect this phase
   exists to remove. Reader and writer ship together.

---

### P3 — One decision point  ·  owner: chat  ·  ratifier: Tech Review

| Item | From node |
|---|---|
| completion-extension gate calls `evaluate()` instead of deciding inline | `governor` — two policies, one ledger, **155 seconds apart** |
| a stated rule for when the critic is required, as a pure function over `(mode, sources, signal, answer, terminated_by)` | `critic` — 203 budget-exhausted turns ship unaudited |
| resolve `master_objective`: revive on the ReAct path, or retire it and delete `continuity` + 4 readers | `run_pipeline`, `continuity` |
| resolve the four clarify mechanisms down to the one that runs | `clarification` |

**Metric:** number of modules that can grant an extension round: 2 → 1. Turns
audited where `terminated_by == budget_exhausted`: 0 → the rule's stated target.
I4 and I5 will move **by design** here — this is the one phase where that is the
point, and the expected delta must be predicted before the cut and compared after.

### P4 — Split  ·  owner: chat  ·  ratifier: Tech Review + Eval

Only after the gate has worked three times, and with the P2 latency baseline in hand.

| Target | Size | Split named in the findings |
|---|---|---|
| `react_loop.py` | 6,113 lines | Ananth's item; measured in the node |
| `integrate.py` | 1,887 lines | already three named passes — A / B / C |
| `prompts.py` | 1,365 lines, **no test file** | separate the parameter planner from the prompt generator |
| `orchestrator.py` | 1,902 lines, 31 log-and-continue | the turn owner |

**Metric:** every extracted unit has a test file; total lines roughly flat (a split
that shrinks the total is doing something else too, and should be a separate change).

### P5 — Config UX  ·  owner: chat + Prompt Studio owner  ·  ratifier: Tech Review

The governor's `_MODE_DEFAULTS`, the directive→composition map and the
role→reasoning_depth map move to the control plane the Prompt Composition Studio
already has. This is where "change model speed and latency without a deploy" lands.

**Hard prerequisite, from the `governor` node:** `confidence_bar` is unbounded, and
setting agentic to `"low"` silently disables the mandatory groundedness floor for
every agentic turn. A dropdown that can turn off the safety audit needs a guard, not
a save button. **No UX ships before that bound exists.**

---

## 3b. Process rules earned during the program

Each of these came from something that actually went wrong. They are here because
they will recur.

**A subagent audits the brief, not the source.** During P1a, Chat Master dispatched
the import-graph sweep to a subagent and, in writing its prompt, collapsed two
adjacent lines of the work order — a delete-list entry for `refined_query.py` and a
STAYS caveat for `query_refinement.py` — into one false sentence naming the wrong
file. The subagent did honest work against that paraphrase, correctly found the named
file had no live importers, and reported "the spec was wrong." It was auditing the
paraphrase. That reached me twice as a defect in my artifact, the second time with
more confidence than the first.

Two things stopped it: the subagent re-derived the import graph **from the code**
rather than trusting its brief, and I grepped both documents instead of deferring to
a confident peer. **Rule: when a delegated check reports that the spec is wrong, read
the spec before believing it — the brief is not the spec.** And when handing a
module list to a subagent, pass the file paths verbatim rather than a summary of why
each is on the list.

This is the same shape as two findings already in the log: a filter that makes an
answer look complete, and reading a code default as deployed behaviour. In all three
a faithful process runs against a lossy copy of the truth and produces a confident
wrong answer.

**Every deploy in this program builds from a DIRTY working tree.** P1a's image was
built from `f2aac16` plus another session's uncommitted `frontend/platform.html` and
`db/schema/051_*.sql`, because `gcloud builds submit` uploads the working directory,
not the committed SHA — the deploy log says `working tree: DIRTY` outright. Chat
Master flagged it rather than letting it pass. Neither file affects chat behaviour,
but **a deployed revision is therefore not byte-identical to its commit**, so no
revision is a clean before/after reference point while the shared checkout carries
other sessions' work. Anyone reading a phase's live behaviour as attributable to that
phase's commit alone is over-claiming.

**TWO SESSIONS ARE EDITING ONE WORKING TREE, and this is now a live hazard rather
than a theoretical one.** Observed 2026-09-09 01:5x: while Chat Master's P1c
deletions (`continuity.py`, `master_objective.py`, `objective_eval.py`,
`user_context_resolution.py`, `user_leverage.py`) sat uncommitted in
`mobius-chat`, the LLM Agent was concurrently editing `app/services/llm_analytics.py`
and `tests/test_llm_analytics.py` in the same tree — wiring `module_key` /
`variant_id` into the `llm_calls` writer.

The specific danger is staging, not merging. P1a was staged as `git add app/ tests/`,
which was safe **only because** no other session had touched those directories at
that moment. It now has: `tests/test_llm_analytics.py` is under `tests/`. The same
command today would sweep another team's uncommitted work into a refactor commit,
which is a failure this fleet has already had once in a shared checkout.

**Rule: stage refactor commits by explicit path, never by directory**, and read
`git status` immediately before committing rather than trusting the state from when
the work started.

**It does NOT affect the gate.** I2 and I4 are computed from `chat_turns.thinking_log`;
the LLM Agent's change writes `llm_calls`. Different table, no overlap with any
invariant. Recorded so nobody assumes contamination that isn't there — and so nobody
assumes safety on the next change either, since a concurrent edit to the LLM call
path itself WOULD move latency and could move I5 once it is un-deferred.

**Ananth's standing instruction, 2026-09-08: LOG findings, do not spin off work.**
Cross-seat items get written down and handed over only when the owner is already
engaged. The reason is this exact situation — a peer acting on a finding mid-flight
changes the code underneath a running measurement.

**Where the work lands.** P1a was committed to `main` in the shared `mobius-chat`
checkout rather than a branch. Chat Master flagged the choice rather than making it
silently: branching a checkout that other sessions and the schema generators read
live would break them mid-flight. Ananth's call; recorded here so it is a decision
and not a habit. Chat also staged `app/` and `tests/` explicitly rather than `-A`,
correctly leaving another session's `db/schema/051_*.sql` and `frontend/platform.html`
uncommitted — the shared-checkout discipline this program needs.

## 3c. Bugs are fixed inside their module's refactor

**Ananth's ruling, 2026-09-09:** when we refactor a module, that module's logged bugs
get fixed in the same pass. Not as a separate remediation phase, not as a backlog.

This changes what the phases mean. P3/P4/P5 are no longer "restructure and move on" —
each is **restructure + close that module's findings**, and the node's findings list is
the checklist for its own refactor. A module is done when it is both restructured and
its bugs are gone, and the roadmap's per-node bug count is the acceptance criterion.

**Why it is the right sequencing rather than a convenience.** Every bug on this page is
attached to a node, and the person restructuring a module is the only person who will
ever hold its whole shape in their head at once. Deferring a fix to a later pass means
paying the comprehension cost twice and re-deriving why the bug was safe to fix — which
is precisely how the `cf_intent` and `query_refinement` near-misses happened.

**What it does NOT change:** the gate still runs per change, the invariants still have
to hold, and a fix that moves an invariant still needs a named, reviewed diff. Bundling
a fix with a restructure does not bundle their evidence — otherwise "the module was
refactored and the tests pass" silently becomes the proof for a behaviour change nobody
reviewed on its own terms.

**And a finding that turns out to need a PRODUCT decision leaves the pass and goes to
Ananth** rather than being resolved by whoever is holding the file (Chat Master's
condition, accepted). `/pipeline` is the precedent — a UI deletion wearing a refactor's
clothes.

**Carve-out:** cross-module and cross-repo items stay separate — the PHI classifier
gap, the JWTs in request logs, the queue durability work, the RAG write surface. Those
have their own owners and are already listed under "Not in this program".

## 3d. Definition of done for a node — production readiness

**Ananth, 2026-09-09:** *"when chat is done I want us to test but also make the module
production ready — test = unit test + latency test."*

A node's pass is finished when **all five** hold. Four are computable; the fifth is a
judgement that has to be argued.

### 1 · Findings closed, each with its own evidence
Every `OWNER(chat)` finding on the node is fixed, and each has a before/after in the
commit. Bundling a fix inside a restructure does not bundle their evidence — otherwise
"the module was refactored and the tests pass" becomes the proof for a behaviour change
nobody reviewed. Findings belonging to other seats stay open and are named as such.

### 2 · Unit test — coverage reaches GUARDED
Not "a test file exists". Eval's enum, and only the top state counts:

```
ABSENT           nothing calls the node's entrypoint
IMPORTED-NOT-CALLED  imported, never called
PERIPHERAL       called, no contract tag
GUARDED          called + a contract tag Eval has audited
ASSERTS-NOTHING  tagged, but the assertion cannot catch the defect
```

The node's tag names the failure mode from its own findings —
`@pytest.mark.guards("state_load:no_silent_reset")`. **Reachability is mechanical and
mine; the audit that the assertion would actually fail is Eval's.** A node cannot mark
itself GUARDED.

### 3 · Latency test — assert the COUNTS, report the distribution
Eval's ruling, and the distinction is what makes this testable at all:

- **Counts are deterministic — assert them at n=1.** "This module issues exactly N DB
  reads to these targets" is a unit-testable claim that fails the moment someone adds a
  read inside a loop. This is the assertion.
- **Wall time is not** — p50 4.7s against p95 15.6s on flash alone. A wall-time
  assertion is a flake generator. Report **p50 and p95 per module, never the mean**, and
  treat a move as signal only against a noise floor from ≥5 runs.
- **A 0 is "not measured", never "free."** A node without a span cannot pass this.

### 4 · Observability — the node can report its own failure
It emits a span under its own node key, and **there exists a code path by which its
failure is recorded**. This is the phase's own rule turned on the node: if the only
evidence of a failure is that something downstream looks wrong, the node is not ready
however green its tests are.

### 5 · Rating — of the guarantee, not the construction
Technical Review's ruling. Clean structure around a lossy guarantee rates **lower**,
not higher. A node leaves its pass rated on what it now guarantees, argued in its
findings, not on how tidy the code became.

---

**`state_load` as the worked example**, since it is first:

| | now | done when |
|---|---|---|
| findings | 5 (4 chat, 1 DB seat) | 4 closed with evidence; the DB-seat one named and left |
| coverage | **ABSENT** | GUARDED — `state_load:no_silent_reset`, audited by Eval |
| latency | **p50 1,229ms · p95 2,192ms**, 57 of 107 spans over 1s | asserts `n=1` per read to each of its four targets; p50/p95 reported against a ≥5-run floor |
| observability | emits a span | a failed read is *recordable* — today it returns `None` and vanishes |
| rating | RED | argued, not assumed |

**And the latency finding is what the counts were built for.** `state_load`'s four reads
are `chat_state` 369ms, `chat_turn_messages` 909ms, `chat_turns` 1,452ms,
`chat_threads` 605ms — **every `n` is 1**. So it is not a loop; it is four sequential
round-trips. A bare duration would have said "state_load is slow" and sent someone
hunting a loop. Count + target says "four reads, none repeated, all slow", which is a
different fix: parallelise or collapse them.

## 4. Not in this program

Named so they are not silently absorbed:

- **`CHAT_ENV=prod` + `CHAT_AUTH_MODE=optional`** — unauthenticated turns accepted.
  Security posture, not refactor. Needs Ananth's authorisation and staging first;
  no clean unauthenticated POST has been sent.
- **`mobius-rag` unauthenticated corpus write** — `roles/run.invoker → allUsers`,
  and 1 of 79 write routes audited. Owned by payor-policy.
- **HIPAA audit write is fail-open** while the gate is fail-closed. Decision pending.
- **Queue has no delivery guarantee** and no depth alerting. Its own workstream.
- **No retention or cleanup path** for `chat_threads` / `chat_turns`. DB seat.

---

## 5. Sign-off

**Nothing above starts until every row is signed.** Each seat is being asked for a
specific ruling, not general agreement.

**Status note, 2026-09-09.** This table sat at one ☑ while the program ran to the end
of P2 and through the first P3 node. That is a bookkeeping failure, not a governance
one — the seats did rule, and the work moved on their rulings; the table simply was
never updated. It is corrected below. Where a seat ruled on the substance without ever
being asked for a formal signature, the row says so rather than claiming a signature
that was not given — **RULED** is not **SIGNED**, and the distinction is the point of
the table.

| Seat | What they are ratifying | Status |
|---|---|---|
| **Chat Master** | that the chat-assigned bugs are correctly theirs and correctly described (count is generated — see `docs/chat-refactor-roadmap.md`, never hardcoded here); the P1→P5 order; the `master_objective` revive-or-retire call | **☑ RULED BY EXECUTION 2026-09-08/09** — accepted the assignment and delivered P1.1, P1a, P1b, P1c, P1d, P2a and P2b in the stated order, ~31,900 lines removed, zero regressions; caught two of my own errors against the artifact (the `credentialing_envelope` tombstone still reading green, and my "2 acquires for 15 reads" sample straddling a deploy). No separate signature was ever requested — the order was executed rather than ratified. |
| **DB seat** | the table evidence behind the deletions (11 of 13 empty), the FK set, and that `chat_state` / `chat_turns` are safe to read as a replay corpus | **☑ RULED 2026-09-08** — and materially changed the design: ruled it a **differential gate, not a replay of production** (adopted verbatim in §above, because `chat_state` is mutated in place with no history), required stratification on `context_summary` (1,853 present / 897 absent), and caught that PRE was a moving `now() - interval '60 days'` window rather than a frozen set — which is why the corpus is now a committed file. Also filed the cross-node finding that `mobius_chat` has **no query guard**. |
| **Technical Review** | the test gate itself — invariants I1–I7 and the phase order | **☑ SIGNED 2026-09-08** — verified the frozen baseline artifact directly (fingerprint, strata, every cited number) rather than the writeup. Two items for the record below. |
| **Eval** | the replay corpus design: stratification, sample size, and what it can and cannot prove — specifically that answer quality is out of scope for the invariant set | **☑ RULED 2026-09-08/09** — supplied the coverage enum (ABSENT / IMPORTED-NOT-CALLED / PERIPHERAL / GUARDED / ASSERTS-NOTHING) with the rule that **a node cannot mark itself GUARDED**; ruled the latency method (three layers; **counts are signal at n=1**, wall-time needs a ≥5-run noise floor, report p50/p95 never mean, and a count must carry its target); audited `state_load` and ruled it **GUARDED**. Open on their side: Q6 (bandit in the Eval macro schema) and Layer-2 audits of `queue`, `jurisdiction`, `clarification`. |
| **Prompt Studio owner** | that the control plane is the right home for the governor's tables (Phase 4) | ☐ **NOT ASKED YET** — and correctly so: Phase 4 has not started. This is the one row where the blank is accurate rather than stale. Ask before P4 opens, not after. |
| **Ananth** | the two open product calls: revive or retire `master_objective`, and whether removing the `use_react` API field is acceptable | **☑ DECIDED 2026-09-08** — both calls made: *"yes remove use_react, retire master_objective"*. Also settled the prod-count question by ruling there is no prod (*"there is no prod we are in pre-prod"*), and confirmed the endpoint removals after I checked with org_agent and roster agent. |

**Technical Review's two record items, not conditions on their signature:**

1. **P1.1 is now load-bearing for the whole program.** If the deterministic harness
   slips, I3 and I5 stay deferred indefinitely and the program ships without ever
   gating the two invariants most likely to matter — PHI verdict and groundedness
   floor — on anything but hope. The honest gap beats a fake tolerance, but the
   dependency is stated here so a timeline slip is visible rather than discovered.
2. **P3's acceptance criterion is structural, full stop.** P3 is done when there is
   exactly **one writer** to `_pp_extension_rounds_used`. Not when the two constants
   agree; not when one path defers to the other's number. An implementation that
   reconciles 120 and 275 into a shared constant but leaves two call sites both
   permitted to write the counter has **not** closed the finding, regardless of what
   the numbers show at that gate.

**First full-suite baseline, 2026-09-08: 26 tests already failing** (2,593 collected,
2,561 passed, 6 skipped, 128s). **Ananth ruled these are long-standing and must not
block the program**, so the gate handles them the way it handles swallows — a frozen
set it subtracts, monotonic in one direction:

> `docs/chat-test-baseline.json` — 26 tests, captured before any P1a deletion. A
> failure IN the set is not a regression. A failure NOT in the set fails the gate. A
> baseline test that starts passing is reported so the list can shrink. **The list may
> shrink, never grow, without an explicit decision.**

That is a stronger gate than "triage first would have given us", because it keeps
working while the 26 are outstanding and it names any new failure immediately.

**What the 26 actually are, characterised rather than assumed:** 12 of them are two
missing local packages — `pythonjsonlogger` (7) and `opentelemetry` (5) — both
declared in `requirements.txt` (lines 34, 46-50), so that is a local venv gap and not
an unpinned dependency. The remaining 14 are uncharacterised.

**TWO SIZE RATCHETS ARE BREACHED, not one.**
`test_react_split_phase_1i.TestReactLoopRatchet` (react_loop line ceiling) and
`test_api_hygiene_guard.TestMainPySizeRatchet` (main.py size). Somebody built guards
against exactly the growth this program exists to reverse, and both are already
failing. That is P4's acceptance criterion failing before P4 starts, twice.

**ANANTH'S DECISIONS, 2026-09-08 — two of the three open questions are closed:**

1. **`master_objective`: RETIRE.** Not revived on the ReAct path. `continuity` and
   its readers come out in favour of `react_unfinished_reason` /
   `react_unblock_ask`, which already work and are wired at six sites. This moves
   from P3 (decide) to P1 (delete) — it is now a removal, not a reconciliation.
2. **`use_react`: REMOVE the field.** The contract change is accepted.

**And decision 2 changes the evidence the classic-path deletion needs.** While
`POST /chat` accepts `use_react`, the classic path is *reachable but unused* — so
proving a deletion safe means running turns through the new code, which needs the
P1.1 harness. Remove the field and the path becomes **statically unreachable**: no
configuration and no request can enter it. The deletion is then justified by an
import-graph proof plus a green suite, not by empirical replay.

That is a real unblock, and it must not be over-claimed. It licenses **this
deletion**, whose targets are provably unreachable. It does NOT generalise: the
credentialing removal touches 125 references inside live shared modules, and
`master_objective`'s retirement deletes readers that live code still calls. Those
still need the harness.

**Sequencing consequence:** P1 splits.

  P1.1 deterministic replay harness              DONE 2026-09-08, verified
  P1a  remove use_react -> classic path unreachable        DONE 2026-09-08, VERIFIED
       2,181 lines removed. Gate exit 0: 0 regressions, I2 383->383, I4 0->0,
       I7 506->502 (fell, as required). Unreachability re-proved independently:
       zero importers for all six modules, no use_react anywhere in app/,
       orchestrator imports clean.
  P1b  NOT BLOCKING — Ananth 2026-09-08: "we have had these failures for a
       while." The 26 are frozen as an accepted baseline the gate SUBTRACTS
       (docs/chat-test-baseline.json), rather than a queue to clear first.
  P1c  retire master_objective + continuity      needs the harness
  P1d  credentialing code removal                needs the harness + the two
       roster-skill items below

**P1a verified 2026-09-08, independently.** I re-ran the full suite myself
(2,530/2,560, 25 failed, 147s), re-ran the gate (exit 0), re-proved unreachability by
import grep, and measured the diff at 2,181 `.py` deletions rather than accepting the
number. My 1,159 was app-code only and covered the first layer; the gap is almost
entirely test files that exclusively exercised deleted modules.

**Chat Master's three corrections, adjudicated:**

- **Correction 1 (my STAYS/DELETE call was inverted) — NOT UPHELD, and it matters
  because acting on it would introduce the error it warns about.** The written order
  and this document both say `state/refined_query.py` (226) is in the delete list and
  `state/query_refinement.py` (128) stays because `blueprint.py:6` imports
  `reframe_for_retrieval` from it. That is what the docs say and what the code now
  does: `refined_query.py` is gone, `query_refinement.py` is untouched and
  `blueprint.py` still imports it. The two-file hazard is real and worth the flag —
  it is why I called it out in the first place — but the order was not inverted and
  the findings doc needs no correction here.
- **Correction 2 (transitive layer is TRIM, not DELETE) — UPHELD.**
  `plan_display.py` is live in ReAct (`react_loop.py:107`, `react/prompts.py:34`) and
  `message_resolver.py` is called from the shared orchestrator preamble before the
  branch. Both correctly left in place. I flagged them as *suspected* sweeps and said
  the sweep had not been done; they did it and the answer is narrower than feared.
- **Correction 3 (2,181, not 1,159) — UPHELD and verified.** 1,298 app + 883 test.

**The out-of-scope fix is KEPT, not reverted.** `test_latency_no_regrets` patched
`orchestrator.clear_progress`, which is not an attribute of that module and never has
been — it was failing on that regardless of `use_react`. That is the "newly passing 1"
and it is a genuine pre-existing failure fixed, not a regression masked; I re-ran the
suite independently to confirm. The known-failing baseline shrinks 26 -> 25, which is
the direction its own rule permits, and the reason is recorded in its `shrink_log`.

**P1.1 verified 2026-09-08.** `tests/harness/`, 31/31 passing, covering I1/I2/I4/I7.
It invokes the real `run_react` with `_call_llm_json` patched by responses keyed on
call number — pinned inputs, code-only diffs, which is the mechanism Technical Review
asked for. **Two limits, stated so "harness done" is not read as more than it is:**
it tests invariant *logic* on ~10 synthetic scenarios and does NOT replay the frozen
2,750 (the baseline supplies derived constants only); and its I7 is scoped to
`react_loop` at ≤21 swallows, where the global count is 506 across 233 modules — a
deletion elsewhere would not trip it.

**`use_react` removal has no behavioural consumer.** `deep-research` sends the key at
`run_research.py:54` and `run_turn.py:40`, but both send `True`, and `ChatRequest`
carries `model_config = {"extra": "ignore"}` — added deliberately after the
2026-04-18 disconnect. So the key is silently dropped and they land on the ReAct path,
which is the only path. Tell deep-research to drop it as courtesy, not coordination.

**P1d absorbs the roster-skill coupling** (Ananth's call, 2026-09-08). org-agent is
closed out — it never calls chat's credentialing endpoints; it talks to the roster
skill directly as its org master, and its only other references are two role labels.
Outside mobius-chat there are exactly two callers, both in the roster skill:

  1. `/chat/credentialing-runs/{runId}/validate` — `pipeline-chat.js:637,668`.
     The one genuinely live coupling. Either the skill drops the call or absorbs
     the logic.
  2. `/chat/roster-truth/{org}/provider/{id}/summary` — `nppes_validation/
     routes.py:2527`, a server-side proxy to **a path chat never registered**
     (chat's is `/chat/credentialing-runs/{run_id}/roster-truth`). It has been
     404ing. Their bug regardless of the deletion; fix or remove it.

The 114 `app.js` references are chat's OWN frontend, not an external consumer — they
come out with the workflow rather than blocking it. That is Chat FE work, not a veto.
I had described this as a sibling service depending on the surface; it is one call
site pair in one file.

3. **Prod row counts — WITHDRAWN as a blocker. Ananth was right and I was wrong.**
   Two reasons, and I should have caught the second before writing it down.

   The tables are not being dropped, so the irreversible half is already off the
   table and row counts were only ever evidence for it. And **there is no
   production.** Verified rather than assumed: three GCP projects exist, and the
   only live chat is `mobius-chat` in `mobius-os-dev`. `mobius-chat-api` /
   `-worker` in both `mobius-staging-mobius` and `mobiusos-new` were last deployed
   **2026-02-05** — seven months ago. `mobius-os-dev` IS the environment, so its
   row counts are the evidence, not a weak proxy for evidence somewhere else.

   I imported the DB seat's dev-vs-prod caveat without checking whether the second
   half of that distinction exists. The caveat was sound reasoning about a world
   with a production deployment; it was not a fact about ours.

   **But checking it surfaced a real blocker that row counts were hiding, and it
   points the other way.** Chat's 13 credentialing routes DO have callers:

   - `mobius-chat/frontend/static/app.js` — **114 credentialing references**, plus
     refs in `index.html`, `roster-unified.html`, `signin.html`, `pipeline.html`.
   - `mobius-skills/provider-roster-credentialing/static/pipeline-chat.js` calls
     `credentialing-runs/` — **the skill service that supposedly owns the domain
     calls back into chat's routes.** So the relationship is not clean duplication
     with chat as the redundant copy; the two are entangled, and that service is
     live and actively iterated (revision 00094).

   So P1d is NOT a code-only deletion behind an empty schema. It is a removal that
   takes a frontend surface and a sibling service's dependency with it. That is a
   larger and different change, and it needs the Chat FE seat, which I do not hold.

   One thing I checked and will not over-claim: two of the FE element ids the JS
   binds to (`credentialingPreferOutsideIn`, `credentialingUploadRoster`) do not
   exist in any HTML, so those listeners silently never attach — that part is dead.
   I checked two ids out of 114 references. That is a hint, not an audit, and it is
   the FE seat's call, not mine.
4. What the 83 integrator-bypass turns matching no known bypass actually are.
5. Whether `should_run_critic`'s rule is per-mode or global.
