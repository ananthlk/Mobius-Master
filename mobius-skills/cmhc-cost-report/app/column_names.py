"""
Column display names for CMHC HCRIS worksheets (form 2088-17).
Source: CMS Form CMS-2088-17, Provider Reimbursement Manual Part II Ch 45.
Maps (worksheet_code, column_number) -> human-readable name for grid/table headers.
"""
from typing import Any

# Worksheet A000000 = Statement of Costs by Cost Center (CMHC 2088-17)
# Column codes from HCRIS; names aligned with form layout.
_WS_A000000: dict[int, str] = {
    0: "Cost center / Description",
    100: "Total costs (prior year)",
    200: "Direct cost",
    400: "Total cost",
    500: "Adjustment",
    600: "Net cost",
    700: "Other adjustment",
    800: "Total (settled/final)",
}

# Add common variants (string keys for worksheet)
_CMHC17_WORKSHEETS: dict[str, dict[int, str]] = {
    "A000000": _WS_A000000,
    "A": _WS_A000000,
}

# Form vintage -> worksheet -> column -> name (extend for 2088-92 if needed)
_BY_VINTAGE: dict[str, dict[str, dict[int, str]]] = {
    "2088-17": _CMHC17_WORKSHEETS,
}


def get_column_name(
    worksheet_code: str,
    column_number: int,
    form_vintage: str = "2088-17",
) -> str:
    """Return display name for a worksheet column, or fallback to 'Col {number}'."""
    by_ws = _BY_VINTAGE.get(form_vintage, _CMHC17_WORKSHEETS)
    for key in (worksheet_code, worksheet_code.strip(), worksheet_code.upper()):
        col_map = by_ws.get(key)
        if col_map is not None:
            name = col_map.get(column_number)
            if name:
                return name
    return f"Col {column_number}"


def get_column_names(
    worksheet_code: str,
    column_numbers: list[int],
    form_vintage: str = "2088-17",
) -> list[str]:
    """Return list of display names in same order as column_numbers."""
    return [
        get_column_name(worksheet_code, c, form_vintage)
        for c in column_numbers
    ]
