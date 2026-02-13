from __future__ import annotations

import json
import os
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
import yaml
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Touchpoint comment: restart service after changing defaults.

try:
    # Allow psycopg2 to adapt Python uuid.UUID seamlessly.
    psycopg2.extras.register_uuid()
except Exception:
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_ts() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _load_env() -> None:
    """Best-effort: load mobius-config/.env (without clobbering explicit overrides)."""
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
        preserve = {
            k: os.environ.get(k)
            for k in (
                "QA_DATABASE_URL",
                "CHAT_RAG_DATABASE_URL",
                "CHAT_DATABASE_URL",
                "VERTEX_PROJECT",
                "VERTEX_REGION",
                "VERTEX_INDEX_ENDPOINT_ID",
                "VERTEX_DEPLOYED_INDEX_ID",
            )
            if os.environ.get(k)
        }
        load_dotenv(env_path, override=True)
        for k, v in preserve.items():
            if v is not None:
                os.environ[k] = v
    except Exception:
        return


_load_env()


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def _is_local_host(host: str) -> bool:
    h = (host or "").strip().lower()
    return h in ("127.0.0.1", "localhost", "::1") or h.startswith("127.")


def _build_pg_url(db: str) -> str:
    user = _env("POSTGRES_USER", "postgres") or "postgres"
    pwd = _env("POSTGRES_PASSWORD", "")
    # Safety default: prefer localhost Cloud SQL proxy unless explicitly overridden via QA_DATABASE_URL.
    # This avoids accidentally using a public POSTGRES_HOST from mobius-config/.env in dev.
    raw_host = _env("POSTGRES_HOST", "127.0.0.1") or "127.0.0.1"
    host = raw_host if _is_local_host(raw_host) else "127.0.0.1"
    port = _env("POSTGRES_PORT", "5432") or "5432"
    if pwd:
        return f"postgresql://{user}:{pwd}@{host}:{port}/{db}?connect_timeout=5"
    return f"postgresql://{user}@{host}:{port}/{db}?connect_timeout=5"


def _qa_url() -> str:
    return _env("QA_DATABASE_URL") or _build_pg_url("mobius_qa")


def _chat_rag_url() -> str:
    return _env("CHAT_RAG_DATABASE_URL") or _env("CHAT_DATABASE_URL") or ""


def _conn(url: str):
    return psycopg2.connect(url)


