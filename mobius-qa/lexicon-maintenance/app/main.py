from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
import json
import uuid
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_urls
from app.routers import health as health_router
from app.db import dual_session, get_conn, qa_session, rag_session
from app.repositories import (
    bump_revision as _bump_revision_repo,
    ensure_dismissed_table,
    get_lexicon_meta_and_tags,
    load_dismissed as _load_dismissed_repo,
    parent_exists as _parent_exists_repo,
)
from app.repositories.dismissed_repo import dismissed_fingerprint as _dismissed_fingerprint_repo
from app.candidate_ops import (
    _normalize_phrase,
    fetch_candidate_types_by_ids,
    reject_candidate_by_ids,
    resolve_normalized_to_ids,
    update_candidate_state_by_ids,
    upsert_catalog,
)

logger = logging.getLogger(__name__)


def _urls():
    return get_urls()


def _conn(url: str):
    """Get a pooled connection. Call .close() when done. Prefer qa_session/rag_session/dual_session."""
    return get_conn(url)


app = FastAPI(title="Mobius QA — Lexicon Maintenance API", version="0.1.0")
logging.getLogger("app").setLevel(logging.INFO)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router.router)


# ---------------------------------------------------------------------------
# Dismissed health issues — persistent overrule store
# ---------------------------------------------------------------------------
def _ensure_dismissed_table(qa_url: str) -> None:
    with qa_session() as qa:
        ensure_dismissed_table(qa)


def _dismissed_fingerprint(issue_type: str, tags: list[str]) -> str:
    return _dismissed_fingerprint_repo(issue_type, tags)


def _load_dismissed(qa_url: str) -> list[dict]:
    try:
        with qa_session() as qa:
            qa.autocommit = True
            ensure_dismissed_table(qa)
            cur = qa.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            return _load_dismissed_repo(cur)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Taxonomy structure validation
# ---------------------------------------------------------------------------
_TAG_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$")


def _validate_tag_structure(kind: str, code: str, parent_code: str | None, qa_url: str,
                            spec: dict | None = None) -> None:
    """
    Enforce 2-level taxonomy rules on tag create/update.
    Raises HTTPException(400) on violations.

    Rules:
      1. code matches ^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)?$  (max 2 segments)
      2. Domain containers (no dot): parent_code must be null, NO matching metadata
      3. Tags (has dot): parent_code must be set and must exist in same kind
    """
    if not _TAG_CODE_RE.match(code):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tag code '{code}'. Must be lowercase_snake with max 2 dot-segments "
                   f"(e.g. 'claims' or 'claims.submission'). Regex: {_TAG_CODE_RE.pattern}"
        )

    has_dot = "." in code
    if not has_dot and parent_code:
        raise HTTPException(
            status_code=400,
            detail=f"Domain container '{code}' must not have a parent_code (got '{parent_code}')"
        )

    # Domain containers must not carry matching metadata
    if not has_dot and spec:
        for field in ("strong_phrases", "aliases", "refuted_words"):
            val = spec.get(field)
            if val and isinstance(val, list) and len(val) > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Domain container '{code}' must not have {field} -- "
                           f"add a .general leaf tag instead"
                )

    if has_dot:
        expected_parent = code.rsplit(".", 1)[0]
        if not parent_code:
            raise HTTPException(
                status_code=400,
                detail=f"Child tag '{code}' requires parent_code (expected '{expected_parent}')"
            )
        try:
            with qa_session() as qa:
                cur = qa.cursor()
                if not _parent_exists_repo(cur, kind, parent_code):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Parent tag '{kind}.{parent_code}' does not exist. "
                               f"Create the root tag first."
                    )
        except HTTPException:
            raise
        except Exception:
            pass  # best-effort; don't block on transient DB issues


