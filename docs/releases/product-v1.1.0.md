# Mobius product-v1.1.0

**Cut:** 2026-09-07 · **Modules:** 18 tagged, 7 pre-release, 1 deprecated
**Manifest:** [product-v1.1.0.lock.json](product-v1.1.0.lock.json)

---

## What this release is

**The first one that contains work.** `product-v1.0.0` was a baseline and
`product-v1.0.1` a coverage fix; neither shipped anything new. This one closes
the forty-one-commit gap those two left open, across five modules.

| Module | | Why |
|---|---|---|
| `mobius-chat` | v1.0.0 → **v1.1.0** | Platform framework surface and the Releases tab |
| `mobius-skills` | v1.0.0 → **v1.1.0** | Deep Research: decisions as contracts, cost capture, console auth |
| `mobius-payor` | v1.0.0 → **v1.1.0** | The Research Console, served and gated |
| `product-awareness` | v1.0.0 → **v1.1.0** | Doc registry in Postgres, admin ingestion surface, τ_gap recalibration |
| `mobius-answer-cache` | v1.0.0 → **v1.0.1** | Documentation correction only |

All five are MINOR or PATCH under this repo's rule — MAJOR means a peer module
breaks, not that the change was large. Nothing here changes a shape another
module reads.

## What a user can do that they could not at v1.0.0

- **See what the system is made of.** The platform surface groups every module by
  the 7+1 layer framework, showing what it runs, where the code is, and who owns
  it — read from deploy configs rather than from a description of the system.
- **Read what is released.** A Releases tab rendered from the generated
  lockfiles, which cannot drift from what was tagged.
- **Publish a product document without a code change.** The doc registry moved
  out of a hardcoded dict into Postgres, with an admin surface. Uploaded bodies
  persist, which they did not before — a Cloud Run container has no durable disk.
- **Follow a research question end to end.** The Research Console serves the
  trace live, gated on the fleet's own sign-in, with per-call cost captured.

## Release-ordering constraints — new, and load-bearing

This is the first release where modules constrain each other's deployment. A
lockfile that pinned versions without recording this would be actively
misleading.

1. **`mobius-payor` v1.1.0 hard-depends on `mobius-user`'s
   `POST /api/v1/auth/verify`.** The `/auth/me` fallback was deliberately
   removed, so **rolling back `mobius-user` turns the Research Console into a 503
   by design.** These two cannot be rolled back independently.

2. **`mobius-skills` changed the meaning of `accepted`** — now `bool(kept)`, with
   the required-field check split into `meets_required`. The shape is unchanged
   and nothing breaks, but a consumer branching on `accepted` will see requests
   flip from `not_answered` to accepted-with-caveat. Behaviour change inside an
   unchanged contract: worth reading before consuming.

3. **The console has a generator/server split across two repos.**
   `deep_research/console.py` in `mobius-skills` generates the page;
   `mobius-payor` serves a checked-in copy at
   `app/routers/_research_console_page.py`. **Bumping skills without
   regenerating and redeploying payor leaves the served console behind.** A
   hand-edit to the copy has already caused one production drift.

4. **`research.*` schema ownership is unsettled.** `mobius-payor` reads the
   schema `mobius-skills` owns, and adds `research.judge_override` to it from its
   own migration ledger. Two ledgers writing one schema is how migration
   collisions start — and `payor` already has duplicate migration numbers.

## Carried forward, unresolved

- **`mobius-rag` and `mobius-payor` are still tagged from feature branches** —
  `retriever-answer-engine` and `claude/sources-module-canonical-payor-enumerate`,
  both strictly ahead of `main`. Named as a v1.1.0 requirement in the v1.0.0
  story and still not done. This is now the oldest open item in the release
  history.
- **`payor`'s duplicate migration numbers** (two `047_*`, two `050_*`) remain.
- **`mobius-interact`'s namespace write-auth** remains unenforced.
- Six uncommitted files in `payor` were excluded from its tag — a tag points at a
  commit.

## Attribution

The `mobius-skills` and `mobius-payor` work in this release was done by the Deep
Research session, not by the session cutting it. Their release notes were written
from the commits and verified against the code.

## What v1.2.0 should require

1. `mobius-rag` and `mobius-payor` merged to `main` — third release running.
2. One owner for the `research.*` migration ledger.
3. The console generator and its served copy reconciled, or the copy removed.
