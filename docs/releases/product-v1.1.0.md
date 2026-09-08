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

1. **`mobius-payor` v1.1.0 fails closed on `mobius-user`.** The `/auth/me`
   fallback was removed deliberately: `POST /api/v1/auth/verify` is the only check
   that enforces **deactivation**, and keeping the fallback meant a `mobius-user`
   rollback would silently downgrade to a weaker check. **Reads are gated too**
   (Ananth: "no sign in no access to even view"), so `/api/research/overview` and
   `/request/{id}` are gated as well — the console becomes *unusable*, not
   degraded. And it is not only rollback: **any `mobius-user` outage does this.**
   That is intended behaviour, and the failure message says which of the two it is.

2. **`mobius-skills` changed the meaning of `accepted`** — now `bool(kept)`, with
   the required-field check split into `meets_required`. Shape unchanged,
   behaviour changed. The reasoning: acceptance is about whether the answer met
   the requester's intent, not about validating the request. **A consumer that
   cannot store a record without a given field should branch on `meets_required`
   and refuse on its own contract**, not on `accepted`.

3. **The console has two independent staleness paths, not one.**
   - `deep_research/console.py` in `mobius-skills` generates the page, served
     from a checked-in copy at `mobius-payor app/routers/_research_console_page.py`.
     A `console.py` change needs **regenerate + redeploy payor**.
   - `deep_research/console_data.py` builds the reader-facing vocabulary into the
     `research.language` **table**, fetched at runtime. A `language.py` change
     needs **console_data re-run, and no payor redeploy at all**.

   Two paths out of one repo, with different remedies. The drift was real: the
   generator previously emitted a page with no `boot()` while the deployed copy
   had one hand-added, so regenerating would have shipped an empty console. Fixed
   in this release.

4. **`research.*` DDL is owned by `mobius-payor`, and always has been** — since
   `045_deep_research.sql`. Thirteen payor migrations touch the schema, including
   064/065/066. `mobius-skills` owns the **code** that reads and writes it;
   `067_judge_override.sql` is consistent with that split, not a violation.

   *An earlier draft of this story claimed shared ownership was a new violation.
   That was wrong, corrected after review by the Deep Research seat and verified
   against both repositories.*

   Two real problems remain in that area:
   - **Four duplicate migration numbers**, not two: `033`, `034`, `047`, `050`.
   - **`067` was applied out of band** — run directly with psycopg2, bypassing the
     `migrations_applied` ledger, and registered retrospectively with a note
     saying so. The single-ledger rule exists so nobody has to reconstruct what
     ran. Surfaced by this release review rather than by the apply.
   - The DDL files are **duplicated across both repos** — `deep-research/schema/`
     holds byte-identical copies of payor's `045`/`046`/`047`. Payor's ledger is
     authoritative; the copies are a drift risk with no mechanism keeping them in
     step.

## Carried forward, unresolved

- **`mobius-rag` and `mobius-payor` were tagged from feature branches** —
  `retriever-answer-engine` and `claude/sources-module-canonical-payor-enumerate`,
  both strictly ahead of `main` at the moment this release was cut. Named as a
  requirement in the v1.0.0 story and unresolved through three releases.
  **Both were fast-forwarded to `main` immediately after this tag** — see
  RELEASES.md. The tags still point at the branch commits, which is accurate:
  that is where they were cut from.
- **`payor`'s duplicate migration numbers** — `033`, `034`, `047` and `050`, all
  four duplicated.
- **`mobius-interact`'s namespace write-auth** remains unenforced.
- Six uncommitted files in `payor` were excluded from its tag — a tag points at a
  commit.

## Attribution

The `mobius-skills` and `mobius-payor` work in this release was done by the Deep
Research session, not by the session cutting it. Their release notes were written
from the commits and verified against the code.

## What v1.2.0 should require

1. `mobius-rag` and `mobius-payor` merged to `main` — third release running.
2. The four duplicate payor migration numbers resolved, and the duplicated
   DDL copies in `deep-research/schema/` either removed or kept in step.
3. The console generator and its served copy reconciled, or the copy removed.
