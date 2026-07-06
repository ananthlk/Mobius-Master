"""Shared skill implementations for Mobius.

Consumers import from ``mobius_skills_core.skills.<skill_name>``; the
top-level package exports only the shared types so ``from
mobius_skills_core import SkillResult`` works for consumers that don't
need to import a specific skill.
"""
from mobius_skills_core._types import (
    ChunkRef,
    Emitter,
    SkillEvent,
    SkillResult,
    SkillUsage,
    SourceRef,
)

__all__ = [
    "ChunkRef",
    "Emitter",
    "SkillEvent",
    "SkillResult",
    "SkillUsage",
    "SourceRef",
]
