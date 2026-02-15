"""Repository layer: DB access for lexicon, candidates, dismissed issues."""
from app.repositories.lexicon_repo import (
    bump_revision,
    get_lexicon_meta_and_tags,
    get_tag,
    parent_exists,
)
from app.repositories.dismissed_repo import (
    ensure_dismissed_table,
    load_dismissed,
)

__all__ = [
    "bump_revision",
    "get_lexicon_meta_and_tags",
    "get_tag",
    "parent_exists",
    "ensure_dismissed_table",
    "load_dismissed",
]
