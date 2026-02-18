"""
Shared candidate operations used by review-bulk, apply-operations, and health fix apply.

Ensures consistent behavior for reject, merge, add_alias, create_tag across all entry points.
"""
from __future__ import annotations

import logging
import re
from typing import Any


def _normalize_phrase(s: str) -> str:
    """Collapse internal whitespace, strip, lowercase — matches DB variations like 'age  of' vs 'age of'."""
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.strip()).strip().lower()

logger = logging.getLogger(__name__)

# Re-export for callers
__all__ = [
    "_normalize_phrase",
    "reject_candidate_in_rag",
    "reject_candidate_by_ids",
    "update_candidate_state_in_rag",
    "update_candidate_state_by_ids",
    "upsert_catalog",
    "fetch_candidate_types",
    "resolve_normalized_to_ids",
]


def fetch_candidate_types_by_ids(rag_cur, ids: list[str]) -> dict[str, str]:
    """
    Fetch candidate_type per id from policy_lexicon_candidates.
    Returns {id: candidate_type} where candidate_type is p|d|j.
    """
    if not ids:
        return {}
    ids_clean = [str(x).strip() for x in ids if str(x).strip()]
    if not ids_clean:
        return {}
    rag_cur.execute(
        """
        SELECT id::text, COALESCE(NULLIF(trim(lower(candidate_type)), ''), 'd') AS ct
        FROM policy_lexicon_candidates
        WHERE id::text = ANY(%s)
        """,
        (ids_clean,),
    )
    rows = rag_cur.fetchall()
    out: dict[str, str] = {}
    for r in rows:
        if isinstance(r, dict):
            i = str(r.get("id", ""))
            ct = str(r.get("ct", "d")).strip().lower()
        else:
            i = str(r[0]) if len(r) > 0 else ""
            ct = str(r[1]) if len(r) > 1 else "d"
        if i:
            out[i] = ct if ct in ("p", "d", "j") else "d"
    return out


def fetch_candidate_types(rag_cur, norm_keys: list[str]) -> dict[str, str]:
    """
    Fetch candidate_type per normalized key from policy_lexicon_candidates.
    Returns {normalized_key: candidate_type} where candidate_type is p|d|j.
    Uses same whitespace normalization as update_candidate_state_in_rag.
    """
    if not norm_keys:
        return {}
    keys_norm = [*{_normalize_phrase(k) for k in norm_keys if _normalize_phrase(k)}]
    if not keys_norm:
        return {}
    rag_cur.execute(
        """
        SELECT DISTINCT ON (trim(lower(regexp_replace(normalized, E'\\s+', ' ', 'g'))))
            trim(lower(regexp_replace(normalized, E'\\s+', ' ', 'g'))) AS nk,
            COALESCE(NULLIF(trim(lower(candidate_type)), ''), 'd') AS ct
        FROM policy_lexicon_candidates
        WHERE trim(lower(regexp_replace(normalized, E'\\s+', ' ', 'g'))) = ANY(%s)
        ORDER BY trim(lower(regexp_replace(normalized, E'\\s+', ' ', 'g'))), COALESCE(occurrences, 1) DESC
        """,
        (keys_norm,),
    )
    rows = rag_cur.fetchall()
    out: dict[str, str] = {}
    for r in rows:
        if isinstance(r, dict):
            nk = str(r.get("nk", ""))
            ct = str(r.get("ct", "d")).strip().lower()
        else:
            nk = str(r[0]) if len(r) > 0 else ""
            ct = str(r[1]) if len(r) > 1 else "d"
        if nk:
            out[nk] = ct if ct in ("p", "d", "j") else "d"
    return out


