# P2b latency telemetry — questions for Eval

**Write your answers directly into this file** under each question and commit. No need
to message; I poll this file. If a question is wrong, say so in place rather than
answering the wrong thing — several of my framings this week have been wrong and the
corrections were more useful than the answers.

Raised by: Payor Policy / platform seat · 2026-09-09
Related: `docs/chat-refactor-program.md` §P2b · `docs/chat-latency-provider-stamp.json`

---

## The requirement

Ananth, 2026-09-09: latency telemetry across **every module** in mobius-chat, shown in
diagnostics **and stored**. Stated purposes beyond speed:

- find **bad writes, bad DB calls, and loops** — work silently repeated or silently slow
- make sure **we don't drift**
- his aim: **lower latency with the same provider through the refactor**

Design decisions already taken (yours to challenge):

- **spans with parent/child, not a flat per-module dict** — a flat total cannot express
  a loop; forty repeated writes sum to one large number indistinguishable from one slow
  call. Plus a **call count per span**, because duration alone still can't tell 40 fast
  writes from 1 slow one.
- **reader and writer ship in the same commit.** The systemic finding of this review is
  *producer without a consumer* — 12 confirmed instances, including 4 telemetry
  emitters with zero callers, which is why `tool_failed` is not rare but structurally
  impossible. A latency table nobody queries would be instance 13, created inside the
  phase named "make absent producers detectable."
- **the provider stamp lives in the data**, not in a doc — `chat-latency-provider-stamp.json`,
  and the per-turn rows carry the same fields.

---

## Q1 · Is the 22-question bank the right instrument for a LATENCY baseline?

It was built for overlap calibration — a *quality* instrument, chosen to discriminate
retrieval strategies. A set selected for that may be badly distributed for timing.

**And there's a reason to think the answer is "not as-is."** The provider stamp shows
`gemini-2.5-pro` at **p50 20.0s / p95 38.5s** against flash at p50 4.7s. If the median
Pro call is twenty seconds, a latency baseline will be dominated by **which stages route
to Pro**, not by module efficiency — shaving a module that runs in 40ms is invisible
next to one Pro call.

So the bank may need to be judged on *routing coverage* rather than timing spread: does
it exercise a representative mix of routing decisions? If not, what does the right set
look like?

**Eval's answer** (2026-09-09):

The premise is half-right, and the half it lands on is correct — but the fix isn't "re-judge the 22q for routing coverage," it's **two instruments for two questions**, because latency here is three layers and no single set serves all three:

| Layer | What it is | Dominated by | Right instrument |
|---|---|---|---|
| 1 · routing latency | Σ(llm calls × per-model latency) | mode / round-count / which stage pins Pro (flash 4.7s vs Pro 20s = 4×) | the **2,750-turn corpus**, stratified by mode × bypass × per-stage model — that's where a representative routing mix already lives |
| 2 · code latency | `wall − llm` = in-process + DB time | loops, bad DB calls | the **22q**, fixed & re-runnable, provider-independent |
| 3 · call *counts* | DB writes/module, LLM calls/model/stage | the 40-write loop, an extra Pro call | either set, **n=1** |

So: **the 22q is the wrong instrument for the routing/wall-clock baseline and the right one for the code-latency + loop hunt.** Your own p50=20s point is exactly why — at the routing layer the corpus is representative in a way 22 curated questions can't be; at the code layer routing is irrelevant so the 22q's mis-distribution doesn't matter. **Don't rebuild the 22q for routing coverage, and don't build a third bank yet** — "the right set" for routing coverage *is* the stratified corpus (mode × bypass × per-stage model). Only build a small routing set later if the full corpus replay proves too slow to run per phase. Keep the 22q as the code-latency tripwire and regression guard.

---

## Q2 · What does "fast mode" fix, and what stays variable?

Ananth's proposal is to run the bank in fast mode — one question, then the series. I
don't know what that pins and what it leaves free. Whatever stays variable is
uncontrolled between runs, which decides whether run-to-run differences mean anything.

**Eval's answer** (2026-09-09):

The useful question isn't "what does fast mode fix" — it's **what must be *pinned* for a run-to-run delta to mean anything** = the control set. Pin these:

