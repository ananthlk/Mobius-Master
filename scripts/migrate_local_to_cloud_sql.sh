#!/usr/bin/env bash
# Migrate all Mobius databases from local PostgreSQL to Cloud SQL.
#
# Moves: mobius_rag, mobius_chat, mobius_user (whichever exist locally).
# Target: Cloud SQL dev (34.135.72.145 / mobius-platform-dev-db).
#
# Usage:
#   CLOUD_SQL_PASSWORD=YOUR_PASSWORD ./scripts/migrate_local_to_cloud_sql.sh
#   SOURCE_POSTGRES_HOST=localhost SOURCE_POSTGRES_PASSWORD=postgres ./scripts/migrate_local_to_cloud_sql.sh
#
# Env:
#   SOURCE_POSTGRES_HOST, PORT, USER, PASSWORD - Local postgres (default: localhost:5432, postgres/postgres)
#   CLOUD_POSTGRES_HOST, PORT, USER           - Cloud SQL (default: 34.135.72.145:5432, postgres)
#   CLOUD_SQL_PASSWORD or POSTGRES_PASSWORD   - Cloud SQL password (from mobius-rag .env)
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOBIUS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$MOBIUS_ROOT"

# Load mobius-rag .env for DATABASE_URL
if [[ -f mobius-rag/.env ]]; then
  set -a
  # shellcheck source=/dev/null
  source mobius-rag/.env
  set +a
fi

# Source: local postgres (host:port/user/pass from URL or defaults)
SOURCE_HOST="${SOURCE_POSTGRES_HOST:-localhost}"
SOURCE_PORT="${SOURCE_POSTGRES_PORT:-5432}"
SOURCE_USER="${SOURCE_POSTGRES_USER:-postgres}"
SOURCE_PWD="${SOURCE_POSTGRES_PASSWORD:-postgres}"
if [[ -n "${SOURCE_DATABASE_URL:-}" ]]; then
  # Parse URL for host/port/user (simplified: assume postgresql://user:pass@host:port/db)
  if [[ "$SOURCE_DATABASE_URL" =~ postgresql://([^:]+):([^@]+)@([^:]+):([0-9]+)/(.+) ]]; then
    SOURCE_USER="${BASH_REMATCH[1]}"
    SOURCE_PWD="${BASH_REMATCH[2]}"
    SOURCE_HOST="${BASH_REMATCH[3]}"
    SOURCE_PORT="${BASH_REMATCH[4]}"
  fi
fi

# Cloud: dev Cloud SQL (34.135.72.145 = mobius-platform-dev-db)
CLOUD_HOST="${CLOUD_POSTGRES_HOST:-34.135.72.145}"
CLOUD_PORT="${CLOUD_POSTGRES_PORT:-5432}"
CLOUD_USER="${CLOUD_POSTGRES_USER:-postgres}"
CLOUD_PWD="${CLOUD_SQL_PASSWORD:-${POSTGRES_PASSWORD:-MobiusDev123\$}}"

DATABASES=(mobius_rag mobius_chat mobius_user)

# Ensure pg_dump available
if ! command -v pg_dump >/dev/null 2>&1; then
  echo "ERROR: pg_dump not found. Install PostgreSQL client tools."
  exit 1
fi

echo "=== Migrate Local DB → Cloud SQL ==="
echo "Source: ${SOURCE_HOST}:${SOURCE_PORT}"
echo "Target: ${CLOUD_HOST}:${CLOUD_PORT}"
echo "Databases: ${DATABASES[*]}"
echo ""

for db in "${DATABASES[@]}"; do
  DUMP_FILE="$MOBIUS_ROOT/${db}_migration_$(date +%Y%m%d_%H%M%S).sql"

  echo "--- $db ---"
  # Check if source DB exists
  if ! PGPASSWORD="$SOURCE_PWD" psql -h "$SOURCE_HOST" -p "$SOURCE_PORT" -U "$SOURCE_USER" -d "$db" -t -c "SELECT 1" >/dev/null 2>&1; then
    echo "  Skip: source $db not found or unreachable"
    continue
  fi

  echo "  Dumping..."
  PGPASSWORD="$SOURCE_PWD" pg_dump -h "$SOURCE_HOST" -p "$SOURCE_PORT" -U "$SOURCE_USER" -d "$db" \
    --no-owner --no-acl > "$DUMP_FILE" 2>/dev/null || {
    echo "  Failed to dump $db"
    rm -f "$DUMP_FILE"
    continue
  }

  # Prepare: replace owner, remove DROP, add pgvector for mobius_rag
  PREPARED="${DUMP_FILE%.sql}_prepared.sql"
  sed -e 's/OWNER TO [a-zA-Z0-9_]*/OWNER TO postgres/g' \
      -e 's/Owner: [a-zA-Z0-9_]*/Owner: postgres/g' \
      -e '/^DROP /d' \
      "$DUMP_FILE" > "$PREPARED"
  if [[ "$db" == "mobius_rag" ]] && grep -q "vector\|chunk_embeddings" "$PREPARED" 2>/dev/null; then
    if ! grep -q "CREATE EXTENSION.*vector" "$PREPARED" 2>/dev/null; then
      echo "CREATE EXTENSION IF NOT EXISTS vector;" | cat - "$PREPARED" > "${PREPARED}.tmp"
      mv "${PREPARED}.tmp" "$PREPARED"
    fi
  fi

  echo "  Importing to Cloud SQL..."
  PGPASSWORD="$CLOUD_PWD" psql -h "$CLOUD_HOST" -p "$CLOUD_PORT" -U "$CLOUD_USER" -d "$db" \
    -f "$PREPARED" -v ON_ERROR_STOP=1 2>/dev/null || {
    echo "  Failed to import $db (check credentials and that DB exists on cloud)"
    rm -f "$DUMP_FILE" "$PREPARED"
    continue
  }

  echo "  Done."
  rm -f "$DUMP_FILE" "$PREPARED"
done

echo ""
echo "=== Migration complete ==="
echo "Next: Update .env files to point to Cloud SQL, then delete local DB."
echo "  See docs/MIGRATE_LOCAL_TO_CLOUD.md"
