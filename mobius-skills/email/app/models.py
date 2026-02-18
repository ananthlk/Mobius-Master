"""Pydantic models for email requests and responses."""
from pydantic import BaseModel, Field
from typing import Literal, Optional


class EmailDraft(BaseModel):
    """Draft email payload."""
    to: list[str] = Field(default_factory=list, description="To addresses")
    cc: list[str] = Field(default_factory=list, description="CC addresses")
    subject: str = ""
    body: str = ""


class EmailPrepareRequest(BaseModel):
    """Request for /email/prepare: get draft (and optional mailto)."""
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    subject: Optional[str] = None
    body: Optional[str] = None
    user_text: Optional[str] = None
    composition: Literal["direct", "llm"] = "direct"
    sender: Literal["system", "user_client"] = "system"


class EmailPrepareResponse(BaseModel):
    """Response from /email/prepare."""
    draft: EmailDraft
    mailto: Optional[str] = None  # Set when sender=user_client


class EmailSendRequest(BaseModel):
    """Request for /email/send."""
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    subject: str = ""
    body: str = ""
    sender: Literal["system", "user_client"] = "system"
    confirm_before_send: bool = False


class EmailSendResponse(BaseModel):
    """Response from /email/send."""
    sent: bool = False
    requires_confirmation: bool = False
    draft: Optional[EmailDraft] = None
    message_id: Optional[str] = None
    mailto: Optional[str] = None
    error: Optional[str] = None
    confirmation: Optional[str] = None
