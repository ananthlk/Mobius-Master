"""FastAPI app for the feedback classifier: POST /classify, GET /health.

Stateless. Turns a user's raw feedback into a structured classification. The
chat service persists the result and manages cadence — see
``mobius-chat/app/storage/product_feedback.py``.
"""
from __future__ import annotations

import json
import logging
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FEEDBACK_LLM_STAGE, FEEDBACK_MAX_TOKENS
from app.llm_client import llm_complete
from app.models import Classification, ClassifyRequest, ClassifyResponse
from app.policy import coerce_category, coerce_sentiment, coerce_severity, route_for
from app.prompts import SYSTEM_PROMPT, build_user_prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mobius Feedback", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json(text: str) -> dict:
    """Extract the first balanced JSON object from a model response."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s[4:] if s[:4].lower() == "json" else s
    try:
        return json.loads(s)
    except Exception:
        m = _JSON_RE.search(s)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    raise ValueError("no parseable JSON in model output")


@app.get("/health")
def health():
    return {"ok": True, "service": "mobius-feedback"}


@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest) -> ClassifyResponse:
    verbatim = (req.verbatim or "").strip()
    if not verbatim:
        return ClassifyResponse(
            classification=Classification(),
            routed_to="product_backlog",
            skipped=True,
            reason="empty_verbatim",
        )

    user_prompt = build_user_prompt(
        verbatim=verbatim,
        context_excerpt=req.context_excerpt,
        provisional_category=req.provisional_category,
    )

    try:
        text, usage = llm_complete(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            stage=FEEDBACK_LLM_STAGE,
            max_tokens=FEEDBACK_MAX_TOKENS,
            correlation_id=req.correlation_id,
        )
    except Exception as e:
        logger.warning("[feedback] llm call failed: %s", e)
        return _fallback(verbatim, req.provisional_category, reason="llm_unavailable")

    try:
        raw = _parse_json(text)
    except Exception as e:
        # §3 PHI-in-logs: never log raw model output text — length only.
        logger.warning("[feedback] parse failed: %s (output len=%d)", e, len(text or ""))
        return _fallback(verbatim, req.provisional_category, reason="parse_failed", usage=usage)

    category = coerce_category(raw.get("category") or req.provisional_category)
    classification = Classification(
        category=category,
        sentiment=coerce_sentiment(raw.get("sentiment")),
        severity=coerce_severity(raw.get("severity")),
        summary=(raw.get("summary") or "").strip()[:160],
        tidied=(raw.get("tidied") or verbatim).strip()[:600],
    )
    return ClassifyResponse(
        classification=classification,
        routed_to=route_for(category),
        usage=usage,
    )


def _fallback(
    verbatim: str, provisional: str | None, reason: str, usage: dict | None = None
) -> ClassifyResponse:
    """Degrade gracefully: keep the user's words, best-effort category, no crash."""
    category = coerce_category(provisional)
    return ClassifyResponse(
        classification=Classification(
            category=category,
            summary=verbatim[:160],
            tidied=verbatim[:600],
        ),
        routed_to=route_for(category),
        skipped=False,
        reason=reason,
        usage=usage or {},
    )