def resolve_normalized_to_ids(rag_cur, normalized: str, state_filter: str = "proposed") -> list[str]:
    """
    Resolve normalized phrase to list of row IDs (for apply-operations that receive normalized from LLM).
    Returns ids of rows matching the phrase (whitespace-normalized) with the given state.
    Falls back to prefix/contains match when exact match fails (LLM may abbreviate "hcpcs code" -> "hcpcs").
    """
    nk = _normalize_phrase(normalized)
    if not nk:
        return []

    # Exact match first
    rag_cur.execute(
        """
        SELECT id::text FROM policy_lexicon_candidates
        WHERE trim(lower(regexp_replace(normalized, E'\\s+', ' ', 'g'))) = %s AND state = %s
        """,
        (nk, state_filter),
    )
    rows = rag_cur.fetchall()
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict):
            vid = r.get("id")
        else:
            vid = r[0] if len(r) > 0 else None
        if vid:
            out.append(str(vid))
    if out:
        return out

    # Fallback: contains match (e.g. LLM returns "hcpcs", DB has "hcpcs code")
    pattern = f"%{nk}%"
    rag_cur.execute(
        """
        SELECT id::text FROM policy_lexicon_candidates
        WHERE state = %s
          AND (trim(lower(regexp_replace(normalized, E'\\s+', ' ', 'g'))) LIKE %s
               OR trim(lower(normalized)) LIKE %s)
        ORDER BY COALESCE(occurrences, 1) DESC
        LIMIT 50
        """,
        (state_filter, pattern, pattern),
    )
    for r in rag_cur.fetchall():
        if isinstance(r, dict):
            vid = r.get("id")
        else:
            vid = r[0] if len(r) > 0 else None
        if vid:
            out.append(str(vid))
    if out:
        logger.info("[candidate_ops] resolve_normalized_to_ids: no exact match for %r, fuzzy matched %d rows", normalized, len(out))
    return out


def update_candidate_state_by_ids(
    rag_cur,
    ids: list[str],
    new_state: str,
    reviewer: str | None = None,
    reviewer_notes: str | None = None,
    *,
    candidate_type: str | None = None,
    proposed_tag: str | None = None,
) -> int:
    """
    Update policy_lexicon_candidates rows by ID.
    When new_state is 'rejected', also clears llm_verdict to 'reject' and proposed_tag to NULL
    so the stored data reflects the user's decision (no leftover "proposed" suggestion).
    Returns the number of rows updated.
    """
    if not ids:
        return 0
    ids_clean = [str(x).strip() for x in ids if str(x).strip()]
    if not ids_clean:
        return 0
    rev = reviewer or "lexicon-ui"
    notes = (reviewer_notes or "")[:500]
    ct_val = candidate_type if candidate_type in ("p", "d", "j") else None
    pt_val = (proposed_tag or "").strip() or None
    st = (new_state or "").strip().lower()

    if st == "rejected":
        # Clear llm_verdict and proposed_tag so rejected rows don't show old LLM suggestion
        rag_cur.execute(
            """
            UPDATE policy_lexicon_candidates
            SET state = %s,
                llm_verdict = 'reject',
                proposed_tag = NULL,
                candidate_type = COALESCE(%s, candidate_type),
                reviewer = %s,
                reviewer_notes = %s
            WHERE id::text = ANY(%s)
            """,
            (new_state, ct_val, rev, notes, ids_clean),
        )
    else:
        rag_cur.execute(
            """
            UPDATE policy_lexicon_candidates
            SET state = %s,
                candidate_type = COALESCE(%s, candidate_type),
                proposed_tag = COALESCE(%s, proposed_tag),
                reviewer = %s,
                reviewer_notes = %s
            WHERE id::text = ANY(%s)
            """,
            (new_state, ct_val, pt_val, rev, notes, ids_clean),
        )
    return rag_cur.rowcount


