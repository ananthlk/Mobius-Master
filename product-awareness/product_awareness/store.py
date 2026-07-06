"""Pluggable vector store.

Prod: Chroma (a dedicated ``product_docs`` collection — its own DB, no contamination
of the policy corpus). Offline/dev+test: a numpy cosine store persisted as .npz + .jsonl,
so ingest/search run with numpy alone. Both speak the same tiny protocol.

Selection (``PRODUCT_DOCS_STORE``): ``auto`` (default) → Chroma if importable, else
numpy; ``chroma`` → force Chroma; ``numpy`` → force the local store.
"""
from __future__ import annotations

import json
import os
from typing import Any, Protocol

import numpy as np

from . import config


class Store(Protocol):
    def reset(self) -> None: ...
    def add(self, ids: list[str], vectors: np.ndarray,
            metadatas: list[dict], documents: list[str]) -> None: ...
    def query(self, vector: np.ndarray, k: int,
              where: dict | None = None) -> list[dict]: ...
    def count(self) -> int: ...


def _normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


def _matches(md: dict, where: dict | None) -> bool:
    if not where:
        return True
    return all(md.get(k) == v for k, v in where.items())


class NumpyStore:
    """Local cosine store. Vectors are L2-normalized on add, so dot == cosine."""

    def __init__(self, collection: str = config.COLLECTION, index_dir=config.INDEX_DIR):
        self.name = "numpy"
        self.collection = collection
        self._dir = index_dir
        self._vecs_path = index_dir / f"{collection}.npz"
        self._meta_path = index_dir / f"{collection}.jsonl"
        self._vectors: np.ndarray | None = None
        self._rows: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self._vecs_path.exists() and self._meta_path.exists():
            self._vectors = np.load(self._vecs_path)["vectors"]
            self._rows = [json.loads(l) for l in self._meta_path.read_text().splitlines() if l.strip()]

    def reset(self) -> None:
        self._vectors = None
        self._rows = []
        for p in (self._vecs_path, self._meta_path):
            if p.exists():
                p.unlink()

    def add(self, ids, vectors, metadatas, documents) -> None:
        vecs = np.vstack([_normalize(v) for v in vectors]).astype(np.float32)
        self._vectors = vecs if self._vectors is None else np.vstack([self._vectors, vecs])
        self._rows.extend(
            {"id": i, "metadata": m, "document": d}
            for i, m, d in zip(ids, metadatas, documents)
        )
        self._persist()

    def _persist(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(self._vecs_path, vectors=self._vectors)
        with self._meta_path.open("w") as f:
            for r in self._rows:
                f.write(json.dumps(r) + "\n")

    def query(self, vector, k, where=None) -> list[dict]:
        if self._vectors is None or not self._rows:
            return []
        q = _normalize(vector)
        sims = self._vectors @ q
        order = np.argsort(-sims)
        out: list[dict] = []
        for idx in order:
            row = self._rows[int(idx)]
            if not _matches(row["metadata"], where):
                continue
            out.append({"id": row["id"], "score": float(sims[idx]),
                        "metadata": row["metadata"], "document": row["document"]})
            if len(out) >= k:
                break
        return out

    def count(self) -> int:
        return len(self._rows)


class ChromaStore:
    """Production backend — a dedicated Chroma collection (cosine)."""

    def __init__(self, collection: str = config.COLLECTION, index_dir=config.INDEX_DIR):
        import chromadb  # lazy

        self.name = "chroma"
        self.collection_name = collection
        index_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(index_dir))
        self._coll = self._client.get_or_create_collection(
            name=collection, metadata={"hnsw:space": "cosine"})

    def reset(self) -> None:
        try:
            self._client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._coll = self._client.get_or_create_collection(
            name=self.collection_name, metadata={"hnsw:space": "cosine"})

    def add(self, ids, vectors, metadatas, documents) -> None:
        self._coll.upsert(
            ids=ids,
            embeddings=[list(map(float, v)) for v in vectors],
            metadatas=metadatas,
            documents=documents,
        )

    @staticmethod
    def _chroma_where(where: dict | None) -> dict | None:
        # Chroma requires $and to combine multiple equality conditions.
        if not where:
            return None
        if len(where) == 1:
            return dict(where)
        return {"$and": [{k: v} for k, v in where.items()]}

    def query(self, vector, k, where=None) -> list[dict]:
        res = self._coll.query(
            query_embeddings=[list(map(float, vector))],
            n_results=k,
            where=self._chroma_where(where),
        )
        out: list[dict] = []
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        for i, dist, m, d in zip(ids, dists, metas, docs):
            out.append({"id": i, "score": 1.0 - float(dist),  # cosine distance -> similarity
                        "metadata": m, "document": d})
        return out

    def count(self) -> int:
        return self._coll.count()


