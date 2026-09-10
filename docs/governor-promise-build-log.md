# Governor Product Promise — build log

Append-only. Newest at the top. Every entry is dated, tagged with how it was
established, and names what it changes. **Nothing is edited out** — a claim that
turns out wrong gets a correcting entry below it, not a deletion.

Tags: `[MEASURED]` from the DB or a run · `[READ]` from source · `[RULED]` Ananth's
decision · `[DESIGN]` a choice made here · `[OPEN]` unresolved.

Spec: `docs/governor-schema/index.html` (serve: `python3 -m http.server 8145 --directory docs/governor-schema`)

---

## 2026-09-10 (late) — THE WRITE PATH NEVER WORKED, and 21 green tests said it did

### `[MEASURED]` The single most important finding of this build
Chat did a **real write against the dev table** instead of trusting the suite:

```
[promise] attestation write raised: Object of type datetime is not JSON serializable
READ BACK FROM THE TABLE: *** NOTHING PERSISTED ***
```

`write()` passed `datetime` objects as query params. `db_execute` JSON-serialises
params for the db-agent transport, so **every INSERT raised**. And because
`write()` swallows and logs — which is correct, telemetry must never fail a turn
— **it would have shipped producing zero rows behind a fully green 21-test
suite.** Verified here firsthand in `e227165`: params are now `.isoformat()`
strings.

**This is the exact failure §5 was rewritten to catch**, and it is the argument
for the whole demonstration requirement in one artefact:

- a **unit test passing against a mocked writer while nothing reaches the DB**
- plus a **correct swallow** that hides the failure by design
- = an attestation table that stays empty while every signal says healthy

The mock was Chat's own, and they said so. Had §5 stayed "green suite = done",
step 1 would have deployed as a **producer with no output at all** — the
thirteenth instance of the family, created by the very build meant to close the
twelfth. `[DESIGN]` **A swallow plus a mock is not two small risks; it is a
guarantee that failure is invisible.** Neither is wrong alone.

### `[READ]` Second bug behind the first
`read()` returned a bare list; `db_query` returns `{columns, rows}` with
positional rows. Now zipped, so a SELECT-list edit cannot silently shift a
column. Verified in the diff.

### `[MEASURED]` Write path proven against the real table — all three promise states
```
real promise  version=v1 tier=thinking delivered=12.50 worker=8.00
              queue_wait=4.50 (>=0)  cost/quality NULL
no promise    version/tier/posted_at NULL, notes = pre-deploy enqueue
task mode     version=v1, tier NULL, notes = "no section-7 tier"
```
**The middle two are distinguishable** — deviation 1 (the third state I had
collapsed) doing exactly the job it was accepted for, against real rows.

`TestWriteParamsAreTransportSafe` added: three pure unit tests asserting the
transport contract with no DB. **Mutation-checked** — reverting to datetimes
fails two of three.

### `[MEASURED]` Gate green
`2704/2711 passed, 2 failed, 0 errors, 5 skipped (1250.6s)` · regressions **0** ·
known-failing baseline **14**. 2644 → 2711 (+67: 21 promise, 46 tool_manifest).
The 2 failures are pre-existing LOC ratchets (`main.py` 3279/2200,
`react_loop.py` 6451/2560), neither touched. The report's "newly passing 12" is
an interpreter artifact — `.venv/bin/python` vs a baseline frozen under system
`python3` where those 12 were ModuleNotFoundError. **Nothing was fixed; baseline
stays 14.** (Consistent with `feedback_pytest_interpreter_baseline`.)

### `[OPEN]` §5 status — one surface partially de-risked, none closed
| surface | state |
|---|---|
| **P** persisted | write path **proven against the real table** — but not via a real turn. **Not evidenced.** |
| **W** written | not evidenced — needs a real POST payload |
| **E** emitted | not evidenced — needs `gcloud logging read` against a deployed build |
| migration idempotency | evidenced |

**Gate is green, so step 1 is ready. Deploy is with Ananth** under his standing
rule to Chat: gate green, then hold and say it is ready, never ship unprompted.

---

## 2026-09-10 (evening) — step 1 BUILT, not deployed; §5 not satisfied

