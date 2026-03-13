"""J_tags jurisdiction alignment: conventions for j_tag codes that scope retrieval by jurisdiction.

See docs/J_TAGS_JURISDICTION.md for full specification.
"""

# Prefixes for jurisdiction j_tag codes (e.g. state.FL, payor.sunshine)
J_TAG_PREFIX_STATE = "state."
J_TAG_PREFIX_PAYOR = "payor."
J_TAG_PREFIX_PROGRAM = "program."

# Perspective codes (no prefix)
J_TAG_PROVIDER = "provider"
J_TAG_PATIENT = "patient"


def jurisdiction_to_j_tag_code(dimension: str, value: str) -> str | None:
    """Build a j_tag code from jurisdiction dimension and value.

    dimension: 'state' | 'payor' | 'program' | 'perspective'
    value: e.g. 'FL', 'sunshine', 'medicaid', 'provider_office' -> 'provider'

    Returns None if dimension/value not recognized.
    """
    if not value or not isinstance(value, str):
        return None
    v = value.strip().lower()
    if not v:
        return None
    if dimension == "state":
        return J_TAG_PREFIX_STATE + v.upper() if len(v) == 2 else J_TAG_PREFIX_STATE + v.replace(" ", "_")
    if dimension == "payor":
        return J_TAG_PREFIX_PAYOR + v.replace(" ", "_")
    if dimension == "program":
        return J_TAG_PREFIX_PROGRAM + v.replace(" ", "_")
    if dimension == "perspective":
        if v in ("provider_office", "provider"):
            return J_TAG_PROVIDER
        if v == "patient":
            return J_TAG_PATIENT
    return None
