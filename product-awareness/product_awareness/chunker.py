"""Markdown → chunks.

One chunk per ``##`` H2 section (split if long), plus a small overview chunk from the
title + tagline. Carries the reality-gate ``status`` flag: chunks under
``## Not yet available (planned)`` are ``planned``; everything else ``current``. That
flag is what lets search split ``docs_gap`` (miss) from ``feature_request`` (planned hit).
``## Doc-readiness notes`` is author meta and is never ingested.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from . import config

_H1 = re.compile(r"^#\s+(.*)$")
_H2 = re.compile(r"^##\s+(.*)$")


@dataclass
class Chunk:
    chunk_id: str
    module: str
    doc_title: str
    section: str
    doc_type: str
    audience: str
    status: str          # current | planned
    in_scope: bool
    source_path: str
    source_commit: str
    text: str
    n_chars: int

    def to_dict(self) -> dict:
        return asdict(self)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _split_long(text: str, max_chars: int) -> list[str]:
    """Pack paragraphs/bullet-groups (double-newline boundaries) up to max_chars."""
    if len(text) <= max_chars:
        return [text]
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if cur and len(cur) + len(para) + 2 > max_chars:
            parts.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        parts.append(cur)
    return parts


def chunk_file(path: Path, source_commit: str = "uncommitted") -> list[Chunk]:
    meta = config.DOC_META.get(path.name)
    if meta is None:
        return []  # not a known manual (e.g. README.md) — skip
    module, audience, in_scope = meta["module"], meta["audience"], meta["in_scope"]
    rel = str(path.relative_to(config.REPO_ROOT))
    lines = path.read_text(encoding="utf-8").splitlines()

    # title (H1) + tagline (following blockquote)
    doc_title, tagline, start = path.stem, "", 0
    for j, ln in enumerate(lines):
        m = _H1.match(ln)
        if m:
            doc_title = m.group(1).strip()
            for k in range(j + 1, min(j + 4, len(lines))):
                if lines[k].startswith(">"):
                    tagline = lines[k].lstrip("> ").strip()
                    break
            start = j + 1
            break

    # partition into H2 sections
    sections: list[tuple[str, list[str]]] = []
    head, body = None, []
    for ln in lines[start:]:
        m = _H2.match(ln)
        if m:
            if head is not None:
                sections.append((head, body))
            head, body = m.group(1).strip(), []
        elif head is not None:
            body.append(ln)
    if head is not None:
        sections.append((head, body))

    chunks: list[Chunk] = []

    def mk(chunk_id, section, doc_type, status, text):
        chunks.append(Chunk(
            chunk_id=chunk_id, module=module, doc_title=doc_title, section=section,
            doc_type=doc_type, audience=audience, status=status, in_scope=in_scope,
            source_path=rel, source_commit=source_commit, text=text, n_chars=len(text)))

    if tagline:
        # Thin overview chunks (title+tagline only) win retrieval on identity-ish
        # queries but can't answer them (the honesty critic flags "only a title with
        # no body"). Fold in the Purpose section's first paragraph so the overview
        # is substantive enough to answer what it attracts.
        purpose_lead = ""
        for heading, body_lines in sections:
            if heading == "Purpose":
                body_text = "\n".join(body_lines).strip()
                purpose_lead = body_text.split("\n\n", 1)[0].strip()
                break
        text = f"# {doc_title}\n\n{tagline}"
        if purpose_lead:
            text += f"\n\n{purpose_lead}"
        mk(f"{module}:overview:0", "Overview", "overview", "current", text)

    for heading, body_lines in sections:
        if heading in config.EXCLUDE_SECTIONS:
            continue
        body_text = "\n".join(body_lines).strip()
        if not body_text:
            continue
        status = "planned" if heading.lower().startswith("not yet available") else "current"
        doc_type = config.SECTION_DOC_TYPE.get(heading, "reference")
        for n, piece in enumerate(_split_long(body_text, config.MAX_CHUNK_CHARS)):
            mk(f"{module}:{_slug(heading)}:{n}", heading, doc_type, status,
               f"# {doc_title} — {heading}\n\n{piece}")

    return chunks
