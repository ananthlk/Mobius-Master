# Chat refactor — program plan

**Status: DRAFT, awaiting sign-off. No refactor work starts until the sign-off table
at the end is complete.**

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
| classic path (`resolve`, `plan`, `classify`, `clarify`, `refined_query`, `clarification`) | 1,159 lines + 54-line branch | imported by nothing but the branch; 3 user-facing strings, 0 live occurrences in 2,741 turns | `use_react` is a per-request API field — removing the branch is a **contract change**; and `query_refinement.py` looks legacy but `blueprint.py` needs it |
| `credentialing_envelope` — 7 of 8 functions | 177 lines | 7 have zero callers | none; this one is genuinely free |
| credentialing workflow — **code only** | 8,994 lines + 125 refs in shared modules | `provider-roster-credentialing` skill owns the domain and references `provider_roster` directly, so this is **duplication, not disuse** — a stronger argument than emptiness | needs prod counts + the skill owner confirming who writes `provider_roster`; the 125 scattered refs are the real work |
| credentialing tables — **DO NOT DROP** | 11 empty tables | DB seat's ruling: empty tables cost nothing, dropping is the irreversible half, and row counts do not license it | revisit after the code is gone and they have sat empty a quarter |

**Metric:** lines removed; `log-and-continue` handler count down; **zero** invariant
movement. If any invariant moves, the deletion was not dead code. Explicitly NOT a
latency metric — the baseline for that does not exist until P2.

### P2 — Instrument: latency and decisions  ·  BLOCKING for P3–P5  ·  owner: chat + Eval

Nothing after this point can be measured without it.

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

| Seat | What they are ratifying | Status |
|---|---|---|
| **Chat Master** | that the 16 chat-assigned bugs are correctly theirs and correctly described; the P1→P5 order; the `master_objective` revive-or-retire call | ☐ |
| **DB seat** | the table evidence behind the deletions (11 of 13 empty), the FK set, and that `chat_state` / `chat_turns` are safe to read as a replay corpus | ☐ |
| **Technical Review** | the test gate itself — invariants I1–I7 and the phase order | **☑ SIGNED 2026-09-08** — verified the frozen baseline artifact directly (fingerprint, strata, every cited number) rather than the writeup. Two items for the record below. |
| **Eval** | the replay corpus design: stratification, sample size, and what it can and cannot prove — specifically that answer quality is out of scope for the invariant set | ☐ |
| **Prompt Studio owner** | that the control plane is the right home for the governor's tables (Phase 4) | ☐ |
| **Ananth** | the two open product calls: revive or retire `master_objective`, and whether removing the `use_react` API field is acceptable | ☐ |

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
2,561 passed, 6 skipped, 128s) — including this program's own guard,
`TestReactLoopRatchet::test_react_loop_loc_under_ceiling`. The gate cannot read
"tests pass" until those 26 are triaged into accepted-baseline or fixed. Filed as a
P1 item.

Open questions carried into sign-off, unresolved on purpose:

1. Revive `master_objective` on the ReAct path, or retire it in favour of
   `react_unfinished_reason` / `react_unblock_ask`? Opposite work either way.
2. Is removing the per-request `use_react` field an acceptable contract change, and
   does any client send it?
3. Prod row counts for the credentialing tables — dev being empty is not a mandate.
4. What the 83 integrator-bypass turns matching no known bypass actually are.
5. Whether `should_run_critic`'s rule is per-mode or global.