def _ensure_tables() -> None:
    qa_url = _qa_url()
    conn = _conn(qa_url)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS retrieval_eval_suites (
              id UUID PRIMARY KEY,
              name TEXT NOT NULL,
              description TEXT,
              suite_spec JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS retrieval_eval_questions (
              id UUID PRIMARY KEY,
              suite_id UUID NOT NULL REFERENCES retrieval_eval_suites(id) ON DELETE CASCADE,
              qid TEXT NOT NULL,
              intent TEXT,
              bucket TEXT,
              question TEXT NOT NULL,
              gold JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              UNIQUE (suite_id, qid)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS retrieval_eval_runs (
              id UUID PRIMARY KEY,
              suite_id UUID NOT NULL REFERENCES retrieval_eval_suites(id) ON DELETE CASCADE,
              status TEXT NOT NULL DEFAULT 'queued', -- queued|running|completed|failed
              params JSONB NOT NULL DEFAULT '{}'::jsonb,
              summary JSONB NOT NULL DEFAULT '{}'::jsonb,
              error TEXT,
              started_at TIMESTAMPTZ,
              completed_at TIMESTAMPTZ,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS retrieval_eval_run_question_metrics (
              id UUID PRIMARY KEY,
              run_id UUID NOT NULL REFERENCES retrieval_eval_runs(id) ON DELETE CASCADE,
              suite_id UUID NOT NULL REFERENCES retrieval_eval_suites(id) ON DELETE CASCADE,
              qid TEXT NOT NULL,
              intent TEXT,
              bucket TEXT,
              question TEXT NOT NULL,
              expect_in_manual BOOLEAN,
              gold_parent_ids TEXT[],
              bm25_gold_rank INT,
              bm25_hit_at_1 BOOLEAN,
              bm25_hit_at_3 BOOLEAN,
              bm25_hit_at_5 BOOLEAN,
              bm25_hit_at_10 BOOLEAN,
              bm25_max_norm_score DOUBLE PRECISION,
              bm25_would_answer BOOLEAN,
              bm25_false_positive_answer BOOLEAN,
              hier_gold_rank INT,
              hier_hit_at_1 BOOLEAN,
              hier_hit_at_3 BOOLEAN,
              hier_hit_at_5 BOOLEAN,
              hier_hit_at_10 BOOLEAN,
              hier_top1_similarity DOUBLE PRECISION,
              hier_would_answer BOOLEAN,
              hier_false_positive_answer BOOLEAN,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              UNIQUE (run_id, qid)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS retrieval_eval_run_retrieval_rows (
              id UUID PRIMARY KEY,
              run_id UUID NOT NULL REFERENCES retrieval_eval_runs(id) ON DELETE CASCADE,
              suite_id UUID NOT NULL REFERENCES retrieval_eval_suites(id) ON DELETE CASCADE,
              qid TEXT NOT NULL,
              method TEXT NOT NULL, -- bm25|hier
              rank INT NOT NULL,
              item_id TEXT NOT NULL,
              parent_metadata_id TEXT,
              score DOUBLE PRECISION,
              raw_score DOUBLE PRECISION,
              match BOOLEAN NOT NULL DEFAULT FALSE,
              match_why TEXT,
              page_number INT,
              source_type TEXT,
              snippet TEXT,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_retrieval_eval_runs_suite ON retrieval_eval_runs(suite_id, created_at DESC);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_retrieval_eval_run_rows_run ON retrieval_eval_run_retrieval_rows(run_id, qid, method, rank);"
        )
        cur.close()
    finally:
        conn.close()


app = FastAPI(title="Mobius QA — Retrieval Eval Studio API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_STARTUP_ERROR: str | None = None
_DOCS_CACHE: dict[str, Any] | None = None


@app.on_event("startup")
def _startup() -> None:
    global _STARTUP_ERROR
    try:
        _ensure_tables()
        _STARTUP_ERROR = None
    except Exception as e:
        # Don't prevent the server from starting; surface via /health and endpoint errors.
        _STARTUP_ERROR = f"{type(e).__name__}: {e}"


@app.get("/health")
def health() -> dict[str, Any]:
    # If startup failed earlier (e.g. DB not ready yet), retry now.
    try:
        _require_ready()
    except HTTPException as e:
        raise e
    try:
        c = _conn(_qa_url())
        cur = c.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        c.close()
        return {"status": "ok", "ts": _utc_ts()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"qa_db unhealthy: {type(e).__name__}: {e}")


def _require_ready() -> None:
    """Ensure DB tables exist; raise a clean error if not."""
    global _STARTUP_ERROR
    # Self-heal: if startup failed due to DB readiness, retry on demand.
    try:
        _ensure_tables()
        _STARTUP_ERROR = None
        return
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        # Preserve initial startup error context if present, but allow recovery later.
        _STARTUP_ERROR = _STARTUP_ERROR or msg
        raise HTTPException(status_code=500, detail=f"db_init_failed: {msg}")


def _qa_exec(sql: str, params: tuple | list | None = None, *, fetch: bool = False) -> list[dict[str, Any]] | None:
    conn = _conn(_qa_url())
    conn.autocommit = True
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or None)
        rows = cur.fetchall() if fetch else None
        cur.close()
        return [dict(r) for r in rows] if rows is not None else None
    finally:
        conn.close()


@app.get("/api/suites")
def list_suites() -> dict[str, Any]:
    _require_ready()
    rows = _qa_exec(
        """
        SELECT id::text AS id, name, description, suite_spec, created_at, updated_at
        FROM retrieval_eval_suites
        ORDER BY updated_at DESC, created_at DESC
        """,
        fetch=True,
    ) or []
    return {"suites": rows}


@app.post("/api/suites")
def create_suite(body: dict = Body(...)) -> dict[str, Any]:
    _require_ready()
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    description = str(body.get("description") or "").strip() or None
    suite_spec = body.get("suite_spec") or {}
    if not isinstance(suite_spec, dict):
        raise HTTPException(status_code=400, detail="suite_spec must be an object")
    sid = uuid.uuid4()
    _qa_exec(
        """
        INSERT INTO retrieval_eval_suites(id, name, description, suite_spec, created_at, updated_at)
        VALUES (%s, %s, %s, %s::jsonb, NOW(), NOW())
        """,
        (sid, name, description, json.dumps(suite_spec)),
    )
    return {"status": "ok", "suite_id": str(sid)}


@app.post("/api/suites/{suite_id}/spec")
def update_suite_spec(suite_id: str, body: dict = Body(...)) -> dict[str, Any]:
    _require_ready()
    try:
        sid = uuid.UUID(suite_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid suite_id")
    suite_spec = body.get("suite_spec") or {}
    if not isinstance(suite_spec, dict):
        raise HTTPException(status_code=400, detail="suite_spec must be an object")
    touched = _qa_exec("SELECT 1 AS ok FROM retrieval_eval_suites WHERE id=%s", (sid,), fetch=True) or []
    if not touched:
        raise HTTPException(status_code=404, detail="suite not found")
    _qa_exec(
        "UPDATE retrieval_eval_suites SET suite_spec=%s::jsonb, updated_at=NOW() WHERE id=%s",
        (json.dumps(suite_spec), sid),
    )
    return {"status": "ok", "suite_id": str(sid), "suite_spec": suite_spec}


@app.get("/api/suites/{suite_id}")
def get_suite(suite_id: str) -> dict[str, Any]:
    _require_ready()
    try:
        sid = uuid.UUID(suite_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid suite_id")
    suites = _qa_exec(
        """
        SELECT id::text AS id, name, description, suite_spec, created_at, updated_at
        FROM retrieval_eval_suites
        WHERE id = %s
        """,
        (sid,),
        fetch=True,
    ) or []
    if not suites:
        raise HTTPException(status_code=404, detail="suite not found")
    questions = _qa_exec(
        """
        SELECT id::text AS id, qid, intent, bucket, question, gold, created_at, updated_at
        FROM retrieval_eval_questions
        WHERE suite_id = %s
        ORDER BY qid ASC
        """,
        (sid,),
        fetch=True,
    ) or []
    return {"suite": suites[0], "questions": questions}


@app.get("/api/documents")
def list_documents(
    search: str | None = None,
    limit: int = 200,
    allow_stale: bool = True,
    clear_cache: bool = False,
) -> dict[str, Any]:
    """
    List available published documents from Chat DB (`published_rag_metadata`).
    This powers the UI multi-select for scoping retrieval eval.
    """
    # Intentionally does NOT require QA DB (so doc selection still works even if QA DB is temporarily unavailable).
    chat_db_url = _chat_rag_url()
    if not chat_db_url:
        raise HTTPException(status_code=400, detail="CHAT_RAG_DATABASE_URL (or CHAT_DATABASE_URL) must be set")
    lim = max(1, min(int(limit or 200), 2000))
    q = (search or "").strip()
    # Small in-memory cache so the UI can stay usable during transient DB saturation.
    global _DOCS_CACHE
    if clear_cache:
        _DOCS_CACHE = None
    try:
        conn = psycopg2.connect(chat_db_url)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            where = ["document_id IS NOT NULL"]
            params: list[Any] = []
            if q:
                where.append("(COALESCE(document_display_name,'') ILIKE %s OR COALESCE(document_filename,'') ILIKE %s)")
                params.extend([f"%{q}%", f"%{q}%"])
            cur.execute(
                f"""
                SELECT
                  document_id::text AS document_id,
                  max(NULLIF(document_display_name, '')) AS document_display_name,
                  max(NULLIF(document_filename, '')) AS document_filename,
                  COALESCE(
                    max(NULLIF(document_display_name, '')),
                    max(NULLIF(document_filename, '')),
                    document_id::text
                  ) AS document_label,
                  max(NULLIF(document_authority_level, '')) AS document_authority_level,
                  max(document_payer) AS document_payer,
                  max(document_state) AS document_state,
                  max(document_program) AS document_program,
                  sum(CASE WHEN source_type='hierarchical' THEN 1 ELSE 0 END)::bigint AS hierarchical_rows,
                  sum(CASE WHEN source_type='fact' THEN 1 ELSE 0 END)::bigint AS fact_rows,
                  max(updated_at) AS updated_at
                FROM published_rag_metadata
                WHERE {" AND ".join(where)}
                GROUP BY document_id
                ORDER BY updated_at DESC NULLS LAST, document_label ASC NULLS LAST
                LIMIT {lim}
                """,
                params or None,
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            _DOCS_CACHE = {"ts": _utc_ts(), "documents": rows}
            return {"documents": rows, "stale": False}
        finally:
            conn.close()
    except Exception as e:
        cached = (_DOCS_CACHE or {}).get("documents") if isinstance(_DOCS_CACHE, dict) else None
        if allow_stale and cached:
            return {
                "documents": cached,
                "stale": True,
                "error": f"{type(e).__name__}: {e}",
                "cached_at": (_DOCS_CACHE or {}).get("ts"),
            }
        raise HTTPException(status_code=500, detail=f"Failed to load documents: {type(e).__name__}: {e}")


@app.get("/api/debug/llm")
def debug_llm() -> dict[str, Any]:
    """Return the resolved Vertex LLM config (no secrets)."""
    try:
        cfg = _vertex_llm_cfg()
        return {"vertex_llm": cfg}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


@app.post("/api/suites/{suite_id}/questions/import-yaml")
def import_questions_yaml(suite_id: str, body: dict = Body(...)) -> dict[str, Any]:
    _require_ready()
    try:
        sid = uuid.UUID(suite_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid suite_id")
    y = str(body.get("yaml") or "").strip()
    if not y:
        raise HTTPException(status_code=400, detail="yaml is required")
    try:
        data = yaml.safe_load(y) or {}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid yaml: {type(e).__name__}: {e}")
    qs = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(qs, list) or not qs:
        raise HTTPException(status_code=400, detail="yaml must contain top-level 'questions: [...]'")

    inserted = 0
    updated = 0
    errors: list[dict[str, Any]] = []
    conn = _conn(_qa_url())
    conn.autocommit = True
    try:
        cur = conn.cursor()
        for i, q in enumerate(qs, start=1):
            if not isinstance(q, dict):
                continue
            qid = str(q.get("id") or f"Q{i:03d}").strip()
            question = str(q.get("question") or "").strip()
            if not question:
                continue
            intent = str(q.get("intent") or "").strip().lower() or None
            bucket = str(q.get("bucket") or "").strip().lower() or None
            gold = q.get("gold") if isinstance(q.get("gold"), dict) else {}
            try:
                # Track insert vs update in a second query (keep logic simple)
                cur.execute("SELECT 1 FROM retrieval_eval_questions WHERE suite_id=%s AND qid=%s", (sid, qid))
                existed = cur.fetchone() is not None
                cur.execute(
                    """
                    INSERT INTO retrieval_eval_questions(id, suite_id, qid, intent, bucket, question, gold, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
                    ON CONFLICT (suite_id, qid)
                    DO UPDATE SET intent = EXCLUDED.intent,
                                  bucket = EXCLUDED.bucket,
                                  question = EXCLUDED.question,
                                  gold = EXCLUDED.gold,
                                  updated_at = NOW()
                    """,
                    (uuid.uuid4(), sid, qid, intent, bucket, question, json.dumps(gold)),
                )
                if existed:
                    updated += 1
                else:
                    inserted += 1
            except Exception as e:
                errors.append({"qid": qid, "error": str(e)})
        cur.execute("UPDATE retrieval_eval_suites SET updated_at = NOW() WHERE id = %s", (sid,))
        cur.close()
    finally:
        conn.close()

    cnt = _qa_exec("SELECT count(*)::int AS n FROM retrieval_eval_questions WHERE suite_id = %s", (sid,), fetch=True) or []
    n_total = int(cnt[0]["n"]) if cnt else None
    return {"status": "ok", "suite_id": str(sid), "inserted": inserted, "updated": updated, "errors": errors, "total": n_total}


@app.post("/api/suites/{suite_id}/questions/auto-generate")
def auto_generate_questions(suite_id: str, body: dict = Body(None)) -> dict[str, Any]:
    """
    Auto-generate a question set for the suite using an LLM, grounded in selected documents.
    - Fetches hierarchical paragraph evidence from published_rag_metadata for the selected documents.
    - Calls Vertex Gemini to produce YAML with gold.parent_metadata_ids referencing those evidence ids.
    - Imports the YAML into retrieval_eval_questions (same behavior as import-yaml).
    """
    _require_ready()
    try:
        sid = uuid.UUID(suite_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid suite_id")

    body = body or {}
    n_total = int(body.get("n_total") or 20)
    n_canonical = int(body.get("n_canonical") or max(2, n_total // 4))
    n_out = int(body.get("n_out_of_manual") or max(2, n_total // 6))
    n_factual = max(0, n_total - n_canonical - n_out)
    if n_total <= 0 or n_total > 80:
        raise HTTPException(status_code=400, detail="n_total must be 1..80")
    if n_canonical < 0 or n_out < 0 or n_factual < 0:
        raise HTTPException(status_code=400, detail="invalid bucket counts")

    # Load suite spec (for doc selection)
    suite_rows = _qa_exec("SELECT suite_spec FROM retrieval_eval_suites WHERE id=%s", (sid,), fetch=True) or []
    if not suite_rows:
        raise HTTPException(status_code=404, detail="suite not found")
    spec = suite_rows[0].get("suite_spec") if isinstance(suite_rows[0].get("suite_spec"), dict) else {}
    doc_ids_raw = spec.get("document_ids") or spec.get("document_id_list") or []
    document_ids = [str(x).strip() for x in doc_ids_raw] if isinstance(doc_ids_raw, list) else []
    document_ids = [d for d in document_ids if d]
    authority = str(spec.get("document_authority_level") or "").strip() or None
    if not document_ids and not authority:
        raise HTTPException(status_code=400, detail="Suite spec must include document_ids (recommended) or document_authority_level")

    chat_db_url = _chat_rag_url()
    if not chat_db_url:
        raise HTTPException(status_code=400, detail="CHAT_RAG_DATABASE_URL (or CHAT_DATABASE_URL) must be set")

    # If only authority was provided, pull a small set of doc_ids from that authority for generation.
    if not document_ids and authority:
        conn = psycopg2.connect(chat_db_url)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT document_id::text
                FROM published_rag_metadata
                WHERE document_authority_level = %s
                ORDER BY document_id::text
                LIMIT 50
                """,
                (authority,),
            )
            document_ids = [r[0] for r in cur.fetchall() if r and r[0]]
            cur.close()
        finally:
            conn.close()

    max_per_doc = int(body.get("max_paragraphs_per_doc") or 35)
    max_total = int(body.get("max_paragraphs_total") or 160)
    evidence = _fetch_evidence_candidates(chat_db_url, document_ids, max_per_doc=max_per_doc, max_total=max_total)
    if not evidence:
        raise HTTPException(status_code=400, detail="No hierarchical evidence found for selected documents (check publish/sync)")

    # Build prompt
    evidence_lines = []
    for e in evidence:
        evidence_lines.append(
            "\n".join(
                [
                    f"- id: {e.get('id')}",
                    f"  document_id: {e.get('document_id')}",
                    f"  document_name: {e.get('document_name')}",
                    f"  page_number: {e.get('page_number')}",
                    f"  section_path: {e.get('section_path')}",
                    f"  chapter_path: {e.get('chapter_path')}",
                    f"  text: |",
                    "    " + str(e.get("text") or "").replace("\n", "\n    "),
                ]
            )
        )

    prompt = "\n".join(
        [
            "You are generating a retrieval evaluation question set for a RAG system.",
            "We are evaluating retrieval only (BM25 sentences vs hierarchical vector retrieval).",
            "",
            "## Task",
            f"- Generate exactly {n_total} questions.",
            f"- Include exactly {n_canonical} canonical questions (summarization of a section).",
            f"- Include exactly {n_factual} factual questions (single fact answerable from one paragraph).",
            f"- Include exactly {n_out} out-of-manual questions (should abstain).",
            "",
            "## Output format (YAML only)",
            "Return YAML with top-level key `questions:` as a list of objects with keys:",
            "Do NOT wrap the YAML in triple backticks or any code fences. Output raw YAML only.",
            "- id: Q001, Q002, ... (unique)",
            "- intent: canonical|factual",
            "- bucket: in_manual|out_of_manual",
            "- question: string",
            "- gold: object",
            "",
            "## Gold labeling rules",
            "- For in_manual questions: gold.parent_metadata_ids MUST be a list with exactly 1 id, chosen from the evidence list below.",
            "  Use the evidence paragraph id that contains the answer/crux.",
            "- For out_of_manual questions: set gold.expect_in_manual=false and DO NOT include parent_metadata_ids.",
            "- Do not invent ids. Only use evidence ids provided below.",
            "",
            "## Evidence paragraphs (published_rag_metadata rows)",
            *evidence_lines,
            "",
            "Now produce the YAML.",
        ]
    )

    raw = _call_vertex_llm(prompt)
    y = _extract_yaml_block(raw)
    if not y or "questions:" not in y:
        raise HTTPException(status_code=500, detail="LLM did not return valid YAML with `questions:`")
    # Validate YAML quickly
    try:
        parsed = yaml.safe_load(y) or {}
        if not isinstance(parsed, dict) or not isinstance(parsed.get("questions"), list):
            raise ValueError("bad schema")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM YAML parse failed: {type(e).__name__}: {e}")

    # Import into suite using same upsert logic as import-yaml
    res = import_questions_yaml(suite_id=str(sid), body={"yaml": y})
    return {"status": "ok", "suite_id": str(sid), "yaml": y, "import": res, "evidence_count": len(evidence)}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _split_sentences(text: str) -> list[str]:
    if not (text or "").strip():
        return []
    t = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", t)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) > 420:
            sub = re.split(r"\s*;\s*|\s+\u2022\s+|\s+\-\s+", p)
            out.extend([s.strip() for s in sub if s.strip()])
        else:
            out.append(p)
    return out


@dataclass(frozen=True)
class SentenceDoc:
    sid: str
    parent_metadata_id: str
    sentence_text: str
    page_number: int | None
    section_path: str | None
    chapter_path: str | None
    document_display_name: str | None


def _fetch_paragraphs(chat_db_url: str, authority_level: str) -> list[dict[str, Any]]:
    conn = psycopg2.connect(chat_db_url)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT id,
                   document_id::text AS document_id,
                   text,
                   page_number,
                   section_path,
                   chapter_path,
                   document_display_name,
                   paragraph_index
            FROM published_rag_metadata
            WHERE document_authority_level = %s
              AND source_type = 'hierarchical'
            ORDER BY page_number NULLS LAST, paragraph_index NULLS LAST, id
            """,
            (authority_level,),
        )
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _fetch_paragraphs_for_documents(chat_db_url: str, document_ids: list[str]) -> list[dict[str, Any]]:
    doc_ids = [str(x).strip() for x in (document_ids or []) if str(x).strip()]
    if not doc_ids:
        return []
    conn = psycopg2.connect(chat_db_url)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT id,
                   document_id::text AS document_id,
                   text,
                   page_number,
                   section_path,
                   chapter_path,
                   document_display_name,
                   paragraph_index
            FROM published_rag_metadata
            WHERE document_id::text = ANY(%s)
              AND source_type = 'hierarchical'
            ORDER BY document_display_name NULLS LAST,
                     page_number NULLS LAST,
                     paragraph_index NULLS LAST,
                     id
            """,
            (doc_ids,),
        )
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _build_sentence_corpus(paragraph_rows: list[dict[str, Any]]) -> list[SentenceDoc]:
    corpus: list[SentenceDoc] = []
    for r in paragraph_rows:
        pid = str(r.get("id") or "")
        # Carry doc_id for post-filtering/debug later (not stored on SentenceDoc today).
        txt = (r.get("text") or "").strip()
        if not pid or not txt:
            continue
        if re.search(r"\.{6,}", txt[:250]):
            continue
        for i, s in enumerate(_split_sentences(txt), start=1):
            if len(s) < 25:
                continue
            sid = f"{pid}:{i}"
            corpus.append(
                SentenceDoc(
                    sid=sid,
                    parent_metadata_id=pid,
                    sentence_text=s,
                    page_number=r.get("page_number"),
                    section_path=r.get("section_path"),
                    chapter_path=r.get("chapter_path"),
                    document_display_name=r.get("document_display_name"),
                )
            )
    return corpus


def _gold_expect_in_manual(q: dict[str, Any]) -> bool:
    b = (q.get("bucket") or "").strip().lower()
    g = q.get("gold") or {}
    if isinstance(g, dict) and "expect_in_manual" in g:
        return bool(g.get("expect_in_manual"))
    return b != "out_of_manual"


def _gold_match_candidate(q: dict[str, Any], cand: SentenceDoc) -> dict[str, Any]:
    g = q.get("gold") or {}
    if not isinstance(g, dict):
        return {"matched": False, "why": None}
    parent_ids = g.get("parent_metadata_ids") or []
    if isinstance(parent_ids, str):
        parent_ids = [parent_ids]
    if isinstance(parent_ids, list) and parent_ids:
        if cand.parent_metadata_id in {str(x) for x in parent_ids if x}:
            return {"matched": True, "why": "parent_metadata_id"}
    hay = (cand.sentence_text or "").lower()
    contains: list[str] = []
    for key in ("answer_contains", "crux_contains"):
        v = g.get(key)
        if isinstance(v, str) and v.strip():
            contains.append(v.strip())
        elif isinstance(v, list):
            contains.extend([str(x).strip() for x in v if str(x).strip()])
    for needle in contains:
        if needle.lower() in hay:
            return {"matched": True, "why": f"contains:{needle[:48]}"}
    rx = g.get("answer_regex")
    if isinstance(rx, str) and rx.strip():
        try:
            if re.search(rx, cand.sentence_text or "", flags=re.IGNORECASE):
                return {"matched": True, "why": "answer_regex"}
        except re.error:
            pass
    return {"matched": False, "why": None}


def _sigmoid(x: float, k: float, x0: float) -> float:
    try:
        return 1.0 / (1.0 + pow(2.718281828, -k * (x - x0)))
    except Exception:
        return 0.0


def _sigmoid_normalize(raw_scores: list[float], k: float, x0: float) -> list[float]:
    return [float(_sigmoid(float(s), float(k), float(x0))) for s in raw_scores]


def _sigmoid_params_from_max_raw(max_raw_scores: list[float]) -> tuple[float, float]:
    xs = [float(x) for x in max_raw_scores if x is not None]
    if not xs:
        return (1.0, 0.0)
    xs.sort()
    p50 = xs[len(xs) // 2]
    p90 = xs[max(0, int(len(xs) * 0.9) - 1)]
    x0 = p50
    denom = (p90 - p50) if p90 != p50 else (abs(p50) + 1e-6)
    k = 2.2 / float(denom)
    return (float(k), float(x0))


def _run_bm25_eval(
    authority_level: str | None,
    document_ids: list[str] | None,
    questions: list[dict[str, Any]],
    top_k: int,
    abstain_threshold: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chat_db_url = _chat_rag_url()
    if not chat_db_url:
        raise RuntimeError("CHAT_RAG_DATABASE_URL (or CHAT_DATABASE_URL) must be set for BM25 corpus")
    if document_ids:
        paras = _fetch_paragraphs_for_documents(chat_db_url, document_ids)
    else:
        if not authority_level:
            raise RuntimeError("BM25 eval requires either authority_level or document_ids")
        paras = _fetch_paragraphs(chat_db_url, authority_level)
    corpus = _build_sentence_corpus(paras)
    if not corpus:
        raise RuntimeError("No corpus sentences found for authority_level")

    from rank_bm25 import BM25Okapi

    tokenized = [_tokenize(d.sentence_text) for d in corpus]
    bm25 = BM25Okapi(tokenized)

    max_raw_scores: list[float] = []
    for q in questions:
        q_tokens = _tokenize(q.get("question") or "")
        raw = bm25.get_scores(q_tokens)
        try:
            max_raw_scores.append(float(max(raw)) if len(raw) else 0.0)
        except Exception:
            max_raw_scores.append(0.0)
    k_val, x0 = _sigmoid_params_from_max_raw(max_raw_scores)

    per_q: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for q in questions:
        qid = str(q.get("id") or "").strip()
        question = q.get("question") or ""
        intent = (q.get("intent") or "").strip().lower()
        bucket = (q.get("bucket") or "").strip().lower()
        q_tokens = _tokenize(question)
        raw = bm25.get_scores(q_tokens)
        idxs = sorted(range(len(raw)), key=lambda j: float(raw[j]), reverse=True)[: int(top_k)]
        raw_top = [float(raw[j]) for j in idxs]
        docs_top = [corpus[j] for j in idxs]
        norm_top = _sigmoid_normalize(raw_top, k=k_val, x0=x0)
        max_norm = float(norm_top[0]) if norm_top else None

        expect_in_manual = _gold_expect_in_manual(q)
        would_answer = bool(max_norm is not None and max_norm >= float(abstain_threshold))
        fp = (not expect_in_manual) and would_answer

        best_rank = None
        best_why = None
        for rank, d in enumerate(docs_top, start=1):
            m = _gold_match_candidate(q, d)
            if m["matched"]:
                best_rank = rank
                best_why = m["why"]
                break

        per_q.append(
            {
                "qid": qid,
                "intent": intent,
                "bucket": bucket,
                "question": question,
                "expect_in_manual": expect_in_manual,
                "gold_best_rank": best_rank,
                "gold_match_why": best_why,
                "max_norm_score": max_norm,
                "would_answer": would_answer,
                "false_positive_answer": fp,
            }
        )

        for rank, (d, s_raw, s_norm) in enumerate(zip(docs_top, raw_top, norm_top), start=1):
            m = _gold_match_candidate(q, d)
            rows.append(
                {
                    "qid": qid,
                    "rank": int(rank),
                    "parent_metadata_id": d.parent_metadata_id,
                    "sentence_text": d.sentence_text,
                    "page_number": d.page_number,
                    "raw_score": float(s_raw),
                    "norm_score": float(s_norm),
                    "match": bool(m["matched"]),
                    "match_why": m["why"],
                }
            )
    return (per_q, rows)


def _vertex_cfg() -> dict[str, str]:
    project = _env("VERTEX_PROJECT")
    region = _env("VERTEX_REGION", "us-central1")
    endpoint_id = _env("VERTEX_INDEX_ENDPOINT_ID")
    deployed_id = _env("VERTEX_DEPLOYED_INDEX_ID")
    if not project or not endpoint_id or not deployed_id:
        raise RuntimeError("Missing Vertex config: set VERTEX_PROJECT, VERTEX_INDEX_ENDPOINT_ID, VERTEX_DEPLOYED_INDEX_ID")
    return {"project": project, "region": region, "endpoint_id": endpoint_id, "deployed_id": deployed_id}


def _vertex_llm_cfg() -> dict[str, str]:
    # Prefer extracting the project from the index endpoint resource name if present.
    # This avoids using a placeholder project id (e.g. "mobiusos-new") that doesn't have model access.
    def _project_from_resource(res: str) -> str | None:
        m = re.search(r"projects/([^/]+)/", (res or "").strip())
        return m.group(1) if m else None

    endpoint_res = (
        _env("VERTEX_INDEX_ENDPOINT_ID")
        or _env("CHAT_VERTEX_INDEX_ENDPOINT_ID")
        or ""
    )
    project = (
        _project_from_resource(endpoint_res)
        or _env("VERTEX_PROJECT")
        or _env("VERTEX_PROJECT_ID")
        or _env("CHAT_VERTEX_PROJECT_ID")
        or _env("VERTEX_PROJECT_ID")
    )
    region = _env("VERTEX_REGION", "") or _env("VERTEX_LOCATION", "") or _env("CHAT_VERTEX_LOCATION", "") or "us-central1"
    # Match chat defaults unless explicitly overridden
    model = (
        _env("EVAL_LLM_MODEL", "")
        or _env("RETRIEVAL_EVAL_LLM_MODEL", "")
        or _env("CHAT_VERTEX_MODEL", "")
        or _env("VERTEX_MODEL", "")
        or "gemini-2.0-flash"
    )
    if not project:
        raise RuntimeError("Missing Vertex project: set VERTEX_INDEX_ENDPOINT_ID (preferred) or VERTEX_PROJECT/CHAT_VERTEX_PROJECT_ID")
    return {"project": project, "region": region, "model": model}


def _call_vertex_llm(prompt: str) -> str:
    """
    Call a Vertex Gemini model to generate YAML.
    Returns raw model text (caller is responsible for extracting YAML).
    """
    cfg = _vertex_llm_cfg()
    import vertexai
    try:
        from vertexai.generative_models import GenerativeModel  # type: ignore
    except Exception as e:
        raise RuntimeError(f"Vertex generative models not available: {type(e).__name__}: {e}")

    vertexai.init(project=cfg["project"], location=cfg["region"])
    model = GenerativeModel(cfg["model"])
    resp = model.generate_content(
        prompt,
        generation_config={
            "temperature": float(_env("EVAL_LLM_TEMPERATURE", "0.2") or "0.2"),
            "max_output_tokens": int(_env("EVAL_LLM_MAX_OUTPUT_TOKENS", "4096") or "4096"),
        },
    )
    text = getattr(resp, "text", None)
    if not text:
        # Fallback: stitch from candidates if present
        try:
            cands = getattr(resp, "candidates", None) or []
            parts = []
            for c in cands:
                content = getattr(c, "content", None)
                if content and getattr(content, "parts", None):
                    for p in content.parts:
                        t = getattr(p, "text", None)
                        if t:
                            parts.append(t)
            text = "\n".join(parts).strip()
        except Exception:
            text = ""
    return (text or "").strip()


def _extract_yaml_block(text: str) -> str:
    """
    Extract YAML from a model response.
    Accepts either raw YAML or fenced ```yaml blocks.
    """
    t = (text or "").strip()
    if not t:
        return ""
    m = re.search(r"```yaml\s*([\s\S]*?)```", t, flags=re.IGNORECASE)
    if m:
        return (m.group(1) or "").strip()
    m2 = re.search(r"```\s*([\s\S]*?)```", t)
    if m2 and "questions:" in (m2.group(1) or ""):
        return (m2.group(1) or "").strip()
    # Handle unclosed fences: if there's an opening ``` (optionally with yaml), strip first fence line
    # and stop at the next fence line if it exists.
    if "```" in t:
        lines = t.splitlines()
        # Find first fence line
        start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                start = i
                break
        if start is not None:
            body_lines = lines[start + 1 :]
            end = None
            for j, line in enumerate(body_lines):
                if line.strip().startswith("```"):
                    end = j
                    break
            if end is not None:
                body_lines = body_lines[:end]
            cleaned = "\n".join(body_lines).strip()
            if cleaned:
                return cleaned
    return t


def _fetch_evidence_candidates(
    chat_db_url: str,
    document_ids: list[str],
    *,
    max_per_doc: int = 40,
    max_total: int = 180,
) -> list[dict[str, Any]]:
    """
    Fetch hierarchical paragraphs as candidate evidence for question generation.
    Returns list of dicts: {id, document_id, document_name, page_number, section_path, chapter_path, text}
    """
    doc_ids = [str(x).strip() for x in (document_ids or []) if str(x).strip()]
    if not doc_ids:
        return []
    conn = psycopg2.connect(chat_db_url)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT id::text AS id,
                   document_id::text AS document_id,
                   COALESCE(document_display_name, document_filename, document_id::text) AS document_name,
                   page_number,
                   section_path,
                   chapter_path,
                   text
            FROM published_rag_metadata
            WHERE document_id::text = ANY(%s)
              AND source_type = 'hierarchical'
            ORDER BY document_id, page_number NULLS LAST, paragraph_index NULLS LAST, id
            """,
            (doc_ids,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    finally:
        conn.close()

    # Filter + sample
    def ok_text(s: str) -> bool:
        if not (s or "").strip():
            return False
        if re.search(r"\.{6,}", s[:220]):  # TOC dot leaders
            return False
        return len(s.strip()) >= 200

    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        txt = str(r.get("text") or "")
        if not ok_text(txt):
            continue
        did = str(r.get("document_id") or "")
        grouped.setdefault(did, []).append(r)

    picked: list[dict[str, Any]] = []
    for did in doc_ids:
        rs = grouped.get(did) or []
        # Prefer paragraphs with section/chapter labels (better for canonical)
        rs.sort(
            key=lambda x: (
                0 if (x.get("section_path") or x.get("chapter_path")) else 1,
                -(len(str(x.get("text") or ""))),
            )
        )
        picked.extend(rs[: max(0, int(max_per_doc))])

    # Cap total and trim text
    picked = picked[: max_total]
    for r in picked:
        t = str(r.get("text") or "").strip()
        # Keep enough context for question generation but avoid giant prompt.
        if len(t) > 1200:
            r["text"] = t[:1200].rsplit(" ", 1)[0] + "…"
        else:
            r["text"] = t
    return picked


def _embed_query(text: str, project: str, region: str) -> list[float]:
    import vertexai
    from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

    model = _env("VERTEX_EMBEDDING_MODEL", "gemini-embedding-001")
    dims = int(_env("VERTEX_EMBEDDING_DIMS", "1536") or "1536")
    task_type = _env("VERTEX_EMBEDDING_TASK_TYPE", "RETRIEVAL_DOCUMENT")

    vertexai.init(project=project, location=region)
    m = TextEmbeddingModel.from_pretrained(model)
    inputs = [TextEmbeddingInput(text, task_type=task_type)]
    resp = m.get_embeddings(inputs, output_dimensionality=dims)
    if not resp or not resp[0].values:
        raise RuntimeError("Empty embedding returned from Vertex")
    return list(resp[0].values)


def _vertex_find_neighbors(
    endpoint_id: str,
    deployed_index_id: str,
    query_embedding: list[float],
    k: int,
    authority_level: str | None,
    payer: str | None,
    state: str | None,
    program: str | None,
    project: str,
    region: str,
) -> list[dict[str, Any]]:
    from google.cloud import aiplatform
    from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import Namespace

    aiplatform.init(project=project, location=region)
    endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=endpoint_id)
    namespaces = [Namespace(name="source_type", allow_tokens=["hierarchical"], deny_tokens=[])]
    if authority_level:
        namespaces.append(Namespace(name="document_authority_level", allow_tokens=[authority_level], deny_tokens=[]))
    if payer:
        namespaces.append(Namespace(name="document_payer", allow_tokens=[payer], deny_tokens=[]))
    if state:
        namespaces.append(Namespace(name="document_state", allow_tokens=[state], deny_tokens=[]))
    if program:
        namespaces.append(Namespace(name="document_program", allow_tokens=[program], deny_tokens=[]))
    resp = endpoint.find_neighbors(
        deployed_index_id=deployed_index_id,
        queries=[query_embedding],
        num_neighbors=int(k),
        filter=namespaces,
    )
    neighbors = resp[0] if resp else []
    out: list[dict[str, Any]] = []
    for n in neighbors:
        nid = getattr(n, "id", None)
        if not nid:
            continue
        dist = getattr(n, "distance", None)
        out.append({"id": str(nid), "distance": float(dist) if dist is not None else None})
    return out


def _similarity_from_distance(distance: float | None) -> float | None:
    if distance is None:
        return None
    try:
        d = float(distance)
    except Exception:
        return None
    return max(0.0, min(1.0, 1.0 - d / 2.0))


def _fetch_metadata_by_id(chat_db_url: str, ids: list[str]) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    conn = psycopg2.connect(chat_db_url)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT id,
                   document_id::text AS document_id,
                   document_display_name,
                   text,
                   page_number,
                   source_type
            FROM published_rag_metadata
            WHERE id::text = ANY(%s)
            """,
            (ids,),
        )
        rows = cur.fetchall()
        cur.close()
        return {str(r["id"]): dict(r) for r in rows}
    finally:
        conn.close()


def _run_hier_eval(
    authority_level: str | None,
    document_ids: list[str] | None,
    payer: str | None,
    state: str | None,
    program: str | None,
    questions: list[dict[str, Any]],
    top_k: int,
    answer_threshold: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chat_db_url = _chat_rag_url()
    if not chat_db_url:
        raise RuntimeError("CHAT_RAG_DATABASE_URL (or CHAT_DATABASE_URL) must be set to fetch metadata")

    vcfg = _vertex_cfg()

    per_q: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    doc_allow = {str(x) for x in (document_ids or []) if str(x).strip()} if document_ids else None
    # Fetch more than top_k when we need to post-filter by document.
    fetch_k = int(top_k)
    if doc_allow:
        fetch_k = max(int(top_k) * 8, 50)
        fetch_k = min(fetch_k, 200)
    for q in questions:
        qid = str(q.get("id") or "").strip()
        question = q.get("question") or ""
        intent = (q.get("intent") or "").strip().lower()
        bucket = (q.get("bucket") or "").strip().lower()
        gold = q.get("gold") if isinstance(q.get("gold"), dict) else {}
        gold_parents = gold.get("parent_metadata_ids") or []
        if isinstance(gold_parents, str):
            gold_parents = [gold_parents]
        gold_set = {str(x) for x in gold_parents if str(x).strip()}

        query_emb = _embed_query(question, project=vcfg["project"], region=vcfg["region"])
        neigh = _vertex_find_neighbors(
            endpoint_id=vcfg["endpoint_id"],
            deployed_index_id=vcfg["deployed_id"],
            query_embedding=query_emb,
            k=fetch_k,
            authority_level=authority_level,
            payer=payer,
            state=state,
            program=program,
            project=vcfg["project"],
            region=vcfg["region"],
        )
        ids = [n["id"] for n in neigh if n.get("id")]
        meta = _fetch_metadata_by_id(chat_db_url, ids)

        # If the suite selected specific documents, post-filter neighbors by document_id.
        if doc_allow:
            filtered = []
            for n in neigh:
                mid = str(n.get("id") or "")
                m = meta.get(mid) or {}
                did = str(m.get("document_id") or "")
                if did and did in doc_allow:
                    filtered.append(n)
                if len(filtered) >= int(top_k):
                    break
            neigh = filtered

        best_rank = None
        for rank, n in enumerate(neigh, start=1):
            if str(n.get("id") or "") in gold_set and gold_set:
                best_rank = rank
                break
        top1_sim = _similarity_from_distance(neigh[0].get("distance")) if neigh else None
        expect_in_manual = _gold_expect_in_manual(q)
        would_answer = bool(top1_sim is not None and float(top1_sim) >= float(answer_threshold))
        fp = (not expect_in_manual) and would_answer

        per_q.append(
            {
                "qid": qid,
                "intent": intent,
                "bucket": bucket,
                "question": question,
                "expect_in_manual": expect_in_manual,
                "gold_best_rank": best_rank,
                "top1_similarity": top1_sim,
                "would_answer": would_answer,
                "false_positive_answer": fp,
            }
        )

        for rank, n in enumerate(neigh, start=1):
            nid = str(n.get("id") or "")
            sim = _similarity_from_distance(n.get("distance"))
            r = meta.get(nid) or {}
            txt = str(r.get("text") or "")
            snippet = txt[:220].replace("\n", " ").strip()
            rows.append(
                {
                    "qid": qid,
                    "rank": int(rank),
                    "neighbor_id": nid,
                    "similarity": sim,
                    "page_number": r.get("page_number"),
                    "source_type": r.get("source_type"),
                    "snippet": snippet,
                    "match": bool(nid in gold_set) if gold_set else False,
                    "match_why": "parent_metadata_id" if (nid in gold_set and gold_set) else None,
                }
            )
    return (per_q, rows)


def _hit_flags(best_rank: int | None) -> dict[str, bool | None]:
    if best_rank is None:
        return {"at_1": None, "at_3": None, "at_5": None, "at_10": None}
    return {"at_1": best_rank <= 1, "at_3": best_rank <= 3, "at_5": best_rank <= 5, "at_10": best_rank <= 10}


def _load_suite_questions(suite_id: uuid.UUID, limit: int | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    suite_rows = _qa_exec(
        "SELECT id::text AS id, name, description, suite_spec FROM retrieval_eval_suites WHERE id = %s",
        (suite_id,),
        fetch=True,
    ) or []
    if not suite_rows:
        raise RuntimeError("suite not found")
    q_rows = _qa_exec(
        """
        SELECT qid, intent, bucket, question, gold
        FROM retrieval_eval_questions
        WHERE suite_id = %s
        ORDER BY qid ASC
        """,
        (suite_id,),
        fetch=True,
    ) or []
    qs: list[dict[str, Any]] = []
    for r in q_rows:
        qs.append(
            {
                "id": str(r.get("qid") or ""),
                "intent": r.get("intent"),
                "bucket": r.get("bucket"),
                "question": r.get("question"),
                "gold": r.get("gold") if isinstance(r.get("gold"), dict) else {},
            }
        )
    if limit is not None:
        qs = qs[: max(0, int(limit))]
    return (suite_rows[0], qs)


def _set_run_status(run_id: uuid.UUID, status: str, *, summary: dict | None = None, error: str | None = None) -> None:
    fields = ["status = %s", "updated_at = NOW()"]
    params: list[Any] = [status]
    if status == "running":
        fields.append("started_at = COALESCE(started_at, NOW())")
    if status in ("completed", "failed"):
        fields.append("completed_at = NOW()")
    if summary is not None:
        fields.append("summary = %s::jsonb")
        params.append(json.dumps(summary))
    if error is not None:
        fields.append("error = %s")
        params.append(error)
    params.append(run_id)
    _qa_exec(f"UPDATE retrieval_eval_runs SET {', '.join(fields)} WHERE id = %s", tuple(params))


def _insert_run_outputs(
    run_id: uuid.UUID,
    suite_id: uuid.UUID,
    questions: list[dict[str, Any]],
    bm25_per_q: list[dict[str, Any]],
    bm25_rows: list[dict[str, Any]],
    hier_per_q: list[dict[str, Any]],
    hier_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    bm_by = {str(r["qid"]): r for r in bm25_per_q}
    h_by = {str(r["qid"]): r for r in hier_per_q}
    q_by = {str(q["id"]): q for q in questions}

    conn = _conn(_qa_url())
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM retrieval_eval_run_retrieval_rows WHERE run_id = %s", (run_id,))
        cur.execute("DELETE FROM retrieval_eval_run_question_metrics WHERE run_id = %s", (run_id,))

        for qid, q in q_by.items():
            b = bm_by.get(qid) or {}
            h = h_by.get(qid) or {}
            gold = (q.get("gold") or {}) if isinstance(q.get("gold"), dict) else {}
            parents = gold.get("parent_metadata_ids") or []
            if isinstance(parents, str):
                parents = [parents]
            parent_ids = [str(x) for x in parents if str(x).strip()]
            b_rank = b.get("gold_best_rank")
            h_rank = h.get("gold_best_rank")
            b_hits = _hit_flags(int(b_rank) if b_rank is not None else None)
            h_hits = _hit_flags(int(h_rank) if h_rank is not None else None)

            cur.execute(
                """
                INSERT INTO retrieval_eval_run_question_metrics(
                  id, run_id, suite_id, qid, intent, bucket, question, expect_in_manual, gold_parent_ids,
                  bm25_gold_rank, bm25_hit_at_1, bm25_hit_at_3, bm25_hit_at_5, bm25_hit_at_10,
                  bm25_max_norm_score, bm25_would_answer, bm25_false_positive_answer,
                  hier_gold_rank, hier_hit_at_1, hier_hit_at_3, hier_hit_at_5, hier_hit_at_10,
                  hier_top1_similarity, hier_would_answer, hier_false_positive_answer,
                  created_at
                )
                VALUES (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s,
                  %s, %s, %s,
                  %s, %s, %s, %s, %s,
                  %s, %s, %s,
                  NOW()
                )
                """,
                (
                    uuid.uuid4(),
                    run_id,
                    suite_id,
                    qid,
                    q.get("intent"),
                    q.get("bucket"),
                    q.get("question"),
                    bool(b.get("expect_in_manual")) if "expect_in_manual" in b else bool(h.get("expect_in_manual")),
                    parent_ids if parent_ids else None,
                    int(b_rank) if b_rank is not None else None,
                    b_hits["at_1"],
                    b_hits["at_3"],
                    b_hits["at_5"],
                    b_hits["at_10"],
                    float(b.get("max_norm_score")) if b.get("max_norm_score") is not None else None,
                    bool(b.get("would_answer")) if "would_answer" in b else None,
                    bool(b.get("false_positive_answer")) if "false_positive_answer" in b else None,
                    int(h_rank) if h_rank is not None else None,
                    h_hits["at_1"],
                    h_hits["at_3"],
                    h_hits["at_5"],
                    h_hits["at_10"],
                    float(h.get("top1_similarity")) if h.get("top1_similarity") is not None else None,
                    bool(h.get("would_answer")) if "would_answer" in h else None,
                    bool(h.get("false_positive_answer")) if "false_positive_answer" in h else None,
                ),
            )

        for r in bm25_rows:
            cur.execute(
                """
                INSERT INTO retrieval_eval_run_retrieval_rows(
                  id, run_id, suite_id, qid, method, rank, item_id, parent_metadata_id,
                  score, raw_score, match, match_why, page_number, source_type, snippet, created_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                """,
                (
                    uuid.uuid4(),
                    run_id,
                    suite_id,
                    str(r.get("qid") or ""),
                    "bm25",
                    int(r.get("rank") or 0),
                    str(r.get("parent_metadata_id") or ""),
                    str(r.get("parent_metadata_id") or ""),
                    float(r.get("norm_score")) if r.get("norm_score") is not None else None,
                    float(r.get("raw_score")) if r.get("raw_score") is not None else None,
                    bool(r.get("match") or False),
                    r.get("match_why"),
                    int(r.get("page_number")) if r.get("page_number") is not None else None,
                    "hierarchical",
                    str(r.get("sentence_text") or "")[:240],
                ),
            )

        for r in hier_rows:
            cur.execute(
                """
                INSERT INTO retrieval_eval_run_retrieval_rows(
                  id, run_id, suite_id, qid, method, rank, item_id, parent_metadata_id,
                  score, raw_score, match, match_why, page_number, source_type, snippet, created_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                """,
                (
                    uuid.uuid4(),
                    run_id,
                    suite_id,
                    str(r.get("qid") or ""),
                    "hier",
                    int(r.get("rank") or 0),
                    str(r.get("neighbor_id") or ""),
                    str(r.get("neighbor_id") or ""),
                    float(r.get("similarity")) if r.get("similarity") is not None else None,
                    None,
                    bool(r.get("match") or False),
                    r.get("match_why"),
                    int(r.get("page_number")) if r.get("page_number") is not None else None,
                    r.get("source_type"),
                    str(r.get("snippet") or "")[:240],
                ),
            )
        cur.close()
    finally:
        conn.close()

    def _as_int(x) -> int | None:
        try:
            return int(x) if x is not None else None
        except Exception:
            return None

    def _rate(num: int, denom: int) -> float:
        return float(num) / float(denom) if denom else 0.0

    # Summary (computed from the same per-q objects we persisted)
    with_gold = 0
    bm_hit1 = bm_hit3 = bm_hit5 = bm_hit10 = 0
    hi_hit1 = hi_hit3 = hi_hit5 = hi_hit10 = 0
    out_total = 0
    bm_fp = 0
    hi_fp = 0

    for qid, q in q_by.items():
        gold = (q.get("gold") or {}) if isinstance(q.get("gold"), dict) else {}
        parents = gold.get("parent_metadata_ids") or []
        if isinstance(parents, str):
            parents = [parents]
        parent_ids = [str(x) for x in parents if str(x).strip()]
        b = bm_by.get(qid) or {}
        h = h_by.get(qid) or {}

        expect_in_manual = bool(b.get("expect_in_manual")) if "expect_in_manual" in b else bool(h.get("expect_in_manual"))
        if not expect_in_manual:
            out_total += 1
            bm_fp += 1 if bool(b.get("false_positive_answer")) else 0
            hi_fp += 1 if bool(h.get("false_positive_answer")) else 0

        b_rank = _as_int(b.get("gold_best_rank"))
        h_rank = _as_int(h.get("gold_best_rank"))

        if parent_ids:
            with_gold += 1
            bm_hit1 += 1 if (b_rank is not None and b_rank <= 1) else 0
            bm_hit3 += 1 if (b_rank is not None and b_rank <= 3) else 0
            bm_hit5 += 1 if (b_rank is not None and b_rank <= 5) else 0
            bm_hit10 += 1 if (b_rank is not None and b_rank <= 10) else 0

            hi_hit1 += 1 if (h_rank is not None and h_rank <= 1) else 0
            hi_hit3 += 1 if (h_rank is not None and h_rank <= 3) else 0
            hi_hit5 += 1 if (h_rank is not None and h_rank <= 5) else 0
            hi_hit10 += 1 if (h_rank is not None and h_rank <= 10) else 0

    total = len(questions)
    summary = {
        "run_id": str(run_id),
        "questions_total": total,
        "questions_with_gold": with_gold,
        "questions_out_of_manual": out_total,
        "bm25": {
            "hit_at_1": _rate(bm_hit1, with_gold),
            "hit_at_3": _rate(bm_hit3, with_gold),
            "hit_at_5": _rate(bm_hit5, with_gold),
            "hit_at_10": _rate(bm_hit10, with_gold),
            "false_positive_answer_count": bm_fp,
        },
        "hier": {
            "hit_at_1": _rate(hi_hit1, with_gold),
            "hit_at_3": _rate(hi_hit3, with_gold),
            "hit_at_5": _rate(hi_hit5, with_gold),
            "hit_at_10": _rate(hi_hit10, with_gold),
            "false_positive_answer_count": hi_fp,
        },
    }
    return summary


_RUN_LOCK = threading.Lock()
_RUN_THREADS: dict[str, threading.Thread] = {}


def _run_eval_background(run_id: uuid.UUID, suite_id: uuid.UUID, suite_spec: dict[str, Any]) -> None:
    try:
        _set_run_status(run_id, "running")
        authority = str(suite_spec.get("document_authority_level") or "").strip() or None
        doc_ids_raw = suite_spec.get("document_ids") or suite_spec.get("document_id_list") or []
        document_ids = [str(x).strip() for x in doc_ids_raw] if isinstance(doc_ids_raw, list) else []
        document_ids = [d for d in document_ids if d]
        if not authority and not document_ids:
            raise RuntimeError("suite_spec requires either document_authority_level or document_ids")
        top_k = int(suite_spec.get("top_k") or 10)
        limit_questions = suite_spec.get("limit_questions")
        bm25_thresh = float(suite_spec.get("bm25_answer_threshold") or 0.65)
        hier_thresh = float(suite_spec.get("hier_answer_threshold") or 0.88)
        payer = str(suite_spec.get("document_payer") or "").strip() or None
        state = str(suite_spec.get("document_state") or "").strip() or None
        program = str(suite_spec.get("document_program") or "").strip() or None

        suite, questions = _load_suite_questions(suite_id, limit=int(limit_questions) if limit_questions is not None else None)
        if not questions:
            raise RuntimeError("suite has no questions")

        bm25_per_q, bm25_rows = _run_bm25_eval(
            authority_level=authority,
            document_ids=document_ids or None,
            questions=questions,
            top_k=top_k,
            abstain_threshold=bm25_thresh,
        )
        hier_per_q, hier_rows = _run_hier_eval(
            authority_level=authority,
            document_ids=document_ids or None,
            payer=payer,
            state=state,
            program=program,
            questions=questions,
            top_k=top_k,
            answer_threshold=hier_thresh,
        )

        summary = _insert_run_outputs(
            run_id=run_id,
            suite_id=suite_id,
            questions=questions,
            bm25_per_q=bm25_per_q,
            bm25_rows=bm25_rows,
            hier_per_q=hier_per_q,
            hier_rows=hier_rows,
        )
        summary["suite_id"] = str(suite_id)
        summary["suite_name"] = suite.get("name")
        summary["suite_spec"] = suite_spec
        _set_run_status(run_id, "completed", summary=summary)
    except Exception as e:
        _set_run_status(run_id, "failed", error=f"{type(e).__name__}: {e}")


@app.post("/api/suites/{suite_id}/runs")
def start_run(suite_id: str, body: dict = Body(None)) -> dict[str, Any]:
    _require_ready()
    try:
        sid = uuid.UUID(suite_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid suite_id")
    suite_rows = _qa_exec("SELECT id::text AS id, suite_spec FROM retrieval_eval_suites WHERE id = %s", (sid,), fetch=True) or []
    if not suite_rows:
        raise HTTPException(status_code=404, detail="suite not found")
    spec = suite_rows[0].get("suite_spec") if isinstance(suite_rows[0].get("suite_spec"), dict) else {}
    body = body or {}
    override = body.get("suite_spec_override") if isinstance(body.get("suite_spec_override"), dict) else {}
    merged = dict(spec or {})
    merged.update(override)

    rid = uuid.uuid4()
    _qa_exec(
        """
        INSERT INTO retrieval_eval_runs(id, suite_id, status, params, summary, created_at, updated_at)
        VALUES (%s, %s, 'queued', %s::jsonb, '{}'::jsonb, NOW(), NOW())
        """,
        (rid, sid, json.dumps({"suite_spec": merged})),
    )
    _qa_exec("UPDATE retrieval_eval_suites SET suite_spec = %s::jsonb, updated_at = NOW() WHERE id = %s", (json.dumps(merged), sid))

    t = threading.Thread(target=_run_eval_background, args=(rid, sid, merged), daemon=True)
    with _RUN_LOCK:
        _RUN_THREADS[str(rid)] = t
    t.start()
    return {"status": "ok", "run_id": str(rid)}


@app.get("/api/runs")
def list_runs(suite_id: str | None = None, limit: int = 50) -> dict[str, Any]:
    _require_ready()
    lim = max(1, min(int(limit or 50), 500))
    params: list[Any] = []
    where = []
    if suite_id:
        try:
            params.append(uuid.UUID(suite_id))
            where.append("suite_id = %s")
        except Exception:
            raise HTTPException(status_code=400, detail="invalid suite_id")
    wsql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = _qa_exec(
        f"""
        SELECT id::text AS id, suite_id::text AS suite_id, status, params, summary, error, created_at, started_at, completed_at, updated_at
        FROM retrieval_eval_runs
        {wsql}
        ORDER BY created_at DESC
        LIMIT {lim}
        """,
        tuple(params) if params else None,
        fetch=True,
    ) or []
    return {"runs": rows}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    _require_ready()
    try:
        rid = uuid.UUID(run_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid run_id")
    runs = _qa_exec(
        """
        SELECT id::text AS id, suite_id::text AS suite_id, status, params, summary, error, created_at, started_at, completed_at, updated_at
        FROM retrieval_eval_runs
        WHERE id = %s
        """,
        (rid,),
        fetch=True,
    ) or []
    if not runs:
        raise HTTPException(status_code=404, detail="run not found")
    metrics = _qa_exec(
        """
        SELECT qid, intent, bucket, question, expect_in_manual, gold_parent_ids,
               bm25_gold_rank, bm25_hit_at_1, bm25_hit_at_3, bm25_hit_at_5, bm25_hit_at_10, bm25_max_norm_score, bm25_would_answer, bm25_false_positive_answer,
               hier_gold_rank, hier_hit_at_1, hier_hit_at_3, hier_hit_at_5, hier_hit_at_10, hier_top1_similarity, hier_would_answer, hier_false_positive_answer
        FROM retrieval_eval_run_question_metrics
        WHERE run_id = %s
        ORDER BY qid ASC
        """,
        (rid,),
        fetch=True,
    ) or []
    return {"run": runs[0], "questions": metrics}


@app.get("/api/runs/{run_id}/questions/{qid}")
def get_run_question_detail(run_id: str, qid: str) -> dict[str, Any]:
    _require_ready()
    try:
        rid = uuid.UUID(run_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid run_id")
    qid = (qid or "").strip()
    if not qid:
        raise HTTPException(status_code=400, detail="qid is required")
    m = _qa_exec(
        "SELECT * FROM retrieval_eval_run_question_metrics WHERE run_id = %s AND qid = %s",
        (rid, qid),
        fetch=True,
    ) or []
    if not m:
        raise HTTPException(status_code=404, detail="question not found in run")
    rows = _qa_exec(
        """
        SELECT method, rank, item_id, score, raw_score, match, match_why, page_number, source_type, snippet
        FROM retrieval_eval_run_retrieval_rows
        WHERE run_id = %s AND qid = %s
        ORDER BY method ASC, rank ASC
        """,
        (rid, qid),
        fetch=True,
    ) or []
    return {"metric": m[0], "rows": rows}

