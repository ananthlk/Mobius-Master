"""
Google Address Validation API client for normalizing addresses.

Used for L1/L2 and bh_roster address matching: normalizes addresses so "434 West Kennedy Blvd"
and "434 W Kennedy" resolve to the same canonical form.

Requires: GOOGLE_APPLICATION_CREDENTIALS or gcloud auth, and Address Validation API enabled.
Falls back to None (caller uses local normalizer) if API unavailable.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NormalizedAddress:
    """Canonical address from Google or local fallback."""
    address_line_1: str
    city: str
    state: str
    zip5: str
    zip_plus_4: str
    formatted_address: str

    def street_zip_key(self) -> str:
        """Key for street+unit matching: normalized address_line_1|zip5."""
        line1 = " ".join((self.address_line_1 or "").upper().split())
        return f"{line1}|{self.zip5}"

    def zip_only_key(self) -> str:
        """Key for zip-only matching."""
        return self.zip5


def _extract_zip5(zip_val: str) -> str:
    digits = re.sub(r"\D", "", str(zip_val or ""))
    return digits[:5] if len(digits) >= 5 else ""


def normalize_via_google(
    address_line_1: str,
    city: str,
    state: str,
    postal_code: str | None = None,
    *,
    region_code: str = "US",
) -> NormalizedAddress | None:
    """
    Validate and normalize an address via Google Address Validation API.
    Returns NormalizedAddress or None if API fails / unavailable.
    """
    try:
        from google.maps import addressvalidation_v1
        from google.type import postal_address_pb2
    except ImportError as e:
        logger.debug("google-maps-addressvalidation not installed: %s", e)
        return None

    addr_line = (address_line_1 or "").strip()
    city_val = (city or "").strip()
    state_val = (state or "").strip()
    zip_val = (postal_code or "").strip()
    if not addr_line and not city_val:
        return None

    lines = [addr_line]
    if city_val or state_val or zip_val:
        parts = [p for p in [city_val, state_val, zip_val] if p]
        if parts:
            lines.append(", ".join(parts))

    try:
        client = addressvalidation_v1.AddressValidationClient()
        pa = postal_address_pb2.PostalAddress(
            region_code=region_code,
            address_lines=lines,
        )
        if city_val:
            pa.locality = city_val
        if state_val and len(state_val) <= 3:
            pa.administrative_area = state_val
        if zip_val:
            pa.postal_code = zip_val

        request = addressvalidation_v1.ValidateAddressRequest(address=pa)
        response = client.validate_address(request=request)

        if not response.result or not response.result.address:
            return None

        result_addr = response.result.address
        pa_out = result_addr.postal_address
        if not pa_out:
            return None

        line1 = pa_out.address_lines[0] if pa_out.address_lines else addr_line
        locality = pa_out.locality or city_val
        admin = pa_out.administrative_area or state_val
        postal = pa_out.postal_code or zip_val
        digits = re.sub(r"\D", "", str(postal))
        zip5 = digits[:5] if len(digits) >= 5 else str(postal)
        zip_plus = digits[5:9] if len(digits) >= 9 else ""
        formatted = result_addr.formatted_address or ""

        return NormalizedAddress(
            address_line_1=line1,
            city=locality,
            state=admin,
            zip5=zip5,
            zip_plus_4=zip_plus,
            formatted_address=formatted,
        )
    except Exception as e:
        logger.warning("Google Address Validation API failed: %s", e)
        return None


def normalized_from_local(
    address_line_1: str,
    city: str,
    state: str,
    postal_code: str | None,
) -> NormalizedAddress:
    """Build NormalizedAddress from local normalization when Google is unavailable."""
    from app.address_normalizer import normalize_street, normalize_state, extract_zip5
    line1 = normalize_street(address_line_1).strip() or (address_line_1 or "").strip()
    zip5 = extract_zip5(postal_code)
    digits = re.sub(r"\D", "", str(postal_code or ""))
    zip_plus = digits[5:9] if len(digits) >= 9 else ""
    return NormalizedAddress(
        address_line_1=line1,
        city=(city or "").strip(),
        state=normalize_state(state),
        zip5=zip5,
        zip_plus_4=zip_plus,
        formatted_address="",
    )