def update_candidate_state_in_rag(
    rag_cur,
    normalized: str,
    new_state: str,
    reviewer: str | None = None,
    reviewer_notes: str | None = None,
    *,
    candidate_type: str | None = None,
    proposed_tag: str | None = None,
) -> int:
    """
    Update policy_lexicon_candidates rows matching normalized (case-insensitive).
    Only updates rows with state='proposed'.
    When new_state is 'rejected', also clears llm_verdict to 'reject' and proposed_tag to NULL.
    Returns the number of rows updated.
    """
    nk = _normalize_phrase(normalized)
    rev = reviewer or "lexicon-ui"
    notes = (reviewer_notes or "")[:500]
    ct_val = candidate_type if candidate_type in ("p", "d", "j") else None
    pt_val = (proposed_tag or "").strip() or None
    st = (new_state or "").strip().lower()

    if st == "rejected":
        rag_cur.execute(
            """
            UPDATE policy_lexicon_candidates
            SET state = %s,
                llm_verdict = 'reject',
                proposed_tag = NULL,
                candidate_type = COALESCE(%s, candidate_type),
                reviewer = %s,
                reviewer_notes = %s
            WHERE trim(lower(regexp_replace(normalized, E'\\s+', ' ', 'g'))) = %s AND state = 'proposed'
            """,
            (new_state, ct_val, rev, notes, nk),
        )
    else:
        rag_cur.execute(
            """
            UPDATE policy_lexicon_candidates
            SET state = %s,
                candidate_type = COALESCE(%s, candidate_type),
                proposed_tag = COALESCE(%s, proposed_tag),
                reviewer = %s,
                reviewer_notes = %s
            WHERE trim(lower(regexp_replace(normalized, E'\\s+', ' ', 'g'))) = %s AND state = 'proposed'
            """,
            (new_state, ct_val, pt_val, rev, notes, nk),
        )
    rc = rag_cur.rowcount
    # Verify immediately in same connection (catches commit/DB mismatch issues)
    if rc > 0:
        try:
            rag_cur.execute(
                """
                SELECT state, count(*) FROM policy_lexicon_candidates
                WHERE trim(lower(regexp_replace(normalized, E'\\s+', ' ', 'g'))) = %s
                GROUP BY state
                """,
                (nk,),
            )
            verify = rag_cur.fetchall()
            logger.info("[candidate_ops] after UPDATE: normalized=%r rows_updated=%d verify=%s", normalized, rc, verify)
        except Exception as ve:
            logger.warning("[candidate_ops] verify failed: %s", ve)
    if rc == 0:
        # Diagnostic: check if any rows exist for this normalized (different state/whitespace?)
        try:
            rag_cur.execute(
                """
                SELECT state, count(*) FROM policy_lexicon_candidates
                WHERE trim(lower(regexp_replace(normalized, E'\\s+', ' ', 'g'))) = %s
                GROUP BY state
                """,
                (nk,),
            )
            rows = rag_cur.fetchall()
            if rows:
                logger.warning(
                    "[candidate_ops] UPDATE matched 0 rows for normalized=%r; existing rows: %s",
                    normalized, rows,
                )
            else:
                logger.warning(
                    "[candidate_ops] UPDATE matched 0 rows for normalized=%r; no rows exist in policy_lexicon_candidates",
                    normalized,
                )
        except Exception as diag_err:
            logger.warning("[candidate_ops] UPDATE matched 0 for %r; diagnostic query failed: %s", normalized, diag_err)
    return rc


