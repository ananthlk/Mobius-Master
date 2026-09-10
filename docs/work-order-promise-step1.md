# Work order — Promise Step 1: integrate promise-start and promise-end

**To:** Chat Master · **From:** Governor seat · **Date:** 2026-09-10
**Spec:** `docs/governor-schema/index.html` §7c (the clock), §7d (the sequence), §7a/§7b (the attestation)
**Log:** `docs/governor-promise-build-log.md`

---

## 0. Scope — read this before anything else

**Step 1 is a boundary, not a measurement.** It succeeds when a turn can be asked
*"what did you promise?"* and answer, and when that promise is closed exactly
once at the end of the turn.

**In scope:** attach a promise at POST · carry it · close it at PUBLISH · one row.

**Explicitly OUT of scope — do not fix these here**, they are step 3:
- `parser` / `phi_classify` `correlation_id` attribution
- cost-class declaration per module
- the unclassified-module ruling (`rag_extraction`, `rag_strategy_*`, …)
- the conformance report
- anything in §9/§9a (overrides — designed, not being built)

If a term cannot be honestly filled in step 1, **write it as an explicit null
with a reason**, do not go and fix its source. The nulls are the step-3 backlog.

---

## 1. The handler lives in the governor's module — not in chat's API layer

**New file: `app/pipeline/react/promise.py`** — beside `governor.py`, owned by the
governor seat. Chat wires the call sites; the promise's shape and rules live here.

This matters because step 2 (levers/targets) will have the governor read the
promise it is carrying. If the handler is spread across `api/chat.py` and
`orchestrator.py`, step 2 has nothing to read from.

```python
# app/pipeline/react/promise.py

PROMISE_VERSION = "v1"            # bump when §7 numbers change; NEVER edit in place

@dataclass(frozen=True)
class Promise:
    version: str                  # PROMISE_VERSION at the time of POST
    tier: str                     # fast | normal | thinking  (from chat_mode)
    posted_at: datetime           # wall-clock UTC — see §3 trap
    latency_s: float              # promised, from the §7 table
    cost_c: float                 # promised (exploration bound, 15x)
    quality: str                  # "none" | "some" | "best"  — ordinal, §7

def open_promise(chat_mode: str | None, now: datetime) -> Promise: ...
def to_payload(p: Promise) -> dict: ...        # for the queue
def from_payload(d: dict | None) -> Promise | None: ...  # tolerant of absence

@dataclass(frozen=True)
class Attestation:
    correlation_id: str
    promise_version: str
    tier: str
    posted_at: datetime
    published_at: datetime
    outcome: str                  # completed | clarification | failed | unknown
    delivered_latency_s: float    # published_at - posted_at  ← THE PROMISE CLOCK
    worker_latency_s: float | None    # existing duration_ms, kept for comparison
    delivered_cost_c: float | None = None      # step 3 — null in step 1
    delivered_quality: str | None = None       # step 3 — null in step 1
    excludes: list[str] | None = None          # step 3

def close_promise(p: Promise | None, *, correlation_id, outcome, now) -> Attestation | None
def write(a: Attestation) -> None      # the row; must never raise into the caller
```

**Promise values come from §7 and are hard-coded here in step 1.** Not from
`_MODE_DEFAULTS` — those are levers, and §7a's deletion rule keeps levers out of
the promise. A config surface for these is P5's job, not this work order's.

---

## 2. Three wiring points

### 2a. POST — `app/api/chat.py:315` `post_chat`
After the payload dict is built and before `get_queue().publish_request(...)`:

```python
promise = open_promise(body.chat_mode, datetime.now(UTC))
payload["promise"] = to_payload(promise)
```
One key. Additive — older workers ignore it, same convention as the `user_id`
comment already in that function.

### 2b. CARRY — `app/worker/run.py:249` → `PipelineContext`
Read `payload.get("promise")` the same way `chat_mode` is read at `run.py:59`,
pass it into `run_pipeline(...)`, and land it on `ctx.promise`
(`app/pipeline/context.py`, beside `chat_mode` at :250).

**Tolerate absence.** In-flight requests enqueued before deploy have no
`promise` key. `from_payload(None)` returns `None`; the turn runs normally and
its attestation records `outcome` with a null promise. **Do not synthesise a
promise at the worker** — a promise invented after POST is not a promise, and it
would silently backfill the exact gap this work order exists to expose.

### 2c. PUBLISH — and this is the part that needs care

There are **three publish terminals**, not one:
- `_publish_completed` — `orchestrator.py:1379`, called from **:889, :909, :988, :1090**
- `_publish_clarification_or_refinement` — `:1093`
- `_publish_failed` — `:1659`, called from **:836, :921, :996, :1063**

`_publish_completed` also has an **early `return` at :1385** when
`ctx.response_payload` is empty.

**Do not write the attestation inside the publish functions.** Doing so in
`_publish_completed` alone means every failed turn, every clarification turn,
and every empty-payload turn silently has no attestation — which is precisely
the failure §7b names: *the emit sits on the success path, and the most valuable
attestation is the one that goes missing.*

