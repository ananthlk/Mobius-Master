# Chat refactor — program plan

**Status: DRAFT, awaiting sign-off. No refactor work starts until the sign-off table
at the end is complete.**

Companion to `docs/chat-schema-findings.md` (73 bugs · 66 checks · 60 verified-ok
across 35 nodes), which is generated and must not be hand-edited. This document is
hand-written: it sequences that inventory into work, and defines the pre-test /
eval / post-test gate every phase has to pass.

---

## 0. The finding that shapes the whole plan

**Most of what we want to change is currently unobservable, so it cannot be
baselined.** This is not a caveat — it is the reason Phase 0 exists and blocks
everything else.

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
it is. Phase 0 is not preparation for the work; it is the work that makes the rest
provable.

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

**The replay corpus.** 2,741 live turns over 60 days are already in
`chat_turns` with their `thinking_log`. That is the baseline set — real traffic, not
synthetic. Every measurement in the findings log was taken from it, so the same
queries are the harness. Eval to rule on stratification (by mode, by
`unfinished_reason`, by bypass class) and on how many turns are enough.

**Invariants — must be identical before and after, every phase.** These are
assertions about the envelope, not about answer text:

| # | Invariant | Why it is the right assertion |
|---|---|---|
| I1 | every turn produces exactly one terminal envelope | catches a refactor that drops a finalize path — there are 12+ `_finalize_response` call sites |
| I2 | the set of turns that bypass the integrator is unchanged | 383 today; a change here is a change in what the user sees |
| I3 | PHI gate verdict per turn is unchanged | fail-closed must stay fail-closed |
| I4 | `rounds_used` and `max_rounds` per turn are unchanged | the governor's arithmetic is the thing most at risk |
| I5 | groundedness floor ran / skipped per turn is unchanged | 966 / 634 today |
| I6 | the source set per turn is unchanged | retrieval must not shift under a refactor of control flow |
| I7 | no new swallowed exception | count `log-and-continue` handlers; the number may fall, never rise |

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

1. Anything that makes the system observable comes first — you cannot baseline blind.
2. Deletion before restructuring — do not refactor code you are about to remove.
3. Unify a decision before moving it — do not build a UX over a policy that lives in
   two places.
4. Split large modules last — the highest-risk, highest-blast-radius work, done when
   the test gate is proven by three earlier phases.

---

## 3. Phases

### Phase 0 — Make it measurable  ·  BLOCKING  ·  owner: chat + Eval

Nothing else starts until this lands.

| Item | From node | Why it blocks |
|---|---|---|
| governor emits its own decisions | `governor` | the round policy is invisible; I4 cannot be asserted from a module that logs nothing |
| `react_trace` emit failure stops being a `logger.debug` swallow | `react_loop` | the single observability window can fail silently |
| persist `keep` | `react_loop` | curation is untestable retrospectively without it |
| effective-config surface | `governor` | 116 knobs on invisible defaults; "what was deployed" is unanswerable at baseline time |
| latency per segment | `orchestrator` | 19 of 25 modules untimed; no phase can claim a latency effect |

**Metric:** every invariant I1–I7 computable from emitted telemetry alone, without a
DB join written by hand for the occasion.

### Phase 1 — Delete  ·  owner: chat  ·  ratifier: DB seat (tables), Tech Review (contract)

Lowest risk in the program and the largest clarity gain. Nothing here changes live
behaviour if the measurements hold.

| Target | Size | Evidence | Caveat that must be cleared first |
|---|---|---|---|
| classic path (`resolve`, `plan`, `classify`, `clarify`, `refined_query`, `clarification`) | 1,159 lines + 54-line branch | imported by nothing but the branch; 3 user-facing strings, 0 live occurrences in 2,741 turns | `use_react` is a per-request API field — removing the branch is a **contract change**; and `query_refinement.py` looks legacy but `blueprint.py` needs it |
| `credentialing_envelope` — 7 of 8 functions | 177 lines | 7 have zero callers | none; this one is genuinely free |
| credentialing workflow | 8,994 lines + 125 refs in shared modules | 11 of 13 tables empty; `provider-roster-credentialing` skill owns the domain | **dev DB only** — prod row counts and route callers not checked; the 125 scattered refs are the real work, not the file deletions |

**Metric:** lines removed; `log-and-continue` handler count down; **zero** invariant
movement. If any invariant moves, the deletion was not dead code.

### Phase 2 — One decision point  ·  owner: chat  ·  ratifier: Tech Review

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

### Phase 3 — Split  ·  owner: chat  ·  ratifier: Tech Review + Eval

Only after the gate has worked three times.

| Target | Size | Split named in the findings |
|---|---|---|
| `react_loop.py` | 6,113 lines | Ananth's item; measured in the node |
| `integrate.py` | 1,887 lines | already three named passes — A / B / C |
| `prompts.py` | 1,365 lines, **no test file** | separate the parameter planner from the prompt generator |
| `orchestrator.py` | 1,902 lines, 31 log-and-continue | the turn owner |

**Metric:** every extracted unit has a test file; total lines roughly flat (a split
that shrinks the total is doing something else too, and should be a separate change).

### Phase 4 — Config UX  ·  owner: chat + Prompt Studio owner  ·  ratifier: Tech Review

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
| **Chat Master** | that the 16 chat-assigned bugs are correctly theirs and correctly described; the Phase 1→4 order; the `master_objective` revive-or-retire call | ☐ |
| **DB seat** | the table evidence behind the deletions (11 of 13 empty), the FK set, and that `chat_state` / `chat_turns` are safe to read as a replay corpus | ☐ |
| **Technical Review** | the test gate itself — whether invariants I1–I7 are the right assertions and whether the phase order is sound | ☐ |
| **Eval** | the replay corpus design: stratification, sample size, and what it can and cannot prove — specifically that answer quality is out of scope for the invariant set | ☐ |
| **Prompt Studio owner** | that the control plane is the right home for the governor's tables (Phase 4) | ☐ |
| **Ananth** | the two open product calls: revive or retire `master_objective`, and whether removing the `use_react` API field is acceptable | ☐ |

Open questions carried into sign-off, unresolved on purpose:

1. Revive `master_objective` on the ReAct path, or retire it in favour of
   `react_unfinished_reason` / `react_unblock_ask`? Opposite work either way.
2. Is removing the per-request `use_react` field an acceptable contract change, and
   does any client send it?
3. Prod row counts for the credentialing tables — dev being empty is not a mandate.
4. What the 83 integrator-bypass turns matching no known bypass actually are.
5. Whether `should_run_critic`'s rule is per-mode or global.
