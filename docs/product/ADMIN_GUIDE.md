# Mobius Chat — admin guide

Two audiences:

- **Part A — Platform / internal operations**: people who configure GCP, Postgres, Vertex, Redis, sync jobs, and local dev orchestration.
- **Part B — Organization administrators**: people who manage tenants, users, and auth — as implemented in **mobius-user** and consumed by apps like Mobius Chat.

Mobius Chat **does not** ship a full “clinic admin console” for task routing or roles in the sense of [mobius-os/USER_TASK_MAPPING.md](../../mobius-os/USER_TASK_MAPPING.md); that document describes **mobius-os** task visibility. Use Part B for **identity and account** scope only unless your deployment adds more UI.

---

## Part A — Platform and internal operations

### A.1 Quick orientation

| Concern | Where to read |
|--------|----------------|
| Repo layout, `mstart` / `mstop` | [README.md](../../README.md) |
| Developer setup, venv, `.env` | [docs/DEVELOPER_SETUP.md](../DEVELOPER_SETUP.md), [docs/ONE_ENVIRONMENT_SETUP.md](../ONE_ENVIRONMENT_SETUP.md) |
| Chat-specific env vars | [mobius-chat/docs/ENV.md](../../mobius-chat/docs/ENV.md) |
| Cross-service env matrix | [mobius-config/env-matrix.md](../../mobius-config/env-matrix.md) |
| Secrets and credential files (overview) | [docs/credentials_reference.md](../credentials_reference.md) |

### A.2 Chat service configuration (checklist)

1. **Queue**: `QUEUE_TYPE` = `memory` (single process) or `redis` (API + worker split). Redis URL when applicable. See [mobius-chat/docs/ENV.md](../../mobius-chat/docs/ENV.md).
2. **Vertex AI**: `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, `VERTEX_MODEL`, and **`GOOGLE_APPLICATION_CREDENTIALS`** pointing at a readable service account JSON.
3. **RAG**:
   - `VERTEX_INDEX_ENDPOINT_ID`, `VERTEX_DEPLOYED_INDEX_ID` — Vertex AI Vector Search.
   - `CHAT_RAG_DATABASE_URL` — Postgres with `published_rag_metadata` (and related schema per your migration path).
   - Optional **narrowing filters**: `CHAT_RAG_FILTER_PAYER`, `CHAT_RAG_FILTER_STATE`, `CHAT_RAG_FILTER_PROGRAM`, `CHAT_RAG_FILTER_AUTHORITY_LEVEL` — if set, retrieval is restricted to matching metadata.
4. **Skills / MCP** (when using tools): `MCP_SERVER_URL`, `CHAT_SKILLS_GOOGLE_SEARCH_URL`, timeouts — see [mobius-chat/docs/ENV.md](../../mobius-chat/docs/ENV.md).

### A.3 RAG data path (who does what)

- **MOBIUS-DBT / sync jobs** publish from the analytics mart into Postgres and Vertex; Chat is a **consumer** (read-only on published metadata).
- Contract and expectations: [mobius-dbt/docs/CONTRACT_MOBIUS_CHAT_PUBLISHED_RAG.md](../../mobius-dbt/docs/CONTRACT_MOBIUS_CHAT_PUBLISHED_RAG.md).
- Chat setup steps: [mobius-chat/docs/PUBLISHED_RAG_SETUP.md](../../mobius-chat/docs/PUBLISHED_RAG_SETUP.md).

### A.4 Health and troubleshooting

- General: [docs/TROUBLESHOOTING.md](../TROUBLESHOOTING.md).
- Chat staging / streaming: [docs/chat_staging_stream_troubleshooting.md](../chat_staging_stream_troubleshooting.md) when relevant.

### A.5 Operational split

| Layer | Typical owner | Notes |
|-------|----------------|-------|
| **Chat API + worker** | App team | Scaling, Redis, process restarts |
| **Vertex + index** | Platform / ML | Index deploy, quota, endpoint IDs |
| **Postgres `mobius_chat`** | DBA / platform | Migrations, backups, connection limits |
| **Sync from dbt → Chat stores** | Data / platform | Pipeline failures block fresh content |

---

## Part B — Organization administrators (current scope)

### B.1 Identity and tenancy

The **mobius-user** package owns a dedicated PostgreSQL database (`mobius_user`) with:

- **tenant**, **role**, **app_user**, sessions, activities, preferences.

Each Mobius module (e.g. mobius-os, mobius-chat) uses its own application database; cross-module references use **`user_id`** (UUID) only.

Setup and migrations: [Mobius-user/README.md](../../Mobius-user/README.md).

### B.2 Auth in Mobius Chat

- FastAPI routes can include the **auth router** (`/api/v1/auth/...`): register, login, refresh, logout, `/me`, onboarding, preferences — see the same README’s endpoint table.
- The **web client** can use **@mobius/auth** for a consistent login / account modal: [mobius-auth/README.md](../../mobius-auth/README.md).

**What org admins should expect today**

- User provisioning may be **self-serve** (register) or **integrated** with your deployment’s policies — not fully described here.
- **Roles and activities** in mobius-user are available to consuming apps; the **Chat** sidebar exposes sign-in / account when wired up. Fine-grained **task admin** for clinic staff is a **mobius-os** concern, not this chat-only guide.

### B.3 Security practices

- Rotate **`JWT_SECRET`** and service account keys per your policy.
- Never commit `.env` or JSON keys; use secret managers in production.
- Align `USER_DATABASE_URL` and JWT settings across every service that validates the same users.

---

## Related product docs

- [CAPABILITIES.md](CAPABILITIES.md) — what the assistant can answer.
- [USER_GUIDE_CHAT.md](USER_GUIDE_CHAT.md) — end-user UI walkthrough.
