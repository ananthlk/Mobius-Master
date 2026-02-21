#!/usr/bin/env python3
"""
Inventory of Chat/RAG state before any deletions.

Reports:
  - Documents available to Chat (published_rag_metadata)
  - Tags available (policy_lexicon_entries, document_tags, policy_line_tags)
  - Vertex DB populated (from sync_runs; optionally from Vertex API)

Env: CHAT_DATABASE_URL or CHAT_RAG_DATABASE_URL (same as mobius-chat)

Usage:
  python scripts/inventory_chat_rag_state.py
  python scripts/inventory_chat_rag_state.py --output reports/chat_rag_inventory.md
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / "mobius-dbt" / ".env")
    load_dotenv(_project_root / "mobius-chat" / ".env")
    load_dotenv(_project_root / "mobius-config" / ".env")
except ImportError:
    pass

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("Install psycopg2-binary: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


def _connect_db(url: str):
    """Connect using URL; parse into components for special chars in password."""
    import urllib.parse
    try:
        from sqlalchemy.engine import make_url
        parsed = make_url(url)
        return psycopg2.connect(
            host=parsed.host or "localhost",
            port=parsed.port or 5432,
            dbname=(parsed.database or "postgres").lstrip("/"),
            user=parsed.username or "postgres",
            password=parsed.password or "",
            connect_timeout=10,
        )
    except ImportError:
        pass
    parsed = urllib.parse.urlparse(url)
    netloc = parsed.netloc
    path = (parsed.path or "/").lstrip("/") or "postgres"
    userinfo, _, hostport = netloc.rpartition("@")
    if not hostport:
        return psycopg2.connect(url)
    username, _, password = userinfo.partition(":")
    password = urllib.parse.unquote_to_bytes(password).decode("utf-8", "replace")
    host, _, port_str = hostport.rpartition(":")
    port = int(port_str) if port_str.isdigit() else 5432
    return psycopg2.connect(
        host=host or "localhost",
        port=port,
        dbname=path,
        user=urllib.parse.unquote(username) if username else "postgres",
        password=password,
        connect_timeout=10,
    )


def run_inventory() -> dict:
    chat_url = (
        os.environ.get("CHAT_DATABASE_URL")
        or os.environ.get("CHAT_RAG_DATABASE_URL")
        or ""
    ).strip()
    if not chat_url or "${" in chat_url:
        raise ValueError("Set CHAT_DATABASE_URL or CHAT_RAG_DATABASE_URL")

    conn = _connect_db(chat_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    inv = {"generated_at": datetime.now(timezone.utc).isoformat(), "source": str(conn.info)}
    try:
        # 1. published_rag_metadata
        cur.execute("SELECT COUNT(*) AS cnt FROM published_rag_metadata")
        inv["published_rag_metadata_rows"] = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(DISTINCT document_id) AS cnt FROM published_rag_metadata")
        inv["published_rag_metadata_documents"] = cur.fetchone()["cnt"]
        cur.execute(
            "SELECT source_type, COUNT(*) AS cnt FROM published_rag_metadata GROUP BY source_type ORDER BY cnt DESC"
        )
        inv["published_rag_metadata_by_source_type"] = [dict(r) for r in cur.fetchall()]
        cur.execute(
            "SELECT document_display_name, document_id, COUNT(*) AS chunks "
            "FROM published_rag_metadata GROUP BY document_id, document_display_name ORDER BY chunks DESC LIMIT 50"
        )
        inv["published_rag_metadata_document_list"] = [dict(r) for r in cur.fetchall()]

        # 2. policy_lexicon
        cur.execute("SELECT COUNT(*) AS cnt FROM policy_lexicon_entries WHERE active = true")
        inv["policy_lexicon_entries"] = cur.fetchone()["cnt"]
        cur.execute("SELECT kind, COUNT(*) AS cnt FROM policy_lexicon_entries WHERE active = true GROUP BY kind")
        inv["policy_lexicon_by_kind"] = [dict(r) for r in cur.fetchall()]

        # 3. document_tags
        cur.execute("SELECT COUNT(*) AS cnt FROM document_tags")
        inv["document_tags_rows"] = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(DISTINCT document_id) AS cnt FROM document_tags")
        inv["document_tags_documents"] = cur.fetchone()["cnt"]

        # 4. policy_line_tags
        cur.execute("SELECT COUNT(*) AS cnt FROM policy_line_tags")
        inv["policy_line_tags_rows"] = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(DISTINCT document_id) AS cnt FROM policy_line_tags")
        inv["policy_line_tags_documents"] = cur.fetchone()["cnt"]

        # 5. sync_runs (Vertex upsert counts)
        cur.execute(
            "SELECT run_id, started_at, finished_at, mart_rows_read, postgres_rows_written, "
            "vector_rows_upserted, status FROM sync_runs ORDER BY started_at DESC LIMIT 5"
        )
        inv["sync_runs"] = [dict(r) for r in cur.fetchall()]

        # 6. policy_lexicon_meta
        cur.execute("SELECT COUNT(*) AS cnt FROM policy_lexicon_meta")
        inv["policy_lexicon_meta"] = cur.fetchone()["cnt"]
    finally:
        cur.close()
        conn.close()

    return inv


def to_markdown(inv: dict) -> str:
    lines = [
        "# Chat/RAG State Inventory",
        "",
        f"**Generated:** {inv['generated_at']}",
        f"**Source:** Chat Postgres (mobius_chat)",
        "",
        "---",
        "",
        "## 1. Documents Available to Chat",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Rows (chunks/facts) | {inv.get('published_rag_metadata_rows', 0):,} |",
        f"| Distinct documents | {inv.get('published_rag_metadata_documents', 0):,} |",
        "",
        "### By source_type",
        "",
        "| source_type | Count |",
        "|-------------|-------|",
    ]
    for r in inv.get("published_rag_metadata_by_source_type", []):
        lines.append(f"| {r.get('source_type', '')} | {r.get('cnt', 0):,} |")
    lines.extend([
        "",
        "### Top documents (by chunk count)",
        "",
        "| Document | document_id | Chunks |",
        "|----------|-------------|--------|",
    ])
    for r in inv.get("published_rag_metadata_document_list", []):
        name = (r.get("document_display_name") or "—")[:60]
        doc_id = str(r.get("document_id", ""))[:36]
        lines.append(f"| {name} | {doc_id} | {r.get('chunks', 0):,} |")
    lines.extend([
        "",
        "---",
        "",
        "## 2. Tags Available",
        "",
        f"| Table | Rows | Distinct documents |",
        f"|-------|------|-------------------|",
        f"| policy_lexicon_meta | {inv.get('policy_lexicon_meta', 0):,} | — |",
        f"| policy_lexicon_entries (active) | {inv.get('policy_lexicon_entries', 0):,} | — |",
        f"| document_tags | {inv.get('document_tags_rows', 0):,} | {inv.get('document_tags_documents', 0):,} |",
        f"| policy_line_tags | {inv.get('policy_line_tags_rows', 0):,} | {inv.get('policy_line_tags_documents', 0):,} |",
        "",
        "### Lexicon by kind",
        "",
        "| kind | Count |",
        "|------|-------|",
    ])
    for r in inv.get("policy_lexicon_by_kind", []):
        lines.append(f"| {r.get('kind', '')} | {r.get('cnt', 0):,} |")
    lines.extend([
        "",
        "---",
        "",
        "## 3. Vertex AI Vector Search (from sync_runs)",
        "",
        "| Run | Started | vector_rows_upserted | postgres_rows_written | status |",
        "|-----|---------|----------------------|------------------------|--------|",
    ])
    for r in inv.get("sync_runs", []):
        started = str(r.get("started_at", ""))[:19] if r.get("started_at") else "—"
        vec = r.get("vector_rows_upserted") or "—"
        pg = r.get("postgres_rows_written") or "—"
        status = r.get("status", "—")
        run_id = str(r.get("run_id", ""))[:8]
        lines.append(f"| {run_id}... | {started} | {vec} | {pg} | {status} |")
    lines.extend([
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Published chunks/facts:** {inv.get('published_rag_metadata_rows', 0):,}",
        f"- **Documents with published content:** {inv.get('published_rag_metadata_documents', 0):,}",
        f"- **Documents with document_tags:** {inv.get('document_tags_documents', 0):,}",
        f"- **Documents with policy_line_tags:** {inv.get('policy_line_tags_documents', 0):,}",
        f"- **Line-level tag rows:** {inv.get('policy_line_tags_rows', 0):,}",
        "",
    ])
    latest = inv.get("sync_runs") or []
    if latest:
        vec = latest[0].get("vector_rows_upserted")
        if vec is not None:
            lines.append(f"- **Last Vertex upsert:** {vec:,} vectors")
    return "\n".join(lines)


def main() -> int:
    out_path = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            out_path = Path(sys.argv[idx + 1])
    if not out_path:
        out_path = _project_root / "reports" / "chat_rag_inventory.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        inv = run_inventory()
    except Exception as e:
        print(f"Inventory failed: {e}", file=sys.stderr)
        return 1

    md = to_markdown(inv)
    out_path.write_text(md, encoding="utf-8")
    print(f"Wrote {out_path}", flush=True)
    print("", flush=True)
    print(md, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
