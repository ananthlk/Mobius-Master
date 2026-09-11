# Chat v2 — schema delta

What exists, what changes, what is new. `[MEASURED]` against dev, 2026-09-11.
Row counts approximate from `pg_class`.

---

## 1 · UNCHANGED — v2 uses these exactly as they are

| table | rows | role in v2 |
|---|---|---|
| `chat_threads` | 5,515 | thread identity. **The scope of the gap ledger** |
| `chat_turn_messages` | 11,214 | the transcript |
| `prompt_blocks` · `prompt_compositions` · `prompt_composition_members` | — | **v2 reads prompts from here ONLY.** No prompt text in v2 code |
| `llm_calls` | 76,632 | per-call telemetry. **Not v2''s to fix** — see §5 |
| `turn_spans` | 5,154 | per-module latency. See the open question in §4 |
| `adjudication_scores` | 299 | post-run critic verdicts — **fire-and-forget, outside the promise** |
| `chat_progress_events` | 232,349 | **the event stream, and no schema change is needed** — see §3 |

---

## 2 · CHANGED

### `turn_attestations` — the main delta (migration 068)

Live today with 15 columns. **Everything below is additive and idempotent**
(`run_migrations.py:179` re-applies every file on every boot).

| add | why | gated on |
|---|---|---|
| `exit_mode` | **semantic** outcome — `complete`/`budget`/`capability`/`error`. A turn can be mechanically `completed` and semantically `budget`, and **that is the common case** | the `how` that populates it |
| `orchestrator_version` | **v1 vs v2 comparison is the whole safety argument.** Without it the phased routing cannot be evaluated | v2 skeleton |
| `first_delivery_at` | POST → first useful content. **Distinct from `published_at`** | per-round draft emit |
| `band_s` · `in_band` | `[RULED]` ± relaxation. **Three outcomes, not a boolean** | — |
| `continuation_offered` | measures whether *"I can close these if you like"* is ever accepted. **An offer nobody takes is a worse answer dressed as a helpful one** | exit modes |
| `forecast_latency_s` | the user-facing estimate, **distinct from the promise.** Answers *"did we tell the user the truth"* separately from *"did we keep the promise"* | step 2 / planner |
| `tools_offered` · `declared_latency_ms` · `declared_version` | turns Tool Manifest''s **declared** latencies into measured ones via set-level co-occurrence. **`declared_version` prevents a declaration edit from retroactively rewriting the accuracy history that was about to correct it** | Tool Manifest |
| `gaps_closed_ids` · `gaps_open_at_exit` | **ids, not counts.** Counts are what made 182 stuck-gap turns invisible | `thread_gaps` |

**Rule carried from tonight: a field ships in the same change as the `how` that
populates it.** An empty `open_items` reads as *"no open items"*, not as
*"nobody writes this yet"* — which is the `needs_route_clarification` shape (4
fields, 0 writers, falsy defaults).

### `chat_state` — a deletion, not an addition

`state_json` carries **13 keys**, one of which is `refined_query`.
`[MEASURED]` `PipelineContext.refined_query` has **zero writers, 17 reads**, and
every read is `ctx.refined_query or ctx.message` — so every one is
unconditionally `ctx.message`. Yet `orchestrator.py:1575` does:

```python
merged = {**(ctx.merged_state or {}), "refined_query": ctx.refined_query}
save_state_tracked(ctx, merged)
```

**Every completed turn performs a second `chat_state` write whose only added
payload is a constant `None`** — and `storage/threads.py:750` documents that
second write as the cause of a compare-and-set defect fixed earlier today.

**v2 does not perform it.** `[OPEN]` Removing the key from `state_json` is a v1
cleanup, not v2''s — v2 simply never writes it.

---

## 3 · NO CHANGE NEEDED — the per-round draft

`chat_progress_events` already carries the channel. `[MEASURED]` 30 days:

```
thinking 54,510 · bandit_reward_persisted 23,083 · message 8,110
integrator_partial 3,439 · detail_ready 2,200 · quality_audit 1,336
draft_ready 1,231 · tool_progress 122
```

**1,231 `draft_ready` events against ~1,266 turns — almost exactly one per
turn.** That is the measurement behind *"the draft only reaches the user at the
end."*

**So this is an emit-frequency change, not a schema change.** `event_type` stays
`draft_ready`; v2 fires it per round carrying `running_answer`.
**Task #33 history must travel with the work order** — the per-round event was
removed on 2026-08-05 because it streamed **raw tool-result text**, not a
synthesis. **The removal was correct; the fix is different content on the same
channel, never a revert.**

---

## 4 · NEW

### `thread_gaps` — migration 067

Spec''d in `docs/governor-thread-gaps-spec.md`. Governor-minted `gap_id`,
thread-scoped, read at `state_load`, **written once at turn end** in the
attestation''s `finally`. Carries `opened_promise_version` because a gap
outlives the promise it was opened under, and `attempted_by` because **that is
the only thing that separates BUDGET from CAPABILITY at exit** — without it the
system defaults to the flattering explanation.

### Round-level records — `[OPEN]`, and I would not decide this alone

Per-posture latency is needed to calibrate the admission formula, and today
every cost figure is a **round average used as a proxy for every posture** —
certainly wrong, since a FRAME round with no tool call is cheaper than a CLOSE
round that calls rag.

**Two options, and the second has a trap:**

1. **A `turn_rounds` table** — explicit, unsampled, one row per round.
2. **Reuse `turn_spans`** with `module='posture:EXPLORE'` — no new table, and it
   matches Ananth''s standing instruction *"if you write to the emit envelope
   table it should pick it up, don''t invent something new."*

🔴 **The trap in option 2:** `turn_spans` carries `sampled` and `sample_rate`
columns. **A sampled span cannot back a conformance number** — if posture rounds
are sampled, per-posture calibration is computed on an unknown subset. Option 2
is right **only if posture spans are exempt from sampling**, and that exemption
has to be explicit, not assumed.

---

## 5 · NOT v2''s to fix, but v2 is blocked by them

| item | owner | effect on v2 |
|---|---|---|
| `llm_calls.turn_id` **NULL on all 25,310 rows**, and `chat_turns` has **no `turn_id` column** | llm_manager | join on `correlation_id`; **never use `turn_id`** |
| `react_1` cost coverage **686/1,236** | llm_manager | spend understated **on the path v2 steers** → **fails open.** **Cost may INFORM, must not DECIDE** |
| worker never sets the logging ContextVar | chat telemetry | **every worker log line of every turn is uncorrelated in Cloud Logging** |
| `requires` **0 of 59** populated; Stage A has never filtered | Tool Manifest | every exclusion is ranking, none is a permission boundary |

---

## 6 · Order

```
067  thread_gaps                         ← everything reads it
068  turn_attestations additive columns  ← each WITH its populating how
     (no migration) per-round draft_ready emit frequency
     (no migration) v2 stops writing refined_query
0xx  round records — after the sampling question is settled
```

**Every migration idempotent.** `CREATE TABLE IF NOT EXISTS`,
`ADD COLUMN IF NOT EXISTS` — there is no applied-ledger and every file re-runs
on every boot.
