"""
Mobius Healthcare skills: answer healthcare queries using CMS coverage, ICD-10, NPI.

MCP-ready surface. Call answer_healthcare_query(question) from MCP server or HTTP API.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.clients import (
    lookup_icd10_code,
    lookup_npi,
    search_coverage,
    search_icd10,
    search_npi,
)
from app.config import (
    ANTHROPIC_API_KEY,
    HEALTHCARE_LLM_PROVIDER,
    VERTEX_MODEL,
    VERTEX_LOCATION,
    VERTEX_PROJECT_ID,
)

logger = logging.getLogger(__name__)

# Patterns to detect query intent
NPI_PATTERN = re.compile(r"\b(\d{10})\b|npi\s*#?\s*(\d{10})|look\s*up\s*npi|provider\s*(?:lookup|search)", re.I)
ICD10_PATTERN = re.compile(
    r"icd[- ]?10|icd10|diagnosis\s*code|procedure\s*code|code\s*(?:for|meaning)|[A-Z]\d{2}(?:\.\d{2,4})?",
    re.I,
)
COVERAGE_PATTERN = re.compile(
    r"cover(?:ed|age)|medicare|medicaid|ncd|lcd|prior\s*auth|reimburse|cpt\s*\d+|hcpcs",
    re.I,
)


def _classify_query(question: str) -> list[str]:
    """Return list of data sources to query: icd10, npi, cms_coverage."""
    q = (question or "").strip()
    sources = []
    if ICD10_PATTERN.search(q):
        sources.append("icd10")
    if NPI_PATTERN.search(q):
        sources.append("npi")
    if COVERAGE_PATTERN.search(q):
        sources.append("cms_coverage")
    if not sources:
        sources = ["icd10", "npi", "cms_coverage"]
    return sources


def _extract_npi(question: str) -> str | None:
    """Extract 10-digit NPI from question if present."""
    m = re.search(r"\b(\d{10})\b", question)
    return m.group(1) if m else None


def _extract_icd10_code(question: str) -> str | None:
    """Extract ICD-10-like code (e.g. Z00.00, A15.0) from question."""
    m = re.search(r"\b([A-Z]\d{2}(?:\.\d{2,4})?)\b", question, re.I)
    return m.group(1).upper() if m else None


def _gather_context(question: str, sources: list[str]) -> dict[str, Any]:
    """Call APIs and gather context for LLM."""
    ctx: dict[str, Any] = {"question": question, "icd10": [], "npi": None, "coverage": []}

    if "icd10" in sources:
        code = _extract_icd10_code(question)
        if code:
            r = lookup_icd10_code(code)
            if r:
                ctx["icd10"].append(r)
        if not ctx["icd10"]:
            # Search by terms (e.g. "diabetes", "tuberculosis")
            terms = question[:80].replace("?", "").strip()
            for word in terms.split()[:3]:
                if len(word) > 2 and word.isalpha():
                    ctx["icd10"].extend(search_icd10(word, max_results=5))
                    break
            if not ctx["icd10"]:
                ctx["icd10"].extend(search_icd10(terms[:50], max_results=5))

    if "npi" in sources:
        npi_num = _extract_npi(question)
        if npi_num:
            r = lookup_npi(npi_num)
            if r:
                ctx["npi"] = r
        if ctx["npi"] is None and any(
            w in question.lower() for w in ("provider", "doctor", "npi", "look up")
        ):
            # Try name search - would need first/last from question; simplified
            pass

    if "cms_coverage" in sources:
        cov = search_coverage(query=question[:60] if len(question) > 60 else question, limit=10)
        ctx["coverage"] = cov.get("documents") or cov.get("results") or []

    return ctx


def _call_llm(prompt: str) -> str:
    """Call configured LLM (Vertex or Anthropic)."""
    if HEALTHCARE_LLM_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
        try:
            from app.config import ANTHROPIC_MODEL
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return (msg.content[0].text if msg.content else "").strip()
        except Exception as e:
            logger.warning("Anthropic LLM failed: %s", e)
            return f"I gathered data but could not synthesize an answer: {e}"
    # Vertex
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        vertexai.init(project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)
        model = GenerativeModel(VERTEX_MODEL)
        resp = model.generate_content(prompt)
        return (resp.text or "").strip()
    except Exception as e:
        logger.warning("Vertex LLM failed: %s", e)
        return f"I gathered data but could not synthesize an answer: {e}"


def answer_healthcare_query(
    question: str,
    data_sources: list[str] | None = None,
) -> str:
    """
    Answer a healthcare question using CMS coverage, ICD-10, and NPI data.
    Returns synthesized answer string. Used by MCP tool and HTTP API.
    """
    question = (question or "").strip()
    if not question:
        return "Please provide a healthcare question (e.g. ICD-10 code lookup, NPI lookup, Medicare coverage)."

    sources = data_sources or _classify_query(question)
    ctx = _gather_context(question, sources)

    # Build prompt
    parts = [f"Question: {question}\n"]
    if ctx.get("icd10"):
        parts.append("ICD-10 data:\n" + json.dumps(ctx["icd10"], indent=2) + "\n")
    if ctx.get("npi"):
        parts.append("NPI data:\n" + json.dumps(ctx["npi"], indent=2) + "\n")
    if ctx.get("coverage"):
        parts.append("CMS Coverage documents:\n" + json.dumps(ctx["coverage"][:10], indent=2) + "\n")

    if not any((ctx.get("icd10"), ctx.get("npi"), ctx.get("coverage"))):
        prompt = (
            f"You are a healthcare information assistant. The user asked: {question}\n"
            "No specific data was found from our APIs (ICD-10, NPI, CMS Coverage). "
            "Provide a helpful, general response about what they might be looking for, "
            "or suggest rephrasing (e.g. include an NPI number, ICD-10 code, or coverage topic)."
        )
    else:
        prompt = (
            "You are a healthcare information assistant. Use the following data to answer the user's question. "
            "Be concise and cite sources (e.g. 'Per ICD-10:', 'From NPI registry:').\n\n"
            + "\n".join(parts)
            + "\nAnswer:"
        )

    return _call_llm(prompt)
