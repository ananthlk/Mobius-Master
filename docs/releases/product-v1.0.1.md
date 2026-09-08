# Mobius product-v1.0.1

**Cut:** 2026-09-07 · **Modules:** 18 tagged, 7 pre-release, 1 deprecated
**Manifest:** [product-v1.0.1.lock.json](product-v1.0.1.lock.json)

---

## What this release is

**A coverage fix.** `product-v1.0.0` pinned fourteen modules and presented itself
as the state of the system. It was not: four services were running in dev from
repositories the manifest never named, so "what is in production?" still had an
answer the manifest could not give.

This release adds those four. No code changed to make it — the work was
establishing that they were missing, giving two of them a repository, and writing
down what they actually do.

## The four

| Module | Service | Why it was missing |
|---|---|---|
| **Mobius-user** | `mobius-user` | 52 commits, live, owns the `mobius_user` database — simply never added to the release set. |
| **mobius-feedback** | `mobius-feedback` | Tracked as 16 loose files in the superproject. Not a repository, so it could not carry a tag. |
| **mobius-db-agent** | `mobius-db-agent` | Carried as *pre-release* in v1.0.0 while already serving traffic. |
| **specs-platform** | `mobius-specs` | Tracked as 11 loose files in the superproject. Same problem as mobius-feedback. |

`mobius-feedback` and `specs-platform` were carved into their own private
repositories for this release, the same treatment `product-awareness` received in
v1.0.0. Both are now registered rather than living as folders that deploy.

## What this release does NOT contain

**Five modules have moved since they were tagged, and this manifest pins the
tags, not the branches.** Forty-one commits sit outside this release:

| Module | Commits ahead of its tag |
|---|---|
| mobius-skills | 15 |
| mobius-payor | 11 |
| mobius-chat | 8 |
| product-awareness | 6 |
| mobius-answer-cache | 1 |

That includes the entire platform-framework rebuild, the product-corpus registry
move to Postgres, and the τ_gap recalibration — all of it shipped to dev today
and none of it in `product-v1.0.1`.

This is a lockfile behaving correctly: a module's version only changes when
someone bumps it, and nobody bumped these. But it means **v1.0.1 is a wider
manifest, not a newer one.** Releasing today's work needs those five modules
re-tagged, each with its own notes — a separate act, deliberately not folded in
here.

## Carried forward from v1.0.0, unchanged

- **`mobius-rag` and `mobius-payor` are still tagged from feature branches** —
  `retriever-answer-engine` and `claude/sources-module-canonical-payor-enumerate`.
  Both remain strictly ahead of `main`, so the branch is still the live product.
  This was named as a v1.1.0 requirement in the v1.0.0 story and has not moved.
- **`mobius-os` stays at v1.1.0**, ahead of the rest, as it was.

## What writing the notes turned up

Two defects found while documenting the new modules, both recorded in their
release notes rather than fixed here:

- **`specs-platform` serves specs from a feature branch.** `GITHUB_RAW` in
  `server.py` is hardcoded to
  `raw.githubusercontent.com/ananthlk/Mobius-Master/service-line-registry/docs` —
  a real branch, but not `main`, with no environment override. The live Specs
  Catalog therefore does not show anything merged to `main`, including everything
  written today.
- **Two services default to open.** `Mobius-user` falls back to
  `CORS_ALLOW_ORIGINS=*` when the variable is unset, and `mobius-db-agent`'s REST
  routes run unauthenticated — warning only — when `DB_AGENT_INTERNAL_KEY` is
  unset. Both are fail-open where the rest of the fleet fails closed.

## Module versions

Eighteen modules. The fourteen from v1.0.0 at unchanged versions, plus:

| Module | Version | Commit |
|---|---|---|
| Mobius-user | v1.0.0 | `cef1a10` |
| mobius-feedback | v1.0.0 | `8c3d319` |
| mobius-db-agent | v1.0.0 | `569c212` |
| specs-platform | v1.0.0 | `d518eea` |

**Pre-release** (untagged, carried in the manifest): `mobius-config`,
`mobius-contracts`, `mobius-design`, `mobius-document-viewer`,
`mobius-migrations`, `mobius-qa-modules`, `mobius-rag-api`.

**Deprecated:** `mobius-retriever`.

## What v1.1.0 should require

Unchanged from v1.0.0, plus one:

1. `mobius-rag` and `mobius-payor` merged to `main`.
2. The `payor` duplicate migration numbers (047, 050) resolved.
3. `mobius-interact` namespace write-auth enforced.
4. **The five stale module tags bumped**, so a product release and the running
   system stop diverging by forty-one commits.
