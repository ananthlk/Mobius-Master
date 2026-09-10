# Governor Product Promise — build log

Append-only. Newest at the top. Every entry is dated, tagged with how it was
established, and names what it changes. **Nothing is edited out** — a claim that
turns out wrong gets a correcting entry below it, not a deletion.

Tags: `[MEASURED]` from the DB or a run · `[READ]` from source · `[RULED]` Ananth's
decision · `[DESIGN]` a choice made here · `[OPEN]` unresolved.

Spec: `docs/governor-schema/index.html` (serve: `python3 -m http.server 8145 --directory docs/governor-schema`)

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
