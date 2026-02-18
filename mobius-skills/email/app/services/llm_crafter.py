"""LLM-crafted subject and body from user text (to/cc context)."""
import json
import logging
import os
import re

logger = logging.getLogger(__name__)

MAX_USER_TEXT_LEN = 8000


def craft_subject_and_body(to: list[str], cc: list[str], user_text: str) -> dict[str, str] | None:
    """
    Use LLM to produce subject and body from user_text and recipient context.
    Returns {"subject": str, "body": str} or None if LLM not configured or fails.
    """
    if not user_text or not user_text.strip():
        return None
    text = user_text.strip()[:MAX_USER_TEXT_LEN]
    to_str = ", ".join(to) if to else ""
    cc_str = ", ".join(cc) if cc else ""

    # Try OpenAI first
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        try:
            return _craft_openai(to_str, cc_str, text, api_key)
        except Exception as e:
            logger.warning("OpenAI email craft failed: %s", e)

    # Try Vertex
    if os.getenv("VERTEX_PROJECT_ID") and os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            return _craft_vertex(to_str, cc_str, text)
        except Exception as e:
            logger.warning("Vertex email craft failed: %s", e)

    return None


def _parse_llm_output(raw: str) -> dict[str, str] | None:
    """Parse LLM response into subject and body. Accepts JSON or Subject: ...\\n\\nBody."""
    raw = (raw or "").strip()
    if not raw:
        return None
    # Try JSON first
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            sub = data.get("subject") or data.get("Subject") or ""
            body = data.get("body") or data.get("Body") or ""
            return {"subject": sub.strip(), "body": body.strip()}
    except json.JSONDecodeError:
        pass
    # Fallback: Subject: ...\n\n...body...
    m = re.search(r"(?i)subject\s*:\s*(.+?)(?=\n\n|\nBody\s*:|\Z)", raw, re.DOTALL)
    sub = m.group(1).strip() if m else ""
    body = raw
    if m:
        body = raw[m.end() :].strip()
        if body.lower().startswith("body"):
            body = re.sub(r"^body\s*:\s*", "", body, flags=re.I)
    return {"subject": sub, "body": body}


def _craft_openai(to_str: str, cc_str: str, user_text: str, api_key: str) -> dict[str, str] | None:
    import httpx

    prompt = f"""You are writing a professional email. Given the recipient context and the user's intent below, output exactly a JSON object with two keys: "subject" (one line) and "body" (plain text email body). No other text.

Recipients (to): {to_str or 'not specified'}
Recipients (cc): {cc_str or 'none'}

User intent / draft:
{user_text}
"""
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": "You output only valid JSON with keys subject and body."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2000,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    choice = resp.json().get("choices", [{}])[0]
    content = (choice.get("message", {}).get("content") or "").strip()
    return _parse_llm_output(content)


def _craft_vertex(to_str: str, cc_str: str, user_text: str) -> dict[str, str] | None:
    import vertexai
    from vertexai.generative_models import GenerativeModel

    project = os.getenv("VERTEX_PROJECT_ID")
    location = os.getenv("VERTEX_LOCATION", "us-central1")
    vertexai.init(project=project, location=location)
    model = GenerativeModel(os.getenv("VERTEX_MODEL", "gemini-1.5-flash"))
    prompt = f"""You are writing a professional email. Given the recipient context and the user's intent below, output exactly a JSON object with two keys: "subject" (one line) and "body" (plain text email body). No other text.

Recipients (to): {to_str or 'not specified'}
Recipients (cc): {cc_str or 'none'}

User intent / draft:
{user_text}
"""
    response = model.generate_content(
        prompt,
        generation_config={"max_output_tokens": 2000},
    )
    if not response or not response.text:
        return None
    return _parse_llm_output(response.text.strip())
