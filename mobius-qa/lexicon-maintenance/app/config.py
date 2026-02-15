"""Lexicon maintenance configuration: env, DB URLs."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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


def qa_url() -> str:
    return _env("QA_DATABASE_URL") or _build_pg_url("mobius_qa")


def rag_url() -> str:
    url = _env("RAG_DATABASE_URL")
    if url:
        return url
    url = _env("DATABASE_URL")
    if url:
        return url.replace("postgresql+asyncpg://", "postgresql://")
    return _build_pg_url("mobius_rag")


@dataclass
class DbUrls:
    qa: str
    rag: str


def get_urls() -> DbUrls:
    return DbUrls(qa=qa_url(), rag=rag_url())
