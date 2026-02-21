#!/usr/bin/env python3
"""
List documents in the Chat/RAG corpus with tagging coverage.

Useful for choosing a document with better document_tags / policy_line_tags for testing.
Outputs: document name, document_id, chunk count, has document_tags, line_tags count, sample d_tags.

Env: CHAT_DATABASE_URL or CHAT_RAG_DATABASE_URL

Usage:
  python scripts/list_documents_with_tags.py
  python scripts/list_documents_with_tags.py --json   # machine-readable
"""

import json
import os
import sys
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


def main() -> int:
    chat_url = (
        os.environ.get("CHAT_DATABASE_URL")
        or os.environ.get("CHAT_RAG_DATABASE_URL")
        or ""
    ).strip()
    if not chat_url or "${" in chat_url:
        print("Set CHAT_DATABASE_URL or CHAT_RAG_DATABASE_URL", file=sys.stderr)
        return 1

    as_json = "--json" in sys.argv

    conn = _connect_db(chat_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Documents from published_rag_metadata with chunk counts
    cur.execute("""
        SELECT document_id, document_display_name, document_payer, document_authority_level,
               COUNT(*) AS chunks
        FROM published_rag_metadata
        GROUP BY document_id, document_display_name, document_payer, document_authority_level
        ORDER BY chunks DESC
    """)
    docs = [dict(r) for r in cur.fetchall()]

    # document_tags per document
    cur.execute("""
        SELECT document_id, p_tags, d_tags, j_tags
        FROM document_tags
    """)
    doc_tags_by_id = {}
    for r in cur.fetchall():
        doc_id = str(r.get("document_id", ""))
        doc_tags_by_id[doc_id] = {
            "p_tags": r.get("p_tags") or {},
            "d_tags": r.get("d_tags") or {},
            "j_tags": r.get("j_tags") or {},
        }

    # policy_line_tags count per document
    cur.execute("""
        SELECT document_id, COUNT(*) AS line_tag_count
        FROM policy_line_tags
        GROUP BY document_id
    """)
    line_tags_count = {str(r["document_id"]): r["line_tag_count"] for r in cur.fetchall()}

    cur.close()
    conn.close()

    # Build output
    rows = []
    for d in docs:
        doc_id = str(d.get("document_id", ""))
        dt = doc_tags_by_id.get(doc_id, {})
        n_d_tags = len(dt.get("d_tags") or {})
        n_p_tags = len(dt.get("p_tags") or {})
        n_j_tags = len(dt.get("j_tags") or {})
        n_line_tags = line_tags_count.get(doc_id, 0)
        has_doc_tags = n_d_tags > 0 or n_p_tags > 0 or n_j_tags > 0

        # Sample d_tags (for quick inspection)
        d_tags = dt.get("d_tags") or {}
        sample_d = list(d_tags.keys())[:8] if isinstance(d_tags, dict) else []

        rows.append({
            "document_id": doc_id,
            "document_display_name": d.get("document_display_name") or "—",
            "document_payer": d.get("document_payer") or "—",
            "chunks": d.get("chunks", 0),
            "has_document_tags": has_doc_tags,
            "d_tags_count": n_d_tags,
            "p_tags_count": n_p_tags,
            "j_tags_count": n_j_tags,
            "line_tags_count": n_line_tags,
            "sample_d_tags": sample_d,
        })

    if as_json:
        print(json.dumps(rows, indent=2))
        return 0

    # Human-readable table
    print("Documents in library (Chat/RAG corpus)\n")
    print("| Document | document_id | Chunks | Doc tags | d_tags | Line tags | Sample d_tags |")
    print("|----------|-------------|--------|----------|--------|-----------|---------------|")
    for r in rows:
        name = (r["document_display_name"] or "—")[:40]
        doc_id_short = r["document_id"][:8] + "..." if len(r["document_id"]) > 8 else r["document_id"]
        dt_yn = "✓" if r["has_document_tags"] else "—"
        sample = ", ".join(r["sample_d_tags"][:4]) if r["sample_d_tags"] else "—"
        if len(sample) > 35:
            sample = sample[:32] + "..."
        print(f"| {name} | {doc_id_short} | {r['chunks']} | {dt_yn} | {r['d_tags_count']} | {r['line_tags_count']} | {sample} |")

    print("\nDoc tags = document_tags (JPD scoping). Line tags = policy_line_tags (reranker).")
    print("Documents with more d_tags and line_tags generally have better JPD/tag_match behavior.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
