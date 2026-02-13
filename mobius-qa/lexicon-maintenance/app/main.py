from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
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
                SELECT kind::text, code::text, spec, active::bool
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
                tag_rows.append(
                    {
                        "id": f"tag:{k}:{code}",
                        "row_type": "tag",
                        "kind": k,
                        "status": "approved",
                        "code": code,
                        "category": (r.get("spec") or {}).get("category") if isinstance(r.get("spec"), dict) else None,
                        "description": (r.get("spec") or {}).get("description") if isinstance(r.get("spec"), dict) else None,
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
                COALESCE(max(COALESCE(confidence, 0)), 0) AS max_confidence
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
    """Bulk update candidate states in RAG DB (supports reject/flag/restore)."""
    u = _urls()
    norms = body.get("normalized_list") or []
    if not isinstance(norms, list) or not norms:
        raise HTTPException(status_code=400, detail="normalized_list is required")
    next_state = str(body.get("state") or "").strip().lower()
    if next_state not in ("proposed", "rejected", "flagged"):
        raise HTTPException(status_code=400, detail="state must be proposed|rejected|flagged (approve not wired in this build)")
    reviewer = str(body.get("reviewer") or "").strip() or None
    notes = body.get("reviewer_notes")

    norm_keys = [str(x).strip().lower() for x in norms if str(x).strip()]
    if not norm_keys:
        raise HTTPException(status_code=400, detail="normalized_list is empty")

    try:
        rag = _conn(u.rag)
        rag.autocommit = True
        cur = rag.cursor()
        updated = []
        errors = []
        for nk in norm_keys:
            try:
                cur.execute(
                    """
                    UPDATE policy_lexicon_candidates
                    SET state = %s,
                        reviewer = %s,
                        reviewer_notes = %s
                    WHERE trim(lower(normalized)) = %s
                    RETURNING normalized
                    """,
                    (next_state, reviewer, notes, nk),
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
        return {"status": "ok", "updated": updated, "errors": errors, "lexicon_revision": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk review failed: {type(e).__name__}: {e}")