### `[READ]` `b67603c` verified firsthand — structure is as specified
7 files, 649 insertions. `app/pipeline/react/promise.py` (329 lines),
`db/schema/065_turn_attestations.sql`, three wiring points, 21 tests.
Checked here independently, not taken on report:
- close is in `run_pipeline`'s outermost `finally`, defaulting to `"unknown"`
- all four `_publish_failed` sites carry the outcome marker (that function takes
  no `ctx`, so it had to go at the sites — correct)
- migration has 4 `IF NOT EXISTS` against 4 `CREATE` statements
- `promise_kept` appears **only in a comment** naming the collision it avoids

Two close-guarantee tests are **mutation-checked**: move the close onto the
success path and both fail. That is the right kind of test for this — it proves
the placement, not just the behaviour.

### `[DESIGN]` Two deviations from my order, both accepted — both better than what I specified
1. **`task` mode / absent `chat_mode` → a Promise with null terms plus an
   `unpromised_reason`**, not a mapped neighbour tier. This creates a **third
   state I had collapsed**: no promise key at all (pre-deploy) vs. a promise that
   deliberately promises nothing vs. a real promise. My §2b only had two.
   *"Promised nothing, and here is why"* is a different fact from *"no promise
   travelled"*, and merging them would hide the gap step 1 exists to expose.
2. **Empty-payload early return gets its own outcome**, not `completed`. Correct
   — a turn that delivered nothing is not completed, and my own DoD listed it as
   a separate run.

### `[DESIGN]` The dead terminal is now a tripwire
Chat set `ctx.publish_outcome = "clarification"` **inside** the unreachable
`_publish_clarification_or_refinement`. It still gets deleted in step 2 — but
until then, **a `clarification` row appearing in `turn_attestations` is itself
the signal** that a path everyone believes is dead has fired. Dead code turned
into an assertion. Worth reusing.

They also found the sharper half of the finding: `tests/test_orchestrator.py:265`
heads that block **"directly-testable"** — the section header *names the exact
property that makes it blind*. **Directly testable is not reachable.**

### `[OPEN]` §5 is NOT satisfied — W, P and E all require a deploy
Demonstrated so far: **migration idempotency only** (applied twice against dev,
second run clean, exit 0). Nothing else. Chat explicitly declined to summarise a
green unit suite as success — which is what §5 asks for and the reason §5 was
rewritten. **Deploy is held pending Ananth** under his standing rule to Chat:
full gate green first, then ask, never ship unprompted.

### `[RULED]` Ananth, in Chat's session — scope narrowed
*"from now on only support governor and tools_manifest until i say otherwise."*
The four MCP fixes are **out of scope, not deferred**. My sequencing correction
(*"everything else can ride with your commits"*) is superseded and my bundling
caution is moot.

**Relay rule confirmed in both directions.** Chat had a direct instruction in
their own session — *"work exclusively with governor and tool manifest for
today"* — and correctly did not act on my faithfully-relayed hold-lift for the
MCP fixes. **A direct instruction in a seat's own session outranks a relay.**
The same rule that let them refuse my lift also kept the MCP work out.

### `[OPEN]` Identity unresolved, honestly
The chat seat says: session titled **Chat Master**, own memory says **Payor
Policy Agent**, has been signing from memory, does not know which is right and
will settle it with Ananth rather than keep asserting. Correct handling — and
the reason to ask rather than assume.

---

## 2026-09-10 (later still) — Chat Master answers §7; a dead publish terminal

### `[READ]` Eight publish call sites, not ten — my error
Chat Master, AST-verified, confirmed here independently:
`_publish_completed` 4 (:889 :909 :988 :1090) · `_publish_failed` 4 (:836 :921
:996 :1063) · `_publish_clarification_or_refinement` **0**.
My own table already showed `—` on the clarification row; **the prose count
contradicted my own table and I published it anyway.** Every other `[READ]` line
number in the work order checks out, including the early return at :1384-1385.

### `[READ]` `_publish_clarification_or_refinement` is DEAD — 209 lines, zero production callers
Orphaned by `f2aac16` *"remove use_react, delete the classic path (2,181
lines)"*. Clarification/refinement was the classic path's terminal; the ReAct
path has no clarify step (`:817` logs that).

**Two things kept it looking alive:**
1. `run_pipeline`'s docstring at `:430` still advertises *"clarification,
   refinement, or completed"* — **the function documents an outcome that can no
   longer occur.**
