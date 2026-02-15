"""Lexicon repository: policy_lexicon_meta, policy_lexicon_entries (QA DB)."""
from __future__ import annotations

import json
import uuid
from typing import Any

import psycopg2.extras


def get_lexicon_meta_and_tags(qa_cur) -> tuple[dict, list[dict]]:
    """Load meta and active tags from policy_lexicon_meta and policy_lexicon_entries."""
    qa_cur.execute(
        """
        SELECT COALESCE(revision,0)::bigint AS revision,
               COALESCE(lexicon_version,'v1')::text AS lexicon_version,
               lexicon_meta
        FROM policy_lexicon_meta
        ORDER BY updated_at DESC NULLS LAST
        LIMIT 1
        """
    )
    meta = qa_cur.fetchone() or {}
    meta = dict(meta) if meta else {}
    lexicon_meta = meta.get("lexicon_meta") if isinstance(meta.get("lexicon_meta"), dict) else (meta.get("lexicon_meta") or {})

    qa_cur.execute(
        """
        SELECT kind::text, code::text, parent_code::text, spec, active::bool
        FROM policy_lexicon_entries
        WHERE active = true
        ORDER BY kind, code
        """
    )
    tags = []
    for r in qa_cur.fetchall() or []:
        r = dict(r) if hasattr(r, "keys") else {}
        tags.append({
            "kind": (r.get("kind") or "").strip().lower(),
            "code": r.get("code"),
            "parent": r.get("parent_code"),
            "spec": r.get("spec") if isinstance(r.get("spec"), dict) else {},
        })
    return meta, tags


def bump_revision(qa_cur) -> int:
    """Increment policy_lexicon_meta.revision (create row if missing). Returns new revision."""
    qa_cur.execute(
        """
        SELECT id, COALESCE(revision,0)::bigint AS revision
        FROM policy_lexicon_meta
        ORDER BY updated_at DESC NULLS LAST
        LIMIT 1
        """
    )
    row = qa_cur.fetchone()
    rid = None
    rev = 0
    if isinstance(row, dict):
        rid = row.get("id")
        rev = int(row.get("revision") or 0)
    elif isinstance(row, (list, tuple)) and row:
        rid = row[0]
        rev = int(row[1] or 0) if len(row) > 1 else 0
    if rid:
        new_rev = int(rev or 0) + 1
        qa_cur.execute(
            "UPDATE policy_lexicon_meta SET revision=%s, updated_at=NOW() WHERE id=%s",
            (new_rev, rid),
        )
        return new_rev
    new_rev = 1
    qa_cur.execute(
        """
        INSERT INTO policy_lexicon_meta(id, lexicon_version, lexicon_meta, revision, created_at, updated_at)
        VALUES (%s, %s, %s::jsonb, %s, NOW(), NOW())
        """,
        (str(uuid.uuid4()), "v1", json.dumps({}), new_rev),
    )
    return new_rev


def get_tag(qa_cur, kind: str, code: str) -> dict | None:
    """Get a single tag by kind and code."""
    qa_cur.execute(
        """
        SELECT kind::text, code::text, parent_code::text, spec, active::bool
        FROM policy_lexicon_entries
        WHERE kind = %s AND code = %s
        LIMIT 1
        """,
        (kind, code),
    )
    row = qa_cur.fetchone()
    return dict(row) if row else None


def parent_exists(qa_cur, kind: str, parent_code: str) -> bool:
    """Check if parent tag exists."""
    qa_cur.execute(
        "SELECT 1 FROM policy_lexicon_entries WHERE kind = %s AND code = %s LIMIT 1",
        (kind, parent_code),
    )
    return qa_cur.fetchone() is not None


def list_entries_all(qa_cur) -> list[dict[str, Any]]:
    """Load all lexicon entries (for health analyze)."""
    qa_cur.execute(
        "SELECT kind::text, code::text, parent_code::text, spec, active::bool FROM policy_lexicon_entries ORDER BY kind, code"
    )
    return [dict(r) for r in (qa_cur.fetchall() or [])]
