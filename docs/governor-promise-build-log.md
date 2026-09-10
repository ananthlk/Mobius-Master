# Governor Product Promise — build log

Append-only. Newest at the top. Every entry is dated, tagged with how it was
established, and names what it changes. **Nothing is edited out** — a claim that
turns out wrong gets a correcting entry below it, not a deletion.

Tags: `[MEASURED]` from the DB or a run · `[READ]` from source · `[RULED]` Ananth's
decision · `[DESIGN]` a choice made here · `[OPEN]` unresolved.

Spec: `docs/governor-schema/index.html` (serve: `python3 -m http.server 8145 --directory docs/governor-schema`)

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
