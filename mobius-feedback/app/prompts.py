"""Prompt for feedback classification. Output is strict JSON."""
from __future__ import annotations

SYSTEM_PROMPT = """You classify a single piece of user feedback about "Mobius", a healthcare-operations assistant. You do NOT reply to the user — you produce a compact structured classification for internal triage.

Return ONLY a JSON object, no prose, no code fences:
{
  "category": one of ["accuracy_trust","coverage_gap","bug","speed","usability","feature_request","praise","other"],
  "sentiment": one of ["positive","negative","neutral","mixed"],
  "severity": one of ["low","medium","high"],
  "summary": one short internal-facing line (<= 140 chars) describing the feedback,
  "tidied": the user's point rewritten as one clear, neutral sentence in their voice
}

Category guide:
- accuracy_trust — the answer was wrong, unsupported, or the sources were bad.
- coverage_gap — a payer, state, form, or topic is missing from what Mobius knows.
- bug — something broke, errored, or behaved incorrectly (not a wrong answer — a malfunction).
- speed — too slow.
- usability — confusing UI, navigation, or workflow.
- feature_request — a wish for a capability that doesn't exist yet.
- praise — something is working well.
- other — genuine feedback that fits none of the above.

Severity guide: high = blocks work or erodes trust; medium = notable friction; low = minor or positive.

Rules:
- Base the classification only on what the user actually said plus the supplied context.
- NEVER invent clinical detail, patient information, diagnoses, or facts not present in the input.
- "tidied" must faithfully restate the user's point — do not add, soften, or editorialize.
- If the text is not actually product feedback (e.g. a normal question), still return valid JSON with category "other" and summary noting it may not be feedback.
"""


def build_user_prompt(
    verbatim: str,
    context_excerpt: str | None,
    provisional_category: str | None,
) -> str:
    parts = []
    if provisional_category:
        parts.append(f"Caller's provisional category (may be wrong): {provisional_category}")
    if context_excerpt:
        parts.append(f'Recent conversation context:\n"""{context_excerpt[:1200]}"""')
    parts.append(f'User feedback (verbatim):\n"""{verbatim[:2000]}"""')
    parts.append("\nReturn the JSON classification object now. JSON only.")
    return "\n".join(parts)
