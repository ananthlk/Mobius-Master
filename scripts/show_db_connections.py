#!/usr/bin/env python3
"""
List all PostgreSQL connections to see who/what is using the DB.
Use when diagnosing "connection slots" errors. Requires at least one free slot.
Run: python scripts/show_db_connections.py
"""
import os
import sys

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

try:
    conn = psycopg2.connect(url, connect_timeout=10)
except Exception as e:
    print(f"ERROR: Could not connect: {e}")
    print("  (Slots may be full. Try: scripts/clear_db_slots.sh --restart)")
    sys.exit(1)

cur = conn.cursor()
cur.execute("SELECT count(*), (SELECT setting::int FROM pg_settings WHERE name='max_connections') FROM pg_stat_activity")
total, max_conn = cur.fetchone()
print(f"Connections: {total} / {max_conn} (max)")
print()

cur.execute("""
  SELECT pid, usename, datname, state,
         COALESCE(application_name, '') AS app,
         COALESCE(client_addr::text, 'local') AS client
  FROM pg_stat_activity
  WHERE datname IS NOT NULL
  ORDER BY datname, usename, state
""")
rows = cur.fetchall()
print(f"{'PID':>8}  {'User':<12}  {'Database':<14}  {'State':<20}  {'App':<25}  Client")
print("-" * 95)
for r in rows:
    pid, user, db, state, app, client = r
    state = (state or "null")[:18]
    app = (app or "")[:23]
    print(f"{pid:>8}  {user:<12}  {db:<14}  {state:<20}  {app:<25}  {client}")

cur.execute("""
  SELECT client_addr::text, count(*)
  FROM pg_stat_activity
  WHERE client_addr IS NOT NULL
  GROUP BY client_addr
  ORDER BY count(*) DESC
""")
by_ip = cur.fetchall()
if by_ip:
    print()
    print("By client IP:")
    for ip, n in by_ip:
        print(f"  {ip}: {n} connection(s)")

cur.close()
conn.close()