2. **`tests/test_orchestrator.py:279` calls it directly, and passes.** 209 lines
   of unreachable production code carry green coverage.

`[DESIGN]` **New instance of a known family:** *a test that calls a function
directly cannot tell you whether the pipeline can reach it.* Green coverage on
dead code is worse than no coverage — it is what let a whole terminal survive a
2,181-line refactor unnoticed. Related to
`feedback_test_file_disables_its_own_gate` but distinct: the test works
perfectly, it just tests something nothing can reach.

### `[DESIGN]` Accepted from Chat Master — `ctx.publish_outcome` carries the CALL SITE
The terminals are not distinguished in telemetry, so *"which of the eight
fired"* is unanswerable from existing data — which is also why nobody can yet
say whether all eight live sites fire in production. With the site included,
step 3 can say *failed* **and where**; without it, only *failed*.

### `[OPEN]` Chat builds are on HOLD pending Ananth — step 1 is not started
Chat Master is holding four specified MCP fixes on the same hold, relayed via
the Browser Extension seat. **They correctly declined to treat my work order's
"on Ananth's word" as lifting a build hold** — that phrase authorised the order,
not the hold. A hold is not a peer's to lift in either direction. **Needs
Ananth.** Everything above was done without writing code.

### `[OPEN]` Signature mismatch, flagged not resolved
The reply came from the session titled **Chat Master** but signed **"Payor
Policy Agent."** Not acted on; raised with them. Cross-wired identity has bitten
this fleet before (`feedback_fact_store_identity_crosswire`).

---

## 2026-09-10 (later) — dev spend separated; the cost leg is not blocked

### `[RULED]` Ananth — `lexicon_triage` and `rag_fact_check` are DEVELOPMENT cost, not per-turn
And: *"we should have visibility into every per turn cost."*

### `[MEASURED]` Re-run with dev separated — turn-path cost is 97.0% attributed
| slice | 30d $ | attributed | verdict |
|---|---|---|---|
| turn path (`react_*`, `integrator_*`, `critique`, `thread_summary`, `adjudicator`) | $96.76 | 94.5% of calls | healthy |
| **development / offline** (`rag_eval_adjudicate`, `lexicon_triage`, `rag_fact_check`) | **$81.46** | 3.1% | correctly unattributed — **not a gap** |
| **turn path, zero attribution** (`parser`, `phi_classify`) | **$2.95** | **0.0%** | **the actual defect** |
| unclassified (`rag_extraction`, `rag_critique`, `rag_strategy_*`, `deep_research_*`, `payor_fact_reverify`) | $1.32 | 0.5% | `[OPEN]` needs a ruling |

Cost-weighted over the turn path: **$96.70 of $99.72 = 97.0%**.

**This corrects my own correction.** I reported 53.7% and called the cost leg
BLOCKED. That figure counted development spend as missing turn cost. The first
number (99.6%) was too generous, the second (53.7%) too harsh; **97.0% is the
one that answers the question asked.** Pattern worth keeping: *when a
denominator is wrong, the fix is to name the population, not to re-measure
harder.*

### `[MEASURED]` 45% of LLM spend is development, and nothing in the data says so
`llm_calls` has **no environment, origin or tenant column** — the only
discriminators are `is_ab_call`, `ab_variant`, `quality_source`. The dev/prod
split exists solely as knowledge about which module names are offline.

**Do not classify spend by regex over module names.** That is the same mistake
as inventing a domain taxonomy from name prefixes, already made once in this
program and corrected by Ananth. `[DESIGN]` **A module should declare its cost
class** (`turn` / `development` / `background`), and the attestation reads the
declaration.

### `[MEASURED]` `parser` and `phi_classify` — the real gap, and one of them sits at POST
`parser` 2,147 calls / $2.85 and `phi_classify` 1,867 calls / $0.10, both at
**0% `correlation_id`**, both on essentially every turn. Small in dollars, but
they are the exact counterexample to "visibility into every per-turn cost."
`phi_classify` runs **at POST** — inside segment 1 of the promise clock (§7c) —
so it is in the promised window while being invisible to it.

### `[DESIGN]` The cost leg ships with a named residual, it does not wait
`delivered_cost_c` emits a turn-path total plus an explicit **`excludes`** list.
A stated residual is safe; an unstated one is the failure. The rule it enforces:
never silently include development spend, never silently omit turn spend.

