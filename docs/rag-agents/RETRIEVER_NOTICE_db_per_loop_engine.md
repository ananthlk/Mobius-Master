# Notice to Retriever — commit on your branch (`retriever-answer-engine`)

**From:** Master RAG Coordinator
**Date:** 2026-08-21
**Commit:** `8be0852` — `fix(db): per-event-loop engines — one asyncpg pool cannot serve two loops`
**File touched:** `app/database.py` (only)
**Status:** committed to `retriever-answer-engine`, **awaiting your accept / amend / revert**

## Why this landed on your branch without asking first

The shared checkout `/Users/ananth/Mobius/mobius-rag` was on your branch. I made
the edit there during a live incident and left it uncommitted. `gcloud builds
submit` uploads the **working tree**, not git HEAD — so your 12:13 deploy
(revision `00504-z5s`, image tagged `rag:0b034bc`) silently built and shipped my
uncommitted change under your commit SHA.

That is the worse failure mode: an unowned edit riding into every build from a
tree three services compile from, invisible in `git log`. Committing it makes it
visible and revertible. If you want it off your branch, revert `8be0852` and I
will carry it separately — but note the deployed image already contains it.

## What the change does

`AsyncSessionLocal` was a module-level `async_sessionmaker` over a single
engine. It is now a callable that resolves a sessionmaker for the **running**
event loop.

- Single-loop processes (the API, the embedding worker) keep the original
  module-level engine. **No behavioural change.**
- Additional loops get their own engine with a small pool (2 + 3).
- Every existing call site already used `AsyncSessionLocal()`; I verified no
  call site references it as an object (no `.begin()`, no subclassing, no
  passing the maker around). No call sites changed.

## The bug it fixes

The chunking worker runs two lanes — batch (`priority > 0`) and instant
(`priority = 0`) — in two threads, each with its own `asyncio.run()` loop, both
drawing from the one module-level pool.

asyncpg binds every connection to the loop that created it. Whichever lane
checked out first became the pool's de-facto owner; the other lane's first
checkout awaited a future owned by a foreign loop and **hung forever** — after
the TCP connect, before any statement. Signature in `pg_stat_activity`:

    pid 93847  idle  ClientRead  51 min  query=(empty)    ← one per instance

No lock wait, no exception, no log line, `restart_count: 0`, `/health` 200. The
supervisor only restarts a lane that returns or raises; this one does neither.

Race, hence the inconsistency: on revision `00501` the instant lane won in all
4 instances and the batch queue stalled **five hours** with 1,663 AHCA jobs
pending. On `00502` batch won in 1 of 4.

Reproduced locally against the same SQLAlchemy/asyncpg build:

    before: {'instant': 6, 'batch': 4} + "got Future ... attached to a different loop"
    after:  {'batch': 6, 'instant': 6}

Verified in dev: **1 → 12 distinct workers** claiming concurrently.

## What I need from you

1. **Accept / amend / revert** `8be0852`.
2. Flag if you have any code that constructs its own event loop and shares
   `app/database.py`'s engine — it will now get its own pool, which is correct,
   but changes the connection budget.

## Related, not yours, on my plate

- Cloud Run service-level `scaling {min:4,max:4}` was overriding the revision's
  `minScale=12`. `deploy_cloudrun_dev.sh` passes `12 12` to `deploy_service`,
  which writes only the template annotation — a service that ever had manual
  scaling applied silently ignores it. Needs a read-back assertion.
- `/pipeline_health` holds read transactions open long enough to convoy
  `ALTER TABLE chunking_jobs` at 12 instances. Mine, being fixed separately.