def upsert_catalog(
    rag_cur,
    candidate_type: str,
    normalized_key: str,
    proposed_tag_key: str,
    proposed_tag: str | None,
    state: str,
    reviewer: str | None = None,
    reviewer_notes: str | None = None,
) -> None:
    """
    Insert or update policy_lexicon_candidate_catalog.
    Unique key: (candidate_type, normalized_key, proposed_tag_key).
    Best-effort: catches and ignores DB errors so callers can still report success.
    """
    ct = candidate_type.strip().lower()[:1] if candidate_type else "d"
    if ct not in ("p", "d", "j"):
        ct = "d"
    nk = (normalized_key or "")[:300]
    ptk = (proposed_tag_key or "")[:300]
    pt = (proposed_tag or "")[:500]
    st = (state or "rejected").strip().lower()
    if st not in ("rejected", "approved", "flagged", "proposed"):
        st = "rejected"
    rev = (reviewer or "lexicon-ui")[:255]
    notes = (reviewer_notes or "")[:500]

    try:
        rag_cur.execute(
            """
            INSERT INTO policy_lexicon_candidate_catalog
            (candidate_type, normalized_key, normalized, proposed_tag_key, proposed_tag, state, reviewer, reviewer_notes, decided_at, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW())
            ON CONFLICT (candidate_type, normalized_key, proposed_tag_key)
            DO UPDATE SET state = EXCLUDED.state,
                          reviewer = COALESCE(EXCLUDED.reviewer, policy_lexicon_candidate_catalog.reviewer),
                          reviewer_notes = COALESCE(EXCLUDED.reviewer_notes, policy_lexicon_candidate_catalog.reviewer_notes),
                          decided_at = NOW(), updated_at = NOW()
            """,
            (ct, nk, (normalized_key or "")[:500], ptk, pt or None, st, rev, notes),
        )
    except Exception:
        pass  # Best-effort; main operation (candidate update) already succeeded


def reject_candidate_by_ids(
    rag_cur,
    ids: list[str],
    normalized_for_catalog: str,
    reviewer: str | None = None,
    reviewer_notes: str | None = None,
    *,
    candidate_type: str | None = None,
    ct_by_id: dict[str, str] | None = None,
) -> tuple[int, str | None]:
    """
    Reject candidates by ID. Uses normalized_for_catalog for upsert_catalog.
    Returns (rows_updated, error_message).
    """
    if not ids:
        return 0, "no_ids"
    nk = _normalize_phrase(normalized_for_catalog)
    rev = reviewer or "lexicon-ui"
    notes = (reviewer_notes or "LLM-recommended reject")[:500]
    ct = candidate_type
    if not ct and ct_by_id:
        ct = ct_by_id.get(ids[0]) or "d"
    if not ct or ct not in ("p", "d", "j"):
        ct = "d"

    rows = update_candidate_state_by_ids(
        rag_cur, ids, "rejected", reviewer=rev, reviewer_notes=notes
    )
    if rows == 0:
        return 0, "no_rows_updated"

    upsert_catalog(
        rag_cur,
        candidate_type=ct,
        normalized_key=nk,
        proposed_tag_key="",
        proposed_tag=None,
        state="rejected",
        reviewer=rev,
        reviewer_notes=notes,
    )
    return rows, None


def reject_candidate_in_rag(
    rag_cur,
    normalized: str,
    reviewer: str | None = None,
    reviewer_notes: str | None = None,
    *,
    candidate_type: str | None = None,
    ct_by_nk: dict[str, str] | None = None,
) -> tuple[int, str | None]:
    """
    Reject a candidate: update policy_lexicon_candidates and upsert catalog.
    Returns (rows_updated, error_message).
    If rows_updated is 0, error_message is set (caller should report failure).
    """
    nk = normalized.strip().lower()
    rev = reviewer or "lexicon-ui"
    notes = (reviewer_notes or "LLM-recommended reject")[:500]
    ct = candidate_type
    if not ct and ct_by_nk:
        ct = ct_by_nk.get(nk) or "d"
    if not ct or ct not in ("p", "d", "j"):
        ct = "d"

    rows = update_candidate_state_in_rag(
        rag_cur, normalized, "rejected", reviewer=rev, reviewer_notes=notes
    )
    if rows == 0:
        logger.info("[candidate_ops] reject_candidate_in_rag: normalized=%r rows_updated=0", normalized)
        return 0, "no_rows_updated"

    logger.info("[candidate_ops] reject_candidate_in_rag: normalized=%r rows_updated=%d", normalized, rows)
    upsert_catalog(
        rag_cur,
        candidate_type=ct,
        normalized_key=nk,
        proposed_tag_key="",
        proposed_tag=None,
        state="rejected",
        reviewer=rev,
        reviewer_notes=notes,
    )
    return rows, None
