"""
Per-client address normalization for L1/L2 matching.
USPS-style normalization: ZIP5 extraction, street suffix expansion, directionals.
No external API required; can be extended with Google Address Validation later.
"""
from __future__ import annotations

import re
from typing import Any

# USPS street suffix abbreviations -> canonical form
STREET_SUFFIX_MAP: dict[str, str] = {
    "allee": "alley", "aly": "alley", "anex": "annex", "annex": "annex", "anx": "annex",
    "arc": "arcade", "arcade": "arcade", "av": "avenue", "ave": "avenue", "avenue": "avenue",
    "bayoo": "bayou", "bayou": "bayou", "bch": "beach", "beach": "beach",
    "bend": "bend", "blf": "bluff", "bluf": "bluff", "bluff": "bluff",
    "blvd": "boulevard", "boul": "boulevard", "boulevard": "boulevard",
    "br": "branch", "brnch": "branch", "branch": "branch",
    "byp": "bypass", "bypa": "bypass", "bypass": "bypass",
    "cir": "circle", "circ": "circle", "crcl": "circle", "crcle": "circle", "circle": "circle",
    "clb": "club", "club": "club",
    "cmn": "common", "common": "common",
    "cor": "corner", "corners": "corners", "corner": "corner",
    "ct": "court", "courts": "courts", "court": "court",
    "cres": "crescent", "crescent": "crescent", "crst": "crescent",
    "ctr": "center", "center": "center", "centre": "center", "centers": "centers",
    "dr": "drive", "driv": "drive", "drive": "drive", "drv": "drive",
    "est": "estate", "estate": "estate", "estates": "estates",
    "exp": "expressway", "expr": "expressway", "express": "expressway", "expressway": "expressway",
    "ext": "extension", "extension": "extension", "extn": "extension",
    "fld": "field", "field": "field", "fields": "fields",
    "flt": "flat", "flat": "flat", "flts": "flats",
    "frd": "ford", "ford": "ford", "fords": "fords",
    "forest": "forest", "forests": "forests", "frst": "forest",
    "fry": "ferry", "ferry": "ferry",
    "gdn": "garden", "garden": "garden", "gardn": "garden", "gardens": "gardens",
    "gateway": "gateway", "gtwy": "gateway",
    "gln": "glen", "glen": "glen", "glens": "glens",
    "grn": "green", "green": "green", "greens": "greens",
    "hbr": "harbor", "harbor": "harbor", "harbors": "harbors", "harbr": "harbor",
    "hvn": "haven", "haven": "haven",
    "hts": "heights", "heights": "heights", "hgts": "heights",
    "hwy": "highway", "highway": "highway", "highwy": "highway",
    "holw": "hollow", "hollow": "hollow", "holws": "hollows",
    "inlt": "inlet", "inlet": "inlet",
    "is": "island", "island": "island", "islands": "islands", "islnd": "island",
    "jct": "junction", "junction": "junction", "jctn": "junction", "junctn": "junction",
    "ln": "lane", "lane": "lane", "lanes": "lanes",
    "lndg": "landing", "landing": "landing",
    "lk": "lake", "lake": "lake", "lakes": "lakes",
    "lcks": "locks", "locks": "locks",
    "mdw": "meadow", "meadows": "meadows", "medows": "meadows",
    "ml": "mill", "mills": "mills", "mill": "mill",
    "mnr": "manor", "manor": "manor", "manors": "manors",
    "mt": "mount", "mount": "mount", "mnt": "mount", "mtn": "mountain", "mountain": "mountain",
    "pkwy": "parkway", "parkway": "parkway", "parkwy": "parkway",
    "pass": "pass", "path": "path", "pike": "pike", "pikes": "pike",
    "pl": "place", "place": "place", "plz": "plaza", "plza": "plaza", "plaza": "plaza",
    "pt": "point", "point": "point", "points": "points",
    "pr": "prairie", "prr": "prairie", "prairie": "prairie",
    "rd": "road", "road": "road", "roads": "roads",
    "row": "row",
    "run": "run",
    "shr": "shore", "shore": "shore", "shores": "shores",
    "sq": "square", "sqr": "square", "sqre": "square", "squ": "square", "square": "square",
    "st": "street", "str": "street", "street": "street", "streets": "streets", "strt": "street",
    "ter": "terrace", "terr": "terrace", "terrace": "terrace",
    "trl": "trail", "trail": "trail", "trails": "trails", "trls": "trails",
    "tunl": "tunnel", "tunnel": "tunnel", "tunls": "tunnels",
    "tpke": "turnpike", "turnpike": "turnpike", "trnpk": "turnpike",
    "un": "union", "union": "union", "unions": "unions",
    "vly": "valley", "valley": "valley", "valleys": "valleys", "vally": "valley",
    "via": "viaduct", "viaduct": "viaduct", "vdct": "viaduct",
    "vis": "vista", "vista": "vista", "vst": "vista", "vsta": "vista",
    "way": "way", "ways": "ways",
}

