"""LLM client for feedback — router-first, Anthropic fallback. Mirrors vibe."""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


def _router_url() -> str:
    return (
        os.environ.get("FEEDBACK_LLM_ROUTER_URL")
        or os.environ.get("MOBIUS_CHAT_URL")
        or "http://localhost:8000"
    ).rstrip("/")


def _router_key() -> str:
    return os.environ.get("MOBIUS_SKILL_LLM_INTERNAL_KEY", "")


def _use_router() -> bool:
    flag = os.environ.get("FEEDBACK_USE_CHAT_LLM_ROUTER", "1")
    return flag not in ("0", "false", "False") and bool(_router_key())


def _anthropic_complete(system: str, user: str, max_tokens: int, model: str) -> str:
    from app.config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("No ANTHROPIC_API_KEY and LLM router unavailable")
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    content = f"{system}\n\n{user}" if system else user
    resp = client.messages.create(
        model=model, max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
    )
    return (resp.content[0].text if resp.content else "").strip()


def llm_complete(
    system: str,
    user: str,
    stage: str = "feedback",
    max_tokens: int = 600,
    correlation_id: str | None = None,
    timeout_sec: float = 30.0,
) -> tuple[str, dict[str, Any]]:
    if _use_router():
        url = f"{_router_url()}/internal/skill-llm"
        payload: dict[str, Any] = {
            "system": system or "",
            "user": user or "",
            "stage": stage,
            "max_tokens": max_tokens,
        }
        if correlation_id:
            payload["correlation_id"] = correlation_id
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-Mobius-Skill-LLM-Key": _router_key(),
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout_sec) as r:
                resp = json.loads(r.read().decode())
            text = (resp.get("text") or "").strip()
            usage = resp.get("usage") or {}
            logger.info("[feedback.llm] router stage=%s model=%s", stage, usage.get("model", "?"))
            return text, usage
        except Exception as e:
            logger.warning("[feedback.llm] router failed (%s) — falling back to Anthropic", e)

    from app.config import ANTHROPIC_MODEL
    text = _anthropic_complete(system, user, max_tokens, ANTHROPIC_MODEL)
    return text, {"model": ANTHROPIC_MODEL, "provider": "anthropic_direct"}
