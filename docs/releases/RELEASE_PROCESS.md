# Mobius Release Process

How a version number gets assigned, what it means, and how a release is cut.

## The two-level model

Mobius is not one codebase. It is ~24 repositories that ship on their own clocks.
So versioning happens at two levels, and they mean different things.

### Level 1 — Module version (`v1.2.3`)

Every shipping module carries its **own semver tag in its own repo**. A module
version answers: *what state is this one service in?*

```
mobius-chat   v1.0.0
mobius-rag    v1.0.0
mobius-os     v1.1.0     ← different, because it shipped ahead
```

Semver rules, applied to a service rather than a library:

| Bump | When |
|---|---|
| **MAJOR** | A contract other modules depend on changed incompatibly — an API shape, an event envelope, a DB column another module reads. Anything that makes a peer module break if it does not also change. |
| **MINOR** | New capability, backward compatible. New endpoint, new skill, new surface. |
| **PATCH** | Fix or hardening. No new capability, no contract change. |

The test for MAJOR is always *"does a peer break?"* — not *"is this a big change?"*.
A 200-commit refactor that keeps every contract intact is a MINOR.

### Level 2 — Product version (`product-v1.0.0`)

A product release is a **lockfile**, not a codebase. It pins the exact module
version and commit SHA of every module at one instant, and tells the story of
what that combination does for a user.

```
product-v1.0.0
  ├── mobius-chat        v1.0.0  @ 3fa105d
  ├── mobius-rag         v1.0.0  @ 53f6178
  ├── mobius-os          v1.1.0  @ a5696f4
  └── … 11 more
```

The product version bumps on its own rules:

| Bump | When |
|---|---|
| **MAJOR** | The product story changes — what Mobius *is* to a user is different. |
| **MINOR** | A user-visible capability arrives (any module MINOR that reaches a surface). |
| **PATCH** | Only fixes shipped. No user-visible new capability. |

A product MINOR does **not** require every module to bump. Most releases move
two or three modules and pin the rest unchanged.

## What lives where

```
docs/releases/
  RELEASE_PROCESS.md          ← this file
  RELEASES.md                 ← the history index, newest first
  product-v1.0.0.md           ← the aggregated story: what this release IS
  product-v1.0.0.lock.json    ← the manifest: module → version → SHA → branch
  modules/
    mobius-chat/v1.0.0.md     ← per-module release notes, generated from commits
    mobius-rag/v1.0.0.md
    …
```

Tags:
- module tags live **in each module's own repo** (`git -C mobius-chat tag v1.0.0`)
- product tags live **in the Mobius superproject** (`git tag product-v1.0.0`)

## Cutting a release

### 1. Tag the modules that moved

```bash
scripts/release/tag_module.sh mobius-chat v1.1.0
```

Creates an annotated tag whose message is the generated release notes. Refuses
to tag a dirty working tree, and refuses to reuse an existing version.

### 2. Generate the manifest

```bash
scripts/release/cut_product_release.py 1.1.0
```

Walks every module in the release set, reads its newest semver tag and the SHA
that tag points at, and writes `product-v1.1.0.lock.json`. This is **read from
git, never hand-edited** — a hand-typed SHA is a lie waiting to happen.

### 3. Write the story

`product-v1.1.0.md` is the narrative: what a user can now do that they could
not before. Drafted from the module release notes, then edited by a human. This
is the artifact the production release team reads.

### 4. Tag the product

```bash
git tag -a product-v1.1.0 -F docs/releases/product-v1.1.0.md
```

## Honesty rules

These exist because a release manifest that overstates maturity is worse than
no manifest at all.

1. **A module is only in the release set if it actually ships.** Stubs and
   experiments are listed in the manifest under `pre_release`, with their real
   commit count, and carry no version tag.
2. **The manifest records the branch it tagged.** When a module's live state is
   on a feature branch rather than `main`, the manifest says so rather than
   quietly tagging a stale `main`.
3. **Release notes are generated from commits, then reviewed.** The generator
   proposes; a human decides what is user-visible. A commit log is not a
   release note.
4. **Deprecated modules are never re-tagged.** They are recorded once with the
   version they died at.

## Release set (as of product-v1.0.0)

**Shipping — 14 modules, tagged:**
mobius-chat, mobius-rag, mobius-payor, mobius-skills, mobius-skills-mcp,
mobius-os, mobius-story-ui, mobius-qa, mobius-interact, mobius-dbt,
mobius-auth, mobius-answer-cache, mobius-vault, product-awareness

**Pre-release — carried in the manifest, untagged:**
mobius-config, mobius-contracts, mobius-db-agent, mobius-design,
mobius-document-viewer, mobius-migrations, mobius-qa-modules, mobius-rag-api

**Deprecated — not in the release set:**
mobius-retriever (superseded by the RAG module's own retrieval path)
