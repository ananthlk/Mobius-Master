# DB Consolidation Proposal: Common vs Separate

Based on the [DB Inventory](DB_INVENTORY.md), this document proposes what could live in a shared DB vs what stays separate.

---

## Current state (summary)

- **mobius-os:** One Postgres DB (e.g. `mobius`) — app data (tenants, users, patients, resolution plans, evidence, tasks, billing, etc.). No shared tables with other modules.
- **mobius-rag:** One Postgres DB (e.g. `mobius_rag`) — documents, chunks, embeddings, publish pipeline. Source for dbt ingest.
- **mobius-chat:** One Postgres DB (e.g. `mobius_chat`) — `published_rag_metadata` + `sync_runs` (written by mobius-dbt). Optional clone of RAG schema for dev.
- **mobius-dbt:** Reads RAG Postgres, writes BigQuery (landing + mart) and Chat Postgres + Vertex. No dedicated DB; uses other modules’ DBs.

---

## Proposal: what is “common” vs separate

### Candidate for shared (one DB or one instance)

- **Auth / tenants / org config:** Today only mobius-os has tenants, roles, users, auth. If Chat or RAG ever need “current user” or tenant scoping, that could be a **shared platform schema** (e.g. `platform.tenants`, `platform.users`) read by OS, and optionally by Chat/RAG for filtering. **Recommendation:** Defer until there is a concrete need (e.g. Chat or RAG need to resolve tenant/user). No change today.

- **Nothing else** is clearly “common” across all four. RAG data is domain-specific (documents/chunks/embeddings). Chat’s `published_rag_metadata` is the consumer view of that pipeline. OS is a separate product surface (sidecar, patients, tasks).

### What stays separate

- **mobius-rag Postgres:** Keep as-is. High write volume (chunking, embeddings, publish); schema is RAG-specific. dbt reads from it; no need to co-locate with OS or Chat.
- **mobius-chat Postgres:** Keep as-is. Used for `published_rag_metadata` + `sync_runs`; must be the same DB that dbt sync writes to. Could later be the same **instance** as something else (see below), but schema stays Chat-focused.
- **mobius-os Postgres:** Keep as-is. Many app tables; no overlap with RAG/Chat.
- **BigQuery:** Stays separate (landing + mart). Analytics/ETL boundary.

### “One DB” interpretation (if consolidating later)

If you later want **one Postgres instance** to reduce cost/ops:

- **Option A — One instance, multiple databases:** Same server, multiple DBs: e.g. `mobius_platform` (future shared auth/tenants), `mobius` (OS), `mobius_rag` (RAG), `mobius_chat` (Chat). Each app keeps its current connection string; only the host/port (and optionally credentials) are shared. **Recommendation:** Easiest migration; no schema mixing.

- **Option B — One instance, one database, multiple schemas:** Single DB with schemas: e.g. `platform`, `os`, `rag`, `chat`. Apps would use `search_path` or schema-qualified names. Requires config and possibly code changes in each module. **Recommendation:** Only if you need cross-schema queries or strict single-DB governance.

For now, **no consolidation is required.** The inventory and this proposal give a basis to revisit when you introduce shared auth or want to reduce the number of Postgres instances.

---

## Dependencies to respect

- **Chat ↔ dbt sync:** `CHAT_RAG_DATABASE_URL` (Chat) and `CHAT_DATABASE_URL` (dbt) must point to the **same** Postgres DB so that `published_rag_metadata` written by `sync_mart_to_chat.py` is what Chat reads.
- **dbt ↔ RAG:** dbt reads `rag_published_embeddings` from RAG Postgres; RAG does not depend on dbt.
- **OS:** No DB dependency on RAG or Chat.

---

## Next steps (optional)

1. If/when adding shared auth or tenant resolution across products, introduce a **platform** schema (or DB) and document which apps read it.
2. If consolidating instances, prefer **Option A** (one instance, multiple databases) and keep each app’s schema as-is.
3. Keep [DB_INVENTORY.md](DB_INVENTORY.md) updated when adding DBs or env vars.