@app.get("/policy/lexicon")
def get_policy_lexicon():
    """Return lexicon tags + meta from QA DB."""
    try:
        with qa_session() as c:
            cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            meta, tags = get_lexicon_meta_and_tags(cur)
        lexicon_meta = meta.get("lexicon_meta") if isinstance(meta.get("lexicon_meta"), dict) else (meta.get("lexicon_meta") or {})
        return {
            "lexicon_version": meta.get("lexicon_version") or "v1",
            "lexicon_revision": int(meta.get("revision") or 0),
            "lexicon_meta": lexicon_meta if isinstance(lexicon_meta, dict) else {},
            "tags": tags,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load lexicon: {type(e).__name__}: {e}")


def _pick_kind(candidate_types: list[str]) -> str:
    ks = [str(k or "").strip().lower() for k in candidate_types if str(k or "").strip()]
    ks = [k for k in ks if k in ("p", "d", "j")]
    if not ks:
        return "d"
    uniq = sorted(set(ks))
    if len(uniq) == 1:
        return uniq[0]
    if "d" in uniq:
        return "d"
    if "j" in uniq:
        return "j"
    return "p"


def _parse_kind_code(s: str, default_kind: str) -> tuple[str, str]:
    """
    Accept either 'd:contact_information' or 'contact_information'.
    Returns (kind, code).
    """
    raw = (s or "").strip()
    dk = (default_kind or "d").strip().lower() or "d"
    if ":" in raw:
        k, c = raw.split(":", 1)
        k = (k or "").strip().lower() or dk
        c = (c or "").strip()
        return (k, c)
    return (dk, raw)


def _bump_lexicon_revision(qcur) -> int:
    return _bump_revision_repo(qcur)


def _ensure_list(obj: dict, key: str) -> list[str]:
    v = obj.get(key)
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    obj[key] = []
    return obj[key]


def _add_alias_phrase(spec: dict[str, Any], phrase: str, strength: str = "strong") -> dict[str, Any]:
    """
    Add phrase to spec as an alias.
    - strong: spec.strong_phrases: [phrase, ...]
    - weak: spec.weak_keywords.any_of: [phrase, ...] (min_hits default 1)
    """
    p = (phrase or "").strip()
    if not p:
        return spec
    st = (strength or "strong").strip().lower()
    if st == "weak":
        wk = spec.get("weak_keywords")
        if not isinstance(wk, dict):
            wk = {}
        any_of = wk.get("any_of")
        if not isinstance(any_of, list):
            any_of = []
        if p not in [str(x) for x in any_of]:
            any_of.append(p)
        wk["any_of"] = any_of
        wk.setdefault("min_hits", 1)
        spec["weak_keywords"] = wk
        return spec
    # default: strong
    sp = _ensure_list(spec, "strong_phrases")
    if p not in [str(x) for x in sp]:
        sp.append(p)
    spec["strong_phrases"] = sp
    return spec


@app.get("/policy/lexicon/tag-details")
def get_policy_lexicon_tag_details(
    kind: str = Query(...),
    code: str = Query(...),
    min_score: float = Query(0.6),
    top_docs: int = Query(15),
    sample_lines: int = Query(25),
) -> dict[str, Any]:
    """
    UI helper: show one tag's details + usage counts and sample lines from RAG policy_lines.
    """
    u = _urls()
    k = (kind or "").strip().lower()
    c = (code or "").strip()
    if k not in ("p", "d", "j") or not c:
        raise HTTPException(status_code=400, detail="kind and code are required")
    td = max(0, min(int(top_docs or 15), 50))
    sl = max(0, min(int(sample_lines or 25), 200))
    ms = float(min_score or 0.0)

    # Load tag spec from QA
    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        qcur = qa.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        qcur.execute(
            """
            SELECT kind::text, code::text, parent_code::text, spec, active::bool
            FROM policy_lexicon_entries
            WHERE kind = %s AND code = %s
            LIMIT 1
            """,
            (k, c),
        )
        tag = qcur.fetchone() or None
        qcur.close()
        qa.close()
        if not tag:
            raise HTTPException(status_code=404, detail="tag not found")
        tag_out = {
            "kind": k,
            "code": c,
            "parent_code": tag.get("parent_code"),
            "active": bool(tag.get("active")) if tag.get("active") is not None else True,
            "spec": tag.get("spec") if isinstance(tag.get("spec"), dict) else {},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load tag: {type(e).__name__}: {e}")

    # Usage counts + examples from RAG
    try:
        rag = _conn(u.rag)
        rag.autocommit = True
        rcur = rag.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        tag_expr = (
            "policy_lines.p_tags"
            if k == "p"
            else ("COALESCE(policy_lines.inferred_d_tags, policy_lines.d_tags)" if k == "d" else "COALESCE(policy_lines.inferred_j_tags, policy_lines.j_tags)")
        )

        rcur.execute(
            f"""
            WITH expanded AS (
              SELECT
                policy_lines.document_id::text AS document_id,
                policy_lines.page_number AS page_number,
                policy_lines.text AS text,
                e.key AS code,
                CASE
                  WHEN e.value ~ '^[0-9]+(\\.[0-9]+)?$' THEN (e.value)::double precision
                  ELSE NULL
                END AS score
              FROM policy_lines
              CROSS JOIN LATERAL jsonb_each_text({tag_expr}) AS e
              WHERE policy_lines.is_atomic = TRUE
                AND jsonb_typeof({tag_expr}) = 'object'
                AND e.key = %s
            )
            SELECT
              COUNT(*)::bigint AS hit_lines,
              COUNT(DISTINCT document_id)::bigint AS hit_docs,
              COALESCE(MAX(score), 0.0) AS max_score
            FROM expanded
            WHERE score IS NOT NULL AND score >= %s
            """,
            (c, ms),
        )
        usage = rcur.fetchone() or {}

        top_documents = []
        if td > 0:
            rcur.execute(
                f"""
                WITH expanded AS (
                  SELECT
                    policy_lines.document_id::text AS document_id,
                    CASE
                      WHEN e.value ~ '^[0-9]+(\\.[0-9]+)?$' THEN (e.value)::double precision
                      ELSE NULL
                    END AS score
                  FROM policy_lines
                  CROSS JOIN LATERAL jsonb_each_text({tag_expr}) AS e
                  WHERE policy_lines.is_atomic = TRUE
                    AND jsonb_typeof({tag_expr}) = 'object'
                    AND e.key = %s
                )
                SELECT document_id, COUNT(*)::bigint AS hit_lines, COALESCE(MAX(score), 0.0) AS max_score
                FROM expanded
                WHERE score IS NOT NULL AND score >= %s
                GROUP BY document_id
                ORDER BY hit_lines DESC, max_score DESC, document_id ASC
                LIMIT {td}
                """,
                (c, ms),
            )
            for rr in rcur.fetchall() or []:
                top_documents.append(
                    {
                        "document_id": rr.get("document_id"),
                        "hit_lines": int(rr.get("hit_lines") or 0),
                        "max_score": float(rr.get("max_score") or 0.0),
                    }
                )

        samples = []
        if sl > 0:
            rcur.execute(
                f"""
                WITH expanded AS (
                  SELECT
                    policy_lines.document_id::text AS document_id,
                    policy_lines.page_number AS page_number,
                    policy_lines.text AS text,
                    CASE
                      WHEN e.value ~ '^[0-9]+(\\.[0-9]+)?$' THEN (e.value)::double precision
                      ELSE NULL
                    END AS score
                  FROM policy_lines
                  CROSS JOIN LATERAL jsonb_each_text({tag_expr}) AS e
                  WHERE policy_lines.is_atomic = TRUE
                    AND jsonb_typeof({tag_expr}) = 'object'
                    AND e.key = %s
                )
                SELECT document_id, page_number, score, text
                FROM expanded
                WHERE score IS NOT NULL AND score >= %s
                ORDER BY score DESC NULLS LAST, document_id ASC, page_number ASC
                LIMIT {sl}
                """,
                (c, ms),
            )
            for rr in rcur.fetchall() or []:
                txt = str(rr.get("text") or "")
                samples.append(
                    {
                        "document_id": rr.get("document_id"),
                        "page_number": rr.get("page_number"),
                        "score": float(rr.get("score") or 0.0),
                        "text": txt,
                        "snippet": txt[:240].replace("\n", " ").strip(),
                    }
                )

        rcur.close()
        rag.close()
    except Exception as e:
        usage = {"hit_lines": 0, "hit_docs": 0, "max_score": 0.0, "error": f"{type(e).__name__}: {e}"}
        top_documents = []
        samples = []

    return {
        "tag": tag_out,
        "usage": {
            "hit_lines": int((usage or {}).get("hit_lines") or 0),
            "hit_docs": int((usage or {}).get("hit_docs") or 0),
            "max_score": float((usage or {}).get("max_score") or 0.0),
        },
        "top_documents": top_documents,
        "sample_lines": samples,
    }


@app.patch("/policy/lexicon/tags/{kind}/{code}")
def patch_policy_lexicon_tag(kind: str, code: str, body: dict = Body(...)) -> dict[str, Any]:
    """
    Update tag spec/active flag in QA DB. Used by the bundled UI for editing and soft-delete.
    Body: { spec: object, active: bool, reviewer?: string }
    """
    u = _urls()
    k = (kind or "").strip().lower()
    c = (code or "").strip()
    if k not in ("p", "d", "j") or not c:
        raise HTTPException(status_code=400, detail="kind must be p|d|j and code is required")
    spec = body.get("spec") if isinstance(body.get("spec"), dict) else {}
    active = bool(body.get("active")) if "active" in body else True
    parent_code = spec.get("parent_code") if isinstance(spec.get("parent_code"), str) else None

    # Auto-derive parent_code from dotted code when not explicitly provided
    if not parent_code and "." in c:
        parent_code = c.rsplit(".", 1)[0]

    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        cur = qa.cursor()

        # Check if tag already exists (skip structure validation for spec-only edits
        # on existing tags to avoid blocking alias additions etc.)
        cur.execute(
            """
            SELECT id
            FROM policy_lexicon_entries
            WHERE kind = %s AND code = %s
            LIMIT 1
            """,
            (k, c),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            # New tag: enforce full taxonomy validation
            _validate_tag_structure(k, c, parent_code, u.qa, spec=spec)

        if row and row[0]:
            cur.execute(
                """
                UPDATE policy_lexicon_entries
                SET spec = %s::jsonb,
                    active = %s,
                    parent_code = COALESCE(%s, parent_code),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(spec), active, parent_code, row[0]),
            )
        else:
            cur.execute(
                """
                INSERT INTO policy_lexicon_entries(id, kind, code, parent_code, spec, active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, NOW(), NOW())
                """,
                (str(uuid.uuid4()), k, c, parent_code, json.dumps(spec), active),
            )

        new_rev = _bump_lexicon_revision(cur)
        cur.close()
        qa.close()
        return {"status": "ok", "kind": k, "code": c, "active": active, "lexicon_revision": new_rev}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update tag: {type(e).__name__}: {e}")


@app.post("/policy/lexicon/tags/move")
def move_policy_lexicon_tag(body: dict = Body(...)) -> dict[str, Any]:
    """
    Move/rename a tag code (currently used by UI for reorganizing D tags).
    Body: { kind: 'd', from_code: str, to_code: str, parent_code?: str|null }
    """
    u = _urls()
    k = str(body.get("kind") or "").strip().lower()
    from_code = str(body.get("from_code") or "").strip()
    to_code = str(body.get("to_code") or "").strip()
    parent_code = body.get("parent_code")
    parent_code = str(parent_code).strip() if isinstance(parent_code, str) and str(parent_code).strip() else None
    if k not in ("p", "d", "j") or not from_code or not to_code:
        raise HTTPException(status_code=400, detail="kind/from_code/to_code are required")
    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        cur = qa.cursor()
        # Rename the tag
        cur.execute(
            """
            UPDATE policy_lexicon_entries
            SET code = %s,
                parent_code = %s,
                updated_at = NOW()
            WHERE kind = %s AND code = %s
            """,
            (to_code, parent_code, k, from_code),
        )
        if cur.rowcount <= 0:
            raise HTTPException(status_code=404, detail="from_code not found")
        # Best-effort: update children referencing old parent_code
        cur.execute(
            """
            UPDATE policy_lexicon_entries
            SET parent_code = %s,
                updated_at = NOW()
            WHERE kind = %s AND parent_code = %s
            """,
            (to_code, k, from_code),
        )
        new_rev = _bump_lexicon_revision(cur)
        cur.close()
        qa.close()
        return {"status": "ok", "kind": k, "from_code": from_code, "to_code": to_code, "parent_code": parent_code, "lexicon_revision": new_rev}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to move tag: {type(e).__name__}: {e}")


@app.delete("/policy/lexicon/tags/{kind}/{code}")
def delete_policy_lexicon_tag(kind: str, code: str) -> dict[str, Any]:
    """
    Hard-delete a tag from QA DB. Also orphan-promotes any children to root.
    """
    u = _urls()
    k = (kind or "").strip().lower()
    c = (code or "").strip()
    if k not in ("p", "d", "j") or not c:
        raise HTTPException(status_code=400, detail="kind must be p|d|j and code is required")

    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        cur = qa.cursor()

        # Promote children to root (clear their parent_code)
        cur.execute(
            """
            UPDATE policy_lexicon_entries
            SET parent_code = NULL,
                updated_at = NOW()
            WHERE kind = %s AND parent_code = %s
            """,
            (k, c),
        )
        promoted = cur.rowcount

        # Delete the tag
        cur.execute(
            """
            DELETE FROM policy_lexicon_entries
            WHERE kind = %s AND code = %s
            """,
            (k, c),
        )
        deleted = cur.rowcount

        new_rev = _bump_lexicon_revision(cur)
        cur.close()
        qa.close()
        return {"status": "ok", "kind": k, "code": c, "deleted": deleted, "children_promoted": promoted, "lexicon_revision": new_rev}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete tag: {type(e).__name__}: {e}")


@app.post("/policy/lexicon/tags/merge")
def merge_policy_lexicon_tags(body: dict = Body(...)) -> dict[str, Any]:
    """
    Merge source tag into target tag:
      1. Copies all strong_phrases/aliases from source to target spec
      2. Re-parents source's children to target
      3. Deletes source

    Body: { kind: str, source_code: str, target_code: str }
    """
    u = _urls()
    k = str(body.get("kind") or "").strip().lower()
    src = str(body.get("source_code") or "").strip()
    tgt = str(body.get("target_code") or "").strip()
    if k not in ("p", "d", "j") or not src or not tgt:
        raise HTTPException(status_code=400, detail="kind/source_code/target_code are required")
    if src == tgt:
        raise HTTPException(status_code=400, detail="source and target must differ")

    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        cur = qa.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Load source and target
        cur.execute(
            "SELECT kind, code, spec, parent_code FROM policy_lexicon_entries WHERE kind = %s AND code = %s LIMIT 1",
            (k, src),
        )
        src_row = cur.fetchone()
        if not src_row:
            raise HTTPException(status_code=404, detail=f"Source tag {k}.{src} not found")

        cur.execute(
            "SELECT id, kind, code, spec, parent_code FROM policy_lexicon_entries WHERE kind = %s AND code = %s LIMIT 1",
            (k, tgt),
        )
        tgt_row = cur.fetchone()
        if not tgt_row:
            raise HTTPException(status_code=404, detail=f"Target tag {k}.{tgt} not found")

        # Merge phrases from source → target
        src_spec = src_row.get("spec") if isinstance(src_row.get("spec"), dict) else {}
        tgt_spec = tgt_row.get("spec") if isinstance(tgt_row.get("spec"), dict) else {}

        src_phrases = set()
        for field in ("strong_phrases", "phrases"):
            for p in (src_spec.get(field) or []):
                src_phrases.add(str(p).strip())
        # Also add the source code itself as an alias
        src_phrases.add(src.replace("_", " ").strip())

        existing_phrases = set(str(p).strip() for p in (tgt_spec.get("strong_phrases") or []))
        new_phrases = [p for p in src_phrases if p and p not in existing_phrases]

        tgt_strong = list(tgt_spec.get("strong_phrases") or []) + new_phrases
        tgt_spec["strong_phrases"] = tgt_strong

        # Update target with merged spec
        cur.execute(
            """
            UPDATE policy_lexicon_entries
            SET spec = %s::jsonb, updated_at = NOW()
            WHERE kind = %s AND code = %s
            """,
            (json.dumps(tgt_spec), k, tgt),
        )

        # Re-parent source's children to target
        cur.execute(
            """
            UPDATE policy_lexicon_entries
            SET parent_code = %s, updated_at = NOW()
            WHERE kind = %s AND parent_code = %s
            """,
            (tgt, k, src),
        )
        reparented = cur.rowcount

        # Delete source
        cur.execute(
            "DELETE FROM policy_lexicon_entries WHERE kind = %s AND code = %s",
            (k, src),
        )

        new_rev = _bump_lexicon_revision(cur)
        cur.close()
        qa.close()
        return {
            "status": "ok",
            "kind": k,
            "source": src,
            "target": tgt,
            "phrases_merged": len(new_phrases),
            "children_reparented": reparented,
            "lexicon_revision": new_rev,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to merge tags: {type(e).__name__}: {e}")


@app.get("/policy/lexicon/overview")
def get_policy_lexicon_overview(
    kind: str = Query("all"),
    status: str = Query("all"),
    min_score: float = Query(0.6),
    limit: int = Query(700),
    top_docs: int = Query(6),
    search: str | None = Query(None),
):
    """Approved tags from QA + candidate aggregates from RAG (proposed/rejected/flagged)."""
    u = _urls()
    kind_norm = (kind or "all").strip().lower()
    status_norm = (status or "all").strip().lower()
    if kind_norm not in ("all", "p", "d", "j"):
        raise HTTPException(status_code=400, detail="kind must be all|p|d|j")
    if status_norm not in ("all", "approved", "proposed", "rejected", "flagged"):
        raise HTTPException(status_code=400, detail="status must be all|approved|proposed|rejected|flagged")
    lim = max(1, min(int(limit or 700), 5000))
    td = max(0, min(int(top_docs or 6), 20))
    q_search = (search or "").strip()

    # Pull lexicon meta + entries from QA (source of truth)
    qa = None
    qcur = None
    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        qcur = qa.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        qcur.execute(
            """
            SELECT COALESCE(revision,0)::bigint AS revision,
                   COALESCE(lexicon_version,'v1')::text AS lexicon_version,
                   lexicon_meta
            FROM policy_lexicon_meta
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 1
            """
        )
        meta = qcur.fetchone() or {}
        lexicon_revision = int(meta.get("revision") or 0)
        lexicon_version = str(meta.get("lexicon_version") or "v1")

        tag_rows: list[dict[str, Any]] = []
        if status_norm in ("all", "approved"):
            qcur.execute(
                """
                SELECT kind::text, code::text, parent_code::text, spec, active::bool
                FROM policy_lexicon_entries
                WHERE active = true
                """
            )
            for r in qcur.fetchall():
                k = (r.get("kind") or "").strip().lower()
                code = str(r.get("code") or "").strip()
                if not code or k not in ("p", "d", "j"):
                    continue
                if kind_norm != "all" and k != kind_norm:
                    continue
                if q_search and q_search.lower() not in code.lower() and q_search.lower() not in str(r.get("spec") or "").lower():
                    continue
                spec = r.get("spec") if isinstance(r.get("spec"), dict) else {}
                tag_rows.append(
                    {
                        "id": f"tag:{k}:{code}",
                        "row_type": "tag",
                        "kind": k,
                        "status": "approved",
                        "code": code,
                        "parent_code": r.get("parent_code") or None,
                        "category": spec.get("category") if isinstance(spec, dict) else None,
                        "description": spec.get("description") if isinstance(spec, dict) else None,
                        "strong_phrases": spec.get("strong_phrases") or spec.get("phrases") or [],
                        # Filled from RAG DB (policy_lines) below.
                        "hit_lines": 0,
                        "hit_docs": 0,
                        "max_score": 0.0,
                    }
                )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read QA lexicon: {type(e).__name__}: {e}")
    finally:
        try:
            if qcur is not None:
                qcur.close()
        except Exception:
            pass
        try:
            if qa is not None:
                qa.close()
        except Exception:
            pass

    # Tag usage counts for approved tags (from RAG Path B artifacts)
    # These are computed from policy_lines.*_tags JSONB maps (tag_code -> weight).
    if tag_rows:
        try:
            rag = _conn(u.rag)
            rag.autocommit = True
            rcur = rag.cursor()

            # Build lookup for fast updates
            row_by_kind_code: dict[tuple[str, str], dict[str, Any]] = {}
            codes_by_kind: dict[str, list[str]] = {"p": [], "d": [], "j": []}
            for tr in tag_rows:
                k = str(tr.get("kind") or "").strip().lower()
                c = str(tr.get("code") or "").strip()
                if k in ("p", "d", "j") and c:
                    row_by_kind_code[(k, c)] = tr
                    codes_by_kind[k].append(c)

            def _counts_for(kind_k: str, tag_expr_sql: str, codes: list[str]) -> None:
                if not codes:
                    return
                # Note: policy_lines.*_tags may contain JSON null (jsonb_typeof='null'), so we must guard for object.
                rcur.execute(
                    f"""
                    WITH expanded AS (
                      SELECT
                        policy_lines.document_id::text AS document_id,
                        e.key AS code,
                        CASE
                          WHEN e.value ~ '^[0-9]+(\\.[0-9]+)?$' THEN (e.value)::double precision
                          ELSE NULL
                        END AS score
                      FROM policy_lines
                      CROSS JOIN LATERAL jsonb_each_text({tag_expr_sql}) AS e
                      WHERE policy_lines.is_atomic = TRUE
                        AND jsonb_typeof({tag_expr_sql}) = 'object'
                    )
                    SELECT code,
                           COUNT(*)::bigint AS hit_lines,
                           COUNT(DISTINCT document_id)::bigint AS hit_docs,
                           COALESCE(MAX(score), 0.0) AS max_score
                    FROM expanded
                    WHERE score IS NOT NULL
                      AND score >= %s
                      AND code = ANY(%s)
                    GROUP BY code
                    """,
                    (float(min_score or 0.0), codes),
                )
                for code, hit_lines, hit_docs, max_score in (rcur.fetchall() or []):
                    tr = row_by_kind_code.get((kind_k, str(code)))
                    if tr is None:
                        continue
                    tr["hit_lines"] = int(hit_lines or 0)
                    tr["hit_docs"] = int(hit_docs or 0)
                    tr["max_score"] = float(max_score or 0.0)

            _counts_for("p", "policy_lines.p_tags", codes_by_kind["p"])
            # Prefer inferred tags if present; otherwise fall back to d_tags/j_tags
            _counts_for("d", "COALESCE(policy_lines.inferred_d_tags, policy_lines.d_tags)", codes_by_kind["d"])
            _counts_for("j", "COALESCE(policy_lines.inferred_j_tags, policy_lines.j_tags)", codes_by_kind["j"])

            rcur.close()
            rag.close()
        except Exception:
            # Best-effort; never fail the whole endpoint just because counts couldn't be computed.
            try:
                rcur.close()
            except Exception:
                pass
            try:
                rag.close()
            except Exception:
                pass

    # Candidate aggregates from RAG
    cand_rows: list[dict[str, Any]] = []
    if status_norm in ("all", "proposed", "rejected", "flagged"):
        try:
            rag = _conn(u.rag)
            rag.autocommit = True
            rcur = rag.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            where = ["confidence IS NULL OR confidence >= %s"]
            params: list[Any] = [float(min_score or 0.0)]
            if status_norm != "all":
                where.append("state = %s")
                params.append(status_norm)
            if q_search:
                where.append("(normalized ILIKE %s OR COALESCE(proposed_tag,'') ILIKE %s)")
                params.extend([f"%{q_search}%", f"%{q_search}%"])
            if kind_norm != "all":
                where.append("candidate_type = %s")
                params.append(kind_norm)

            sql = f"""
              SELECT
                trim(lower(normalized)) AS norm_key,
                max(normalized) AS normalized,
                array_agg(id::text) AS ids,
                array_agg(DISTINCT candidate_type) AS candidate_types,
                array_agg(DISTINCT proposed_tag) FILTER (WHERE proposed_tag IS NOT NULL AND proposed_tag <> '') AS proposed_tags,
                max(state) AS state,
                count(DISTINCT document_id) AS doc_count,
                COALESCE(sum(COALESCE(occurrences, 1)), count(*)) AS total_occurrences,
                COALESCE(max(COALESCE(confidence, 0)), 0) AS max_confidence,
                -- LLM triage fields (take the first non-null across rows for same normalized phrase)
                max(llm_verdict) AS llm_verdict,
                max(llm_confidence) AS llm_confidence,
                max(llm_reason) AS llm_reason,
                max(llm_suggested_kind) AS llm_suggested_kind,
                max(llm_suggested_code) AS llm_suggested_code,
                max(llm_suggested_parent) AS llm_suggested_parent
              FROM policy_lexicon_candidates
              WHERE {" AND ".join(where)}
              GROUP BY trim(lower(normalized))
              ORDER BY doc_count DESC, total_occurrences DESC, max_confidence DESC, norm_key ASC
              LIMIT {lim}
            """
            rcur.execute(sql, params)
            for r in rcur.fetchall():
                c_types = [str(x or "").strip().lower() for x in (r.get("candidate_types") or []) if str(x or "").strip()]
                kk = _pick_kind(c_types)
                ids_raw = r.get("ids") or []
                ids = [str(x) for x in ids_raw if x] if isinstance(ids_raw, (list, tuple)) else []
                cand_rows.append(
                    {
                        "id": f"cand:{str(r.get('state') or 'proposed').lower()}:{kk}:{str(r.get('norm_key') or '')}",
                        "ids": ids,
                        "row_type": "candidate",
                        "kind": kk,
                        "status": str(r.get("state") or "proposed").lower(),
                        "key": str(r.get("normalized") or ""),
                        "normalized": str(r.get("normalized") or ""),
                        "doc_count": int(r.get("doc_count") or 0),
                        "total_occurrences": int(r.get("total_occurrences") or 0),
                        "max_confidence": float(r.get("max_confidence") or 0.0),
                        "candidate_types": sorted(set([k for k in c_types if k])),
                        "proposed_tags": [str(x) for x in (r.get("proposed_tags") or []) if x],
                        "examples": [],
                        "top_documents": [],
                        # LLM triage fields
                        "llm_verdict": str(r.get("llm_verdict") or "") or None,
                        "llm_confidence": float(r.get("llm_confidence") or 0) if r.get("llm_confidence") is not None else None,
                        "llm_reason": str(r.get("llm_reason") or "") or None,
                        "llm_suggested_kind": str(r.get("llm_suggested_kind") or "") or None,
                        "llm_suggested_code": str(r.get("llm_suggested_code") or "") or None,
                        "llm_suggested_parent": str(r.get("llm_suggested_parent") or "") or None,
                    }
                )

            # Optional: top docs per candidate (best-effort; only for proposed)
            if td > 0 and cand_rows and status_norm in ("all", "proposed"):
                try:
                    norm_keys = [str(r.get("normalized") or "").strip().lower() for r in cand_rows][:200]
                    rcur.execute(
                        """
                        SELECT trim(lower(normalized)) AS norm_key,
                               document_id::text AS document_id,
                               max(document_id::text) AS doc_id,
                               count(*) AS hits,
                               COALESCE(sum(COALESCE(occurrences, 1)), count(*)) AS occ
                        FROM policy_lexicon_candidates
                        WHERE trim(lower(normalized)) = ANY(%s)
                          AND state = 'proposed'
                        GROUP BY trim(lower(normalized)), document_id
                        """,
                        (norm_keys,),
                    )
                    by_norm: dict[str, list[dict[str, Any]]] = {}
                    for rr in rcur.fetchall():
                        nk = str(rr.get("norm_key") or "")
                        by_norm.setdefault(nk, []).append(
                            {
                                "document_id": str(rr.get("document_id") or ""),
                                "document_name": str(rr.get("document_id") or ""),
                                "occurrences": int(rr.get("occ") or 0),
                            }
                        )
                    # Attach top docs
                    for cr in cand_rows:
                        nk = str(cr.get("normalized") or "").strip().lower()
                        docs = by_norm.get(nk) or []
                        docs.sort(key=lambda d: (-int(d.get("occurrences") or 0), d.get("document_id") or ""))
                        cr["top_documents"] = docs[:td]
                except Exception:
                    pass

            rcur.close()
            rag.close()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read RAG candidates: {type(e).__name__}: {e}")

    return {
        "lexicon_version": lexicon_version,
        "lexicon_revision": lexicon_revision,
        "rows": tag_rows + cand_rows,
    }


def _norm_key(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


@app.get("/policy/candidates/aggregate/related")
def list_policy_candidates_related(
    key: str = Query(...),
    state: str = Query("proposed"),
    limit: int = Query(25),
):
    """Return a naive 'related variants' list (same leading token) for UI convenience."""
    u = _urls()
    k = _norm_key(key)
    if not k:
        raise HTTPException(status_code=400, detail="key is required")
    st = (state or "proposed").strip().lower()
    if st not in ("proposed", "rejected", "flagged", "approved", "all"):
        raise HTTPException(status_code=400, detail="state must be proposed|rejected|flagged|approved|all")
    lim = max(1, min(int(limit or 25), 200))

    core = (k.split() or [""])[0]
    if not core:
        core = k[:12]

    try:
        rag = _conn(u.rag)
        rag.autocommit = True
        cur = rag.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where = ["trim(lower(normalized)) LIKE %s"]
        params: list[Any] = [f"{core}%"]
        if st != "all":
            where.append("state = %s")
            params.append(st)
        cur.execute(
            f"""
            SELECT
              trim(lower(normalized)) AS norm_key,
              max(normalized) AS normalized,
              max(state) AS state,
              count(DISTINCT document_id) AS doc_count,
              COALESCE(sum(COALESCE(occurrences, 1)), count(*)) AS total_occurrences,
              COALESCE(max(COALESCE(confidence, 0)), 0) AS max_confidence,
              array_agg(DISTINCT candidate_type) AS candidate_types,
              array_agg(DISTINCT proposed_tag) FILTER (WHERE proposed_tag IS NOT NULL AND proposed_tag <> '') AS proposed_tags
            FROM policy_lexicon_candidates
            WHERE {" AND ".join(where)}
            GROUP BY trim(lower(normalized))
            ORDER BY doc_count DESC, total_occurrences DESC, max_confidence DESC
            LIMIT {lim}
            """,
            params,
        )
        out = []
        for r in cur.fetchall():
            c_types = [str(x or "").strip().lower() for x in (r.get("candidate_types") or []) if str(x or "").strip()]
            out.append(
                {
                    "key": str(r.get("normalized") or ""),
                    "normalized": str(r.get("normalized") or ""),
                    "state": str(r.get("state") or "proposed"),
                    "doc_count": int(r.get("doc_count") or 0),
                    "total_occurrences": int(r.get("total_occurrences") or 0),
                    "max_confidence": float(r.get("max_confidence") or 0.0),
                    "candidate_types": sorted(set([k for k in c_types if k])),
                    "proposed_tags": [str(x) for x in (r.get("proposed_tags") or []) if x],
                    "core": core,
                }
            )
        cur.close()
        rag.close()
        return {"core": core, "candidates": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load related candidates: {type(e).__name__}: {e}")


@app.get("/policy/candidates/debug")
def debug_candidate_state(normalized: str = Query(..., description="Phrase to inspect")):
    """Return raw rows from policy_lexicon_candidates for a phrase (for debugging)."""
    nk = (normalized or "").strip().lower()
    if not nk:
        raise HTTPException(status_code=400, detail="normalized is required")
    u = _urls()
    try:
        rag = _conn(u.rag)
        rag.autocommit = True
        cur = rag.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT id, document_id, candidate_type, normalized, state, reviewer, reviewer_notes, created_at
            FROM policy_lexicon_candidates
            WHERE trim(lower(regexp_replace(normalized, E'\\s+', ' ', 'g'))) = %s
            ORDER BY state, document_id
            """,
            (_normalize_phrase(normalized),),
        )
        raw = cur.fetchall()
        rows = []
        for r in raw:
            d = dict(r)
            out = {}
            for k, v in d.items():
                if v is None or isinstance(v, (bool, int, float, str)):
                    out[k] = v
                else:
                    out[k] = str(v)
            rows.append(out)
        cur.close()
        rag.close()
        return {"normalized": nk, "count": len(rows), "rows": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/policy/candidates/aggregate/review-bulk")
def review_policy_candidates_aggregate_bulk(body: dict = Body(...)):
    """
    Bulk update candidate states in RAG DB by ID.
    Payload: { id_list: [...], state: 'approved'|'rejected'|'proposed'|'flagged',
      candidate_type_override?: 'p'|'d'|'j', tag_code_map?: { <normalized>: <tag_code>, ... } }
    tag_code_map is used only for state=approved; keys are normalized phrases (from DB).

    Backward compat: if id_list is missing/empty but normalized_list is provided,
    resolve normalized phrases to ids before proceeding.
    """
    u = _urls()
    id_list = body.get("id_list") or []
    ids = [str(x).strip() for x in id_list if str(x).strip()] if isinstance(id_list, list) else []

    # Fallback: resolve normalized_list to ids (for legacy clients)
    if not ids:
        normalized_list = body.get("normalized_list") or []
        norms = [str(x).strip() for x in normalized_list if str(x).strip()] if isinstance(normalized_list, list) else []
        if norms:
            try:
                rag = _conn(u.rag)
                rag.autocommit = True
                cur = rag.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                norm_keys = [re.sub(r"\s+", " ", n.strip().lower()) for n in norms]
                cur.execute(
                    """
                    SELECT DISTINCT id::text
                    FROM policy_lexicon_candidates
                    WHERE trim(lower(regexp_replace(normalized, E'\\\\s+', ' ', 'g'))) = ANY(%s)
                    """,
                    (norm_keys,),
                )
                ids = [str(r.get("id", "")) for r in cur.fetchall() if r.get("id")]
                cur.close()
                rag.close()
                if ids:
                    logger.info("[review-bulk] resolved normalized_list (%d phrases) -> %d ids", len(norms), len(ids))
            except Exception as e:
                logger.warning("[review-bulk] normalized_list fallback failed: %s", e)

    if not ids:
        raise HTTPException(status_code=400, detail="id_list is required (or normalized_list for backward compat)")

    next_state = str(body.get("state") or "").strip().lower()
    if next_state not in ("proposed", "rejected", "flagged", "approved"):
        raise HTTPException(status_code=400, detail="state must be proposed|rejected|flagged|approved")
    reviewer = str(body.get("reviewer") or "").strip() or None
    notes = body.get("reviewer_notes")
    candidate_type_override = str(body.get("candidate_type_override") or "").strip().lower() or None
    tag_code_map = body.get("tag_code_map") if isinstance(body.get("tag_code_map"), dict) else None

    logger.info("[review-bulk] state=%r id_list len=%d", next_state, len(ids))
    new_rev = None
    rag = cur = qa = qcur = None

    if next_state == "approved":
        if candidate_type_override not in ("p", "d", "j"):
            raise HTTPException(status_code=400, detail="candidate_type_override is required for state=approved (p|d|j)")
        if not tag_code_map:
            raise HTTPException(status_code=400, detail="tag_code_map is required for state=approved")

    try:
        rag = _conn(u.rag)
        rag.autocommit = True
        cur = rag.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            "SELECT id::text, normalized FROM policy_lexicon_candidates WHERE id::text = ANY(%s)",
            (ids,),
        )
        rows = cur.fetchall()
        id_to_norm: dict[str, str] = {}
        for r in rows:
            i = str(r.get("id", ""))
            n = str(r.get("normalized", "")).strip()
            if i:
                id_to_norm[i] = n

        # Resolve unique normals for approve path (and for catalog)
        normals_found = list(dict.fromkeys(id_to_norm.values()))

        if next_state == "approved":
            try:
                qa = _conn(u.qa)
                qa.autocommit = True
                qcur = qa.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                for nk in normals_found:
                    mapped = tag_code_map.get(nk) or tag_code_map.get(nk.strip()) or tag_code_map.get(nk.lower()) or None
                    if not mapped:
                        continue
                    tk, tc = _parse_kind_code(str(mapped), candidate_type_override or "d")
                    if tk not in ("p", "d", "j") or not tc:
                        continue
                    qcur.execute(
                        "SELECT id, spec FROM policy_lexicon_entries WHERE kind = %s AND code = %s LIMIT 1",
                        (tk, tc),
                    )
                    row = qcur.fetchone()
                    if row and row.get("id"):
                        spec = row.get("spec") if isinstance(row.get("spec"), dict) else {}
                        spec = dict(spec)
                        spec.setdefault("kind", tk)
                        spec = _add_alias_phrase(spec, nk, strength="strong")
                        qcur.execute(
                            "UPDATE policy_lexicon_entries SET spec = %s::jsonb, active = true, updated_at = NOW() WHERE id = %s",
                            (json.dumps(spec), row["id"]),
                        )
                    else:
                        new_parent = tc.rsplit(".", 1)[0] if "." in tc else None
                        new_spec = {"kind": tk, "description": "", "strong_phrases": [nk]}
                        _validate_tag_structure(tk, tc, new_parent, u.qa, spec=new_spec)
                        qcur.execute(
                            "INSERT INTO policy_lexicon_entries(id, kind, code, parent_code, spec, active, created_at, updated_at) VALUES (%s, %s, %s, %s, %s::jsonb, true, NOW(), NOW())",
                            (str(uuid.uuid4()), tk, tc, new_parent, json.dumps(new_spec)),
                        )
                new_rev = _bump_lexicon_revision(qcur)
                qcur.close()
                qa.close()
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to approve into QA lexicon: {type(e).__name__}: {e}")

        ct_by_id = fetch_candidate_types_by_ids(cur, ids)

        updated = []
        errors = []
        # Group ids by normalized for per-phrase catalog upsert
        by_norm: dict[str, list[str]] = {}
        for i, n in id_to_norm.items():
            nk = _normalize_phrase(n)
            by_norm.setdefault(nk, []).append(i)

        proposed_tag = None
        prop_key = ""
        if next_state == "approved" and tag_code_map and normals_found:
            first_norm = normals_found[0]
            mapped = tag_code_map.get(first_norm) or tag_code_map.get(first_norm.strip()) or tag_code_map.get(first_norm.lower()) or None
            if mapped:
                tk, tc = _parse_kind_code(str(mapped), candidate_type_override or "d")
                proposed_tag = tc
                prop_key = f"{tk}:{tc}".lower()[:300]

        rows_updated = update_candidate_state_by_ids(
            cur,
            ids,
            next_state,
            reviewer=reviewer or "lexicon-ui",
            reviewer_notes=notes,
            candidate_type=candidate_type_override,
            proposed_tag=proposed_tag if next_state == "approved" else None,
        )
        if rows_updated == 0:
            for i in ids:
                errors.append({"id": i, "normalized": id_to_norm.get(i, ""), "error": "no_rows_updated"})
        else:
            for nk, sub_ids in by_norm.items():
                updated.append({"ids": sub_ids, "normalized": nk, "state": next_state})
                ct = ct_by_id.get(sub_ids[0]) if sub_ids else "d"
                if ct not in ("p", "d", "j"):
                    ct = "d"
                upsert_catalog(
                    cur,
                    candidate_type=ct,
                    normalized_key=nk[:500],
                    proposed_tag_key=prop_key,
                    proposed_tag=proposed_tag,
                    state=next_state,
                    reviewer=reviewer or "lexicon-ui",
                    reviewer_notes=notes,
                )

        logger.info("[review-bulk] done: updated=%d errors=%d", len(updated), len(errors))
        return {
            "status": "ok",
            "updated": updated,
            "errors": errors,
            "lexicon_revision": (new_rev if next_state == "approved" else None),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[review-bulk] failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Bulk review failed: {type(e).__name__}: {e}")
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if rag is not None:
            try:
                rag.close()
            except Exception:
                pass
        if qcur is not None:
            try:
                qcur.close()
            except Exception:
                pass
        if qa is not None:
            try:
                qa.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# LLM Triage (on-demand, triggered from UI)
# ---------------------------------------------------------------------------

def _build_lexicon_tree_text(qa_conn) -> str:
    """Build a compact text representation of the approved lexicon for the LLM prompt."""
    cur = qa_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT kind, code, parent_code, spec FROM policy_lexicon_entries WHERE active=true ORDER BY kind, code"
    )
    rows = cur.fetchall()
    cur.close()

    by_kind: dict[str, list[str]] = {"j": [], "d": [], "p": []}
    for r in rows:
        k = str(r.get("kind", "")).strip().lower()
        c = str(r.get("code", "")).strip()
        pc = str(r.get("parent_code") or "").strip()
        spec = r.get("spec") if isinstance(r.get("spec"), dict) else {}
        desc = str(spec.get("description", ""))[:80]
        aliases = ", ".join(str(p) for p in (spec.get("strong_phrases") or spec.get("phrases") or [])[:3])
        indent = "  " if pc else ""
        entry = f"{indent}{c}"
        if aliases:
            entry += f"  (aliases: {aliases})"
        if desc:
            entry += f"  -- {desc}"
        if k in by_kind:
            by_kind[k].append(entry)

    lines = []
    for kind, label in (("j", "Jurisdiction"), ("d", "Domain"), ("p", "Procedural")):
        entries = by_kind.get(kind, [])
        if entries:
            lines.append(f"\n[{label} tags ({len(entries)})]")
            lines.extend(entries)
    return "\n".join(lines)


def _build_rejected_text(rag_conn, limit: int = 100) -> str:
    """Build a text list of recently rejected candidates."""
    cur = rag_conn.cursor()
    cur.execute(
        "SELECT DISTINCT normalized FROM policy_lexicon_candidate_catalog WHERE state='rejected' ORDER BY normalized LIMIT %s",
        (limit,),
    )
    rejected = [r[0] for r in cur.fetchall() if r[0]]
    cur.close()
    if not rejected:
        return "(none)"
    return ", ".join(rejected[:limit])


@app.post("/policy/candidates/llm-triage")
def llm_triage_candidates(body: dict = Body(default={})) -> dict[str, Any]:
    """
    On-demand LLM triage of all pending candidates.

    Fetches all proposed candidates from RAG DB, the full approved lexicon
    from QA DB, and the rejected catalog, then calls Vertex Gemini to
    produce a structured **operation** per candidate:

      - reject_candidate: junk/noise/generic, should be rejected
      - add_alias:        already covered by an existing tag, add as alias
      - create_tag:       genuinely new domain concept, create new tag

    Returns both the operations list (for immediate UI display / mass-apply)
    and persists verdict fields on each candidate row (for reload persistence).

    Body (optional):
      force: bool  -- re-triage candidates that already have an llm_verdict
    """
    u = _urls()
    force = bool(body.get("force", False))

    # 1. Fetch pending candidates from RAG DB
    try:
        rag = _conn(u.rag)
        rag.autocommit = True
        rcur = rag.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        where_clause = "state = 'proposed'"
        if not force:
            where_clause += " AND (llm_verdict IS NULL OR llm_verdict = '')"

        rcur.execute(f"""
            SELECT id::text, normalized, candidate_type, occurrences, confidence
            FROM policy_lexicon_candidates
            WHERE {where_clause}
            ORDER BY occurrences DESC NULLS LAST, normalized
            LIMIT 300
        """)
        candidates = [dict(r) for r in rcur.fetchall()]

        # Also fetch rejected catalog for context
        rejected_text = _build_rejected_text(rag, limit=100)
        rcur.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load candidates: {type(e).__name__}: {e}")

    if not candidates:
        try:
            rag.close()
        except Exception:
            pass
        return {"status": "ok", "triaged": 0, "operations": [], "message": "No pending candidates to triage"}

    # 2. Fetch approved lexicon tree from QA DB
    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        lexicon_tree = _build_lexicon_tree_text(qa)
        qa.close()
    except Exception as e:
        try:
            rag.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to load lexicon: {type(e).__name__}: {e}")

    # 3. Build prompt template and call LLM in batches of 50
    _BATCH_SIZE = 50

    def _build_triage_prompt(batch: list[dict]) -> str:
        cand_lines = []
        for c in batch:
            occ = c.get("occurrences") or 0
            conf = c.get("confidence") or 0.0
            ctype = c.get("candidate_type") or "d"
            cand_lines.append(f'- "{c["normalized"]}" (type={ctype}, occurrences={occ}, confidence={conf:.2f})')
        cand_text = "\n".join(cand_lines)

        return f"""You are an expert healthcare policy taxonomy maintainer.

Below is the current APPROVED lexicon tree for tagging healthcare policy documents:

{lexicon_tree}

Previously REJECTED candidates (do not suggest these again):
{rejected_text}

The following {len(batch)} candidate phrases were extracted from recent document processing.
For EACH candidate, produce exactly one structured operation:

1. **reject_candidate** — for junk, noise, too-generic phrases, partial sentences, conjunctions,
   time references, copyright notices, or anything not a real domain concept.
   Format: {{ "op": "reject_candidate", "normalized": "<phrase>", "reason": "<brief>", "confidence": 0.0-1.0 }}

2. **add_alias** — the phrase is already covered by an existing tag. Add it as an alias.
   Match to the MOST SPECIFIC existing tag, not a broad parent.
   Format: {{ "op": "add_alias", "normalized": "<phrase>", "target_kind": "p|d|j", "target_code": "<existing.tag.code>", "reason": "<brief>", "confidence": 0.0-1.0 }}

3. **create_tag** — a genuinely new domain concept worth adding to the taxonomy.
   Propose placement following existing tree structure and naming conventions.
   Format: {{ "op": "create_tag", "normalized": "<phrase>", "kind": "p|d|j", "code": "<new.tag.code>", "parent_code": "<parent>", "description": "<brief description>", "reason": "<brief>", "confidence": 0.0-1.0 }}

Guidelines:
- Be AGGRESSIVE about rejecting junk. Most candidates should be reject_candidate.
- If a candidate is a near-duplicate of an existing tag, use add_alias not create_tag.
- For add_alias, the target_code MUST be an existing tag from the lexicon tree above.
- For create_tag, propose a code and parent that follow the tree conventions.
- Keep reason fields SHORT (under 15 words) to save space.

Candidates:
{cand_text}

CRITICAL: Respond with ONLY a JSON array of operation objects. Do NOT wrap in code fences.
Output raw JSON only. Every candidate MUST have exactly one operation.
"""

    def _parse_llm_json(raw_text: str) -> list[dict]:
        """Parse JSON from LLM response, with recovery for truncated output."""
        text = raw_text.strip()

        # Strip code fences if LLM wrapped them
        if text.startswith("```"):
            lines_raw = text.split("\n")
            text = "\n".join(line for line in lines_raw if not line.strip().startswith("```"))

        # Try direct parse first
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # Truncated JSON recovery: find the last complete object in the array
        # Look for the last "}," or "}" followed by possible whitespace before truncation
        last_complete = text.rfind("},")
        if last_complete > 0:
            recovered = text[:last_complete + 1] + "]"
            try:
                result = json.loads(recovered)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        # Try closing with just }]
        last_brace = text.rfind("}")
        if last_brace > 0:
            recovered = text[:last_brace + 1] + "]"
            try:
                result = json.loads(recovered)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse LLM JSON (len={len(text)}). First 200 chars: {text[:200]}")

    # 4. Call Vertex Gemini in batches
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        project = os.environ.get("VERTEX_PROJECT") or os.environ.get("VERTEX_PROJECT_ID") or ""
        region = os.environ.get("VERTEX_REGION") or os.environ.get("VERTEX_LOCATION") or "us-central1"
        model_name = os.environ.get("VERTEX_LLM_MODEL") or "gemini-2.0-flash"

        if not project:
            endpoint_id = os.environ.get("VERTEX_INDEX_ENDPOINT_ID") or ""
            import re as _re
            m = _re.search(r"projects/([^/]+)/", endpoint_id)
            if m:
                project = m.group(1)

        if not project:
            try:
                rag.close()
            except Exception:
                pass
            raise HTTPException(status_code=400, detail="VERTEX_PROJECT not configured. Set VERTEX_PROJECT or VERTEX_PROJECT_ID env var.")

        vertexai.init(project=project, location=region)
        llm_model = GenerativeModel(model_name)

        # Process in batches
        triage_results: list[dict] = []
        batches = [candidates[i:i + _BATCH_SIZE] for i in range(0, len(candidates), _BATCH_SIZE)]

        for batch_idx, batch in enumerate(batches):
            prompt = _build_triage_prompt(batch)
            response = llm_model.generate_content(prompt)
            raw_text = response.text.strip()
            batch_results = _parse_llm_json(raw_text)
            triage_results.extend(batch_results)

    except HTTPException:
        raise
    except Exception as e:
        try:
            rag.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"LLM call failed: {type(e).__name__}: {e}")

    # 5. Build lookup, update candidates in RAG DB, collect operations
    ops_by_phrase: dict[str, dict] = {}
    for item in triage_results:
        if not isinstance(item, dict):
            continue
        phrase = (str(item.get("normalized", "")) or "").strip().lower()
        if phrase:
            ops_by_phrase[phrase] = item

    operations: list[dict] = []
    try:
        rcur = rag.cursor()
        updated = 0
        skipped = 0
        for c in candidates:
            norm = (c.get("normalized") or "").strip().lower()
            op = ops_by_phrase.get(norm)
            if not op:
                skipped += 1
                continue

            op_type = str(op.get("op", "")).strip().lower()
            # Map op type to legacy verdict for backward compat
            verdict_map = {"reject_candidate": "reject", "add_alias": "alias", "create_tag": "new_tag"}
            verdict = verdict_map.get(op_type, "")
            if not verdict:
                skipped += 1
                continue

            confidence = 0.0
            try:
                confidence = float(op.get("confidence", 0.0))
            except (ValueError, TypeError):
                pass
            reason = str(op.get("reason", ""))[:500]

            # Determine suggested fields from op
            if op_type == "add_alias":
                suggested_kind = str(op.get("target_kind", ""))[:10]
                suggested_code = str(op.get("target_code", ""))[:500]
                suggested_parent = ""
            elif op_type == "create_tag":
                suggested_kind = str(op.get("kind", ""))[:10]
                suggested_code = str(op.get("code", ""))[:500]
                suggested_parent = str(op.get("parent_code", ""))[:500]
            else:
                suggested_kind = ""
                suggested_code = ""
                suggested_parent = ""

            # Update legacy fields on candidate row
            rcur.execute(
                """
                UPDATE policy_lexicon_candidates
                SET llm_verdict = %s,
                    llm_confidence = %s,
                    llm_reason = %s,
                    llm_suggested_kind = %s,
                    llm_suggested_code = %s,
                    llm_suggested_parent = %s
                WHERE id = %s::uuid
                """,
                (verdict, confidence, reason, suggested_kind, suggested_code, suggested_parent, c["id"]),
            )
            updated += 1

            # Build the operation for frontend display — ensure normalized is present
            clean_op = {**op, "normalized": norm}
            if "confidence" not in clean_op:
                clean_op["confidence"] = confidence
            operations.append(clean_op)

        rcur.close()
        rag.close()

        return {
            "status": "ok",
            "triaged": updated,
            "skipped": skipped,
            "total_candidates": len(candidates),
            "operations": operations,
            "llm_model": model_name,
        }

    except Exception as e:
        try:
            rag.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to update triage results: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Apply candidate operations (batch)
# ---------------------------------------------------------------------------

@app.post("/policy/candidates/apply-operations")
def apply_candidate_operations(body: dict = Body(...)) -> dict[str, Any]:
    """
    Execute a batch of candidate operations produced by LLM triage.

    Body: { operations: [ { op, normalized, ... }, ... ] }

    Supported ops:
      - reject_candidate: reject the candidate phrase
      - add_alias: add the phrase as an alias to an existing tag, then mark candidate absorbed
      - create_tag: create a new lexicon tag with phrase as strong_phrase, then approve candidate
    """
    operations = body.get("operations")
    if not isinstance(operations, list) or not operations:
        raise HTTPException(status_code=400, detail="'operations' array is required and must not be empty")

    u = _urls()
    results: list[dict[str, Any]] = []
    qa = rag = None
    qa_cur = rag_cur = None

    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        qa_cur = qa.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        rag = _conn(u.rag)
        rag.autocommit = True
        rag_cur = rag.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        logger.info("[apply-operations] ops=%d", len(operations))

        for idx, op in enumerate(operations):
            if not isinstance(op, dict):
                results.append({"index": idx, "op": "unknown", "status": "error", "detail": "Invalid operation object"})
                continue

            op_type = str(op.get("op", "")).strip()
            normalized = str(op.get("normalized", "")).strip()

            if not normalized:
                results.append({"index": idx, "op": op_type, "status": "error", "detail": "Missing 'normalized' field"})
                continue

            # Prefer ids from client (loaded from overview); else resolve by normalized
            ids_raw = op.get("ids") if isinstance(op.get("ids"), list) else []
            ids = [str(x).strip() for x in ids_raw if str(x).strip()]
            if not ids:
                ids = resolve_normalized_to_ids(rag_cur, normalized, state_filter="proposed")
            if not ids:
                results.append({"index": idx, "op": op_type, "normalized": normalized, "status": "error", "detail": "no_matching_proposed_rows"})
                continue

            ct_by_id = fetch_candidate_types_by_ids(rag_cur, ids)

            try:
                if op_type == "reject_candidate":
                    rows_updated, err = reject_candidate_by_ids(
                        rag_cur,
                        ids,
                        normalized,
                        reviewer="llm-ops",
                        reviewer_notes=str(op.get("reason", "LLM-recommended reject"))[:500],
                        ct_by_id=ct_by_id,
                    )
                    if rows_updated == 0:
                        logger.warning("[apply-operations] reject_candidate normalized=%r rows=0", normalized)
                        results.append({"index": idx, "op": "reject_candidate", "normalized": normalized, "status": "error", "detail": err or "no_rows_updated"})
                    else:
                        logger.info("[apply-operations] reject_candidate normalized=%r rows=%d ok", normalized, rows_updated)
                        results.append({"index": idx, "op": "reject_candidate", "normalized": normalized, "status": "ok"})

                elif op_type == "add_alias":
                    target_kind = str(op.get("target_kind", "d")).strip().lower()
                    target_code = str(op.get("target_code", "")).strip()
                    if target_kind not in ("p", "d", "j") or not target_code:
                        raise ValueError("target_kind (p/d/j) and target_code are required")

                    # Load existing spec from QA DB; try exact match first, then code ending (e.g. coding.hcpcs for "hcpcs")
                    qa_cur.execute(
                        "SELECT code, spec FROM policy_lexicon_entries WHERE kind = %s AND code = %s LIMIT 1",
                        (target_kind, target_code),
                    )
                    tag_row = qa_cur.fetchone()
                    if not tag_row:
                        qa_cur.execute(
                            "SELECT code, spec FROM policy_lexicon_entries WHERE kind = %s AND (code = %s OR code LIKE %s) AND active = true LIMIT 1",
                            (target_kind, target_code, f"%.{target_code}"),
                        )
                        tag_row = qa_cur.fetchone()
                    if not tag_row:
                        raise ValueError(f"Target tag {target_kind}.{target_code} not found")

                    resolved_code = str(tag_row.get("code", target_code))
                    existing_spec = tag_row.get("spec") if isinstance(tag_row.get("spec"), dict) else {}
                    phrases = list(existing_spec.get("strong_phrases") or existing_spec.get("phrases") or existing_spec.get("aliases") or [])
                    if normalized.lower() not in [str(p).lower() for p in phrases]:
                        phrases.append(normalized)
                    existing_spec["strong_phrases"] = phrases

                    qa_cur.execute(
                        "UPDATE policy_lexicon_entries SET spec = %s::jsonb, updated_at = NOW() "
                        "WHERE kind = %s AND code = %s",
                        (json.dumps(existing_spec), target_kind, resolved_code),
                    )
                    qa_rowcount = qa_cur.rowcount
                    if qa_rowcount == 0:
                        logger.warning("[apply-operations] add_alias QA UPDATE matched 0 rows for %s.%s", target_kind, resolved_code)

                    # Mark candidate as rejected (absorbed) in RAG DB by ID
                    note = f"Added as alias to {target_kind}.{resolved_code}"
                    rows_updated = update_candidate_state_by_ids(
                        rag_cur, ids, "rejected",
                        reviewer="llm-ops", reviewer_notes=note,
                    )
                    if rows_updated == 0:
                        logger.warning("[apply-operations] add_alias normalized=%r rows=0", normalized)
                        results.append({"index": idx, "op": "add_alias", "normalized": normalized, "status": "error", "detail": "no_rows_updated"})
                    else:
                        nk = _normalize_phrase(normalized)
                        prop_key = f"{target_kind}:{resolved_code}".lower()[:300]
                        ct = ct_by_id.get(ids[0]) if ids else target_kind
                        if ct not in ("p", "d", "j"):
                            ct = target_kind
                        upsert_catalog(rag_cur, ct, nk, prop_key, f"{target_kind}.{resolved_code}", "rejected", "llm-ops", note)
                        results.append({"index": idx, "op": "add_alias", "normalized": normalized, "target": f"{target_kind}.{resolved_code}", "status": "ok"})

                elif op_type == "create_tag":
                    kind = str(op.get("kind", "d")).strip().lower()
                    code = str(op.get("code", "")).strip()
                    parent_code = str(op.get("parent_code", "")).strip() or None
                    description = str(op.get("description", ""))[:500]

                    if kind not in ("p", "d", "j") or not code:
                        raise ValueError("kind (p/d/j) and code are required")

                    spec_val: dict[str, Any] = {"strong_phrases": [normalized]}
                    if description:
                        spec_val["description"] = description

                    # Check if tag already exists — just add as alias if so
                    qa_cur.execute(
                        "SELECT spec FROM policy_lexicon_entries WHERE kind = %s AND code = %s LIMIT 1",
                        (kind, code),
                    )
                    existing = qa_cur.fetchone()
                    if existing:
                        ex_spec = existing.get("spec") if isinstance(existing.get("spec"), dict) else {}
                        phrases = list(ex_spec.get("strong_phrases") or [])
                        if normalized.lower() not in [p.lower() for p in phrases]:
                            phrases.append(normalized)
                        ex_spec["strong_phrases"] = phrases
                        if description and not ex_spec.get("description"):
                            ex_spec["description"] = description
                        qa_cur.execute(
                            "UPDATE policy_lexicon_entries SET spec = %s::jsonb, updated_at = NOW() "
                            "WHERE kind = %s AND code = %s",
                            (json.dumps(ex_spec), kind, code),
                        )
                        note = "added phrase to existing tag"
                    else:
                        qa_cur.execute(
                            "INSERT INTO policy_lexicon_entries(id, kind, code, parent_code, spec, active, created_at, updated_at) "
                            "VALUES (%s, %s, %s, %s, %s::jsonb, true, NOW(), NOW())",
                            (str(uuid.uuid4()), kind, code, parent_code, json.dumps(spec_val)),
                        )
                        note = "created new tag"

                    # Mark candidate as approved in RAG DB by ID
                    note_rag = f"Created as {kind}.{code}"
                    rows_updated = update_candidate_state_by_ids(
                        rag_cur, ids, "approved",
                        reviewer="llm-ops", reviewer_notes=note_rag,
                    )
                    if rows_updated == 0:
                        logger.warning("[apply-operations] create_tag normalized=%r rows=0", normalized)
                        results.append({"index": idx, "op": "create_tag", "normalized": normalized, "status": "error", "detail": "no_rows_updated"})
                    else:
                        nk = _normalize_phrase(normalized)
                        prop_key = f"{kind}.{code}".lower()[:300]
                        ct = ct_by_id.get(ids[0]) if ids else kind
                        if ct not in ("p", "d", "j"):
                            ct = kind
                        upsert_catalog(rag_cur, ct, nk, prop_key, f"{kind}.{code}", "approved", "llm-ops", note_rag)
                        results.append({"index": idx, "op": "create_tag", "normalized": normalized, "tag": f"{kind}.{code}", "status": "ok", "note": note})

                else:
                    results.append({"index": idx, "op": op_type, "normalized": normalized, "status": "error", "detail": f"Unknown op: {op_type}"})

            except Exception as ex:
                results.append({"index": idx, "op": op_type, "normalized": normalized, "status": "error", "detail": str(ex)[:500]})
                # Rollback both connections so next op gets a clean state (avoids "transaction is aborted")
                try:
                    rag.rollback()
                except Exception:
                    pass
                try:
                    qa.rollback()
                except Exception:
                    pass

        # Bump lexicon revision if any create/alias ops succeeded
        lexicon_ops = [r for r in results if r.get("op") in ("add_alias", "create_tag") and r.get("status") == "ok"]
        new_rev = 0
        if lexicon_ops:
            qa_cur.execute("UPDATE policy_lexicon_meta SET revision = revision + 1, updated_at = NOW() RETURNING revision")
            rev_row = qa_cur.fetchone()
            new_rev = int(rev_row["revision"]) if rev_row else 0

        failed_count = sum(1 for r in results if r.get("status") == "error")
        return {
            "status": "ok" if failed_count == 0 else "partial",
            "results": results,
            "failed_count": failed_count,
            "applied_count": len(results) - failed_count,
            "lexicon_revision": new_rev,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply operations: {type(e).__name__}: {e}")
    finally:
        if qa_cur is not None:
            try:
                qa_cur.close()
            except Exception:
                pass
        if qa is not None:
            try:
                qa.close()
            except Exception:
                pass
        if rag_cur is not None:
            try:
                rag_cur.close()
            except Exception:
                pass
        if rag is not None:
            try:
                rag.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Revise a single candidate operation via LLM
# ---------------------------------------------------------------------------

@app.post("/policy/candidates/revise")
def revise_candidate_operation(body: dict = Body(...)) -> dict[str, Any]:
    """
    Ask the LLM to revise a suggested operation for a single candidate,
    incorporating user instructions.

    Body: {
      normalized: str,
      current_operation: { op, ... },
      user_instructions: str,
    }
    """
    normalized = str(body.get("normalized", "")).strip()
    current_op = body.get("current_operation") or {}
    user_instructions = str(body.get("user_instructions", "")).strip()

    if not normalized:
        raise HTTPException(status_code=400, detail="'normalized' is required")
    if not user_instructions:
        raise HTTPException(status_code=400, detail="'user_instructions' is required")

    u = _urls()

    # Fetch lexicon context
    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        lexicon_tree = _build_lexicon_tree_text(qa)
        qa.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load lexicon: {type(e).__name__}: {e}")

    prompt = f"""You are an expert healthcare policy taxonomy maintainer.

Below is the current APPROVED lexicon tree:

{lexicon_tree}

A candidate phrase was extracted from document processing:
  Phrase: "{normalized}"

The LLM previously suggested this operation:
{json.dumps(current_op, indent=2)}

The user has provided additional instructions:
"{user_instructions}"

Based on the user's feedback, produce a REVISED operation for this candidate.
Use one of these operation types:

1. reject_candidate: {{ "op": "reject_candidate", "normalized": "{normalized}", "reason": "<reason>", "confidence": 0.0-1.0 }}
2. add_alias: {{ "op": "add_alias", "normalized": "{normalized}", "target_kind": "p|d|j", "target_code": "<existing.tag>", "reason": "<reason>", "confidence": 0.0-1.0 }}
3. create_tag: {{ "op": "create_tag", "normalized": "{normalized}", "kind": "p|d|j", "code": "<new.tag.code>", "parent_code": "<parent>", "description": "<desc>", "reason": "<reason>", "confidence": 0.0-1.0 }}

CRITICAL: Respond with ONLY a single JSON object. No code fences, no explanation, just the operation object.
"""

    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        project = os.environ.get("VERTEX_PROJECT") or os.environ.get("VERTEX_PROJECT_ID") or ""
        region = os.environ.get("VERTEX_REGION") or os.environ.get("VERTEX_LOCATION") or "us-central1"
        model_name = os.environ.get("VERTEX_LLM_MODEL") or "gemini-2.0-flash"

        if not project:
            endpoint_id = os.environ.get("VERTEX_INDEX_ENDPOINT_ID") or ""
            import re as _re
            m = _re.search(r"projects/([^/]+)/", endpoint_id)
            if m:
                project = m.group(1)

        if not project:
            raise HTTPException(status_code=400, detail="VERTEX_PROJECT not configured.")

        vertexai.init(project=project, location=region)
        model_inst = GenerativeModel(model_name)
        response = model_inst.generate_content(prompt)
        raw_text = response.text.strip()

        # Strip code fences
        if raw_text.startswith("```"):
            lines_raw = raw_text.split("\n")
            raw_text = "\n".join(line for line in lines_raw if not line.strip().startswith("```"))

        revised_op = json.loads(raw_text)
        if not isinstance(revised_op, dict):
            raise HTTPException(status_code=500, detail=f"LLM returned unexpected format: {raw_text[:300]}")

        # Ensure normalized is set
        revised_op["normalized"] = normalized

        return {
            "status": "ok",
            "operation": revised_op,
            "llm_model": model_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Revise LLM call failed: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Purge stale candidates (on-demand, triggered from UI)
# ---------------------------------------------------------------------------

@app.post("/policy/candidates/purge-stale")
def purge_stale_candidates(body: dict = Body(default={})) -> dict[str, Any]:
    """
    Remove proposed candidates that duplicate already-decided entries.

    Purges candidates where:
      1. state='proposed' AND normalized matches an approved/rejected entry
         in policy_lexicon_candidate_catalog (RAG DB).
      2. state='proposed' AND normalized matches an existing approved tag phrase
         in policy_lexicon_entries (QA DB).

    Body (optional):
      dry_run: bool  -- if true, only count without deleting
    """
    u = _urls()
    dry_run = bool(body.get("dry_run", False))

    # 1. Collect known-decided phrases from candidate catalog (RAG DB)
    decided_norms: set[str] = set()
    try:
        rag = _conn(u.rag)
        rag.autocommit = True
        rcur = rag.cursor()

        # Phrases decided in catalog (approved or rejected)
        rcur.execute(
            """
            SELECT DISTINCT trim(lower(normalized_key))
            FROM policy_lexicon_candidate_catalog
            WHERE state IN ('approved', 'rejected')
              AND normalized_key IS NOT NULL
              AND normalized_key <> ''
            """
        )
        for (nk,) in rcur.fetchall():
            if nk:
                decided_norms.add(nk.strip().lower())

        # Also collect phrases already approved in candidates table itself
        rcur.execute(
            """
            SELECT DISTINCT trim(lower(normalized))
            FROM policy_lexicon_candidates
            WHERE state IN ('approved', 'rejected')
              AND normalized IS NOT NULL
              AND normalized <> ''
            """
        )
        for (nk,) in rcur.fetchall():
            if nk:
                decided_norms.add(nk.strip().lower())

        rcur.close()
    except Exception as e:
        try:
            rag.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to load decided candidates: {type(e).__name__}: {e}")

    # 2. Collect approved tag phrases from QA lexicon
    tag_norms: set[str] = set()
    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        qcur = qa.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        qcur.execute(
            "SELECT code, spec FROM policy_lexicon_entries WHERE active = true"
        )
        for row in qcur.fetchall():
            code = str(row.get("code") or "").strip()
            if code:
                # The tag code itself (e.g. "member_services" -> "member services")
                tag_norms.add(code.replace("_", " ").strip().lower())
            spec = row.get("spec") if isinstance(row.get("spec"), dict) else {}
            for key in ("strong_phrases", "phrases"):
                for p in (spec.get(key) or []):
                    if isinstance(p, str) and p.strip():
                        tag_norms.add(p.strip().lower())
        qcur.close()
        qa.close()
    except Exception as e:
        try:
            qa.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to load QA lexicon: {type(e).__name__}: {e}")

    all_known = decided_norms | tag_norms
    if not all_known:
        try:
            rag.close()
        except Exception:
            pass
        return {"status": "ok", "purged": 0, "dry_run": dry_run, "message": "No decided/approved phrases found"}

    # 3. Find and purge stale proposed candidates
    try:
        rcur = rag.cursor()

        # Count first
        rcur.execute(
            """
            SELECT count(*) FROM policy_lexicon_candidates
            WHERE state = 'proposed'
              AND trim(lower(normalized)) = ANY(%s)
            """,
            (list(all_known),),
        )
        stale_count = rcur.fetchone()[0] or 0

        if stale_count > 0 and not dry_run:
            # Delete stale rows (they can be regenerated by re-running extraction)
            rcur.execute(
                """
                DELETE FROM policy_lexicon_candidates
                WHERE state = 'proposed'
                  AND trim(lower(normalized)) = ANY(%s)
                """,
                (list(all_known),),
            )
            purged = rcur.rowcount or 0
        else:
            purged = 0

        rcur.close()
        rag.close()

        return {
            "status": "ok",
            "purged": purged,
            "stale_found": stale_count,
            "dry_run": dry_run,
            "decided_phrases": len(decided_norms),
            "tag_phrases": len(tag_norms),
            "total_known": len(all_known),
        }

    except Exception as e:
        try:
            rag.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Purge failed: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Dismissed Issues — CRUD endpoints
# ---------------------------------------------------------------------------

@app.post("/policy/lexicon/health/dismiss")
def dismiss_health_issue(body: dict = Body(...)) -> dict[str, Any]:
    """
    Dismiss/overrule a health issue so LLM skips it in future analyses.
    Body: { issue_type, tags: [], message, reason? }
    """
    u = _urls()
    issue_type = str(body.get("issue_type") or body.get("type") or "").strip()
    tags = body.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    tags = [str(t).strip() for t in tags if str(t).strip()]
    message = str(body.get("message") or "").strip()
    reason = str(body.get("reason") or "").strip() or "User overruled"
    dismissed_by = str(body.get("dismissed_by") or "user").strip()

    if not issue_type:
        raise HTTPException(status_code=400, detail="issue_type is required")

    fingerprint = _dismissed_fingerprint(issue_type, tags)
    _ensure_dismissed_table(u.qa)

    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        cur = qa.cursor()
        cur.execute(
            """
            INSERT INTO policy_lexicon_dismissed_issues
                (id, issue_type, issue_tags, issue_message, issue_fingerprint, reason, dismissed_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (issue_fingerprint) DO UPDATE SET
                reason = EXCLUDED.reason,
                dismissed_by = EXCLUDED.dismissed_by,
                issue_message = EXCLUDED.issue_message,
                created_at = NOW()
            """,
            (str(uuid.uuid4()), issue_type, tags, message, fingerprint, reason, dismissed_by),
        )
        cur.close()
        qa.close()
        return {"status": "ok", "fingerprint": fingerprint}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to dismiss: {type(e).__name__}: {e}")


@app.get("/policy/lexicon/health/dismissed")
def list_dismissed_issues() -> dict[str, Any]:
    """List all dismissed/overruled health issues."""
    u = _urls()
    rows = _load_dismissed(u.qa)
    # Convert timestamps to string for JSON
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = str(r["created_at"])
    return {"status": "ok", "dismissed": rows, "count": len(rows)}


@app.delete("/policy/lexicon/health/dismiss/{fingerprint}")
def undismiss_health_issue(fingerprint: str) -> dict[str, Any]:
    """Re-enable a previously dismissed issue."""
    u = _urls()
    _ensure_dismissed_table(u.qa)
    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        cur = qa.cursor()
        cur.execute(
            "DELETE FROM policy_lexicon_dismissed_issues WHERE issue_fingerprint = %s",
            (fingerprint,),
        )
        deleted = cur.rowcount
        cur.close()
        qa.close()
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Dismissed issue not found")
        return {"status": "ok", "fingerprint": fingerprint}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to un-dismiss: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# LLM Health Analysis (on-demand, triggered from Health tab)
# ---------------------------------------------------------------------------

@app.post("/policy/lexicon/health/analyze")
def llm_health_analyze(body: dict = Body(default={})) -> dict[str, Any]:
    """
    Run an LLM-powered health analysis of the entire lexicon tree.

    Checks for: orphans, duplicates, naming inconsistencies, missing parents,
    coverage gaps, tag depth issues, alias conflicts, and structural suggestions.

    Returns a scored health report with specific recommendations.
    """
    import yaml

    u = _urls()

    # 1. Load entire lexicon from QA
    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        qcur = qa.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        qcur.execute(
            "SELECT kind::text, code::text, parent_code::text, spec, active::bool FROM policy_lexicon_entries ORDER BY kind, code"
        )
        entries = [dict(r) for r in qcur.fetchall()]
        qcur.close()
        qa.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load lexicon: {type(e).__name__}: {e}")

    if not entries:
        return {"status": "ok", "score": 0, "issues": [], "suggestions": [], "summary": "Lexicon is empty."}

    # 2. Build compact tree representation for the LLM
    tree_lines = []
    by_kind: dict[str, list[dict]] = {"p": [], "d": [], "j": []}
    for e in entries:
        k = str(e.get("kind") or "").strip().lower()
        if k in by_kind:
            by_kind[k].append(e)

    for kind, label in (("j", "Jurisdiction"), ("d", "Domain"), ("p", "Procedural")):
        items = by_kind.get(kind, [])
        if not items:
            continue
        tree_lines.append(f"\n## {label} Tags ({len(items)})")
        for e in items:
            code = e.get("code", "")
            parent = e.get("parent_code") or ""
            spec = e.get("spec") if isinstance(e.get("spec"), dict) else {}
            desc = str(spec.get("description", ""))[:60]
            is_domain = "." not in code
            strong = ", ".join(str(p) for p in (spec.get("strong_phrases") or spec.get("phrases") or [])[:4])
            alias_list = ", ".join(str(p) for p in (spec.get("aliases") or [])[:3])
            refuted = ", ".join(str(p) for p in (spec.get("refuted_words") or [])[:3])
            active = e.get("active", True)
            indent = "  " if parent else ""
            marker = "[DOMAIN]" if is_domain else "[TAG]"
            line = f"{indent}{marker} {code}"
            if parent:
                line += f"  [parent: {parent}]"
            if strong:
                line += f"  phrases: [{strong}]"
            if alias_list:
                line += f"  aliases: [{alias_list}]"
            if refuted:
                line += f"  refuted: [{refuted}]"
            if desc:
                line += f"  -- {desc}"
            if not active:
                line += "  (INACTIVE)"
            tree_lines.append(line)

    tree_text = "\n".join(tree_lines)

    # 2b. Load dismissed issues to exclude from analysis
    dismissed_rows = _load_dismissed(u.qa)
    dismissed_fingerprints = set()
    dismissed_block = ""
    if dismissed_rows:
        dismissed_lines = []
        for dr in dismissed_rows:
            fp = dr.get("issue_fingerprint", "")
            dismissed_fingerprints.add(fp)
            d_type = dr.get("issue_type", "")
            d_tags = ", ".join(dr.get("issue_tags") or [])
            d_reason = dr.get("reason", "")
            dismissed_lines.append(f"  - type: {d_type}, tags: [{d_tags}], reason: {d_reason}")
        dismissed_block = "\n\nPREVIOUSLY DISMISSED ISSUES (DO NOT report these again -- the user has reviewed and overruled them):\n" + "\n".join(dismissed_lines)

    # 3. Build prompt
    prompt = f"""You are an expert taxonomy analyst reviewing a healthcare policy lexicon tree.

TAXONOMY TERMINOLOGY:
- Type (kind): j, d, or p
- Domain (code without dot, e.g. "claims"): organizational container ONLY -- must NOT have aliases or matching phrases
- Tag (code with dot, e.g. "claims.denial"): the actual matchable unit with strong_phrases, aliases, refuted_words

DESIGN RULES (do NOT flag violations of these as issues -- they are intentional):
1. Three distinct tag KINDS that serve different purposes:
   - J (Jurisdiction): WHO/WHERE -- geographic entities, payers, agencies, programs
   - D (Domain): WHAT ABOUT -- subject matter topics (claims, eligibility, pharmacy)
   - P (Procedural): ACTION VERBS -- what the user/provider does (submit, appeal, verify)
2. It is CORRECT and INTENTIONAL for the same concept to appear in both D and P with different aliases.
   For example: D.claims.submission (the topic) and P.submission.submit (the action) are NOT duplicates.
   D-tags have topic-oriented phrases, P-tags have action-oriented phrases. Do NOT flag these as conflicts.
3. Tags with similar code names across different kinds (like D.contact_information.email and P.communication.email)
   are NOT alias conflicts IF their strong_phrases are different. Only flag ACTUAL alias duplicates (same exact phrase).
4. Code format is lowercase_snake_case with max 2 dot-segments (domain.tag). This is enforced.
5. Domain containers (no dot in code) are containers ONLY. They must NOT have aliases or matching phrases.
   Each domain should have a .general leaf tag as its catch-all (e.g. claims.general).
   Do NOT flag domains without aliases -- that is correct behavior.
6. Tags with 0 hits may simply need a RAG extraction run -- do NOT flag 0-hit tags as issues.
7. If a domain container still has aliases/strong_phrases, flag it as CRITICAL -- those should be on a .general leaf.
8. Tag metadata includes: strong_phrases (exact match), aliases (alternative names), refuted_words (negative signals), weak_keywords (fuzzy match).

CURRENT LEXICON TREE:
{tree_text}

ANALYZE this lexicon for ACTIONABLE quality issues only. Focus on:
- duplicate: truly redundant tags that should be merged (same kind, overlapping purpose)
- alias_conflict: SAME EXACT phrase string mapped to multiple tags WITHIN the same kind
- coverage: significant gaps for a Medicaid managed care policy lexicon (Florida-focused)
- structural: improvements to the hierarchy that would meaningfully improve tagging accuracy

Do NOT report:
- Cross-kind overlaps (D and P having similar concepts is intentional)
- Tags with 0 hits (extraction hasn't run yet)
- Domain containers without aliases (that is CORRECT -- domains are containers only)
- Naming style issues (snake_case is the standard, all tags follow it)
- Common words like "provider" being on a .general leaf tag (that is intentional for catch-all matching)
{dismissed_block}

Only report issues with severity "critical" or "warning". Skip trivial "info" level items.
Limit to the TOP 10-15 most impactful issues maximum.

CRITICAL REQUIREMENT: Every single issue -- both "critical" AND "warning" severity -- MUST include
a non-empty "operations" array with concrete, executable DB operations.
Do NOT leave operations empty or omit them for warnings. Do NOT provide only text suggestions.
Every issue, regardless of severity, must have at least one operation. NO EXCEPTIONS.

Available operation types:
1. create_tag: {{ "op": "create_tag", "kind": "<p|d|j>", "code": "<tag_code>", "parent_code": "<domain_code or null>",
     "spec": {{ "description": "...", "strong_phrases": [...], "aliases": [...], "refuted_words": [...] }} }}
2. update_tag: {{ "op": "update_tag", "kind": "<p|d|j>", "code": "<existing_code>",
     "spec": {{ ... }} }}   (provide COMPLETE new value for each field you change; omitted fields are preserved)
3. delete_tag: {{ "op": "delete_tag", "kind": "<p|d|j>", "code": "<tag_code>" }}
4. merge_tags: {{ "op": "merge_tags", "kind": "<p|d|j>", "source_code": "<src>", "target_code": "<tgt>" }}
5. move_tag: {{ "op": "move_tag", "kind": "<p|d|j>", "from_code": "<old>", "to_code": "<new>", "parent_code": "<parent or null>" }}

Also provide:
- overall_score: 0-100 (100 = perfect taxonomy, score based on structure and coverage quality)
- summary: 2-3 sentence assessment of the taxonomy health
- top_suggestions: 3-5 highest-impact improvements

Respond with ONLY valid JSON (no markdown, no code fences). Schema:
{{
  "overall_score": <number>,
  "summary": "<text>",
  "top_suggestions": ["<suggestion>", ...],
  "issues": [
    {{
      "type": "<type>",
      "severity": "<critical|warning>",
      "tags": ["<code>"],
      "message": "<description>",
      "fix": "<text explanation of the fix>",
      "operations": [
        {{ "op": "create_tag|update_tag|delete_tag|merge_tags|move_tag", "kind": "p|d|j", "code": "...", ... }}
      ]
    }}
  ]
}}

REMEMBER: The "operations" array is REQUIRED and must be non-empty for EVERY issue,
including warnings. If you report an issue, you MUST provide the operations to fix it.
An issue without operations is useless -- do not include it.
"""

    # 4. Call Vertex Gemini
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        project = os.environ.get("VERTEX_PROJECT") or os.environ.get("VERTEX_PROJECT_ID") or ""
        region = os.environ.get("VERTEX_REGION") or os.environ.get("VERTEX_LOCATION") or "us-central1"
        # Allow caller to pick model; fall back to env then default (pro for deeper analysis)
        model_name = body.get("model") or os.environ.get("VERTEX_HEALTH_LLM_MODEL") or os.environ.get("VERTEX_LLM_MODEL") or "gemini-2.5-pro"

        if not project:
            endpoint_id = os.environ.get("VERTEX_INDEX_ENDPOINT_ID") or ""
            m = re.search(r"projects/([^/]+)/", endpoint_id)
            if m:
                project = m.group(1)

        if not project:
            raise HTTPException(status_code=400, detail="VERTEX_PROJECT not configured")

        vertexai.init(project=project, location=region)
        model = GenerativeModel(model_name)
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # Strip code fences if present
        if raw_text.startswith("```"):
            lines_raw = raw_text.split("\n")
            raw_text = "\n".join(line for line in lines_raw if not line.strip().startswith("```"))
            raw_text = raw_text.strip()

        # Try JSON first (preferred), fall back to YAML
        result = None
        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            # Try extracting JSON from surrounding text
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                try:
                    result = json.loads(raw_text[json_start:json_end])
                except json.JSONDecodeError:
                    pass
        if result is None:
            # Last resort: try YAML
            try:
                result = yaml.safe_load(raw_text)
            except Exception:
                raise HTTPException(
                    status_code=500,
                    detail=f"Could not parse LLM response as JSON or YAML. First 500 chars: {raw_text[:500]}"
                )

        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="LLM returned unexpected format (not a dict)")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM health analysis failed: {type(e).__name__}: {e}")

    # Validate operations in each issue + filter out dismissed
    valid_op_types = ("create_tag", "update_tag", "delete_tag", "merge_tags", "move_tag")
    issues_out = []
    for iss in (result.get("issues") or []):
        if not isinstance(iss, dict):
            continue
        iss_type = str(iss.get("type", "")).strip()
        iss_tags = iss.get("tags") or []
        # Skip if this issue was dismissed by the user
        fp = _dismissed_fingerprint(iss_type, iss_tags)
        if fp in dismissed_fingerprints:
            continue
        ops = []
        for op in (iss.get("operations") or []):
            if isinstance(op, dict) and str(op.get("op", "")).strip() in valid_op_types:
                ops.append(op)
        iss_out = {
            "type": iss_type,
            "severity": str(iss.get("severity", "warning")),
            "tags": iss_tags,
            "message": str(iss.get("message", "")),
            "fix": str(iss.get("fix", "")),
            "operations": ops,
        }
        issues_out.append(iss_out)

    return {
        "status": "ok",
        "score": int(result.get("overall_score", 0)),
        "summary": str(result.get("summary", "")),
        "top_suggestions": result.get("top_suggestions") or [],
        "issues": issues_out,
        "llm_model": model_name,
        "tag_count": len(entries),
        "dismissed_count": len(dismissed_rows),
    }


# ---------------------------------------------------------------------------
# Health Fix — LLM-powered auto-fix (preview + apply)
# ---------------------------------------------------------------------------

@app.post("/policy/lexicon/health/fix/preview")
def health_fix_preview(body: dict = Body(...)) -> dict[str, Any]:
    """
    Given a health issue + optional user instructions, ask the LLM to produce
    a concrete list of structured operations to fix the issue.

    Body: {
      issue: { type, severity, tags, message, fix },
      user_instructions?: string,
      model?: string
    }

    Returns the operations array + explanation WITHOUT executing.
    """
    issue = body.get("issue")
    if not isinstance(issue, dict):
        raise HTTPException(status_code=400, detail="'issue' object is required")

    user_instructions = str(body.get("user_instructions") or "").strip()
    u = _urls()

    # 1. Load full specs for affected tags
    issue_tags = issue.get("tags") or []
    tag_specs: dict[str, dict] = {}
    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        qcur = qa.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if issue_tags:
            qcur.execute(
                "SELECT kind::text, code::text, parent_code::text, spec, active::bool "
                "FROM policy_lexicon_entries WHERE code = ANY(%s)",
                (list(issue_tags),),
            )
            for r in qcur.fetchall():
                code = str(r.get("code") or "")
                kind_val = str(r.get("kind") or "")
                spec_val = r.get("spec") if isinstance(r.get("spec"), dict) else {}
                tag_specs[code] = {
                    "kind": kind_val,
                    "code": code,
                    "parent_code": r.get("parent_code"),
                    "spec": spec_val,
                    "active": r.get("active", True),
                }

        # Also load all domain containers so LLM knows what exists
        qcur.execute(
            "SELECT kind::text, code::text, parent_code::text, spec "
            "FROM policy_lexicon_entries WHERE active = true "
            "ORDER BY kind, code"
        )
        all_entries = [dict(r) for r in qcur.fetchall()]
        qcur.close()
        qa.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load tags: {type(e).__name__}: {e}")

    # Build a compact summary of existing tags for context
    existing_codes = []
    for ent in all_entries:
        k = str(ent.get("kind") or "")
        c = str(ent.get("code") or "")
        is_domain = "." not in c
        marker = "[DOMAIN]" if is_domain else "[TAG]"
        sp = ent.get("spec") if isinstance(ent.get("spec"), dict) else {}
        phrases = ", ".join(str(p) for p in (sp.get("strong_phrases") or [])[:3])
        aliases = ", ".join(str(p) for p in (sp.get("aliases") or [])[:3])
        line = f"  {marker} {k}.{c}"
        if phrases:
            line += f"  phrases: [{phrases}]"
        if aliases:
            line += f"  aliases: [{aliases}]"
        existing_codes.append(line)
    existing_tree = "\n".join(existing_codes)

    # Build detail block for affected tags
    affected_detail = ""
    for code, info in tag_specs.items():
        sp = info.get("spec") or {}
        affected_detail += f"\n  Tag: {info['kind']}.{code}\n"
        affected_detail += f"    parent_code: {info.get('parent_code')}\n"
        affected_detail += f"    description: {sp.get('description', '')}\n"
        affected_detail += f"    strong_phrases: {sp.get('strong_phrases', [])}\n"
        affected_detail += f"    aliases: {sp.get('aliases', [])}\n"
        affected_detail += f"    refuted_words: {sp.get('refuted_words', [])}\n"
        affected_detail += f"    active: {info.get('active', True)}\n"

    # 2. Build the LLM prompt
    prompt = f"""You are an expert taxonomy maintenance assistant. You must produce EXACT structured operations
to fix a health issue in a healthcare policy lexicon.

TAXONOMY RULES:
- Tag codes are lowercase_snake_case, max 2 dot-segments (domain.tag)
- Domain containers (no dot, e.g. "claims") are organizational only -- NO strong_phrases, aliases, or refuted_words
- Leaf tags (with dot, e.g. "claims.general") are the matchable units
- Each domain should have a .general leaf tag as catch-all
- parent_code for leaf tags must reference an existing domain container of the same kind

THE ISSUE:
  Type: {issue.get('type', '')}
  Severity: {issue.get('severity', '')}
  Message: {issue.get('message', '')}
  Affected tags: {', '.join(issue_tags)}
  Original fix suggestion: {issue.get('fix', '')}

AFFECTED TAG DETAILS:
{affected_detail}

{"USER INSTRUCTIONS: " + user_instructions if user_instructions else "No additional user instructions."}

EXISTING LEXICON (for reference — do not duplicate existing tags):
{existing_tree}

PRODUCE a list of operations to fix this issue. Available operations:

1. create_tag: Create a new tag
   {{ "op": "create_tag", "kind": "<p|d|j>", "code": "<tag_code>", "parent_code": "<domain_code or null>",
      "spec": {{ "description": "...", "strong_phrases": [...], "aliases": [...], "refuted_words": [...] }} }}

2. update_tag: Update an existing tag's spec (merges with existing spec)
   {{ "op": "update_tag", "kind": "<p|d|j>", "code": "<existing_code>",
      "spec": {{ "description": "...", "strong_phrases": [...], "aliases": [...] }} }}
   NOTE: For update_tag, provide the COMPLETE new value for each field you want to change.
   For example, to REMOVE all strong_phrases, set "strong_phrases": [].
   Fields not included will be preserved from the existing spec.

3. delete_tag: Delete a tag
   {{ "op": "delete_tag", "kind": "<p|d|j>", "code": "<tag_code>" }}

4. merge_tags: Merge source into target (moves phrases, re-parents children, deletes source)
   {{ "op": "merge_tags", "kind": "<p|d|j>", "source_code": "<src>", "target_code": "<tgt>" }}

5. move_tag: Rename/re-parent a tag
   {{ "op": "move_tag", "kind": "<p|d|j>", "from_code": "<old>", "to_code": "<new>", "parent_code": "<parent or null>" }}

Respond with ONLY valid JSON (no markdown, no code fences). Schema:
{{
  "explanation": "<human-readable summary of what will happen, 2-3 sentences>",
  "operations": [ <list of operation objects> ]
}}
"""

    # 3. Call LLM
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        project = os.environ.get("VERTEX_PROJECT") or os.environ.get("VERTEX_PROJECT_ID") or ""
        region = os.environ.get("VERTEX_REGION") or os.environ.get("VERTEX_LOCATION") or "us-central1"
        model_name = body.get("model") or os.environ.get("VERTEX_HEALTH_LLM_MODEL") or os.environ.get("VERTEX_LLM_MODEL") or "gemini-2.5-pro"

        if not project:
            endpoint_id = os.environ.get("VERTEX_INDEX_ENDPOINT_ID") or ""
            m = re.search(r"projects/([^/]+)/", endpoint_id)
            if m:
                project = m.group(1)
        if not project:
            raise HTTPException(status_code=400, detail="VERTEX_PROJECT not configured")

        vertexai.init(project=project, location=region)
        model = GenerativeModel(model_name)
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # Strip code fences
        if raw_text.startswith("```"):
            lines_raw = raw_text.split("\n")
            raw_text = "\n".join(line for line in lines_raw if not line.strip().startswith("```"))
            raw_text = raw_text.strip()

        # Parse JSON
        result = None
        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                try:
                    result = json.loads(raw_text[json_start:json_end])
                except json.JSONDecodeError:
                    pass
        if result is None:
            raise HTTPException(
                status_code=500,
                detail=f"Could not parse LLM fix response. First 500 chars: {raw_text[:500]}"
            )
        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="LLM returned unexpected format")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM fix preview failed: {type(e).__name__}: {e}")

    operations = result.get("operations") or []
    explanation = str(result.get("explanation", ""))

    # Validate operation shapes
    valid_ops = []
    for op in operations:
        if not isinstance(op, dict):
            continue
        op_type = str(op.get("op", "")).strip()
        if op_type not in ("create_tag", "update_tag", "delete_tag", "merge_tags", "move_tag"):
            continue
        valid_ops.append(op)

    return {
        "status": "ok",
        "explanation": explanation,
        "operations": valid_ops,
        "llm_model": model_name,
    }


@app.post("/policy/lexicon/health/fix/apply")
def health_fix_apply(body: dict = Body(...)) -> dict[str, Any]:
    """
    Execute a list of structured fix operations against the QA DB.
    Body: { operations: [ { op, kind, code, ... }, ... ] }
    """
    operations = body.get("operations")
    if not isinstance(operations, list) or not operations:
        raise HTTPException(status_code=400, detail="'operations' array is required and must not be empty")

    u = _urls()
    results: list[dict[str, Any]] = []
    new_rev = 0

    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        cur = qa.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        for idx, op in enumerate(operations):
            if not isinstance(op, dict):
                results.append({"index": idx, "op": "unknown", "status": "error", "detail": "Invalid operation object"})
                continue

            op_type = str(op.get("op", "")).strip()
            kind = str(op.get("kind", "")).strip().lower()
            code = str(op.get("code", "")).strip()

            try:
                if op_type == "create_tag":
                    parent_code = op.get("parent_code")
                    parent_code = str(parent_code).strip() if isinstance(parent_code, str) and str(parent_code).strip() else None
                    spec_val = op.get("spec") if isinstance(op.get("spec"), dict) else {}

                    if kind not in ("p", "d", "j") or not code:
                        raise ValueError("kind (p/d/j) and code are required")

                    _validate_tag_structure(kind, code, parent_code, u.qa, spec=spec_val)

                    cur.execute(
                        "SELECT id FROM policy_lexicon_entries WHERE kind = %s AND code = %s LIMIT 1",
                        (kind, code),
                    )
                    existing = cur.fetchone()
                    if existing:
                        # Update instead of create if it already exists
                        cur.execute(
                            "UPDATE policy_lexicon_entries SET spec = %s::jsonb, parent_code = COALESCE(%s, parent_code), "
                            "active = true, updated_at = NOW() WHERE kind = %s AND code = %s",
                            (json.dumps(spec_val), parent_code, kind, code),
                        )
                        results.append({"index": idx, "op": "create_tag", "code": f"{kind}.{code}", "status": "ok", "note": "updated existing"})
                    else:
                        cur.execute(
                            "INSERT INTO policy_lexicon_entries(id, kind, code, parent_code, spec, active, created_at, updated_at) "
                            "VALUES (%s, %s, %s, %s, %s::jsonb, true, NOW(), NOW())",
                            (str(uuid.uuid4()), kind, code, parent_code, json.dumps(spec_val)),
                        )
                        results.append({"index": idx, "op": "create_tag", "code": f"{kind}.{code}", "status": "ok"})

                elif op_type == "update_tag":
                    spec_delta = op.get("spec") if isinstance(op.get("spec"), dict) else {}

                    if kind not in ("p", "d", "j") or not code:
                        raise ValueError("kind (p/d/j) and code are required")

                    # Load existing spec and merge
                    cur.execute(
                        "SELECT spec, parent_code FROM policy_lexicon_entries WHERE kind = %s AND code = %s LIMIT 1",
                        (kind, code),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise ValueError(f"Tag {kind}.{code} not found")

                    existing_spec = row.get("spec") if isinstance(row.get("spec"), dict) else {}
                    parent_code = row.get("parent_code")

                    # Merge: spec_delta fields overwrite existing
                    merged_spec = {**existing_spec, **spec_delta}

                    _validate_tag_structure(kind, code, parent_code, u.qa, spec=merged_spec)

                    cur.execute(
                        "UPDATE policy_lexicon_entries SET spec = %s::jsonb, updated_at = NOW() "
                        "WHERE kind = %s AND code = %s",
                        (json.dumps(merged_spec), kind, code),
                    )
                    results.append({"index": idx, "op": "update_tag", "code": f"{kind}.{code}", "status": "ok"})

                elif op_type == "delete_tag":
                    if kind not in ("p", "d", "j") or not code:
                        raise ValueError("kind (p/d/j) and code are required")

                    # Promote children
                    cur.execute(
                        "UPDATE policy_lexicon_entries SET parent_code = NULL, updated_at = NOW() "
                        "WHERE kind = %s AND parent_code = %s",
                        (kind, code),
                    )
                    cur.execute(
                        "DELETE FROM policy_lexicon_entries WHERE kind = %s AND code = %s",
                        (kind, code),
                    )
                    results.append({"index": idx, "op": "delete_tag", "code": f"{kind}.{code}", "status": "ok", "deleted": cur.rowcount})

                elif op_type == "merge_tags":
                    src_code = str(op.get("source_code", "")).strip()
                    tgt_code = str(op.get("target_code", "")).strip()
                    if kind not in ("p", "d", "j") or not src_code or not tgt_code:
                        raise ValueError("kind/source_code/target_code required")

                    # Load source and target
                    cur.execute(
                        "SELECT spec FROM policy_lexicon_entries WHERE kind = %s AND code = %s LIMIT 1",
                        (kind, src_code),
                    )
                    src_row = cur.fetchone()
                    if not src_row:
                        raise ValueError(f"Source {kind}.{src_code} not found")

                    cur.execute(
                        "SELECT spec FROM policy_lexicon_entries WHERE kind = %s AND code = %s LIMIT 1",
                        (kind, tgt_code),
                    )
                    tgt_row = cur.fetchone()
                    if not tgt_row:
                        raise ValueError(f"Target {kind}.{tgt_code} not found")

                    src_spec = src_row.get("spec") if isinstance(src_row.get("spec"), dict) else {}
                    tgt_spec = tgt_row.get("spec") if isinstance(tgt_row.get("spec"), dict) else {}

                    # Merge phrases
                    src_phrases = set(str(p).strip() for p in (src_spec.get("strong_phrases") or []))
                    src_phrases.add(src_code.replace("_", " ").strip())
                    existing_phrases = set(str(p).strip() for p in (tgt_spec.get("strong_phrases") or []))
                    new_phrases = [p for p in src_phrases if p and p not in existing_phrases]
                    tgt_spec["strong_phrases"] = list(tgt_spec.get("strong_phrases") or []) + new_phrases

                    cur.execute(
                        "UPDATE policy_lexicon_entries SET spec = %s::jsonb, updated_at = NOW() WHERE kind = %s AND code = %s",
                        (json.dumps(tgt_spec), kind, tgt_code),
                    )
                    cur.execute(
                        "UPDATE policy_lexicon_entries SET parent_code = %s, updated_at = NOW() WHERE kind = %s AND parent_code = %s",
                        (tgt_code, kind, src_code),
                    )
                    cur.execute(
                        "DELETE FROM policy_lexicon_entries WHERE kind = %s AND code = %s",
                        (kind, src_code),
                    )
                    results.append({"index": idx, "op": "merge_tags", "source": f"{kind}.{src_code}", "target": f"{kind}.{tgt_code}", "status": "ok"})

                elif op_type == "move_tag":
                    from_code = str(op.get("from_code", "")).strip()
                    to_code = str(op.get("to_code", "")).strip()
                    parent_code = op.get("parent_code")
                    parent_code = str(parent_code).strip() if isinstance(parent_code, str) and str(parent_code).strip() else None

                    if kind not in ("p", "d", "j") or not from_code or not to_code:
                        raise ValueError("kind/from_code/to_code required")

                    cur.execute(
                        "UPDATE policy_lexicon_entries SET code = %s, parent_code = %s, updated_at = NOW() "
                        "WHERE kind = %s AND code = %s",
                        (to_code, parent_code, kind, from_code),
                    )
                    if cur.rowcount <= 0:
                        raise ValueError(f"Tag {kind}.{from_code} not found")
                    # Update children
                    cur.execute(
                        "UPDATE policy_lexicon_entries SET parent_code = %s, updated_at = NOW() "
                        "WHERE kind = %s AND parent_code = %s",
                        (to_code, kind, from_code),
                    )
                    results.append({"index": idx, "op": "move_tag", "from": f"{kind}.{from_code}", "to": f"{kind}.{to_code}", "status": "ok"})

                else:
                    results.append({"index": idx, "op": op_type, "status": "error", "detail": f"Unknown operation: {op_type}"})

            except ValueError as ve:
                results.append({"index": idx, "op": op_type, "code": f"{kind}.{code}" if code else "", "status": "error", "detail": str(ve)})
            except HTTPException as he:
                results.append({"index": idx, "op": op_type, "code": f"{kind}.{code}" if code else "", "status": "error", "detail": he.detail})
            except Exception as ex:
                results.append({"index": idx, "op": op_type, "code": f"{kind}.{code}" if code else "", "status": "error", "detail": f"{type(ex).__name__}: {ex}"})

        new_rev = _bump_lexicon_revision(cur)
        cur.close()
        qa.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fix apply failed: {type(e).__name__}: {e}")

    failed = [r for r in results if r.get("status") != "ok"]
    return {
        "status": "ok" if not failed else "partial",
        "results": results,
        "failed_count": len(failed),
        "lexicon_revision": new_rev,
    }


# ---------------------------------------------------------------------------
# Publish QA lexicon → RAG DB
# ---------------------------------------------------------------------------

@app.post("/policy/lexicon/publish")
def publish_lexicon_to_rag(body: dict = Body(default={})) -> dict[str, Any]:
    """
    Copy approved QA lexicon entries to RAG DB so extraction uses the latest tags.
    Body (optional): { dry_run: bool }
    """
    dry_run = bool(body.get("dry_run", False))
    u = _urls()

    try:
        # Import the sync script
        import importlib.util
        sync_path = Path(__file__).resolve().parents[3] / "mobius-dbt" / "scripts" / "sync_qa_lexicon_to_rag.py"
        if not sync_path.exists():
            raise HTTPException(status_code=500, detail=f"Sync script not found at {sync_path}")

        spec = importlib.util.spec_from_file_location("sync_qa_lexicon_to_rag", sync_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.publish_lexicon(u.qa, u.rag, dry_run=dry_run)
        return {"status": "ok", **result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Publish failed: {type(e).__name__}: {e}")

