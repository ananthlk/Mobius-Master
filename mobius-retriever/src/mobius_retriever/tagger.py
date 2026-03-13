"""Extract tags from question text for BM25 corpus scoping. No external deps."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class QuestionTags:
    """Tags extracted from question for filtering (namespace-level)."""
    payer: str | None = None
    program: str | None = None
    state: str | None = None
    authority_level: str | None = None

    def as_filters(self) -> dict[str, str]:
        """Return dict of non-empty filters for SQL WHERE."""
        out: dict[str, str] = {}
        if (self.payer or "").strip():
            out["document_payer"] = self.payer.strip()
        if (self.program or "").strip():
            out["document_program"] = self.program.strip()
        if (self.state or "").strip():
            out["document_state"] = self.state.strip()
        if (self.authority_level or "").strip():
            out["document_authority_level"] = self.authority_level.strip()
        return out


# Canonical payers (align with document_payer in index)
PAYER_NAMES = (
    "Sunshine Health", "Sunshine", "UnitedHealthcare", "United Healthcare", "UHC",
    "Molina", "Aetna", "Humana", "Cigna", "Anthem", "Blue Cross",
)

# Program keywords -> canonical
PROGRAM_KEYWORDS: list[tuple[list[str], str]] = [
    (["medicaid", "medicaid managed care", "mco"], "Medicaid"),
    (["medicare", "medicare advantage", "ma plan"], "Medicare"),
]

# State: abbrevs and full names -> canonical abbrev (matches document_state in index)
STATE_ABBREVS = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
)
# Full name -> abbrev (index typically uses FL not Florida)
STATE_NAME_TO_ABBREV = {
    "Florida": "FL", "North Carolina": "NC", "Texas": "TX", "California": "CA",
    "New York": "NY", "Georgia": "GA", "Ohio": "OH", "Pennsylvania": "PA",
    "Arizona": "AZ", "Illinois": "IL", "Michigan": "MI",
}


def tag_question(text: str) -> QuestionTags:
    """Extract payer, program, state from question text for corpus filtering."""
    t = (text or "").strip()
    tl = t.lower()
    tags = QuestionTags()

    # Payer
    for name in PAYER_NAMES:
        if name.lower() in tl and name.lower() not in ("medicaid", "medicare"):
            tags.payer = name
            break

    # Program
    for keywords, program in PROGRAM_KEYWORDS:
        for kw in keywords:
            if len(kw) <= 3:
                if re.search(r"\b" + re.escape(kw) + r"\b", tl):
                    tags.program = program
                    break
            else:
                if kw in tl:
                    tags.program = program
                    break
        if tags.program:
            break

    # State: full names first (normalize to abbrev), then abbrevs with context
    for name, ab in STATE_NAME_TO_ABBREV.items():
        if name.lower() in tl:
            tags.state = ab
            break
    if not tags.state:
        ctx_patterns: list[str] = [
            r"(?:,|\()\s*(?P<ab>[A-Z]{2})\b",
            r"\bstate\s+of\s+(?P<ab>[A-Z]{2})\b",
            r"\bin\s+(?P<ab>[A-Z]{2})\b",
        ]
        for pat in ctx_patterns:
            m = re.search(pat, t, re.I)
            if m:
                ab = (m.group("ab") or "").upper()
                if ab in STATE_ABBREVS and ab != "ID":  # avoid "member ID"
                    tags.state = ab
                    break

    return tags