**Close the promise once, in `run_pipeline`'s outermost `finally`.** One site,
covers all three terminals and every early return. Set `ctx.publish_outcome`
in each terminal (a string), and let the `finally` read it — defaulting to
`"unknown"` if no terminal ran at all, which is itself a finding worth having.

```python
finally:
    try:
        a = close_promise(getattr(ctx, "promise", None),
                          correlation_id=ctx.correlation_id,
                          outcome=getattr(ctx, "publish_outcome", "unknown"),
                          now=datetime.now(UTC))
        if a: write(a)
    except Exception:
        logger.exception("attestation write failed")   # never break a turn
```

---

## 3. The trap — two clocks, two processes

`t0_start` is a **`perf_counter()`**: monotonic and **process-local**. POST runs
in the API process; the turn runs in the worker. **Two perf_counters from two
processes cannot be subtracted.**

- `posted_at` / `published_at` — **wall-clock UTC** (`datetime.now(UTC)`).
- `t0_start` — **unchanged**. Keep it, keep `duration_ms`. It is not being
  replaced; it is being joined by a second clock that spans processes.
- Record **both** (`delivered_latency_s` and `worker_latency_s`) in step 1. Their
  difference is segments 1+2 of §7c — **the queue wait we currently cannot see**,
  and the first time it becomes visible.

Wall clocks across two machines can skew and can go backwards. If
`published_at < posted_at`, **write the row with `delivered_latency_s = None`
and a reason** — do not clamp to zero. A clamped zero is indistinguishable from
a fast turn.

---

## 4. Migration `065`

`db/schema/065_turn_attestations.sql`. **Must be idempotent** —
`app/db/run_migrations.py:179` globs `db/schema/*.sql` and re-applies every file
on **every boot**; there is no applied-ledger. `CREATE TABLE IF NOT EXISTS`.

**Name it `turn_attestations`. Do NOT name anything `promise_kept`** — that name
is taken: `db/schema/057`, `app/services/promise_kept.py`, and
`docs/SPEC_AC_V2_11_PROMISE_KEPT.md` are the *adjudicator's per-turn quality
verdict* (AC-v2-11, Eval-Architect), a different thing entirely. Two objects
called "promise" in one codebase is already one too many.

Key on `correlation_id` (that is the turn key — **`chat_turns` has no `turn_id`
column**, and `llm_calls.turn_id` is NULL on all 25,310 rows in 30 days; do not
use it). Header comment should state what the table is for and what its nulls
mean, in the style of `060_turn_spans.sql`.

---

## 5. Definition of done — DEMONSTRATED, not asserted

**Ananth, 2026-09-10: step 1 is done when we have SEEN that everything is
written, persisted and emitted.** A green test suite does not close this item.
Unit tests can pass against a mocked writer while nothing reaches the database;
that is the exact shape this program keeps finding. **Run real turns in dev and
show the artifacts.**

Three surfaces must each be evidenced separately (§7b):

| # | surface | means | evidence required |
|---|---|---|---|
| **W** | **written** | the promise is in the queue payload at POST | the payload dict, with its `promise` key, for a real request |
| **P** | **persisted** | the attestation row is in Postgres | `psql` output — the actual row |
| **E** | **emitted** | the structured log line is in Cloud Logging | `gcloud logging read` output — the actual entry |

### The runs

Exercise **all four outcomes**. The last two are the point — they are what prove
the `finally` placement, and a happy-path-only demonstration does not close this.

| outcome | how to provoke it | expected |
|---|---|---|
| `completed` | any normal question | full row |
| `clarification` | a query that trips route clarification (`ctx.needs_route_clarification`) | full row, `outcome=clarification` |
| `failed` | force an exception on the pipeline path in dev | **full row** — a failed turn still closes its promise |
| empty payload | a turn hitting the early `return` at `orchestrator.py:1385` | **full row**, `outcome` set, not missing |

### The queries — run these, paste the raw output

```bash
# proxy must be up on 5433
export PGPASSWORD=$(gcloud secrets versions access latest --secret=db-password)
PSQL="psql -h 127.0.0.1 -p 5433 -U postgres -d mobius_chat"
```

**P1 — one row per turn, all four outcomes present:**
```sql
SELECT outcome, count(*) FROM turn_attestations
WHERE published_at > now() - interval '2 hours' GROUP BY 1 ORDER BY 1;
```

**P2 — exactly one row per turn, no duplicates and no misses.** This is the one
that catches a `finally` that fires twice, or a terminal that returns before it:
```sql
SELECT
  (SELECT count(*) FROM chat_turns WHERE created_at > now() - interval '2 hours') AS turns,
  (SELECT count(*) FROM turn_attestations WHERE published_at > now() - interval '2 hours') AS rows,
  (SELECT count(*) FROM turn_attestations WHERE published_at > now() - interval '2 hours'
     GROUP BY correlation_id HAVING count(*) > 1 LIMIT 1) AS any_duplicate;
```
`turns` and `rows` must match. `any_duplicate` must be empty.

