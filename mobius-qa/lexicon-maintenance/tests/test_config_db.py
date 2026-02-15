"""Unit tests for config and db modules (no DB required for config)."""
import pytest


def test_config_imports():
    """Config module loads and exposes URL getters."""
    from app.config import get_urls, qa_url, rag_url
    urls = get_urls()
    assert urls.qa
    assert urls.rag
    assert "postgresql" in urls.qa or "postgres" in urls.qa


def test_db_imports():
    """DB module loads and exposes session managers."""
    from app.db import get_conn, qa_session, rag_session, dual_session
    assert callable(get_conn)
    assert callable(qa_session)
    assert callable(rag_session)
    assert callable(dual_session)


def test_app_imports():
    """Main app loads without error."""
    from app.main import app
    assert app is not None
    assert app.title == "Mobius QA — Lexicon Maintenance API"


def test_repositories_import():
    """Repository modules load."""
    from app.repositories import (
        bump_revision,
        get_lexicon_meta_and_tags,
        get_tag,
        parent_exists,
        ensure_dismissed_table,
        load_dismissed,
    )
    assert callable(bump_revision)
    assert callable(get_lexicon_meta_and_tags)
