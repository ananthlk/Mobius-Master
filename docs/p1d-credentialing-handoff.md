# P1d — Questions for the Roster & Credentialing owner

**From:** Chat seat (mobius-chat refactor program, phase P1d)
**Date:** 2026-09-09
**Status:** BLOCKED — nothing deleted, nothing committed, tree is intact

**How to answer:** edit this file directly under each question, commit, and I'll pick it up.
Partial answers are fine — answer what you know and mark the rest UNKNOWN. "I don't know,
nobody owns this any more" is a genuinely useful answer and I'd rather have it than a guess.

---

## Context — what this is about

Ananth's directive: chat should not own credentialing/roster. The domain moved to the
`provider-roster-credentialing` skill. I'm removing chat's copy.

**What I found in mobius-chat:** 14 modules, **9,994 lines**, plus 16 HTTP routes and
~2,300 lines of frontend JS.

| Lines | Module |
|---|---|
| 4,395 | `app/services/roster_credentialing_orchestrator.py` |
| 1,033 | `app/services/credentialing_run_service.py` |
| 688 | `app/api/credentialing.py` (16 routes) |
| 602 | `app/storage/roster_truth_pg.py` |
| 538 | `app/storage/credentialing_assertions_pg.py` |
| 329 | `app/api/roster_upload.py` |
| 325 | `app/storage/credentialing_runs_pg.py` |
| 177 | `app/pipeline/credentialing_envelope.py` |
| 176 | `app/services/credentialing_gate_event.py` |
| 175 | `app/services/credentialing_workflow_followups.py` |
| 174 | `app/planner/credentialing_flow_intent.py` |
| 169 | `app/services/credentialing_state_serde.py` |
| 150 | `app/storage/roster_review_pg.py` |
| 63 | `app/services/roster_source_of_truth.py` |

**What the logs say:** 30 days of mobius-chat request logs show **zero traffic** on every
credentialing/roster route except one — `GET /chat/credentialing-runs`, which gets 233 hits
from chat's *own* page bootstrap and returns an empty list every time (the tables have 0 rows).

**Why I'm asking anyway:** logs only show what ran *during the window*. A quarterly job, a
manual flow, or something you're mid-build on would look identical to dead code. Ananth's read
is that your pipeline has "morphed" and looks very different now — if that's right, most of
this is safe. I'd rather confirm than infer.

---

## Q1 — Does your skill call any of chat's credentialing routes? **[most important]**

These are the 16 routes on `app/api/credentialing.py`:

```
GET    /chat/credentialing-runs
POST   /chat/credentialing-runs
DELETE /chat/credentialing-runs/{run_id}
GET    /chat/credentialing-runs/{run_id}
POST   /chat/credentialing-runs/{run_id}/seed-roster
GET    /chat/credentialing-runs/{run_id}/org-npis
GET    /chat/npi-lookup/{npi}
GET    /chat/credentialing-runs/{run_id}/roster-truth
POST   /chat/credentialing-runs/{run_id}/roster-truth
GET    /chat/credentialing-runs/{run_id}/roster-diff
POST   /chat/credentialing-runs/{run_id}/roster-snooze
GET    /chat/credentialing-runs/{run_id}/roster-snoozes
POST   /chat/credentialing-runs/{run_id}/validate
PATCH  /chat/credentialing-runs/{run_id}/pml-tasks
PATCH  /chat/credentialing-runs/{run_id}/taxonomy-tasks
POST   /chat/roster-upload
```

