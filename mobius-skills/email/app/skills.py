"""
Email skills: MCP-ready surface for compose and send.

Use from MCP server: call these functions and map inputs/outputs to tool args/results.
- craft_email_with_llm(to, cc, user_text) -> { subject, body }
- send_via_system(to, cc, subject, body) -> { sent, message_id, error }
- build_mailto_url(to, cc, subject, body) -> url string
- prepare_draft(to, cc, subject, body) -> { to, cc, subject, body } (normalized)
"""
from __future__ import annotations

from typing import Any


def _normalize_to_list(addr: str | list[str] | None) -> list[str]:
    from app.services.sender import _normalize_addresses
    if addr is None:
        return []
    return _normalize_addresses(addr)


def craft_email_with_llm(to: list[str] | str, cc: list[str] | str, user_text: str) -> dict[str, Any]:
    """
    Use LLM to produce subject and body from user text and to/cc context.
    Returns {"subject": str, "body": str} or {"error": str} on failure.
    """
    from app.services.llm_crafter import craft_subject_and_body
    to_list = _normalize_to_list(to)
    cc_list = _normalize_to_list(cc)
    result = craft_subject_and_body(to_list, cc_list, user_text)
    if result is None:
        return {"subject": "", "body": "", "error": "LLM not configured or failed"}
    return {"subject": result["subject"], "body": result["body"]}


def send_via_system(
    to: list[str] | str,
    cc: list[str] | str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """
    Send email from system account (mobiushealthai@gmail.com). Uses Gmail API or SMTP.
    Returns {"sent": bool, "message_id": str | None, "error": str | None}.
    """
    from app.services.sender import send_via_system as _send
    to_list = _normalize_to_list(to)
    cc_list = _normalize_to_list(cc)
    return _send(to_list, cc_list, subject or "", body or "")


def build_mailto_url(
    to: list[str] | str,
    cc: list[str] | str,
    subject: str = "",
    body: str = "",
) -> str:
    """Build mailto URL for user client (open in default mail app)."""
    from app.services.sender import build_mailto_url as _build
    to_list = _normalize_to_list(to)
    cc_list = _normalize_to_list(cc)
    return _build(to_list, cc_list, subject or "", body or "")


def prepare_draft(
    to: list[str] | str,
    cc: list[str] | str,
    subject: str = "",
    body: str = "",
) -> dict[str, Any]:
    """Normalize and return draft payload for pre-send review. No side effects."""
    to_list = _normalize_to_list(to)
    cc_list = _normalize_to_list(cc)
    from app.config import EMAIL_MAX_SUBJECT_LEN, EMAIL_MAX_BODY_LEN
    sub = (subject or "")[:EMAIL_MAX_SUBJECT_LEN]
    b = (body or "")[:EMAIL_MAX_BODY_LEN]
    return {"to": to_list, "cc": cc_list, "subject": sub, "body": b}