**P3 — the promise clock is wider than the worker clock:**
```sql
SELECT correlation_id, tier, promise_version, outcome,
       round(delivered_latency_s::numeric, 2)  AS post_to_publish,
       round(worker_latency_s::numeric, 2)     AS worker_only,
       round((delivered_latency_s - worker_latency_s)::numeric, 2) AS queue_wait
FROM turn_attestations
WHERE published_at > now() - interval '2 hours'
ORDER BY published_at DESC LIMIT 20;
```
**`queue_wait` must be >= 0 on every row.** A negative value means the two clocks
were mixed (§3) and the wiring is wrong — do not explain it away.

**P4 — the nulls are the intended ones, and nothing arrived as a zero or a guess:**
```sql
SELECT count(*) FILTER (WHERE delivered_cost_c IS NOT NULL)    AS cost_should_be_0,
       count(*) FILTER (WHERE delivered_quality IS NOT NULL)   AS quality_should_be_0,
       count(*) FILTER (WHERE promise_version IS NULL)         AS version_should_be_0,
       count(*) FILTER (WHERE posted_at IS NULL)               AS posted_should_be_0
FROM turn_attestations WHERE published_at > now() - interval '2 hours';
```
All four must be **0**. A `delivered_cost_c` of `0.0` is a step-1 failure, not a
cheap turn.

**E — the emit reached Cloud Logging:**
```bash
gcloud logging read \
  'resource.labels.service_name="mobius-chat" AND jsonPayload.event="turn_attestation"' \
  --limit 5 --freshness=2h --format=json
```
Must return entries with the same `correlation_id` values as P3, as structured
`jsonPayload` fields — **not a formatted message string**. A log line that
carries the numbers only inside human-readable text is not an emit; nothing can
read it back.

**W — the payload:** paste the `promise` dict as it was published for one real
request (a debug log at `post_chat`, or read it off the queue). It must contain
`version`, `tier`, `posted_at`, and the three promised terms.

### Also required

- **Migration idempotency, demonstrated:** boot twice against a DB that already
  has the table, and show the second boot is clean.
- **The pre-deploy case:** one turn whose payload has **no** `promise` key —
  enqueued before deploy, or hand-crafted. It must run normally and produce a
  row with a null promise, **not** a synthesised one and **not** a crash.
- **The report-back number:** the observed `queue_wait` spread (min / p50 / p90 /
  max) across the day. This is segments 1+2 of §7c and **nothing has ever
  measured it**. It determines whether §7's latency figures get restated under a
  new `promise_version`.

**If any surface cannot be evidenced, say which one and why — do not summarise
the others as success.** A partial demonstration reported as done is worse than
an honest blocker, because it ends the checking.

---

## 7. QUESTION FOR CHAT — why are there ten publish call sites?

**Ananth is asking this directly, and it is not rhetorical.**

`orchestrator.py` has **three publish terminals reached from ten call sites**:

| terminal | call sites |
|---|---|
| `_publish_completed` (:1379) | :889, :909, :988, :1090 |
| `_publish_failed` (:1659) | :836, :921, :996, :1063 |
| `_publish_clarification_or_refinement` (:1093) | — |

Plus an early `return` at :1385 when `ctx.response_payload` is empty.

**The question:** is this ten *distinct outcomes* the pipeline genuinely has, or
is it one outcome reached ten ways because the exit path was never consolidated?

**Why it matters beyond tidiness.** Ten exits is ten places for a future
telemetry, persistence or contract change to be added in nine of them. That is
the shape this program keeps finding — a producer wired at most of its sites and
silently absent at the rest. The `finally` in §2c is a **workaround for this
structure, not a fix**: it guarantees the attestation closes once regardless of
which exit fired, but it does not make the exits comprehensible.

**What we want back from Chat, in words, not code:**
1. What distinguishes each of the ten? Name them.
2. Which are genuinely different outcomes vs. the same outcome at different
   depths of a `try` nest?
3. Is there a reason not to consolidate them behind one exit that takes an
   outcome enum?
4. **Do all ten actually fire in production, or are some unreachable?** A
   `_publish_*` call site that never runs is a different problem from a
   redundant one, and only Chat can say which.

**This is a question, not a work item.** Do not refactor the exits as part of
step 1 — the answer shapes step 2, and consolidating exits while wiring a new
`finally` through them is two risky changes in one deploy. Answer first.

---

## 6. Standing constraints

- Dev first. Tested in dev, then commit, then deploy, then next item.
- `scripts/deploy.sh dev` — not raw gcloud.
- `.venv/bin/python` for pytest, not system python3.
- Push back on anything above that is wrong. Several claims here are `[READ]`
  from source at specific line numbers; if a line has moved, say so rather than
  guessing at intent.
