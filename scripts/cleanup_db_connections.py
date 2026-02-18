#!/usr/bin/env python3
"""
Terminate idle PostgreSQL connections to free connection slots.
Use when you see: "remaining connection slots are reserved for non-replication superuser connections"
Run: python scripts/cleanup_db_connections.py
"""
import os
import sys

# Load CHAT_RAG_DATABASE_URL from mobius-chat/.env
env_path = os.path.join(os.path.dirname(__file__), "..", "mobius-chat", ".env")
if not os.path.exists(env_path):
    print(f"ERROR: {env_path} not found")
    sys.exit(1)

env = {}
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

url = env.get("CHAT_RAG_DATABASE_URL", "")
if not url:
    print("ERROR: CHAT_RAG_DATABASE_URL not in .env")
    sys.exit(1)

url = url.replace("postgresql+asyncpg://", "postgresql://").replace("/mobius_chat", "/postgres")

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 required. pip install psycopg2-binary")
    sys.exit(1)

conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT count(*) FROM pg_stat_activity")
total = cur.fetchone()[0]
print(f"Total connections: {total}")

cur.execute("""
  SELECT pid, usename, datname, state
  FROM pg_stat_activity
  WHERE datname IN ('mobius_chat', 'mobius_rag', 'mobius_qa')
    AND state IN ('idle', 'idle in transaction')
    AND pid <> pg_backend_pid()
""")
rows = cur.fetchall()
print(f"Terminating {len(rows)} idle/idle-in-transaction connections...")

for r in rows:
    try:
        cur.execute("SELECT pg_terminate_backend(%s)", (r[0],))
        print(f"  Terminated pid {r[0]} ({r[2]}, {r[3]})")
    except Exception as e:
        print(f"  Failed pid {r[0]}: {e}")

cur.execute("SELECT count(*) FROM pg_stat_activity")
after = cur.fetchone()[0]
print(f"Connections after cleanup: {after}")
cur.close()
conn.close()
print("Done. Run ./mstart to restart services.")
