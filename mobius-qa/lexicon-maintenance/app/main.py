from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
import json
import uuid
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


def _load_env() -> None:
    """Best-effort: load mobius-config/.env (without clobbering process overrides)."""
    try:
        root = Path(__file__).resolve().parents[3]  # /Mobius
        cfg_dir = root / "mobius-config"
        env_path = cfg_dir / ".env"
        if not env_path.exists():
            return
        try:
            from dotenv import load_dotenv  # type: ignore
        except Exception:
            return
        # Preserve explicit DB URL overrides, but otherwise prefer mobius-config/.env.
        # This avoids picking up stale shell env (e.g. POSTGRES_HOST pointing to a public IP).
        preserve = {k: os.environ.get(k) for k in ("QA_DATABASE_URL", "RAG_DATABASE_URL") if os.environ.get(k)}
        load_dotenv(env_path, override=True)
        for k, v in preserve.items():
            if v is not None:
                os.environ[k] = v
    except Exception:
        return


_load_env()


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def _build_pg_url(db: str) -> str:
    user = _env("POSTGRES_USER", "postgres") or "postgres"
    pwd = _env("POSTGRES_PASSWORD", "")
    host = _env("POSTGRES_HOST", "127.0.0.1") or "127.0.0.1"
    port = _env("POSTGRES_PORT", "5432") or "5432"
    if pwd:
        return f"postgresql://{user}:{pwd}@{host}:{port}/{db}?connect_timeout=5"
    return f"postgresql://{user}@{host}:{port}/{db}?connect_timeout=5"


def _qa_url() -> str:
    return _env("QA_DATABASE_URL") or _build_pg_url("mobius_qa")


def _rag_url() -> str:
    return _env("RAG_DATABASE_URL") or _build_pg_url("mobius_rag")


@dataclass
class DbUrls:
    qa: str
    rag: str


def _urls() -> DbUrls:
    return DbUrls(qa=_qa_url(), rag=_rag_url())


app = FastAPI(title="Mobius QA — Lexicon Maintenance API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _conn(url: str):
    return psycopg2.connect(url)


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
        # Verify parent exists
        try:
            qa = _conn(qa_url)
            qa.autocommit = True
            cur = qa.cursor()
            cur.execute(
                "SELECT 1 FROM policy_lexicon_entries WHERE kind = %s AND code = %s LIMIT 1",
                (kind, parent_code),
            )
            exists = cur.fetchone()
            cur.close()
            qa.close()
            if not exists:
                raise HTTPException(
                    status_code=400,
                    detail=f"Parent tag '{kind}.{parent_code}' does not exist. "
                           f"Create the root tag first."
                )
        except HTTPException:
            raise
        except Exception:
            pass  # best-effort; don't block on transient DB issues


@app.get("/health")
def health():
    u = _urls()
    try:
        c = _conn(u.qa)
        cur = c.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        c.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"qa_db unhealthy: {type(e).__name__}: {e}")


