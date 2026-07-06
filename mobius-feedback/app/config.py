"""feedback skill — environment config.

Stateless classifier service (mirrors ``mobius-skills/vibe``). Persistence lives
chat-side in ``mobius-chat/app/storage/product_feedback.py``; this service only
turns a user's raw feedback into a structured classification via the LLM.
"""
from __future__ import annotations
import os

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("FEEDBACK_ANTHROPIC_MODEL", "claude-haiku-4-5")

# Stage name for the chat LLM router. Dedicated cheap+fast stage registered in
# mobius-chat (_SKILL_LLM_ALLOWED_STAGES + model_registry) 2026-07-02.
FEEDBACK_LLM_STAGE = os.environ.get("FEEDBACK_LLM_STAGE", "feedback_classify")

# Classification is a small JSON object; 600 tokens is ample headroom.
FEEDBACK_MAX_TOKENS = int(os.environ.get("FEEDBACK_MAX_TOKENS", "600"))