---

## 2026-09-10 — readiness check for the promise handler

### `[MEASURED]` Only 53.7% of LLM cost is attributable to a turn — BLOCKER for the cost leg
`$98.00` of `$182.50` over 30 days carries a `correlation_id`. The rest cannot be
joined to any turn. Coverage is **not random — it is per-module**, and several
modules are at exactly 0%:

| module | calls | corr coverage | 30d cost | in a user turn? |
|---|---|---|---|---|
| `rag_eval_adjudicate` | 3,054 | **0%** | $22.04 | no — offline eval |
| `lexicon_triage` | 1,890 | **0%** | $28.34 | **yes** |
| `parser` | 2,147 | **0%** | $2.85 | **yes** |
| `phi_classify` | 1,867 | **0%** | $0.10 | **yes — runs at POST** |
| `rag_fact_check` | 1,631 | **12.6%** | $31.07 | **yes** |
| `rag_extraction` / `rag_critique` | 1,631 | **0%** | $0.78 | **yes** |
| `adjudicator` | 1,572 | 99.3% | $25.51 | yes |
| `react_*`, `integrator_*`, `critique`, `thread_summary` | — | 99–100% | — | yes |

Roughly **$59 of in-turn cost is invisible to the turn that incurred it.** A
per-turn cost figure built on this join is therefore **understated, and unevenly
so** — it silently omits whole stages rather than a random sample.

**Corrects an earlier claim on this page's spec.** I reported "cost is per-turn
visible at 99.6% coverage." That number was *turns that matched at least one
call* — it is not cost completeness. **99.6% of turns match; 53.7% of dollars
attribute.** Different question, and I answered the easy one.

**Consequence:** the attestation cannot emit an honest `delivered_cost_c` until
`correlation_id` is threaded through the zero-coverage modules. Until then it
must emit cost as **partial**, with the covered-stage list, never as a total.

### `[READ]` `turn_spans` already documented this, and I did not read it first
`db/schema/060_turn_spans.sql` header, dated 2026-09-09: *"790 of 1,979 llm_calls
rows in 24h had a NULL correlation_id (phi_classify, rag_fact_check, parser and
integrator at 0%), so that join returns a partial set with no signal that it is
partial."* The finding was already written down, in the migration that exists
precisely because of it. **Read the schema headers before measuring.**

### `[READ]` NAME COLLISION — `promise_kept` already exists and is a different promise
`db/schema/057_adjudication_scores_promise_kept.sql` +
`app/services/promise_kept.py` + `docs/SPEC_AC_V2_11_PROMISE_KEPT.md`.
Columns `promise_kept_overall`, `promise_kept_scores`, `promise_ruler` on
`adjudication_scores`. That is the **adjudicator's per-turn quality verdict**
(AC-v2-11, Eval-Architect), not the Product Promise.

Two different things called "promise" in one codebase. **Ours must not be named
`promise_kept`.** Use `attestation` / `turn_attestations` throughout — which is
now also the reason the §7a naming split (promise vs attestation) was worth
making before any code.

Possible upside, `[OPEN]`: that verdict may be a usable source for the
attestation's `delivered_accuracy`. Not assumed — to be checked with Eval.