class PgVectorStore:
    """Production backend — pgvector on the existing Cloud SQL Postgres.

    Our OWN table (``product_docs_embeddings``): real, first-class columns for every
    facet (module/audience/doc_type/status/…), so filtering is native SQL with no
    shared-schema whitelist to fight, and the policy corpus is untouched. Uses the same
    pgvector idiom as the platform (``vector(1536)``, cosine ``<=>``, HNSW, query vector
    passed as a text-cast literal so no pgvector Python adapter is required).
    """

    _ALLOWED_FILTERS = {"module", "audience", "doc_type", "status", "in_scope"}

    def __init__(self, table: str = config.PG_TABLE, dsn: str = config.DATABASE_URL):
        import psycopg2  # lazy — only when this backend is selected

        self._psycopg2 = psycopg2
        self.name = "pgvector"
        self._table = table
        self._dsn = dsn
        if not dsn and not os.environ.get("PRODUCT_DOCS_DB_PASSWORD"):
            raise RuntimeError("PgVectorStore: no DATABASE_URL / DB creds configured")
        self.ensure_schema()

    def _conn(self):
        # Cloud SQL path: the postgres password is injected from Secret Manager as
        # PRODUCT_DOCS_DB_PASSWORD (the instance uses password auth, not IAM tokens).
        # Connect with explicit kwargs over the /cloudsql unix socket. Local path:
        # fall back to the plain DSN (e.g. a proxy on localhost).
        pw = os.environ.get("PRODUCT_DOCS_DB_PASSWORD", "").strip()
        if pw:
            return self._psycopg2.connect(
                dbname=os.environ.get("PRODUCT_DOCS_DB_NAME", "mobius_rag"),
                user=os.environ.get("PRODUCT_DOCS_DB_USER", "postgres"),
                password=pw,
                host=os.environ.get(
                    "PRODUCT_DOCS_DB_HOST",
                    "/cloudsql/mobius-os-dev:us-central1:mobius-platform-dev-db"),
            )
        return self._psycopg2.connect(self._dsn)

    def ensure_schema(self) -> None:
        ddl = f"""
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE IF NOT EXISTS {self._table} (
            chunk_id      TEXT PRIMARY KEY,
            module        TEXT NOT NULL,
            doc_title     TEXT,
            section       TEXT,
            doc_type      TEXT,
            audience      TEXT,
            status        TEXT NOT NULL DEFAULT 'current',
            in_scope      BOOLEAN NOT NULL DEFAULT true,
            source_path   TEXT,
            source_commit TEXT,
            document      TEXT NOT NULL,
            embedding_vec vector({config.EMBED_DIM}),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS {self._table}_hnsw
            ON {self._table} USING hnsw (embedding_vec vector_cosine_ops);
        CREATE INDEX IF NOT EXISTS {self._table}_module_idx ON {self._table}(module);
        """
        with self._conn() as c, c.cursor() as cur:
            for stmt in filter(str.strip, ddl.split(";")):
                cur.execute(stmt)

    def reset(self) -> None:
        with self._conn() as c, c.cursor() as cur:
            cur.execute(f"TRUNCATE {self._table}")

    @staticmethod
    def _vec_literal(vector) -> str:
        return "[" + ",".join(repr(float(x)) for x in vector) + "]"

    def add(self, ids, vectors, metadatas, documents) -> None:
        sql = f"""
        INSERT INTO {self._table}
            (chunk_id, module, doc_title, section, doc_type, audience, status,
             in_scope, source_path, source_commit, document, embedding_vec, updated_at)
        VALUES
            (%(chunk_id)s, %(module)s, %(doc_title)s, %(section)s, %(doc_type)s,
             %(audience)s, %(status)s, %(in_scope)s, %(source_path)s, %(source_commit)s,
             %(document)s, CAST(%(vec)s AS vector), now())
        ON CONFLICT (chunk_id) DO UPDATE SET
            module=EXCLUDED.module, doc_title=EXCLUDED.doc_title, section=EXCLUDED.section,
            doc_type=EXCLUDED.doc_type, audience=EXCLUDED.audience, status=EXCLUDED.status,
            in_scope=EXCLUDED.in_scope, source_path=EXCLUDED.source_path,
            source_commit=EXCLUDED.source_commit, document=EXCLUDED.document,
            embedding_vec=EXCLUDED.embedding_vec, updated_at=now()
        """
        rows = [
            {**{k: m.get(k) for k in
                ("chunk_id", "module", "doc_title", "section", "doc_type", "audience",
                 "status", "in_scope", "source_path", "source_commit")},
             "document": d, "vec": self._vec_literal(v)}
            for m, d, v in zip(metadatas, documents, vectors)
        ]
        with self._conn() as c, c.cursor() as cur:
            cur.executemany(sql, rows)

    def query(self, vector, k, where=None) -> list[dict]:
        clauses = ["embedding_vec IS NOT NULL"]
        params: dict = {"q": self._vec_literal(vector), "k": k}
        for key, val in (where or {}).items():
            if key not in self._ALLOWED_FILTERS or val is None:
                continue
            clauses.append(f"{key} = %({key})s")
            params[key] = val
        where_sql = " AND ".join(clauses)
        sql = f"""
        SELECT chunk_id, module, doc_title, section, doc_type, audience, status,
               in_scope, source_path, source_commit, document,
               1 - (embedding_vec <=> CAST(%(q)s AS vector)) AS score
        FROM {self._table}
        WHERE {where_sql}
        ORDER BY embedding_vec <=> CAST(%(q)s AS vector)
        LIMIT %(k)s
        """
        with self._conn() as c, c.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        out = []
        for r in rows:
            score = r.pop("score")
            doc = r.pop("document")
            out.append({"id": r["chunk_id"], "score": float(score),
                        "metadata": r, "document": doc})
        return out

    def count(self) -> int:
        with self._conn() as c, c.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {self._table}")
            return int(cur.fetchone()[0])


def get_store() -> Store:
    """Resolve the backend.

    ``PRODUCT_DOCS_STORE``: ``auto`` (default) → pgvector if a DB + psycopg2 are present,
    else numpy (offline/dev+test). ``pgvector`` / ``numpy`` / ``chroma`` force a backend.
    Chroma is legacy (the platform is migrating off it) — available only when forced.
    """
    choice = os.environ.get("PRODUCT_DOCS_STORE", "auto").lower()
    if choice == "chroma":
        return ChromaStore()
    if choice == "numpy":
        return NumpyStore()
    if choice == "pgvector":
        return PgVectorStore()
    # auto
    if config.DATABASE_URL:
        try:
            return PgVectorStore()
        except Exception:
            pass
    return NumpyStore()
