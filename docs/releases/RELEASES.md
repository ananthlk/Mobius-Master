# Mobius Release History

Newest first. Each product release pins an exact set of module versions —
see the lockfile for commit SHAs.

For how versions are assigned, read [RELEASE_PROCESS.md](RELEASE_PROCESS.md).

---

## product-v1.0.0 — 2026-09-07

**The first formally versioned Mobius.** Not a feature release: a
*baseline*. Fourteen modules that had been shipping continuously for eight
months are pinned to a named version for the first time, so that from here on
"what is in production" is a question with an exact answer.

- **Story:** [product-v1.0.0.md](product-v1.0.0.md)
- **Manifest:** [product-v1.0.0.lock.json](product-v1.0.0.lock.json)

| Module | Version | Notes |
|---|---|---|
| mobius-chat | v1.0.0 | [notes](modules/mobius-chat/v1.0.0.md) |
| mobius-rag | v1.0.0 | [notes](modules/mobius-rag/v1.0.0.md) |
| mobius-payor | v1.0.0 | [notes](modules/mobius-payor/v1.0.0.md) |
| mobius-skills | v1.0.0 | [notes](modules/mobius-skills/v1.0.0.md) |
| mobius-skills-mcp | v1.0.0 | [notes](modules/mobius-skills-mcp/v1.0.0.md) |
| mobius-os | v1.1.0 | [notes](modules/mobius-os/v1.1.0.md) — supersedes a stale `v1.0.0` tag |
| mobius-story-ui | v1.0.0 | [notes](modules/mobius-story-ui/v1.0.0.md) |
| mobius-qa | v1.0.0 | [notes](modules/mobius-qa/v1.0.0.md) |
| mobius-interact | v1.0.0 | [notes](modules/mobius-interact/v1.0.0.md) |
| mobius-dbt | v1.0.0 | [notes](modules/mobius-dbt/v1.0.0.md) |
| mobius-auth | v1.0.0 | [notes](modules/mobius-auth/v1.0.0.md) |
| mobius-answer-cache | v1.0.0 | [notes](modules/mobius-answer-cache/v1.0.0.md) |
| mobius-vault | v1.0.0 | [notes](modules/mobius-vault/v1.0.0.md) |
| product-awareness | v1.0.0 | [notes](modules/product-awareness/v1.0.0.md) — carved out into its own repo for this release |

**Carried as pre-release (untagged, in the manifest):** mobius-config,
mobius-contracts, mobius-db-agent, mobius-design, mobius-document-viewer,
mobius-migrations, mobius-qa-modules, mobius-rag-api.

**Not in the release set:** mobius-retriever (deprecated).

### Two things this release records rather than hides

1. **`mobius-rag` and `mobius-payor` were tagged from feature branches**, not
   `main` — `retriever-answer-engine` (+201 commits) and
   `claude/sources-module-canonical-payor-enumerate` (+227). In both cases the
   branch is strictly ahead of `main`, so the branch *is* the live product and
   `main` is the stale ref. The manifest names the branch it tagged.
2. **`mobius-os` already carried a `v1.0.0` tag** pointing at a January commit,
   roughly sixty commits behind its own HEAD. Rather than move a published tag,
   this release assigns it **v1.1.0**. This is the case that justifies
   per-module semver: one module's clock had already run ahead of the rest.

---

*No releases before this one. Prior tags (`alpha`, `v1`, `v0.13.7-beta`,*
*`answer-engine/baseline-v0`) were ad-hoc markers, not a versioning scheme, and*
*are left in place untouched.*
