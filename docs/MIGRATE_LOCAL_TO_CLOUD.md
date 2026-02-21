# Migrate Local DB to Cloud SQL and Remove Local PostgreSQL

Use this guide to move all Mobius data from a local PostgreSQL to Cloud SQL, then remove the local database and update all RAG modules to use Cloud SQL only.

## Prerequisites

- Cloud SQL dev instance running (34.135.72.145 = mobius-platform-dev-db)
- Databases `mobius_rag`, `mobius_chat`, `mobius_user` created on Cloud SQL
- `pg_dump`, `psql` installed (PostgreSQL client tools)

## Step 1: Migrate data

From the repo root:

```bash
# Password for Cloud SQL postgres user (from mobius-rag/.env or mobius-config)
CLOUD_SQL_PASSWORD='MobiusDev123$' ./scripts/migrate_local_to_cloud_sql.sh
```

If your local postgres uses different host/credentials:

```bash
SOURCE_POSTGRES_HOST=localhost
SOURCE_POSTGRES_PORT=5432
SOURCE_POSTGRES_USER=postgres
SOURCE_POSTGRES_PASSWORD=postgres
CLOUD_SQL_PASSWORD='MobiusDev123$' \
  ./scripts/migrate_local_to_cloud_sql.sh
```

If using **docker-compose** for local RAG DB (mobius-chat/ragdb on port 5433):

```bash
SOURCE_POSTGRES_HOST=127.0.0.1
SOURCE_POSTGRES_PORT=5433
SOURCE_POSTGRES_USER=mobius
SOURCE_POSTGRES_PASSWORD=mobius
CLOUD_SQL_PASSWORD='MobiusDev123$' \
  ./scripts/migrate_local_to_cloud_sql.sh
```

## Step 2: Update RAG modules to Cloud SQL

All RAG modules should point to Cloud SQL (34.135.72.145). The codebase has been updated so that:

- **mobius-rag** requires `DATABASE_URL` (no localhost fallback)
- **mobius-config** uses `POSTGRES_HOST=34.135.72.145`, `CHAT_DATABASE_URL`, etc.
- **mobius-dbt** uses same Cloud SQL for RAG read and Chat write
- **mobius-retriever** uses `CHAT_RAG_DATABASE_URL` / `RAG_DATABASE_URL` from env

Ensure these `.env` files have Cloud SQL URLs:

| File | Variable | Value |
|------|----------|-------|
| mobius-rag/.env | DATABASE_URL | postgresql+asyncpg://postgres:PASSWORD@34.135.72.145:5432/mobius_rag |
| mobius-config/.env | POSTGRES_HOST | 34.135.72.145 |
| mobius-config/.env | CHAT_DATABASE_URL | postgresql://postgres:PASSWORD@34.135.72.145:5432/mobius_chat |
| mobius-config/.env | CHAT_RAG_DATABASE_URL | postgresql://postgres:PASSWORD@34.135.72.145:5432/mobius_chat |
| mobius-dbt/.env | POSTGRES_HOST | 34.135.72.145 |
| mobius-dbt/.env | CHAT_DATABASE_URL | postgresql://postgres:PASSWORD@34.135.72.145:5432/mobius_chat |

## Step 3: Delete local DB

### Option A: Docker Compose (mobius-chat ragdb)

```bash
cd mobius-chat
docker compose down -v
```

This stops and removes the `ragdb` container and its `ragdb_data` volume.

### Option B: Native PostgreSQL (localhost)

```bash
dropdb -h localhost -U postgres mobius_rag
dropdb -h localhost -U postgres mobius_chat
dropdb -h localhost -U postgres mobius_user
```

Optional: stop local postgres if you no longer need it:

```bash
# macOS Homebrew
brew services stop postgresql@16  # or your version

# Linux systemd
sudo systemctl stop postgresql
```

## Step 4: Verify

- Run `mstart` — chunking and embedding workers should connect to Cloud SQL
- Run sync: `cd mobius-dbt && python scripts/sync_rag_lexicon_to_chat.py` — should read policy_lines from Cloud SQL
- Run dev retrieval report — should use Cloud SQL for J/P/D tags
