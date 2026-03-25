#!/usr/bin/env python3
"""
Terminate PostgreSQL connections on mobius_* DBs to free Cloud SQL slots.

When you see:
  FATAL: remaining connection slots are reserved for non-replication superuser connections
the app user cannot connect at all. Set CHAT_RAG_DATABASE_ADMIN_URL to a superuser URL
(typically postgres user, same host/port as proxy), database "postgres", e.g.:
  CHAT_RAG_DATABASE_ADMIN_URL=postgresql://postgres:YOURPASS@127.0.0.1:5433/postgres

mstart exports CHAT_RAG_DATABASE_URL (proxy) before calling this; env wins over mobius-chat/.env.

Optional (dev only, nuclear): MOBIUS_DB_CLEANUP_TERMINATE_ALL_MOB=1 terminates every backend
on mobius_chat / mobius_rag / mobius_qa except this session (requires admin connection).
"""
from __future__ import annotations

import os
import sys

MOBIUS_DBS = ("mobius_chat", "mobius_rag", "mobius_qa")


def _load_dotenv_mobius_chat() -> dict[str, str]:
    env_path = os.path.join(os.path.dirname(__file__), "..", "mobius-chat", ".env")
    out: dict[str, str] = {}
    if not os.path.exists(env_path):
        return out
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _normalize_pg_url(u: str) -> str:
    return (u or "").strip().replace("postgresql+asyncpg://", "postgresql://")


def _app_cleanup_url(chat_rag_url: str) -> str:
    """Connect to postgres DB with same credentials as app URL (for pg_stat_activity + terminate)."""
    u = _normalize_pg_url(chat_rag_url)
    return u.replace("/mobius_chat", "/postgres").replace("/mobius_rag", "/postgres").replace(
        "/mobius_qa", "/postgres"
    )


def _connect_psycopg2(url: str):
    import urllib.parse

    try:
        from sqlalchemy.engine import make_url

        parsed = make_url(url)
        return __import__("psycopg2").connect(
            host=parsed.host or "localhost",
            port=parsed.port or 5432,
            dbname=(parsed.database or "postgres").lstrip("/"),
            user=parsed.username or "postgres",
            password=parsed.password or "",
            connect_timeout=15,
        )
    except ImportError:
        pass

    parsed = urllib.parse.urlparse(url)
    netloc = parsed.netloc
    path = (parsed.path or "/").lstrip("/") or "postgres"
    userinfo, _, hostport = netloc.rpartition("@")
    if not hostport:
        return __import__("psycopg2").connect(url, connect_timeout=15)
    username, _, password = userinfo.partition(":")
    password = urllib.parse.unquote_to_bytes(password).decode("utf-8", "replace")
    host, _, port_str = hostport.rpartition(":")
    port = int(port_str) if port_str.isdigit() else 5432
    return __import__("psycopg2").connect(
        host=host or "localhost",
        port=port,
        dbname=path,
        user=urllib.parse.unquote(username) if username else "postgres",
        password=password,
        connect_timeout=15,
    )


def main() -> int:
    file_env = _load_dotenv_mobius_chat()
    chat_url = (os.environ.get("CHAT_RAG_DATABASE_URL") or file_env.get("CHAT_RAG_DATABASE_URL") or "").strip()
    admin_url = (
        (os.environ.get("CHAT_RAG_DATABASE_ADMIN_URL") or file_env.get("CHAT_RAG_DATABASE_ADMIN_URL") or "").strip()
    )

    if not chat_url:
        print("ERROR: CHAT_RAG_DATABASE_URL not in environment or mobius-chat/.env")
        return 1

    primary = _app_cleanup_url(chat_url)
    admin = _normalize_pg_url(admin_url) if admin_url else ""

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 required. pip install psycopg2-binary")
        return 1

    conn = None
    # Prefer superuser URL first when set — avoids a doomed connect when app slots are exhausted.
    _try_order = (
        (("CHAT_RAG_DATABASE_ADMIN_URL", admin),) if admin else ()
    ) + (("app→postgres db", primary),)
    for label, candidate in _try_order:
        if not candidate:
            continue
        try:
            conn = _connect_psycopg2(candidate)
            print(f"Connected for cleanup via {label}")
            break
        except Exception as e:
            print(f"Connect failed ({label}): {e}")

    if conn is None:
        print(
            "\nNo connection for cleanup. When all non-superuser slots are full:\n"
            "  • Add to mobius-chat/.env (recommended):\n"
            "      CHAT_RAG_DATABASE_ADMIN_URL=postgresql://postgres:PASSWORD@127.0.0.1:5433/postgres\n"
            "  • Or in the shell you must export and quote $ in the password:\n"
            "      export CHAT_RAG_DATABASE_ADMIN_URL='postgresql://postgres:Mobius123$@127.0.0.1:5433/postgres'\n"
            "    (A bare VAR=value line does NOT reach mstart’s Python children; unquoted $ breaks the URL.)\n"
            "Or restart Cloud SQL: mstart --restart-db\n"
        )
        return 1

    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM pg_stat_activity")
    total = cur.fetchone()[0]
    print(f"Total connections: {total}")

    nuclear = (os.environ.get("MOBIUS_DB_CLEANUP_TERMINATE_ALL_MOB") or "").strip() == "1"
    in_dbs = "('mobius_chat','mobius_rag','mobius_qa')"
    if nuclear:
        print(
            "MOBIUS_DB_CLEANUP_TERMINATE_ALL_MOB=1 — terminating ALL backends on mobius_* "
            "(except this session). Requires superuser or pg_signal_backend."
        )
        cur.execute(
            f"""
            SELECT pid, usename, datname, state
            FROM pg_stat_activity
            WHERE datname IN {in_dbs}
              AND pid <> pg_backend_pid()
            """
        )
    else:
        cur.execute(
            f"""
            SELECT pid, usename, datname, state
            FROM pg_stat_activity
            WHERE datname IN {in_dbs}
              AND state IN ('idle', 'idle in transaction')
              AND pid <> pg_backend_pid()
            """
        )
    rows = cur.fetchall()
    print(f"Terminating {len(rows)} connection(s)...")

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
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