@app.get("/policy/lexicon")
def get_policy_lexicon():
    """Return lexicon tags + meta from QA DB."""
    u = _urls()
    try:
        c = _conn(u.qa)
        c.autocommit = True
        cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT COALESCE(revision,0)::bigint AS revision,
                   COALESCE(lexicon_version,'v1')::text AS lexicon_version,
                   lexicon_meta
            FROM policy_lexicon_meta
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 1
            """
        )
        meta = cur.fetchone() or {}
        lexicon_meta = meta.get("lexicon_meta") if isinstance(meta.get("lexicon_meta"), dict) else (meta.get("lexicon_meta") or {})

        cur.execute(
            """
            SELECT kind::text, code::text, parent_code::text, spec, active::bool
            FROM policy_lexicon_entries
            WHERE active = true
            ORDER BY kind, code
            """
        )
        tags = []
        for r in cur.fetchall():
            tags.append(
                {
                    "kind": (r.get("kind") or "").strip().lower(),
                    "code": r.get("code"),
                    "parent": r.get("parent_code"),
                    "spec": r.get("spec") if isinstance(r.get("spec"), dict) else {},
                }
            )
        cur.close()
        c.close()
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
    """Increment policy_lexicon_meta.revision (create row if missing). Returns new revision."""
    qcur.execute(
        """
        SELECT id, COALESCE(revision,0)::bigint AS revision
        FROM policy_lexicon_meta
        ORDER BY updated_at DESC NULLS LAST
        LIMIT 1
        """
    )
    row = qcur.fetchone()
    # Works with both tuple cursors and RealDictCursor.
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
        qcur.execute(
            "UPDATE policy_lexicon_meta SET revision=%s, updated_at=NOW() WHERE id=%s",
            (new_rev, rid),
        )
        return new_rev
    new_rev = 1
    qcur.execute(
        """
        INSERT INTO policy_lexicon_meta(id, lexicon_version, lexicon_meta, revision, created_at, updated_at)
        VALUES (%s, %s, %s::jsonb, %s, NOW(), NOW())
        """,
        (str(uuid.uuid4()), "v1", json.dumps({}), new_rev),
    )
    return new_rev


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

    # Enforce taxonomy structure on new tags (skip validation for existing tag updates
    # that don't change code, to avoid blocking spec-only edits)
    _validate_tag_structure(k, c, parent_code, u.qa, spec=spec)

    try:
        qa = _conn(u.qa)
        qa.autocommit = True
        cur = qa.cursor()

        # Upsert tag row
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
        qcur.close()
        qa.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read QA lexicon: {type(e).__name__}: {e}")

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
                cand_rows.append(
                    {
                        "id": f"cand:{str(r.get('state') or 'proposed').lower()}:{kk}:{str(r.get('norm_key') or '')}",
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


@app.post("/policy/candidates/aggregate/review-bulk")
def review_policy_candidates_aggregate_bulk(body: dict = Body(...)):
    """
    Bulk update candidate states in RAG DB.
    Supports: proposed|rejected|flagged and approved (writes aliases into QA lexicon).
    UI payload shape (bundle):
      { normalized_list: [...], state: 'approved'|'rejected'|..., candidate_type_override?: 'p'|'d'|'j',
        tag_code_map?: { <normalized>: <tag_code or 'd:tag_code'>, ... } }
    """
    u = _urls()
    norms = body.get("normalized_list") or []
    if not isinstance(norms, list) or not norms:
        raise HTTPException(status_code=400, detail="normalized_list is required")
    next_state = str(body.get("state") or "").strip().lower()
    if next_state not in ("proposed", "rejected", "flagged", "approved"):
        raise HTTPException(status_code=400, detail="state must be proposed|rejected|flagged|approved")
    reviewer = str(body.get("reviewer") or "").strip() or None
    notes = body.get("reviewer_notes")

    norm_keys = [str(x).strip().lower() for x in norms if str(x).strip()]
    if not norm_keys:
        raise HTTPException(status_code=400, detail="normalized_list is empty")

    # Approval wiring: when approving, we must write into QA lexicon first (as alias to tag_code_map).
    candidate_type_override = str(body.get("candidate_type_override") or "").strip().lower() or None
    tag_code_map = body.get("tag_code_map") if isinstance(body.get("tag_code_map"), dict) else None
    if next_state == "approved":
        if candidate_type_override not in ("p", "d", "j"):
            raise HTTPException(status_code=400, detail="candidate_type_override is required for state=approved (p|d|j)")
        if not tag_code_map:
            raise HTTPException(status_code=400, detail="tag_code_map is required for state=approved")

        # Update QA lexicon entries: add each normalized phrase as alias to its mapped tag code.
        try:
            qa = _conn(u.qa)
            qa.autocommit = True
            qcur = qa.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            updated_tags: set[tuple[str, str]] = set()
            for nk in norm_keys:
                mapped = tag_code_map.get(nk) or tag_code_map.get(nk.strip()) or None
                if not mapped:
                    continue
                tk, tc = _parse_kind_code(str(mapped), candidate_type_override)
                if tk not in ("p", "d", "j") or not tc:
                    continue
                phrase = nk

                qcur.execute(
                    """
                    SELECT id, spec
                    FROM policy_lexicon_entries
                    WHERE kind = %s AND code = %s
                    LIMIT 1
                    """,
                    (tk, tc),
                )
                row = qcur.fetchone()
                if row and row.get("id"):
                    spec = row.get("spec") if isinstance(row.get("spec"), dict) else {}
                    spec = dict(spec)
                    spec.setdefault("kind", tk)
                    spec = _add_alias_phrase(spec, phrase, strength="strong")
                    qcur.execute(
                        """
                        UPDATE policy_lexicon_entries
                        SET spec = %s::jsonb,
                            active = true,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (json.dumps(spec), row["id"]),
                    )
                else:
                    # Creating a brand-new tag -- validate structure first
                    new_parent = tc.rsplit(".", 1)[0] if "." in tc else None
                    new_spec = {"kind": tk, "description": "", "strong_phrases": [phrase]}
                    _validate_tag_structure(tk, tc, new_parent, u.qa, spec=new_spec)
                    spec = new_spec
                    qcur.execute(
                        """
                        INSERT INTO policy_lexicon_entries(id, kind, code, parent_code, spec, active, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s::jsonb, true, NOW(), NOW())
                        """,
                        (str(uuid.uuid4()), tk, tc, new_parent, json.dumps(spec)),
                    )
                updated_tags.add((tk, tc))

            # Bump revision once per bulk action
            new_rev = _bump_lexicon_revision(qcur)
            qcur.close()
            qa.close()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to approve into QA lexicon: {type(e).__name__}: {e}")

    try:
        rag = _conn(u.rag)
        rag.autocommit = True
        cur = rag.cursor()
        updated = []
        errors = []
        for nk in norm_keys:
            try:
                # Keep proposed_tag in sync for approved
                proposed_tag = None
                candidate_type = None
                if next_state == "approved" and tag_code_map:
                    mapped = tag_code_map.get(nk) or tag_code_map.get(nk.strip()) or None
                    if mapped:
                        tk, tc = _parse_kind_code(str(mapped), candidate_type_override or "d")
                        candidate_type = tk
                        proposed_tag = tc
                cur.execute(
                    """
                    UPDATE policy_lexicon_candidates
                    SET state = %s,
                        candidate_type = COALESCE(%s, candidate_type),
                        proposed_tag = COALESCE(%s, proposed_tag),
                        reviewer = %s,
                        reviewer_notes = %s
                    WHERE trim(lower(normalized)) = %s
                    RETURNING normalized
                    """,
                    (next_state, candidate_type, proposed_tag, reviewer, notes, nk),
                )
                touched = [r[0] for r in cur.fetchall()] if cur.rowcount else []
                if not touched:
                    errors.append({"normalized": nk, "error": "no_rows_updated"})
                else:
                    updated.append({"normalized": nk, "state": next_state})
                # Best-effort: update catalog too (for global suppression)
                try:
                    cur.execute(
                        """
                        INSERT INTO policy_lexicon_candidate_catalog(candidate_type, normalized_key, normalized, proposed_tag_key, proposed_tag, state, reviewer, reviewer_notes, decided_at, created_at, updated_at)
                        VALUES ('alias', %s, %s, '', NULL, %s, %s, %s, NOW(), NOW(), NOW())
                        ON CONFLICT (candidate_type, normalized_key, proposed_tag_key)
                        DO UPDATE SET state = EXCLUDED.state,
                                      reviewer = COALESCE(EXCLUDED.reviewer, policy_lexicon_candidate_catalog.reviewer),
                                      reviewer_notes = COALESCE(EXCLUDED.reviewer_notes, policy_lexicon_candidate_catalog.reviewer_notes),
                                      decided_at = NOW(),
                                      updated_at = NOW()
                        """,
                        (nk[:200], nk[:200], next_state, reviewer, notes),
                    )
                except Exception:
                    pass
            except Exception as e:
                errors.append({"normalized": nk, "error": str(e)})
        cur.close()
        rag.close()
        return {"status": "ok", "updated": updated, "errors": errors, "lexicon_revision": (new_rev if next_state == "approved" else None)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk review failed: {type(e).__name__}: {e}")


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

    Fetches all proposed candidates (llm_verdict IS NULL) from RAG DB,
    the full approved lexicon from QA DB, and the rejected catalog,
    then calls Vertex Gemini to classify each candidate as new_tag / alias / reject.

    Body (optional):
      force: bool  -- re-triage candidates that already have an llm_verdict
    """
    import yaml

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
        return {"status": "ok", "triaged": 0, "message": "No pending candidates to triage"}

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

    # 3. Build prompt
    cand_lines = []
    for c in candidates:
        occ = c.get("occurrences") or 0
        conf = c.get("confidence") or 0.0
        ctype = c.get("candidate_type") or "d"
        cand_lines.append(f'- "{c["normalized"]}" (type={ctype}, occurrences={occ}, confidence={conf:.2f})')
    cand_text = "\n".join(cand_lines)

    prompt = f"""You are an expert healthcare policy taxonomy maintainer.

Below is the current APPROVED lexicon tree for tagging healthcare policy documents:

{lexicon_tree}

Previously REJECTED candidates (do not suggest these again):
{rejected_text}

The following {len(candidates)} candidate phrases were extracted from recent document processing.
For EACH candidate, decide:
1. **verdict**: one of `new_tag` (genuinely new domain concept worth adding), `alias` (already covered by an existing tag -- specify which), or `reject` (junk, noise, too generic, not a real domain concept)
2. **confidence**: 0.0 to 1.0 (how confident you are in the verdict)
3. **reason**: one brief sentence explaining why
4. **suggested_kind**: p, d, or j (only for new_tag or alias; empty string for reject)
5. **suggested_code**: the full tag code (e.g. "health_care_services.chronic_pain") -- for alias, use the existing tag code; for new_tag, propose a new code following the tree conventions
6. **suggested_parent**: the parent tag code (e.g. "health_care_services") -- empty string for reject

Guidelines:
- Be AGGRESSIVE about rejecting junk: time references, copyright notices, generic phrases like "health care", partial sentences, conjunctions
- For alias verdicts, match to the MOST SPECIFIC existing tag, not a broad parent
- For new_tag verdicts, suggest placement that follows the existing tree structure and naming conventions
- If a candidate is a near-duplicate of an existing tag, verdict should be alias, not new_tag

Candidates:
{cand_text}

Respond with ONLY a YAML list. Do NOT wrap in code fences. Output raw YAML only.
Each item: phrase, verdict, confidence, reason, suggested_kind, suggested_code, suggested_parent.
"""

    # 4. Call Vertex Gemini
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        project = os.environ.get("VERTEX_PROJECT") or os.environ.get("VERTEX_PROJECT_ID") or ""
        region = os.environ.get("VERTEX_REGION") or os.environ.get("VERTEX_LOCATION") or "us-central1"
        model_name = os.environ.get("VERTEX_LLM_MODEL") or "gemini-2.0-flash"

        if not project:
            # Try extracting from VERTEX_INDEX_ENDPOINT_ID
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
        model = GenerativeModel(model_name)
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # Strip code fences if LLM wrapped them
        if raw_text.startswith("```"):
            lines_raw = raw_text.split("\n")
            raw_text = "\n".join(
                line for line in lines_raw
                if not line.strip().startswith("```")
            )

        triage_results = yaml.safe_load(raw_text)
        if not isinstance(triage_results, list):
            try:
                rag.close()
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"LLM returned unexpected format. Raw: {raw_text[:500]}")

    except HTTPException:
        raise
    except Exception as e:
        try:
            rag.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"LLM call failed: {type(e).__name__}: {e}")

    # 5. Build lookup and update candidates in RAG DB
    triage_by_phrase: dict[str, dict] = {}
    for item in triage_results:
        if not isinstance(item, dict):
            continue
        phrase = (str(item.get("phrase", "")) or "").strip().lower()
        if phrase:
            triage_by_phrase[phrase] = item

    try:
        rcur = rag.cursor()
        updated = 0
        skipped = 0
        for c in candidates:
            norm = (c.get("normalized") or "").strip().lower()
            triage = triage_by_phrase.get(norm)
            if not triage:
                skipped += 1
                continue

            verdict = str(triage.get("verdict", "")).strip().lower()
            if verdict not in ("new_tag", "alias", "reject"):
                skipped += 1
                continue

            confidence = 0.0
            try:
                confidence = float(triage.get("confidence", 0.0))
            except (ValueError, TypeError):
                pass
            reason = str(triage.get("reason", ""))[:500]
            suggested_kind = str(triage.get("suggested_kind", ""))[:10]
            suggested_code = str(triage.get("suggested_code", ""))[:500]
            suggested_parent = str(triage.get("suggested_parent", ""))[:500]

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

        rcur.close()
        rag.close()

        return {
            "status": "ok",
            "triaged": updated,
            "skipped": skipped,
            "total_candidates": len(candidates),
            "llm_model": model_name,
        }

    except Exception as e:
        try:
            rag.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to update triage results: {type(e).__name__}: {e}")


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

Only report issues with severity "critical" or "warning". Skip trivial "info" level items.
Limit to the TOP 10-15 most impactful issues maximum.

For each issue provide: type, severity, tags (affected codes), message, fix.

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
      "fix": "<fix>"
    }}
  ]
}}
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

    return {
        "status": "ok",
        "score": int(result.get("overall_score", 0)),
        "summary": str(result.get("summary", "")),
        "top_suggestions": result.get("top_suggestions") or [],
        "issues": result.get("issues") or [],
        "llm_model": model_name,
        "tag_count": len(entries),
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