I found exactly one call site in your repo:
`provider_skill/sub_skills/nppes_validation/routes.py:2527` builds
`{chat_base}/chat/roster-truth/{org_name}/provider/{provider_id}/summary` — but **chat never
registered that path** (chat's is `/chat/credentialing-runs/{run_id}/roster-truth`), and the
code raises `HTTPException(503)` at `:2529` before issuing the request. So it looks dead
twice over. Please confirm.

Also: `static/pipeline-chat.js:637,668` in your repo calls
`${API}/chat/credentialing-runs/${runId}/validate`. That file looks like a copy of chat's
own `pipeline-chat.js`. Is it live in your service, or a vendored leftover?

**ANSWER:**

>

---

## Q2 — Is `POST /chat/roster-upload` still used by anything of yours?

This one is separate from the rest because `mobius-skills/appeals-agent/loop/run_loop.py:170`
POSTs to it at the live Cloud Run URL, under a comment header that says `# Endpoints (live)`.
Logs show zero calls in 30 days.

Chat keeps this route as a deliberate "permanent alias" (`app/main.py:2234`) for an
instant-RAG handler. I am **keeping it** until someone confirms it's dead — it's ~329 lines
against a non-zero chance of breaking a loop nobody is watching.

Note your skill has its own `/roster-uploads` (hyphen-plural) surface, which is unaffected.

**ANSWER:**

>

---

## Q3 — Do you write to, or read from, these tables?

Chat's credentialing code touches these. **Nothing will be dropped** — the DB seat's ruling is
code-only, empty tables cost nothing, and dropping is the irreversible half. I'm asking because
if *you* read them, chat deleting its writers changes what you see.

| Table | Rows | Where defined |
|---|---|---|
| `credentialing_runs` | 0 | `db/schema/027_credentialing_runs.sql` |
| `credentialing_assertion` | 0 | `db/schema/018_credentialing_assertion.sql` |
| `roster_review_session` | 0 | `db/schema/017_roster_review.sql` |
| `roster_line_item` | 0 | `db/schema/017_roster_review.sql` |
| `roster_truth` | ? | inline `CREATE TABLE IF NOT EXISTS`, `roster_truth_pg.py:29` |
| `org_summary` | ? | inline, `roster_truth_pg.py:48` |
| `roster_snooze` | ? | inline, `roster_truth_pg.py:58` |
| `provider_roster` | 156 (last write 2026-08-12) | — |
| `roster_events` | 260 (last write 2026-07-06) | — |

`provider_roster` and `roster_events` are the two with data, and my understanding is those are
**yours**, not chat's. Confirm?

Also: `roster_truth_pg.py:439` lazily calls `bulk_import_tasks` from
`app/sub_skills/task_management.py` — so chat's roster code currently writes into the
**task-manager** tables. If that's a path you depend on, say so.

**ANSWER:**

>

---

## Q4 — Is chat's `/pipeline` page yours, ours, or nobody's?

`main.py:3129` serves a `/pipeline` UI backed by ~2,300 lines of JS
(`frontend/static/pipeline-*.js`) making 15 calls into the routes above.

The 233 log hits are this page loading and getting an empty list back. So it *is* being
opened by someone. `main.py:2673` says the router was "restored for pipeline UI."

Is this a surface you or your users rely on, or a debug page that outlived its purpose?

**ANSWER:**

>

---

## Q5 — Anything you're mid-build on that would make this a bad time?

If you have work in flight that assumes chat's credentialing surface exists, tell me and I'll
sequence around it. I'd rather wait than break something you're halfway through.

**ANSWER:**

>

---

## Things I found that are *your* side, offered as FYI — no action needed from me

1. **A route that's been 404ing.** `nppes_validation/routes.py:2527` proxies to
   `/chat/roster-truth/{org}/provider/{id}/summary`, a path chat never registered. It fails
   before issuing the request anyway (`HTTPException(503)` at `:2529`), so `_proxy_url` is
   assigned and unused. Broken regardless of anything I do.

2. **`pipeline-chat.js` looks vendored.** Your `static/pipeline-chat.js` appears to be a copy
   of chat's, and its `API` constant resolves to chat's endpoints (`/chat`, `/chat/stream/`,
   `/chat/response/`). If it's a leftover, it'll break when chat's routes go — worth deleting
   on your side either way.

---

## What happens after you answer

- **If everything is dead:** chat's credentialing surface comes out in one atomic change —
  the 14 modules, the 16 routes, and the frontend together. Not in stages, for a specific
  reason: every route in `api/credentialing.py` imports its dependencies *inside* the handler
  and wraps them in `except Exception: return []`. Deleting the services without the routes
  would leave 16 endpoints returning `200` and empty forever, with the `ImportError` swallowed
  and nothing reporting a problem. Removing them together makes failure honest.

- **If something is live:** it stays, and I record it in the program doc as a permanent
  dependency so nobody deletes it later on a traffic argument.

Either way the tables stay. Nothing is dropped.
