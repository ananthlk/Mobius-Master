"""Database connection pooling and context managers for QA and RAG DBs."""
from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Any, Generator

import psycopg2
import psycopg2.extras
import psycopg2.pool

from app.config import get_urls

_POOL_MIN = 1
_POOL_MAX = int(os.getenv("LEXICON_POOL_MAX", "8"))
_pools: dict[str, "BlockingConnectionPool"] = {}


class BlockingConnectionPool(psycopg2.pool.ThreadedConnectionPool):
    """Wraps ThreadedConnectionPool so getconn() blocks instead of raising PoolError."""

    def __init__(self, minconn: int, maxconn: int, *args: Any, **kwargs: Any):
        super().__init__(minconn, maxconn, *args, **kwargs)
        self._sem = threading.Semaphore(maxconn)

    def getconn(self, *args: Any, **kwargs: Any):
        self._sem.acquire()
        try:
            return super().getconn(*args, **kwargs)
        except Exception:
            self._sem.release()
            raise

    def putconn(self, *args: Any, **kwargs: Any):
        try:
            super().putconn(*args, **kwargs)
        finally:
            self._sem.release()


class PooledConnection:
    """Thin wrapper: delegates to the real connection; close() returns it to the pool."""

    def __init__(self, real_conn: Any, pool: BlockingConnectionPool) -> None:
        self._conn = real_conn
        self._pool = pool
        self._returned = False

    def close(self) -> None:
        if not self._returned:
            self._returned = True
            try:
                self._conn.commit()
            except Exception:
                pass
            try:
                self._conn.rollback()
            except Exception:
                pass
            self._pool.putconn(self._conn)

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> "PooledConnection":
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.close()
        return False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)

    def cursor(self, *args: Any, **kwargs: Any):
        return self._conn.cursor(*args, **kwargs)


def _get_pool(url: str) -> BlockingConnectionPool:
    if url not in _pools:
        _pools[url] = BlockingConnectionPool(_POOL_MIN, _POOL_MAX, url, connect_timeout=10)
    return _pools[url]


def get_conn(url: str) -> PooledConnection:
    """Get a pooled connection. Call .close() when done (returns to pool)."""
    pool = _get_pool(url)
    real = pool.getconn()
    return PooledConnection(real, pool)


@contextmanager
def qa_session() -> Generator[PooledConnection, None, None]:
    """Context manager for a QA DB connection. Autocommit enabled. Always closes on exit."""
    u = get_urls()
    conn = get_conn(u.qa)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def rag_session() -> Generator[PooledConnection, None, None]:
    """Context manager for a RAG DB connection. Autocommit enabled. Always closes on exit."""
    u = get_urls()
    conn = get_conn(u.rag)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def dual_session() -> Generator[tuple[PooledConnection, PooledConnection], None, None]:
    """Context manager for both QA and RAG connections. Both closed on exit."""
    u = get_urls()
    qa = get_conn(u.qa)
    rag = get_conn(u.rag)
    qa.autocommit = rag.autocommit = True
    try:
        yield qa, rag
    finally:
        try:
            qa.close()
        except Exception:
            pass
        try:
            rag.close()
        except Exception:
            pass
