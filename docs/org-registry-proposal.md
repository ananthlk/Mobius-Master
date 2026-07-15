# Canonical Org Registry — Proposal (v1)

**Author:** User Manager Agent · **Date:** 2026-07-08 · **Reviewers:** TASK Agent, Database Agent (platform data-model owner)
**Status:** APPROVED by both reviewers (2026-07-08; TASK Agent + Database Agent amendments folded in below). Build sequence cleared to start.

> **OWNERSHIP AMENDMENT (Ananth, 2026-07-08, supersedes the "owned by mobius-user" line below):**
> The master org registry is owned by the **provider-roster-credentialing service** (it already maintains the operating org index, ~1,000 orgs). Platform flow: an organization is set up first in that master, then users (providers) are created against it, then they enroll. The schema, API semantics (aliases/org_type/status/merged_into, alias-uniqueness guard, one-hop merge chase, `/resolve`), and the warn-then-enforce consumer pattern in this document transfer to that service. **mobius-user consumes** canonical `org_slug`s (its `user_org_membership` keys to them, validated via the master's API at write time — no cross-DB FK); task-manager consumes the same way. The roster service stops deriving slugs by lowercase-hyphenation once its `/resolve` exists; its `POST /org/upsert` accepts an explicit canonical `org_slug`.

## Problem

Org identity on the platform is writer-seeded free text. A scan of ~1,000 prod task rows found: case-variant duplicates ("SUNSHINE" vs "Sunshine Health"), test junk ("NonexistentOrgXYZ123", bare "O"), 84 empty values, service names used as orgs ("instant-rag"), and system scopes ("_shared_", "_payor_registry_"). The platform data-model review separately flagged that `org_slug` has no UNIQUE constraint anywhere. Every new consumer (task assignment, per-user "my tasks", payor readiness, analytics marts) re-derives org identity by string match and inherits these defects.

## Proposal

A single small registry table, owned by the **mobius-user** service (mobius_user DB — it already owns the first intentional consumer, `user_org_membership`):

```sql
CREATE TABLE org_registry (
  org_slug     text PRIMARY KEY
               CHECK (org_slug ~ '^[a-z0-9][a-z0-9-]*$'),  -- grammar enforced in schema, not comment
  display_name text NOT NULL,             -- "Sunshine Health"
  aliases      text[] NOT NULL DEFAULT '{}', -- known free-text variants ("SUNSHINE", "sunshine health")
  org_type     text NOT NULL DEFAULT 'customer', -- customer | payor | internal | system
  status       text NOT NULL DEFAULT 'active',   -- active | quarantined | merged
  merged_into  text REFERENCES org_registry(org_slug),
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()  -- touched on every update; cache validation, incremental sync, quarantine→active audit
);
CREATE UNIQUE INDEX ON org_registry (lower(display_name));
```

`org_slug` is the canonical key with the UNIQUE (PK) constraint the data-model review asked for — and the CHECK means junk ("O", "SUNSHINE") can never arrive as a slug even via a buggy admin call. System scopes (`_shared_`, `_payor_registry_`) are registered as `org_type='system'` rather than banned — they're real routing scopes, just not customer orgs.

**Alias uniqueness (write-path, v1):** `aliases text[]` has no cross-row constraint, so create/update rejects any alias already present in another row's aliases, display_name, or slug (one EXISTS query with unnest) — otherwise two orgs could claim the same alias and `/resolve` becomes ambiguous. If aliases ever grow past dozens per org, promote to an `org_alias` side table with a real UNIQUE index; explicitly not needed in v1.

**Merges:** `/resolve` chases `merged_into` — resolving a name whose org is `status='merged'` returns the canonical target with `matched_via='merged'`, never the tombstone. One hop only: creating a merge that points at another merged row is rejected, so cycle handling is never needed.

**API (mobius-user, mounted like the existing `/api/v1/users` router):**
- `GET /api/v1/orgs` — list (filter by type/status); returns `max(updated_at)`/ETag so cached consumers can validate staleness cheaply
- `GET /api/v1/orgs/{slug}` — one org
- `POST /api/v1/orgs/resolve {name}` — free text → `{org_slug, display_name, matched_via}` or 404; mirrors the identity directory's `/resolve` pattern
- `POST /api/v1/orgs` — create (admin-gated)

## Consumers

**Task-manager (warn-then-enforce, same rollout shape as the task-interface contract):**
1. *Resolution is local, not per-write:* task-manager pulls the full registry (`GET /orgs`, dozens of rows) into an in-process cache (5-min TTL) and resolves against it — zero added write latency, no new hot-path dependency. `/orgs/resolve` remains for interactive callers.
2. *Warn:* on task write, resolve `org_name` locally; resolved → normalize to `display_name` + stamp `org_slug` (new nullable column on `mobius_task`, no cross-DB FK — task-manager migration 005, owned by the TASK Agent); unresolved → accept + log to `task_validation_log` (distinct field, e.g. `org_name: unresolved`).
3. *Enforce:* separate per-writer flag `TASK_ORG_ENFORCE=<csv of source_modules>` — NOT the existing `TASK_VALIDATION_ENFORCE` (that gates writer code correctness; this gates registry data completeness, on a different rollout cadence). Failure semantics split: registry **unreachable** → fail open (accept + log; an outage must never take down fleet-wide task ingestion); org definitively **not found** in a fresh cache → fail closed (422). Empty org stays allowed only where the schema already permits it, stored as NULL, never `""`.

**Dedup-key consequence (accepted trade-off):** `org_name` is part of the task dedup key `(org_name, source_module, source_ref, type, dim)`. Write-time normalization ("SUNSHINE" → "Sunshine Health") means post-normalization writes will not dedup against pre-normalization open rows for the same logical task. Acceptable given no-backfill; noted in the task-interface contract when warn mode lands.

**mobius-user:** `user_org_membership.org_name` migrates to `org_slug` (FK to registry) in its own follow-up migration; `/users/by-identity` responses add slugs alongside display names.

## Migration path for existing free text

1. Seed the registry from the distinct-value scan: map case/spacing variants of the same org to one slug (variants land in `aliases`), register system scopes and known payors (Aetna, Sunshine Health) with proper types.
2. Service sentinels are NOT junk: `instant-rag` (162 rows, active writer) and any other service-named orgs register as `org_type='internal'` — otherwise those writers stay unresolvable and can never be enforced.
3. Genuine junk ("NonexistentOrgXYZ123", "O") registers as rows with `status='quarantined'` — not a side list — so `/resolve` and the cached registry can distinguish "known junk → reject" from "never seen → maybe a new org" (exactly what warn-mode logging needs). Quarantined entries are surfaced as a review task for Ananth.
4. Sequence: registry + routes ship → TASK Agent lands migration 005 + cached-registry warn mode → quarantine review by Ananth → per-writer `TASK_ORG_ENFORCE`.

## Non-goals (v1)

- **No backfill of existing task rows** — historical `org_name` values stay as written; only new writes are validated/normalized.
- No org hierarchy, no cross-org merge tooling beyond the `merged_into` pointer, no auth/tenancy changes.
- No changes to analytics marts. Marts join later via a daily `org_registry` replica to BQ with `last_synced_at` — mobius_user has no PG→BQ sync flow today; tracked as a platform-gameplan Layer-3 sync-flow item, not v1.

## Open questions for reviewers

1. ~~TASK Agent: existing enforcement flag or its own?~~ **Resolved:** own flag (`TASK_ORG_ENFORCE`), reusing validator plumbing/`task_validation_log`.
2. ~~TASK Agent: per-write resolve calls?~~ **Resolved:** cached full-registry pull, fail open on outage / closed on definitive not-found.
3. ~~Database Agent: mobius_user DB home vs platform-shared schema?~~ **Resolved:** mobius_user DB accepted as the better option — single-owner service + API avoids co-owned-DDL failure modes; enables a real in-DB FK from `user_org_membership.org_slug`; `mobius_task.org_slug` staying FK-less with API-side validation confirmed as the correct cross-DB pattern.