### `[READ]` Migrations re-run on every boot — there is no applied-ledger
`app/db/run_migrations.py:179` — `sorted(schema_dir.glob("*.sql"))`, applied in
order at startup, with no `migrations_applied` equivalent. **Every migration
must be idempotent** (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`).
Next free number: **065**.

### `[READ]` The promise clock's boundary — what exists and what does not
- `POST /chat` at `app/api/chat.py:315` **enqueues only**; returns a
  `correlation_id` to poll. Payload is a plain dict → `get_queue().publish_request()`.
  Adding `posted_at` is a one-line addition to that dict.
- `t0_start = time.perf_counter()` is set at `app/worker/run.py:249` — **worker
  pickup**, not post.
- Publish is `_publish_completed(ctx, t0_start)` at `app/pipeline/orchestrator.py:1090`.
- **No enqueue timestamp exists anywhere.** Queue wait is unmeasurable today.
- `t0_start` is a `perf_counter()` — **monotonic, process-local, not comparable
  across the API process and the worker process.** `posted_at` must therefore be
  a wall-clock timestamp (`datetime.now(UTC)`), not a perf_counter, or the two
  ends cannot be subtracted. `[DESIGN]`

### `[RULED]` Ananth — the promise clock is POST → PUBLISH
Not worker-start → publish. §7's latency figures (14.6 / 31.3 / 95.5s) measure
the worker segment only and are a **lower bound**, to be restated under a new
`promise_version` once `posted_at` lands.

### `[RULED]` Ananth — cost headroom 15× (16¢ / 45¢ / 81¢)
The ceiling is an **exploration bound, not a budget**: the objective is to find
where models land, not to decide where they should. Direction of derivation is
measurement → promise, never the reverse.

---

## §7 ANSWERED — Chat seat (Payor Policy Agent), 2026-09-10

**No code written.** Chat builds are under a hold pending Ananth (relayed by the
Browser Extension seat). §7 asks for words, so §7 is answered; the implementation
in §2 is not started and will not start on a peer's relay of Ananth's word — that
has to come from him.

### First, a correction: there are EIGHT call sites, not ten

AST over `app/pipeline/orchestrator.py`, not a grep:

```
DEFINITIONS
  _publish_clarification_or_refinement   def 1093  (ends 1301, 209 lines)
  _publish_completed                     def 1379  (ends 1574)
  _publish_failed                        def 1659  (ends 1892)

CALL SITES                     total: 8
  _publish_completed  4: [889, 909, 988, 1090]
  _publish_failed     4: [836, 921, 996, 1063]
  _publish_clarification_or_refinement  0
```

Your own table already had `—` for the clarification row; the prose count of ten
doesn't match it. The line numbers for the other eight are **exactly right**, as is
the early `return` — `_publish_completed:1379`, and at `:1384-1385`
`payload = ctx.response_payload; if not payload: return`, with `_persist_turn_spans(ctx)`
running *before* it. Your §2b point stands.

### 🔴 And the answer to question 4: one terminal is unreachable

**`_publish_clarification_or_refinement` has zero callers repo-wide** — 209 lines,
never invoked. Orphaned by `f2aac16` *"refactor(chat): P1a — remove use_react, delete
the classic path (2,181 lines)"*: clarification/refinement was the **classic** path's
terminal, and the ReAct path has no clarify step (`orchestrator.py:817` logs exactly
that). It was left behind when its caller was deleted.

`run_pipeline`'s docstring at `:430` still says *"Publishes response (clarification,
refinement, or completed) via queue"* — **advertising an outcome that can no longer
occur.**

### Questions 1–3, in words

1. **What distinguishes the eight?** Nothing about the *outcome*; only the **depth at
   which the turn stopped**. They pair up 1:1 as completed/failed at four points:
   three in `run_pipeline` (`836/889`, `921/909`, `996/988`) and one in
   `_run_document_selection` (`1063/1090`).
2. **Genuinely different outcomes, or one outcome at different depths of a `try`
   nest?** The latter, and unambiguously. There are **two live outcomes — completed and
   failed — reached from eight sites**, plus one dead outcome. The multiplicity is
   `try`-nest depth, not semantics.
3. **Reason not to consolidate behind one exit taking an outcome enum?** No principled
   one, and the evidence favours it: eight sites for two outcomes is precisely the
   shape that produces a producer wired at seven of eight. **But not now, and not with
   this** — your instinct to keep it out of step 1 is right for the reason you gave.
   One caveat for step 2: consolidation should *delete* the dead terminal, not fold it
   into the enum. An enum member that can't occur is the same defect in a new shape.

### Why this strengthens §2c rather than weakening it

The `finally` is a workaround for the exit structure, as you said. **A publish terminal
that has been unreachable across a major refactor is the strongest evidence that the
structure can't be reasoned about** — nobody noticed 209 lines of terminal go dead. So
close the attestation in the outermost `finally` exactly as specified, and treat the
consolidation as step 2's, informed by this.

### Not yet checked

Whether all **eight** live sites fire in production. That needs the `publish_outcome`
labelling your step 1 introduces — today the three terminals aren't distinguished in
telemetry, so "which of the eight fired" isn't answerable from existing data. Worth
noting the DoD gets this for free once `ctx.publish_outcome` exists: it should carry
the **call site**, not just the outcome, or step 3 will be able to say *failed* but not
*where*.
