"""FastAPI app: POST /email/prepare, POST /email/send, GET /health. MCP-ready backend."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import MOBIUS_EMAIL_FROM
from app.models import (
    EmailDraft,
    EmailPrepareRequest,
    EmailPrepareResponse,
    EmailSendRequest,
    EmailSendResponse,
)
from app.skills import build_mailto_url, craft_email_with_llm, prepare_draft, send_via_system

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mobius Email", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    """Health check. Optionally verify Gmail config present for system send."""
    return {"ok": True, "service": "mobius-email", "from": MOBIUS_EMAIL_FROM}


@app.post("/email/prepare", response_model=EmailPrepareResponse)
def email_prepare(req: EmailPrepareRequest):
    """
    Prepare a draft (and optional mailto). If composition=llm and user_text set, LLM crafts subject/body.
    """
    to_list = req.to or []
    cc_list = req.cc or []
    subject = req.subject or ""
    body = req.body or ""

    if req.composition == "llm" and req.user_text and req.user_text.strip():
        crafted = craft_email_with_llm(to_list, cc_list, req.user_text.strip())
        if crafted.get("error"):
            logger.warning("LLM craft returned error: %s", crafted["error"])
        subject = crafted.get("subject") or subject
        body = crafted.get("body") or body

    draft = prepare_draft(to_list, cc_list, subject, body)
    draft_model = EmailDraft(**draft)
    mailto = None
    if req.sender == "user_client":
        mailto = build_mailto_url(draft["to"], draft["cc"], draft["subject"], draft["body"])
    return EmailPrepareResponse(draft=draft_model, mailto=mailto)


@app.post("/email/send", response_model=EmailSendResponse)
def email_send(req: EmailSendRequest):
    """
    Send email (system or user_client). If confirm_before_send=true, return draft for confirmation without sending.
    """
    to_list = req.to or []
    cc_list = req.cc or []
    subject = req.subject or ""
    body = req.body or ""

    if req.confirm_before_send:
        draft = prepare_draft(to_list, cc_list, subject, body)
        draft_model = EmailDraft(**draft)
        mailto = build_mailto_url(draft["to"], draft["cc"], draft["subject"], draft["body"]) if req.sender == "user_client" else None
        return EmailSendResponse(
            sent=False,
            requires_confirmation=True,
            draft=draft_model,
            mailto=mailto,
        )

    if req.sender == "user_client":
        mailto = build_mailto_url(to_list, cc_list, subject, body)
        return EmailSendResponse(
            sent=False,
            requires_confirmation=False,
            mailto=mailto,
            confirmation="Open your mail client to send. Use the mailto URL to open a pre-filled draft.",
        )

    # System send
    result = send_via_system(to_list, cc_list, subject, body)
    if result.get("sent"):
        return EmailSendResponse(
            sent=True,
            message_id=result.get("message_id"),
            confirmation=f"Email sent from {MOBIUS_EMAIL_FROM} to {', '.join(to_list)}.",
        )
    return EmailSendResponse(
        sent=False,
        error=result.get("error") or "Send failed",
    )


@app.post("/email/confirm", response_model=EmailSendResponse)
def email_confirm(req: EmailSendRequest):
    """
    Confirm and send: same body as POST /email/send with confirm_before_send=false.
    Provided for explicit confirm flow (client shows draft, user clicks Send, then calls this).
    """
    # Force actual send
    req.confirm_before_send = False
    return email_send(req)
