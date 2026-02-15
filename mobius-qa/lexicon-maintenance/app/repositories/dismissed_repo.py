"""Dismissed issues repository: policy_lexicon_dismissed_issues (QA DB)."""
from __future__ import annotations

_DISMISSED_TABLE_ENSURED = False


def ensure_dismissed_table(qa_conn) -> None:
    """Auto-create policy_lexicon_dismissed_issues table if it doesn't exist."""
    global _DISMISSED_TABLE_ENSURED
    if _DISMISSED_TABLE_ENSURED:
        return
    try:
        qa_conn.autocommit = True
        cur = qa_conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS policy_lexicon_dismissed_issues (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
                issue_type TEXT NOT NULL,
                issue_tags TEXT[] NOT NULL DEFAULT '{}',
                issue_message TEXT NOT NULL DEFAULT '',
                issue_fingerprint TEXT NOT NULL UNIQUE,
                reason TEXT NOT NULL DEFAULT '',
                dismissed_by TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.close()
        _DISMISSED_TABLE_ENSURED = True
    except Exception:
        pass


def load_dismissed(qa_cur) -> list[dict]:
    """Load all dismissed issues. Assumes table exists."""
    qa_cur.execute(
        "SELECT id, issue_type, issue_tags, issue_message, issue_fingerprint, reason, dismissed_by, created_at "
        "FROM policy_lexicon_dismissed_issues ORDER BY created_at DESC"
    )
    return [dict(r) for r in (qa_cur.fetchall() or [])]


def dismissed_fingerprint(issue_type: str, tags: list[str]) -> str:
    """Stable fingerprint for an issue: type + sorted tags."""
    return f"{issue_type}::{','.join(sorted(t.strip().lower() for t in tags))}"
