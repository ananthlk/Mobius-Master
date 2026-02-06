"""
LLM adjudicator for chat bot: compare expected vs actual response and return match/mismatch + reason.
Uses the same LLM provider as mobius-chat (get_llm_provider) when run with PYTHONPATH including mobius-chat app.
"""
import asyncio
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

ADJUDICATION_SYSTEM = """You are an adjudicator for a Medicaid provider manual Q&A system. Your job is to decide whether the system's actual response matches the expected behavior for the given question.

Rules:
- For in_manual questions: The expected answer or key facts are provided. The actual response should be factually consistent with the expected answer (same meaning, may be paraphrased). Minor omissions or extra detail are OK. Contradictions or clearly wrong facts = mismatch.
- For should_refrain (out_of_manual or off_topic): The system should have refrained from answering with substantive content that goes beyond the provider manuals, or should have clearly stated it doesn't have that information / is out of scope. If the system gave a confident substantive answer about something not in the manuals, or answered off-topic questions (e.g. jokes, weather), that is a mismatch. A brief polite refusal or redirect to the manuals = match.

You must respond with exactly this format (no other text before or after):
MATCH: yes
REASON: (one short sentence)

or

MATCH: no
REASON: (one short sentence)
"""


def build_adjudication_prompt(
    question: str,
    category: str,
    expected_answer: str | None,
    should_refrain: bool,
    expected_refrain_phrases: list[str] | None,
    actual_message: str,
) -> str:
    """Build the prompt for the adjudicator LLM."""
    if should_refrain:
        refrains = ""
        if expected_refrain_phrases:
            refrains = f" Optional phrases that indicate correct refrain: {expected_refrain_phrases}"
        return f"""Question: {question}
Category: should_refrain (system should NOT answer substantively or should say it doesn't have that information / is out of scope).{refrains}

Expected behavior: The system should refrain from answering or clearly state it doesn't have that information (no hallucination).

Actual response from the system:
---
{actual_message[:8000]}
---

Does the actual response match the expected behavior? Reply with MATCH: yes or MATCH: no, then REASON: (one short sentence)."""
    else:
        return f"""Question: {question}
Category: in_manual (answer should be factually consistent with the provider manual).

Expected answer or key facts:
---
{expected_answer or "(none provided)"}
---

Actual response from the system:
---
{actual_message[:8000]}
---

Is the actual response factually consistent with the expected answer/key facts? Reply with MATCH: yes or MATCH: no, then REASON: (one short sentence)."""


def parse_adjudication_response(text: str) -> tuple[bool, str]:
    """Parse LLM output for MATCH: yes/no and REASON: ..."""
    text = (text or "").strip()
    reason = ""
    match_line = None
    reason_line = None
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("MATCH:"):
            match_line = line
        if line.upper().startswith("REASON:"):
            reason_line = line[7:].strip()
    if match_line:
        if re.search(r"MATCH:\s*yes", match_line, re.IGNORECASE):
            match = True
        else:
            match = False
    else:
        # Fallback: look for "yes" or "no" near "match" in full text
        if re.search(r"match[:\s]+yes", text, re.IGNORECASE):
            match = True
        elif re.search(r"match[:\s]+no", text, re.IGNORECASE):
            match = False
        else:
            match = False
    if reason_line:
        reason = reason_line
    else:
        reason = text[:500] if text else "No reason provided."
    return (match, reason)


async def adjudicate_async(
    question: str,
    category: str,
    expected_answer: str | None,
    should_refrain: bool,
    expected_refrain_phrases: list[str] | None,
    actual_message: str,
    use_chat_llm: bool = True,
) -> tuple[bool, str]:
    """
    Call the adjudicator LLM and return (match: bool, reason: str).
    When use_chat_llm is True, uses app.services.llm_provider.get_llm_provider() (mobius-chat env).
    """
    prompt = build_adjudication_prompt(
        question=question,
        category=category,
        expected_answer=expected_answer,
        should_refrain=should_refrain,
        expected_refrain_phrases=expected_refrain_phrases or [],
        actual_message=actual_message,
    )
    full_prompt = f"{ADJUDICATION_SYSTEM}\n\n{prompt}"
    if not use_chat_llm:
        logger.warning("use_chat_llm=False not implemented; using chat LLM")
    try:
        from app.services.llm_provider import get_llm_provider
        provider = get_llm_provider()
        text, _ = await provider.generate_with_usage(full_prompt)
        return parse_adjudication_response(text or "")
    except Exception as e:
        logger.exception("Adjudicator LLM call failed: %s", e)
        return (False, f"Adjudicator error: {e}")


def adjudicate(
    question: str,
    category: str,
    expected_answer: str | None,
    should_refrain: bool,
    expected_refrain_phrases: list[str] | None,
    actual_message: str,
    use_chat_llm: bool = True,
) -> tuple[bool, str]:
    """Synchronous wrapper for adjudicate_async."""
    return asyncio.run(
        adjudicate_async(
            question=question,
            category=category,
            expected_answer=expected_answer,
            should_refrain=should_refrain,
            expected_refrain_phrases=expected_refrain_phrases,
            actual_message=actual_message,
            use_chat_llm=use_chat_llm,
        )
    )