# Ordinal numbers for street matching
ORDINAL_MAP: dict[str, str] = {
    "1st": "first", "first": "first", "2nd": "second", "second": "second",
    "3rd": "third", "third": "third", "4th": "fourth", "fourth": "fourth",
    "5th": "fifth", "fifth": "fifth", "6th": "sixth", "sixth": "sixth",
    "7th": "seventh", "seventh": "seventh", "8th": "eighth", "eighth": "eighth",
    "9th": "ninth", "ninth": "ninth", "10th": "tenth", "tenth": "tenth",
}

# Directional prefixes/suffixes
DIRECTION_MAP: dict[str, str] = {
    "n": "north", "north": "north",
    "s": "south", "south": "south",
    "e": "east", "east": "east",
    "w": "west", "west": "west",
    "ne": "northeast", "northeast": "northeast",
    "nw": "northwest", "northwest": "northwest",
    "se": "southeast", "southeast": "southeast",
    "sw": "southwest", "southwest": "southwest",
}


def extract_zip5(zip_val: str | None) -> str:
    """Extract first 5 digits from zip (handles 32808, 32808-5646, 328085646)."""
    if not zip_val:
        return ""
    s = re.sub(r"\D", "", str(zip_val))
    return s[:5] if len(s) >= 5 else s


def normalize_state(state: str | None) -> str:
    """Normalize state to 2-letter uppercase."""
    if not state:
        return ""
    s = str(state).strip().upper()
    if s == "FLORIDA":
        return "FL"
    return s[:2] if len(s) >= 2 else s


def normalize_city(city: str | None) -> str:
    """Normalize city for matching: lowercase, collapse spaces."""
    if not city:
        return ""
    return " ".join(str(city).lower().split())


def normalize_street(addr: str | None) -> str:
    """
    Normalize street address for matching.
    - Strip punctuation, collapse spaces
    - Expand suffixes (DR -> drive, ST -> street)
    - Expand directionals (E -> east, W -> west)
    - Lowercase for comparison
    """
    if not addr:
        return ""
    s = str(addr).strip()
    s = re.sub(r"[,.]", " ", s)
    s = " ".join(s.split()).lower()
    words = s.split()
    out = []
    for w in words:
        if w in DIRECTION_MAP:
            out.append(DIRECTION_MAP[w])
        elif w in STREET_SUFFIX_MAP:
            out.append(STREET_SUFFIX_MAP[w])
        elif w in ORDINAL_MAP:
            out.append(ORDINAL_MAP[w])
        else:
            out.append(w)
    return " ".join(out)


def normalized_address_key(
    site_address_line_1: str | None,
    site_city: str | None,
    site_state: str | None,
    site_zip: str | None,
) -> str:
    """Produce a comparable key for matching: normalized street | city | state | zip5."""
    street = normalize_street(site_address_line_1)
    city = normalize_city(site_city)
    state = normalize_state(site_state)
    zip5 = extract_zip5(site_zip)
    return f"{street}|{city}|{state}|{zip5}"


def _street_core(street: str) -> str:
    """Strip leading directional from street (e.g. '434 west kennedy boulevard' -> '434 kennedy boulevard')."""
    if not street:
        return street
    words = street.split()
    if len(words) >= 2 and words[1] in {"north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"}:
        return " ".join([words[0]] + words[2:])
    return street


def normalized_address_key_core(
    site_address_line_1: str | None,
    site_city: str | None,
    site_state: str | None,
    site_zip: str | None,
) -> str:
    """Key with leading directional stripped from street, for fallback matching (e.g. '434 W Kennedy' vs '434 Kennedy Blvd')."""
    street = normalize_street(site_address_line_1)
    street_core = _street_core(street)
    city = normalize_city(site_city)
    state = normalize_state(site_state)
    zip5 = extract_zip5(site_zip)
    return f"{street_core}|{city}|{state}|{zip5}"


def normalize_location_for_matching(loc: dict[str, Any]) -> dict[str, Any]:
    """
    Add normalized fields to a location dict for matching.
    Returns a copy with: normalized_key, normalized_zip5, normalized_street, normalized_city, normalized_state.
    """
    addr = loc.get("site_address_line_1") or ""
    city = loc.get("site_city") or ""
    state = loc.get("site_state") or "FL"
    zip_val = loc.get("site_zip") or loc.get("site_zip9") or ""
    out = dict(loc)
    out["normalized_zip5"] = extract_zip5(zip_val)
    out["normalized_street"] = normalize_street(addr)
    out["normalized_city"] = normalize_city(city)
    out["normalized_state"] = normalize_state(state)
    out["normalized_key"] = normalized_address_key(addr, city, state, zip_val)
    return out
