"""Request/response models for the feedback classifier service."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ClassifyRequest(BaseModel):
    verbatim: str = Field(description="The user's own words of feedback.")
    context_excerpt: str | None = Field(
        default=None, description="Recent turns for tone/intent context."
    )
    provisional_category: str | None = Field(
        default=None, description="Optional hint from the caller; the model may override."
    )
    correlation_id: str | None = None


class Classification(BaseModel):
    category: str = "other"
    sentiment: str = "neutral"
    severity: str = "low"
    summary: str = ""
    tidied: str = ""


class ClassifyResponse(BaseModel):
    classification: Classification
    routed_to: str = "product_backlog"
    skipped: bool = False
    reason: str | None = None
    usage: dict = {}
