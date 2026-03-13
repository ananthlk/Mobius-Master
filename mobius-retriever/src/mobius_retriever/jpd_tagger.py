"""J/P/D tagger: tag question with lexicon, resolve document_ids for BM25 corpus scoping.

Uses phrase-matching logic compatible with mobius-rag policy_path_b. Requires RAG_DATABASE_URL
for lexicon (policy_lexicon_*) and document_tags.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Callable

logger = logging.getLogger(__name__)

# Inlined from mobius-rag policy_path_b (avoids sqlalchemy dep)
_SHORT_PHRASE_BOUNDARY_LEN = 4
_boundary_cache: dict[str, re.Pattern[str]] = {}


def _normalize_phrase(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    return " ".join(s.split()).strip().lower()


def _phrase_in_text(phrase: str, text: str) -> bool:
    if not phrase or not text:
        return False
    if len(phrase) <= _SHORT_PHRASE_BOUNDARY_LEN:
        pat = _boundary_cache.get(phrase)
        if pat is None:
            pat = re.compile(r"\b" + re.escape(phrase) + r"\b")
            _boundary_cache[phrase] = pat
        return pat.search(text) is not None
    return phrase in text


def _get_phrase_to_tag_map(lexicon_snapshot) -> tuple[dict[str, tuple[str, str, float]], dict]:
    """Build phrase_map and refuted_map from lexicon (p_tags, d_tags, j_tags)."""
    out: dict[str, tuple[str, str, float]] = {}
    refuted_map: dict[tuple[str, str], set[str]] = {}
    for kind, root in (
        ("p", getattr(lexicon_snapshot, "p_tags", None)),
        ("d", getattr(lexicon_snapshot, "d_tags", None)),
        ("j", getattr(lexicon_snapshot, "j_tags", None)),
    ):
        if not isinstance(root, dict):
            continue
        for code, spec in root.items():
            if not isinstance(spec, dict):
                continue
            code_str = str(code)
            is_domain_container = "." not in code_str
            if is_domain_container:
                code_key = _normalize_phrase(code_str.replace("_", " "))
                if code_key:
                    out[code_key] = (kind, code_str, 1.0)
                continue
            code_key = _normalize_phrase(code_str.replace("_", " "))
            if code_key:
                out[code_key] = (kind, code_str, 1.0)
            phrases: list[str] = []
            for key in ("phrases", "strong_phrases", "aliases"):
                val = spec.get(key)
                if isinstance(val, list):
                    phrases.extend(str(p) for p in val if p and isinstance(p, str))
            if not phrases and isinstance(spec.get("description"), str):
                phrases = [spec["description"]]
            for phrase in phrases:
                norm = _normalize_phrase(phrase)
                if norm:
                    out[norm] = (kind, code_str, 1.0)
            weak = spec.get("weak_keywords")
            if isinstance(weak, dict):
                any_of = weak.get("any_of")
                if isinstance(any_of, list):
                    for phrase in any_of:
                        if phrase and isinstance(phrase, str):
                            norm = _normalize_phrase(phrase)
                            if norm and norm not in out:
                                out[norm] = (kind, code_str, 0.6)
            refuted = spec.get("refuted_words")
            if isinstance(refuted, list):
                for rw in refuted:
                    if rw and isinstance(rw, str):
                        norm_rw = _normalize_phrase(str(rw))
                        if norm_rw:
                            refuted_map.setdefault((kind, code_str), set()).add(norm_rw)
    return out, refuted_map


def _apply_tags_to_line_text(
    line_text: str,
    phrase_map: dict[str, tuple[str, str, float]],
    refuted_map: dict | None = None,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    p_tags: dict[str, float] = {}
    d_tags: dict[str, float] = {}
    j_tags: dict[str, float] = {}
    normalized_line = _normalize_phrase(line_text)
    if not normalized_line:
        return p_tags, d_tags, j_tags
    for phrase, (kind, code, score) in phrase_map.items():
        if not phrase or not _phrase_in_text(phrase, normalized_line):
            continue
        if refuted_map:
            refuted_words = refuted_map.get((kind, code))
            if refuted_words and any(_phrase_in_text(rw, normalized_line) for rw in refuted_words):
                continue
        target = p_tags if kind == "p" else (d_tags if kind == "d" else j_tags)
        if code not in target or score > target[code]:
            target[code] = score
    return p_tags, d_tags, j_tags


@dataclass
class JPDTagResult:
    """Result of J/P/D tagging: question tags and matching document_ids."""
    p_tags: dict[str, float] = field(default_factory=dict)
    d_tags: dict[str, float] = field(default_factory=dict)
    j_tags: dict[str, float] = field(default_factory=dict)
    document_ids: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def has_tags(self) -> bool:
        return bool(self.p_tags or self.d_tags or self.j_tags)

    @property
    def has_document_ids(self) -> bool:
        return len(self.document_ids) > 0


def _load_lexicon_sync(rag_url: str) -> SimpleNamespace | None:
    """Load lexicon from RAG DB (sync). Returns SimpleNamespace with p_tags, d_tags, j_tags or None."""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        logger.warning("psycopg2 not available for J/P/D lexicon load")
        return None
    try:
        conn = psycopg2.connect(rag_url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT kind, code, parent_code, spec FROM policy_lexicon_entries WHERE active = true ORDER BY kind, code"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning("Failed to load lexicon from RAG DB: %s", e)
        return None

    def build_nested(entries_list):
        by_kind: dict[str, dict] = {"p": {}, "d": {}, "j": {}}
        for e in entries_list:
            kind, code, spec = e.get("kind"), e.get("code"), e.get("spec")
            if kind not in by_kind:
                continue
            spec = spec if isinstance(spec, dict) else {}
            entry = dict(spec)
            entry.setdefault("children", {})
            by_kind[kind][str(code)] = entry
        return by_kind["p"], by_kind["d"], by_kind["j"]

    p_tags, d_tags, j_tags = build_nested(rows)
    return SimpleNamespace(p_tags=p_tags, d_tags=d_tags, j_tags=j_tags)


def _normalize_text_for_match(t: str) -> str:
    """Normalize text for matching chunk to policy_line."""
    if not t or not isinstance(t, str):
        return ""
    return " ".join((t or "").split()).strip().lower()


def fetch_line_tags_for_chunks(
    rag_url: str,
    chunks: list[dict],
) -> dict[tuple[str, str], dict[str, dict[str, float]]]:
    """Fetch line-level p_tags, d_tags, j_tags from policy_line_tags (Chat, synced from policy_lines).

    Returns: {(document_id, normalized_text): {"p_tags": {...}, "d_tags": {...}, "j_tags": {...}}}
    Use for line-level tag_match in reranker; falls back to document_tags in reranker when empty.
    """
    if not chunks or not (rag_url or "").strip():
        return {}
    doc_ids = list({str(c.get("document_id", "")) for c in chunks if isinstance(c, dict) and c.get("document_id")})
    if not doc_ids:
        return {}
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        return {}

    def _to_weighted_dict(val) -> dict[str, float]:
        if val is None:
            return {}
        if isinstance(val, dict):
            out: dict[str, float] = {}
            for k, v in val.items():
                if not k:
                    continue
                w = 1.0
                if isinstance(v, (int, float)):
                    w = float(v)
                elif v is True:
                    w = 1.0
                out[str(k)] = max(0.0, min(1.0, w))
            return out
        return {}

    try:
        conn = psycopg2.connect(rag_url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT document_id, normalized_text, p_tags, d_tags, j_tags FROM policy_line_tags "
            "WHERE document_id::text = ANY(%s) AND (p_tags IS NOT NULL OR d_tags IS NOT NULL OR j_tags IS NOT NULL)",
            (doc_ids,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except psycopg2.ProgrammingError as e:
        if "policy_line_tags" in str(e) or "does not exist" in str(e).lower():
            return {}
        raise
    except Exception as e:
        logger.warning("Failed to fetch line tags for chunks: %s", e)
        return {}

    out: dict[tuple[str, str], dict[str, dict[str, float]]] = {}
    for r in rows:
        doc_id = str(r.get("document_id", ""))
        norm = (r.get("normalized_text") or "").strip()
        if not doc_id or not norm:
            continue
        key = (doc_id, norm)
        out[key] = {
            "p_tags": _to_weighted_dict(r.get("p_tags")),
            "d_tags": _to_weighted_dict(r.get("d_tags")),
            "j_tags": _to_weighted_dict(r.get("j_tags")),
        }
    return out


def fetch_document_tags_by_ids(
    rag_url: str,
    document_ids: list[str],
) -> dict[str, dict[str, dict[str, float]]]:
    """Fetch p_tags, d_tags, j_tags with weights for each document_id from document_tags.

    Returns: {document_id: {"p_tags": {code: weight}, "d_tags": {...}, "j_tags": {...}}}
    Weights from jsonb (default 1.0 if stored as true/boolean).
    """
    if not document_ids or not (rag_url or "").strip():
        return {}
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        return {}
    try:
        conn = psycopg2.connect(rag_url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT document_id, p_tags, d_tags, j_tags FROM document_tags WHERE document_id::text = ANY(%s)",
            (document_ids,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning("Failed to fetch document_tags: %s", e)
        return {}

    def _to_weighted_dict(val) -> dict[str, float]:
        if val is None:
            return {}
        if isinstance(val, dict):
            out: dict[str, float] = {}
            for k, v in val.items():
                if not k:
                    continue
                w = 1.0
                if isinstance(v, (int, float)):
                    w = float(v)
                elif v is True:
                    w = 1.0
                out[str(k)] = max(0.0, min(1.0, w))
            return out
        return {}

    out: dict[str, dict[str, dict[str, float]]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        doc_id = str(r.get("document_id", ""))
        if not doc_id:
            continue
        out[doc_id] = {
            "p_tags": _to_weighted_dict(r.get("p_tags")),
            "d_tags": _to_weighted_dict(r.get("d_tags")),
            "j_tags": _to_weighted_dict(r.get("j_tags")),
        }
    return out


def _resolve_document_ids(rag_url: str, p_codes: list[str], d_codes: list[str], j_codes: list[str]) -> list[str]:
    """Find document_ids in document_tags where p_tags/d_tags/j_tags overlap with given codes."""
    if not p_codes and not d_codes and not j_codes:
        return []
    try:
        import psycopg2
    except ImportError:
        return []
    try:
        conn = psycopg2.connect(rag_url)
        cur = conn.cursor()
        conditions = []
        params: list[list[str]] = []
        if p_codes:
            conditions.append("(p_tags IS NOT NULL AND p_tags ?| %s)")
            params.append(p_codes)
        if d_codes:
            conditions.append("(d_tags IS NOT NULL AND d_tags ?| %s)")
            params.append(d_codes)
        if j_codes:
            conditions.append("(j_tags IS NOT NULL AND j_tags ?| %s)")
            params.append(j_codes)
        where = " OR ".join(conditions)
        cur.execute(
            f"SELECT DISTINCT document_id FROM document_tags WHERE {where}",
            params,
        )
        ids = [str(r[0]) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return ids
    except Exception as e:
        logger.warning("Failed to resolve document_ids from document_tags: %s", e)
        return []


def tag_question_and_resolve_document_ids(
    question: str,
    rag_database_url: str,
    emitter: Callable[[str], None] | None = None,
) -> JPDTagResult:
    """Tag question with J/P/D using lexicon, resolve document_ids for BM25 scoping.

    Returns JPDTagResult with p_tags, d_tags, j_tags and document_ids. If lexicon/rag unavailable,
    returns empty result with error message.
    """
    def _emit(msg: str) -> None:
        if emitter and msg.strip():
            emitter(msg.strip())

    result = JPDTagResult()
    if not (rag_database_url or "").strip():
        result.error = "RAG_DATABASE_URL not set; cannot load lexicon or document_tags"
        return result

    lexicon = _load_lexicon_sync(rag_database_url)
    if not lexicon:
        result.error = "Could not load lexicon from RAG DB"
        return result

    n_p = len(lexicon.p_tags or {})
    n_d = len(lexicon.d_tags or {})
    n_j = len(lexicon.j_tags or {})
    _emit(f"J/P/D tagger: lexicon loaded from policy_lexicon_entries (p={n_p} d={n_d} j={n_j} codes)")

    phrase_map, refuted_map = _get_phrase_to_tag_map(lexicon)
    if not phrase_map:
        _emit("J/P/D tagger: lexicon has 0 phrases; no tags applied")
        return result

    _emit(f"J/P/D tagger: phrase map built with {len(phrase_map)} phrase(s)")

    p_tags, d_tags, j_tags = _apply_tags_to_line_text(question, phrase_map, refuted_map)
    result.p_tags = p_tags
    result.d_tags = d_tags
    result.j_tags = j_tags

    if not result.has_tags:
        _emit("J/P/D tagger: no tags matched question (no p/d/j codes)")
        return result

    p_codes = list(p_tags.keys())
    d_codes = list(d_tags.keys())
    j_codes = list(j_tags.keys())
    _emit(f"J/P/D tagger: question matched p={p_codes} d={d_codes} j={j_codes} (from document_tags ?| overlap)")
    _emit(f"J/P/D tagger: resolving document_ids: SELECT document_id FROM document_tags WHERE (p_tags?|p_codes OR d_tags?|d_codes OR j_tags?|j_codes)")

    doc_ids = _resolve_document_ids(rag_database_url, p_codes, d_codes, j_codes)
    result.document_ids = doc_ids
    _emit(f"J/P/D tagger: -> {len(doc_ids)} document(s)" + (f" e.g. {doc_ids[:3]}" if doc_ids else ""))
    return result


def extract_tags_from_text(
    text: str,
    rag_database_url: str,
    kinds: tuple[str, ...] = ("j",),
) -> dict[str, dict[str, float]]:
    """Extract p/d/j tags from text using lexicon phrase matching (same logic as retriever).

    Use from chat to parse user clarification input (e.g. "AHCA and Sunshine Health")
    into j_tag codes aligned with RAG retrieval.

    Args:
        text: User input to tag (message, clarification selection, etc.)
        rag_database_url: RAG DB URL for policy_lexicon_entries
        kinds: Which tag types to return: ("p",), ("d",), ("j",) or combination

    Returns:
        Dict with keys p_tags, d_tags, j_tags (only requested kinds). Values are {code: score}.
    """
    out: dict[str, dict[str, float]] = {"p_tags": {}, "d_tags": {}, "j_tags": {}}
    if not (text or "").strip() or not (rag_database_url or "").strip():
        return out

    lexicon = _load_lexicon_sync(rag_database_url)
    if not lexicon:
        return out

    phrase_map, refuted_map = _get_phrase_to_tag_map(lexicon)
    if not phrase_map:
        return out

    p_tags, d_tags, j_tags = _apply_tags_to_line_text(text, phrase_map, refuted_map)
    if "p" in kinds:
        out["p_tags"] = p_tags
    if "d" in kinds:
        out["d_tags"] = d_tags
    if "j" in kinds:
        out["j_tags"] = j_tags
    return out


def list_j_tag_options(
    rag_database_url: str,
    dimension: str | None = None,
) -> list[dict[str, str]]:
    """List j_tag options from lexicon for clarification UI. Source of truth for choices.

    Args:
        rag_database_url: RAG DB URL for policy_lexicon_entries
        dimension: Optional filter by j_tag prefix: "state", "payor", "program",
            "regulatory_authority", or None for all. Perspective codes (provider, patient)
            have no prefix.

    Returns:
        List of {code, label}. label = spec.description or first phrase/alias.
    """
    if not (rag_database_url or "").strip():
        return []

    lexicon = _load_lexicon_sync(rag_database_url)
    j_tags = getattr(lexicon, "j_tags", None) if lexicon else None
    if not isinstance(j_tags, dict):
        return []

    dim = (dimension or "").strip()
    result: list[dict[str, str]] = []
    for code, spec in j_tags.items():
        if not isinstance(spec, dict):
            continue
        code_str = str(code)
        if dim:
            if dim == "perspective":
                if "." in code_str:
                    continue
            else:
                if not code_str.startswith(f"{dim}."):
                    continue
        label = _j_tag_label(spec, code_str)
        result.append({"code": code_str, "label": label or code_str})
    return sorted(result, key=lambda x: (x["label"].lower(), x["code"]))


def _j_tag_label(spec: dict, code: str) -> str:
    """Get display label for j_tag from spec: description or first phrase/alias."""
    desc = spec.get("description")
    if isinstance(desc, str) and desc.strip():
        return desc.strip()
    for key in ("phrases", "strong_phrases", "aliases"):
        val = spec.get(key)
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
    return code.replace("_", " ").replace(".", " ").title()


def get_phrases_for_j_tags(
    j_tags: dict[str, float],
    rag_database_url: str,
) -> list[str]:
    """Return phrases from lexicon that map to the given j_tag codes.
    Use to strip jurisdiction from intent: remove these phrases from the intent string.
    Returns unique phrases sorted by length descending (strip longer first)."""
    if not j_tags or not (rag_database_url or "").strip():
        return []

    lexicon = _load_lexicon_sync(rag_database_url)
    j_specs = getattr(lexicon, "j_tags", None) if lexicon else {}
    if not isinstance(j_specs, dict):
        return []

    phrases: list[str] = []
    seen: set[str] = set()
    for code in j_tags:
        spec = j_specs.get(code) if isinstance(j_specs.get(code), dict) else {}
        code_phrases: list[str] = []
        for key in ("phrases", "strong_phrases", "aliases"):
            val = spec.get(key)
            if isinstance(val, list):
                for p in val:
                    if p and isinstance(p, str) and (s := str(p).strip()):
                        code_phrases.append(s)
        if not code_phrases and isinstance(spec.get("description"), str):
            d = spec["description"].strip()
            if d:
                code_phrases.append(d)
        weak = spec.get("weak_keywords")
        if isinstance(weak, dict):
            for p in (weak.get("any_of") or []):
                if p and isinstance(p, str) and (s := str(p).strip()):
                    code_phrases.append(s)
        for s in code_phrases:
            s_lower = s.lower()
            if s_lower not in seen:
                seen.add(s_lower)
                phrases.append(s)
    # Sort by length desc so we strip "Sunshine Health" before "Sunshine"
    phrases.sort(key=len, reverse=True)
    return phrases


def j_tags_to_jurisdiction(
    j_tags: dict[str, float],
    rag_database_url: str,
) -> dict[str, str | None]:
    """Map j_tag codes to jurisdiction fields for state patch. Uses lexicon for display values.

    Args:
        j_tags: {code: score} from extract_tags_from_text
        rag_database_url: RAG DB URL for lexicon

    Returns:
        Dict with keys state, payor, program, perspective, regulatory_agency.
        Values are display strings from lexicon (description or phrase). Unset keys omitted.
    """
    if not j_tags or not (rag_database_url or "").strip():
        return {}

    lexicon = _load_lexicon_sync(rag_database_url)
    j_specs = getattr(lexicon, "j_tags", None) if lexicon else {}
    if not isinstance(j_specs, dict):
        return {}

    out: dict[str, str | None] = {}
    for code in j_tags:
        spec = j_specs.get(code) if isinstance(j_specs.get(code), dict) else {}
        label = _j_tag_label(spec, code)

        if code.startswith("state."):
            out["state"] = label
        elif code.startswith("payor."):
            out["payor"] = label
        elif code.startswith("program."):
            out["program"] = label
        elif code.startswith("regulatory_authority."):
            out["regulatory_agency"] = label
        elif code == "provider":
            out["perspective"] = "provider_office"
        elif code == "patient":
            out["perspective"] = "patient"
    return out