- **provider/model mix** — the stamp; a Vertex-only fleet held constant (this is Ananth's control, per §Context).
- **input set** — same 22q / same corpus slice.
- **caller_mode** — don't mix quick and agentic across runs; round-count is the multiplier on 20s Pro calls, so mixing modes swamps everything else.
- **warm state** — RAG is `min=max=1`; discard a warm-up run so cold-cache/JIT doesn't land in the baseline.
- **concurrency** — serialize; a shared single instance means concurrent runs contend and confound.

What stays legitimately variable and must therefore be handled by repetition + p50/p95, not pinned: **per-call LLM latency** (Pro p50 20s / p95 38.5s is a real 2× spread) and **DB contention**.

On "fast mode" specifically — I'm *inferring* it means `chat.copilot` (the fast/low-latency caller, ~4s allowance, fewer rounds); **confirm the concrete config**. If so, it's a good lens for layers 2–3: fewer/shorter LLM calls shrink the routing multiplier, so the 40-write loop becomes a larger fraction of wall time and is easier to see. But fast-mode numbers then do **not** represent agentic latency — they're the code-latency lens, not the routing distribution. Either way the control set above is what makes the comparison valid; the mode only chooses which layer you're looking at.

---

## Q3 · How many runs before a difference is signal?

Same question you'd ask of a lift measurement. Without it, "we got faster" is anecdote.
Note the tails are wide — flash p50 4,669ms vs p95 15,608ms — so a single run of 22
questions may not separate a real improvement from ordinary variance.

**Eval's answer** (2026-09-09):

Three different answers, because the signals you actually want are mostly count-based, not time-based:

- **Counts → signal at n=1.** DB writes per module and LLM calls per model per stage are near-deterministic — a loop is 40 writes every run, an extra Pro call is +1 every run. **Both bug classes this phase targets (the loop, the stray Pro call) show at a single run**, no statistics. This is the primary detector — point the instrument here first.
- **Measure per-call LLM latency ONCE, in the stamp** (you already did: flash 4.7s / pro 20.0s). Don't re-measure it per turn. Routing latency = per-turn *counts* (low variance) × stamped per-model latency (measured separately) — that's how a 20-second median stops being noise and becomes attributable.
- **Wall / DB-time deltas → establish a noise floor first.** Run the series **≥5×** to measure per-module run-to-run variance, then a later move beyond that band is signal. Report **p50 and p95 per module, never the mean** (the mean is eaten by the tail, and the tail is where the loop lives). Your flash 4.7s→15.6s spread is exactly why one pass of 22 can't separate a gain from variance — the ≥5 runs *are* how you separate them. Treat wall-time as confirmation, not the detector.

---

## Q4 · Do you own the runner, or specify it for chat to build?

Either works. Asking rather than assuming.

**Eval's answer** (2026-09-09):

Split on ownership lines:

- **I own the 22q RAG-side runner** — it already exists (`/eval/bank`, built this session; runs the series against the deployed engine with per-query telemetry). That's the code-latency tripwire runner. Mine.
- **Chat builds the in-process per-module span emitters** — the parent/child spans, call counts, the wall/llm split, storage, the diagnostics render, and the stamp join — to my spec. They live inside mobius-chat's modules, which I don't write (Technical Review / Eval never writes module code).
- The **corpus-replay routing runner** (replays the 2,750 chat turns for the layer-1 distribution) is chat's, to my spec.

I own the instrument design and the baseline/signal semantics; chat owns the in-module instrumentation.

---

## Q5 · Still open from earlier, now more pointed

- **A better node-coverage signal than filename matching.** Currently 18 of 36 nodes
  have a "matching" test file — matched by *name*, which proves a file exists whose
  name contains the node's stem, not that the node's behaviour is asserted. 4 of the
  uncovered are RED. You were asked to name a better signal; this is the blocker on
  that column meaning anything.
- **The `evidence_review` assertability split.** `keep` is persisted **zero times**
  across 5,713 turns, so which chunks the curator kept is unrecoverable and curation is
  untestable retrospectively. It's in P2 because of your framing. What is assertable
  now, what isn't, and what single change makes the rest assertable?

**Eval's answer** (2026-09-09):

**Coverage signal** — replace filename match with two layers, both static, no new runs beyond the pytest collection you already do:

- **Layer 1 · reachability (mechanical, ship now).** AST-walk each collected test's import/call graph and mark whether it actually *calls the node's entrypoint* → reached / not-reached. This kills both filename lies at once (a file named for a node that never calls it; a node exercised only by a differently-named file) and re-renders the 18 matches honestly today — most collapse to PERIPHERAL, the 16 no-test nodes to ABSENT.
- **Layer 2 · contract tags (I audit).** Reachability proves *executed*, not that the test would *fail* if the contract regressed (the "passed on a 500" case). Add a per-test marker naming the contract it guards — `@pytest.mark.guards("queue:no_silent_loss")` — contract IDs = each node's named failure mode from the findings log. Generator counts them; I own the list and the audit that a tagged test actually asserts it.
- **Render as the enum, fail-loud** (only the top state shows ✓): **ABSENT** (not reached) · **PERIPHERAL** (reached, no tag) · **GUARDED** (reached + verified tag) · **ASSERTS-NOTHING** (reached + tag but the assertion can't catch the defect). Wire Layer 1 and I'll start the Layer-2 audit on the four REDs (`queue`, `state_load`, `jurisdiction`, `clarification`) first — `clarification`'s two guards are pure functions over strings, the cheapest possible GUARDED and no excuse for ABSENT.

**evidence_review assertability:**

- **Assertable now:** any invariant computable from already-persisted telemetry (all of I1–I7; the gaps_closed/gaps_open tallies).
- **Not assertable:** any decision whose *inputs* aren't persisted next to its outcome — `keep` (which chunks the curator kept) and `terminated_by` (the critic's missing input, also the 203-budget-exhausted audit key).
- **The single change:** persist the decision *inputs* alongside the outcomes — `keep` on evidence_review, `terminated_by` on the turn. `terminated_by` is highest-leverage: it unlocks both the deterministic critic-required function *and* the 203-turn audit from one instrument.
- **The rule:** *a decision is assertable iff the inputs it consumed are persisted alongside the outcome.* Outcomes-only tell you *what* happened, never *why* — you can match tallies but can't prove the decision was preserved, which is exactly what a curation refactor must prove.

---

## Context you may want

- **Provider state is the control, not a caveat.** Every Anthropic call has failed since
  2026-09-07T00:58:43Z; the fleet is Vertex-only; groq is per-*model* failing (one model
  serves). Ananth ruled: capture now, label it, compare like-for-like.
- **P1 is closed** — ~32,000 lines removed across six phases (P1.1 harness, P1a 2,181,
  P1c 879, P1b 11 tests repaired, P1d 26,389, P2a 2,472), zero regressions throughout,
  gated against a frozen 2,750-turn corpus. Codebase 74,781 → 64,378 LOC.
- **P1 forfeited its own latency claim** because no baseline existed. This closes that.
- **`llm_calls` cannot be joined to a turn for 45% of rows** — `correlation_id` is NULL
  on 790 of 1,979 in 24h, with `parser`, `rag_fact_check`, `phi_classify` and
  `integrator` at exactly 0%. Ananth ruled this doesn't block: module-level telemetry
  measures LLM time *inside* the span, so timing never depends on that join.

---

## Eval's sign-off on the taken design decisions + additions (2026-09-09)

All three taken decisions are correct. Endorsed, with a sharpening on each:

- **Spans parent/child + call count — yes.** One addition: label each count by its **target** (which table for DB, which model for LLM), not just a bare integer. "40 writes to `chat_state`" is a loop; "40 writes across 40 tables" is a busy turn — the count alone can't tell them apart, and the loop is the stated target. Count + target can.
- **Reader and writer in the same commit — yes, and the acceptance test is a same-turn read-back, not "a row was written."** My confirmed finding is emitters with zero callers *on the real path* (`tool_failed` structurally impossible). So the bar is: **one real turn on the live path → a per-module row exists → the diagnostics panel renders it → one test asserts all three on that turn.** A row in isolation is instance 13.
- **Provider stamp in the data — yes, and the reader that makes it real is the comparison-guard.** The stamp's consumer is a baseline-compare that **hard-refuses or red-flags when the run's `{provider, model}` mix ≠ the baseline's.** Without that reader the stamp is a labelled producer nobody enforces. Stamp per **model, not per provider** — within Vertex, flash (4.7s) and pro (20s) are 4× apart, so `{provider, model}` is the controlling dimension (your data already has it in that shape).

**One flag on the `correlation_id` NULL (45%, and exactly 0% for parser / rag_fact_check / phi_classify / integrator).** Ananth's ruling is right — in-span timing measures LLM time *inside* the span and never needs the join, so this does not block P2b. But that NULL join key is itself a **producer-13**: a join column populated on only some paths, dead on four stages. It's fine not to depend on it here; it is **not** fine to leave it un-flagged, because a future consumer will join `llm_calls` to turns, get 55% of rows, and believe it has all of them — the same silent-partial failure as `blueprint_snapshot` 0-of-2,744. Mark it **non-joinable** (or populate it), so the next reader can't be quietly wrong.

— Payor Policy / Eval seat

---

## Q6 · Add the model bandit to the Eval macro schema

**Ananth, 2026-09-09:** *"we need to show the bandit in the schema, it is important
enough a concept — and actually add it to the eval macro schema. It is one of the
silent yet effective instruments we have."*

It now has a node in the chat schema (`model_registry`, RED). The second half — the
**Eval macro schema** — is yours, and the reason it belongs there rather than only in
chat's map is that the bandit is an *evaluation instrument*, not a routing detail: it
runs a live experiment on every turn and updates a posterior from outcomes.

**What it is, so you don't have to re-derive it:** Thompson sampling over a Beta
posterior, per model per stage. Phase 1 (<10 quality samples) explores on benchmark
priors; Phase 2 (10–100) blends prior with observed; Phase 3 (100+, `confidence=locked`)
exploits with 5% drift detection. Forced exploration every `EXPLORATION_INTERVAL` turns
gives the least-sampled model a slot so nothing starves. **ReAct rounds are separate
arms** — `react_1..react_4` have their own caps and their own PG rows, so round 1 and
round 4 learn independently. Hard constraints (HIPAA eligibility, context-window floors,
copilot's category exclusion) are applied *before* the draw, not as weights.

**Measured, 7 days:** 8,104 calls, 3,244 hard-pinned, **4,860 (60%) chosen by the
bandit.**

**Three things I think are yours to rule on:**

1. **Where it sits in the macro schema.** It consumes adjudication scores — your
   rubric, your `FACT_CHECKER_VERSION` — as its reward signal. So the loop is
   Eval-judge → posterior → routing → next turn's quality. That closes through your
   instrument, which is the argument for it being on your map rather than only chat's.
2. **Whether the reward is the right one.** It optimises a *quality* posterior. The P2b
   stamp says `gemini-2.5-pro` has p50 **20.0s** against flash at **4.7s**. A bandit
   that cannot see a 4× latency difference will pick the slow model on quality grounds —
   which is a candidate explanation for the routing-latency layer you identified. Should
   latency enter the reward, or stay a hard constraint, or stay out?
3. **Whether "it is learning" is assertable.** Your own rule: *a decision is assertable
   iff the inputs it consumed are persisted alongside the outcome.* The bandit persists
   the outcome (`ab_variant` on an `llm_calls` row) but not the draw — not the posterior
   it sampled from, not which phase it was in, not whether the pick was forced
   exploration. By your rule that makes its decisions **unassertable**, and it is the
   one instrument on the page whose whole job is to change its behaviour over time.

**The finding that prompted this, for context.** The bandit selected Anthropic models
**203 times across 2026-09-08/09 with zero successes** — a provider that has failed 100%
since 09-07 00:58Z — and the documented breaker (`error_rate_24h > 15%` → pull) never
fired. Leading mechanism, unproven: the 24h breaker reads `model_performance_by_stage`,
filtered `WHERE variant_id = 'default'`, the column the writer never populated until the
LLM Agent's fix landed yesterday. A matview whose row set never advances cannot report
the last 24 hours. Same NULL column that froze the ema.

**Eval's answer:**

> _(write here)_

---

## Q7 · Audit the first contract tag — `state_load`, and the gate on calling any node ready

**Ananth, 2026-09-09:** re-measure, then get Eval to audit the tag.

`state_load` is the first node through a P3 pass under the new definition of done. It
needs your Layer-2 audit to move from **PERIPHERAL → GUARDED**, and by our own rule a
node cannot mark itself.

**What was fixed** (`c8fc7c8`, `5979558`, `7e6b9e1`): `get_state` returned `None` for a
DB error *and* for no-row, with a docstring mentioning only the second — so
`state_load`'s `raw = get_state(...) or {}` built a default `ThreadState` and, on any
delta-bearing message, called `save_state_full`, a full replace. **One failed read
destroyed the conversation**, and `state_version` incremented on that same write so the
reset was indistinguishable from turn 12. It now raises `StateUnavailable`, with the
rule stated in the docstring: *state is only replaced from state that was actually read.*

**Current state:** coverage **PERIPHERAL** — `test_state_load_state_integrity.py` exists
and calls the node, no contract tag. Suite 2,541 passed / 14 failed = baseline, 0
regressions.

### What I need from you

**1 · Is `state_load:no_silent_reset` the right contract ID**, and does the test actually
assert it? Your own bar: reachability proves *executed*, not that the test would *fail*
if the contract regressed. The specific question — does the test force a **read error**
(not a missing row) and assert the **stored row** is unchanged, or does it assert on a
return value? Per your read-back rule, only the first counts. I have not audited it
myself; that is deliberately yours.

**2 · Should ASSERTS-NOTHING apply here?** If the test passes but could not catch the
original defect, that is the state you defined for exactly this case, and I would rather
this node be the first to carry it honestly than have GUARDED mean "someone added a tag".

### And a latency question that is yours, because it decides whether a spec is writable

`state_load` measured p50 **1,367ms** before the fix, **4,090ms** after — but read
*counts* went **down** (chat_state 1.36 → 1.22 per span). It is not the fix. Measured
just now:

```
my direct read via cloud-sql-proxy       45ms median
the service's own reads, same tables    260–630ms
```

`CHAT_DB_MODE=direct` is set live, so this is **not** an MCP hop — it is the same
psycopg2 path to the same database, ~10× slower from Cloud Run. I have not established
why, and I am not going to guess.

**So: can a latency spec be written against a per-read overhead nobody has attributed?**
My instinct is no — the counts are assertable today (four reads, `n=1` each, to four
named targets) but any wall-time target would be a number about the environment rather
than the module. Your call, since you set the counts/wall split.

**Eval's answer** (2026-09-09, Payor Policy / Eval seat):

**Verdict: `state_load:no_silent_reset` is the right contract, and the node is GUARDED — not ASSERTS-NOTHING.** Latency spec: **counts yes, wall-time no (not until the per-read overhead is attributed and reassigned).** Audited firsthand against source and by running the test; details below.

**1 · Contract ID and does the test actually assert it — GUARDED.** I checked the two things you named and did not assume:

- **It forces a read *error*, not a missing row.** `test_state_load_state_integrity.py`'s `FakeChatState.query` returns `{"error": {...}}` when `fail_reads=True`, a *distinct* branch from the no-row case `{"rows": []}`. The module (`app/stages/state_load.py:49–56`) turns that into the `except StateUnavailable` path — confirmed by the test asserting `ctx.state_read_failed is True`, while the healthy test asserts it `False`. So the error path and the missing-row path are separated exactly where the original bug fused them.
- **It asserts the *stored row*, not a return value.** The fake is a real store (holds rows, applies writes, bumps `state_version`). `test_failed_read_does_not_overwrite_stored_state` asserts `after == before`, `after_ver == before_ver == 11`, and **`store.writes_attempted == 0`**. That is the read-back rule satisfied — a function can return anything while having destroyed the row, and this test watches the row.
- **It would fail on the exact regression.** Revert to `get_state(...) or {}` and on `fail_reads=True` a `save_state_full` fires → `writes_attempted == 1`, `after != before`, `after_ver == 12`. All three assertions break. The defect cannot come back unseen.
- **It has the complement test that earns GUARDED rather than a one-sided pass.** `test_healthy_read_still_persists_the_delta` blocks the trivial over-fix (a blanket "never write" would pass the first test while breaking the product): a healthy delta-bearing turn must advance `state_version` to 12. Guarding both directions — suppress on failure, persist on success — is what makes this a contract and not a tag.
- **Ran it, didn't just read it** (`.venv/bin/python -m pytest`): **10 passed, 1.31s, exit 0.** So the guarantee is executed and green, not asserted-in-principle.

**2 · ASSERTS-NOTHING does not apply.** It's the honest question and the right instinct to ask, but this test is the opposite case — it targets the precise fusion the defect lived in and fails on the exact revert. If GUARDED is ever going to mean something, this is the node that earns it first.

**Latency — counts yes, wall-time no, and your instinct is correct.** The split falls cleanly:

- **Assertable now (the module's real number):** the four reads, `n=1` each, to four named targets. That *is* `state_load`'s latency spec and it's a genuine one — it measures what the module *does*, and it already caught the fix (counts 1.36 → 1.22 is the module getting strictly better).
- **Not writable (an environment number wearing the module's name):** any wall-time target. Your own data proves it — same psycopg2 path, same DB, same query, only the caller's *location* differs (45ms from the proxy vs 260–630ms from Cloud Run). A controlled comparison that holds query + driver + database constant and varies only caller location **localizes the ~10× to the Cloud Run ↔ Cloud SQL connection/egress path, not to `state_load`'s code.** (I state that as the observation the comparison supports, not as an established root cause — that attribution is still open.) The `1,367 → 4,090ms` "regression" is the proof of the trap: the module got *better* (fewer reads, correct behaviour) while wall-time doubled — so a wall-time gate would have failed a node that improved. A number that moves opposite to the module's quality is not the module's number.

**Consequence for the definition of done.** `state_load` meets it: unit test **GUARDED** (executed, green), latency test = the **count assertions** (assertable now, four named targets). Mark it **ready on counts + GUARDED**. The wall-time is a separate, cross-cutting **DB-access budget** owned by infra, not a per-node gate — do not block this node on it, and do not write a wall-time number into any node's spec until that per-read overhead is attributed and assigned to whoever owns the connection path. A concrete next probe for whoever picks that up: split the span's connection-acquire time from query-execute time — that isolates pool-checkout from network and tells you which half the 10× lives in.

*(Also recorded: your proxy-restart self-correction is right and it's load-bearing here — the spans come from the deployed service's own connection, your proxy is only your query path, so the 45ms-vs-260–630ms gap is two independent connections to one DB, which is exactly what localizes the overhead to the Cloud Run side. Good catch to log rather than bury.)*

**Q6 (bandit in the Eval macro schema) is still mine and still open** — separate design task, I'll take it next; not folded into this ruling.

— Payor Policy / Eval seat

---

## Q7 follow-up — root cause of the per-read wall-time (for the Chat seat)

Ananth asked what's causing the lag, then answered his own question in the form of the fix: *one connection per turn, and clean up after yourselves.* Both are right. Here is the confirmed code-side cause and the fix, for whoever owns `db_client`.

**Root cause (confirmed from source, `app/db_client.py`).** In `CHAT_DB_MODE=direct` (live), every `db_query`/`db_execute` routes through `_fallback_query`/`_fallback_execute`, and **each call does its own `_acquire_conn` → execute → `_release_conn`**. `_acquire_conn` runs a **`SELECT 1` liveness probe + `commit` on every pooled acquire** (`app/db_client.py:~335–345`) before handing the connection back. So each read pays **two** Cloud SQL round-trips — the liveness probe, then the real query. `state_load` alone does ~4 reads → ~8 round-trips; a full turn does 5–10 DB ops → **10–20 round-trips.** The 2026-04-22 pool amortizes the *connect* cost but **not** the per-acquire `SELECT 1`. The *variability* (260–630ms) is `getconn` contention on top — the code already logs a loud **5s acquire-timeout** when the `max=10` pool saturates (`app/db_client.py:~350–360`).

Why the proxy is 45ms: a `psql` session is one warm connection, **no** liveness probe, **one** round-trip. The service reproduces none of that per read.

**The fix — Ananth's, endorsed, two inseparable parts:**

1. **One connection per turn.** Acquire once at turn start, thread it through every stage's DB op, drop the per-query `getconn` and the per-query `SELECT 1`. That collapses 10–20 round-trips into ~one-per-query with zero liveness overhead, and per-read wall-time falls toward the query's own cost. It's the natural next step on the road already started (pool amortizes *connect* → turn-scope amortizes *acquire + liveness*).
2. **Guaranteed release — non-negotiable.** A turn-scoped connection MUST be released on **every** exit path, including exceptions and the now-20s LLM-call timeouts, in a `finally` at turn end. Otherwise it leaks and starves the `max=10` pool — which *is* the `getconn` contention and 5s timeouts we see. Note the shape: cleanup-on-the-failure-path is the exact class of bug `state_load` itself just fixed.

**Honesty caveat.** The per-query `SELECT 1` + acquire/release is confirmed from source. The *base* Cloud Run→Cloud SQL round-trip being high (vs 45ms local) is the network/egress path and is **unmeasured** — I'm not claiming its share. But turn-scoping removes the extra round-trips and the contention regardless of that split, so the fix holds either way.

**How the P2b telemetry proves it (and why the span design matters here).** Split **connection-acquire time (incl. the `SELECT 1`) from query-execute time** in each DB span. Before the fix, acquire-time is non-zero on every read; after, acquire-time → ~0 for reads 2..N of a turn and per-read wall-time → execute-only. That is the acquire/execute split doing exactly the job it was specified for — the `SELECT 1` is acquire-time masquerading as query-time, and the span makes it visible per turn instead of read out of the source by hand.

**Ownership:** `db_client` is the Chat seat's to change; Eval / Technical Review does not write chat module code. This is the diagnosis + the target, not a patch.

— Payor Policy / Eval seat

---

## Layer-2 mutation rule — ruling (enum owner), and a correction to my own audit (2026-09-09)

**Ruling: adopted.** A tag earns **GUARDED** only when the tagged test has been **demonstrated to fail with the guarantee removed** — mutate the guarantee out of `app/`, run, keep only what goes red. Not "asserts the guarantee" as a read. Chat's mutate-don't-read move is correct, and I'm ruling it into the enum definition.

**It corrects my own method, and I'll say so plainly.** I audited `state_load` by reading the four tests and running them green (10 passed) and certified GUARDED on that. Reading + green-run is exactly the **TAGGED-UNVERIFIED** state: it proves the tests pass on the *fixed* code, not that they *fail* on the *broken* code — and only the second is what GUARDED claims. The fourth test is the proof: pre-fix it read correctly and ran green, yet passed with the guarantee deleted (its `before` snapshot was captured post-turn, so it recorded the damaged row and the final assert held on an unrelated compare-and-set miss). I would have passed it by reading. Mutation caught it. Verified firsthand: the fixed fourth test (`tests/test_state_load_state_integrity.py:202`) now snapshots pristine-first and its docstring records the finding.

**Correction to my Q7 ruling.** I wrote `state_load` was "GUARDED, certified by running it (10 passed)." **Withdraw the basis** — green-run ≠ GUARDED. `state_load` is GUARDED **now**, on the mutation evidence: all four `state_load:no_silent_reset` tags demonstrated red under guarantee-removed, after the fourth-test fix. Before that fix the fourth tag was **ASSERTS-NOTHING** wearing a GUARDED-looking test. Same conclusion about the node; correct basis under it.

### Q1 — mutation belongs in the definition; keep TAGGED-UNVERIFIED and ASSERTS-NOTHING distinct

Yes, mutation is the GUARDED bar. But **no**, a tag with no mutation evidence must render **TAGGED-UNVERIFIED, not ASSERTS-NOTHING** — collapsing them violates *could-not-check ≠ checked-false*, my own foundational rule. Refined enum (only GUARDED renders ✓):

- **ABSENT** — no test reaches the node.
- **PERIPHERAL** — reached, no contract tag.
- **TAGGED-UNVERIFIED** — tag present, **mutation not yet run**. Unknown.
- **ASSERTS-NOTHING** — tag present, **mutation run, test stayed green**. Known-hollow.
- **GUARDED** — tag present, **mutation run, test went red**, tied to the current code.

TAGGED-UNVERIFIED and ASSERTS-NOTHING both block "ready", but they demand different actions — *run the mutation* vs *rewrite the test* — and the distinction is the difference between "we haven't looked" and "we looked and it's hollow." Keep both.

### Q2 — record it machine-readably, and record it re-runnably

Yes — without a machine-readable record, GUARDED is itself a producer-with-no-consumer (a state asserted in a transcript, not checkable), and Layer 2 becomes a marker believed *more* than an untagged test while its content is "someone thought this was relevant." So gate GUARDED on recorded evidence. **And go one step further: mutation evidence decays** — a test red under mutation today can pass tomorrow when `app/` or the test changes (verification-timing / cross-repo decay). So:

- **Don't store a bare "went red" boolean.** Store the **mutation as a re-applicable transform** (a patch/diff or a named code-transform that removes the guarantee), the tagged tests that went red, and the `{app_commit, test_commit}` it was verified against.
- **GUARDED renders only when that entry matches the current code state**; a change past the recorded commits demotes it to TAGGED-UNVERIFIED until re-run.
- **End-state:** the mutation graduates into the generator/CI so GUARDED is re-verified automatically, not stamped once. Set this marker/ledger shape **now** — exactly one tag exists, so it's the cheap moment, as you said.

File the fourth test as the **canonical ASSERTS-NOTHING example**: a tagged test that reads correctly, runs green, and survives its own guarantee being deleted. It's the proof the bar must be mutation.

### Consequence for my open audits

My pending Layer-2 audits of **`queue`, `jurisdiction`** (the last RED with no test that calls it) **and `clarification`** are now **mutation runs, not reads** — so the Q2 recording shape is a prerequisite for me to certify any of them GUARDED. Stand up the re-runnable mutation ledger and I'll run the mutations and record the evidence, rather than reading assertions and being wrong the way I nearly was here. **Q6** (bandit in the Eval macro schema) unchanged and still mine.

— Payor Policy / Eval seat

---

## AUDIT — `state_load:no_silent_reset` → **GUARDED** (mutation-verified, independent) — 2026-09-09

**Verdict: GUARDED.** I ran the mutations myself — not on chat's word, not by reading — reverting each after. The generator may flip `state_load` from TAGGED-UNVERIFIED to GUARDED on this record. This is also the **first entry in the mutation ledger** whose shape I ruled in Q2 (re-applicable transform + which tests went red + verified commit).

**Verified against:** `mobius-chat @ c468880`, `tests/test_state_load_state_integrity.py`. Four tags carry `@pytest.mark.guards("state_load:no_silent_reset")` (tests at lines 99, 124, 134, 202). The contract has **two facets**, so it takes **two mutations** — a single mutation covers only three of the four, which is itself the lesson (one mutation ≠ full coverage of a multi-facet guarantee).

| Mutation (re-applicable transform, `app/storage/threads.py`) | Facet removed | Tags that went RED |
|---|---|---|
| **A** — `raise StateUnavailable(_err_message(result) or code)` → `return None, None` (both error-raise sites, `get_state` L606 + `get_state_with_version` L632) | a failed read is indistinguishable from no-row | `test_failed_read_does_not_overwrite_stored_state`, `test_error_and_absence_are_distinguishable`, `test_tracked_write_is_suppressed_after_a_failed_read` (3/3) |
| **B** — `raise StateUnavailable(f"state_json … did not decode …")` → `return None, None` (both decode-raise sites, L616 + L638) | an undecodable row "looks new" instead of raising | `test_undecodable_row_raises_rather_than_looking_new` (1/1) |

Under **A**, the decode tag correctly **stayed green** (its facet was intact) — confirming the mutations are facet-specific, not a blanket break. Under **B**, only the decode tag was exercised and it went red. **Every one of the four tags fails when the guarantee it guards is removed.** Source byte-restored after each run (`git status` clean, zero `MUTATION-AUDIT` residue).

**Ledger shape demonstrated (Q2):** each entry = the mutation as a re-applicable `sed`/patch transform, the tags that went red, and `{app+test commit}` = `c468880`. Per the decay rule, this GUARDED verdict is valid **at `c468880`**; a change to `app/storage/threads.py` or the test file past that commit demotes it to TAGGED-UNVERIFIED until the two mutations are re-run. When the mutation harness is stood up in the generator/CI, these two transforms are its first fixtures.

**Re-audit 2026-09-10 → re-verified at `299519c`** (live record: `docs/chat-mutation-ledger.json`). The decay rule fired **unattended** — chat's `state_load` latency parallelisation moved the test file past `c468880`, and the generator auto-demoted to TAGGED-UNVERIFIED with no one asking. Re-ran both mutations: read-error facet → 3 tags red, decode facet → 1 tag red, source byte-restored, **still GUARDED**. Concurrency check (Platform asked whether parallelisation changed Mutation A's behaviour): **it does not** — `get_state_with_version` is kept sequential *before* the `ThreadPoolExecutor` by design (`state_load.py:101-102`, `fb2f0cf`) so `StateUnavailable` still suppresses every write; verified empirically, tests red exactly as before, no adverse concurrency finding. Also switched the ledger's `tests_went_red` from line numbers to test **names** — line numbers drift faster than the decay rule catches.

— Payor Policy / Eval seat
