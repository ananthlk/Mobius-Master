"""
Parse HCRIS CMHC zip contents: RPT, NMRC, Alpha CSVs into normalized row dicts.
Maps CMS column names to our schema (report_record_key, provider_ccn, worksheet, line, column, value).
"""
import io
import zipfile
from typing import Any, Iterator

import pandas as pd


# CMS HCRIS column name variants (RPT)
RPT_KEY_COLS = ["RPT_REC_NUM", "Report_Record_Number"]
RPT_CCN_COLS = ["PRVDR_NUM", "Provider_Number"]
RPT_FY_BGN_COLS = ["FY_BGN_DT", "Fiscal_Year_Begin_Date"]
RPT_FY_END_COLS = ["FY_END_DT", "Fiscal_Year_End_Date"]
RPT_STATUS_COLS = ["RPT_STUS_CD", "Report_Status_Code", "RPT_STUS"]

# NMRC / Alpha
NMRC_KEY_COLS = ["RPT_REC_NUM", "Report_Record_Number"]
NMRC_WKSHT_COLS = ["WKSHT_CD", "Worksheet_Code", "WKSHT_CD_NMBR"]
NMRC_LINE_COLS = ["LINE_NUM", "Line_Number"]
NMRC_CLMN_COLS = ["CLMN_NUM", "Column_Number"]
NMRC_VAL_COLS = ["ITM_VAL_NUM", "ITEM_VAL", "Item_Value", "Value"]


def _pick_col(row: dict, candidates: list[str]) -> Any:
    for c in candidates:
        if c in row and row[c] is not None and str(row[c]).strip() != "":
            return row[c]
    return None


def _parse_date(s: Any) -> str | None:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    s = str(s).strip()
    if not s:
        return None
    # Try common formats
    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"]:
        try:
            return pd.to_datetime(s, format=fmt).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
    try:
        return pd.to_datetime(s).strftime("%Y-%m-%d")
    except Exception:
        return None


def parse_rpt_df(df: pd.DataFrame, form_vintage: str) -> list[dict]:
    """Convert RPT dataframe to landing rows."""
    rows = []
    for _, r in df.iterrows():
        row = r.to_dict()
        key = _pick_col(row, RPT_KEY_COLS)
        ccn = _pick_col(row, RPT_CCN_COLS)
        fy_bgn = _parse_date(_pick_col(row, RPT_FY_BGN_COLS))
        fy_end = _parse_date(_pick_col(row, RPT_FY_END_COLS))
        status = _pick_col(row, RPT_STATUS_COLS)
        if key is None:
            key = _pick_col(row, list(df.columns)[:1])  # fallback first col
        if key is None:
            continue
        rows.append({
            "report_record_key": str(key).strip(),
            "provider_ccn": str(ccn).strip() if ccn is not None else None,
            "fiscal_year_start": fy_bgn,
            "fiscal_year_end": fy_end,
            "report_status": str(status).strip() if status is not None else None,
            "form_vintage": form_vintage,
        })
    return rows


def parse_nmrc_df(df: pd.DataFrame) -> list[dict]:
    """Convert NMRC dataframe to landing rows (report_record_key, worksheet, line, column, value)."""
    rows = []
    for _, r in df.iterrows():
        row = r.to_dict()
        key = _pick_col(row, NMRC_KEY_COLS)
        wksht = _pick_col(row, NMRC_WKSHT_COLS)
        line = _pick_col(row, NMRC_LINE_COLS)
        clmn = _pick_col(row, NMRC_CLMN_COLS)
        val = _pick_col(row, NMRC_VAL_COLS)
        if key is None:
            continue
        try:
            line_int = int(float(line)) if line is not None and str(line).strip() else None
        except (ValueError, TypeError):
            line_int = None
        try:
            clmn_int = int(float(clmn)) if clmn is not None and str(clmn).strip() else None
        except (ValueError, TypeError):
            clmn_int = None
        try:
            val_float = float(val) if val is not None and str(val).strip() else None
        except (ValueError, TypeError):
            val_float = None
        rows.append({
            "report_record_key": str(key).strip(),
            "worksheet": str(wksht).strip() if wksht is not None else None,
            "line": line_int,
            "column": clmn_int,
            "value": val_float,
        })
    return rows


def parse_alpha_df(df: pd.DataFrame) -> list[dict]:
    """Convert Alpha/Alphnmrc dataframe to landing rows (value is STRING)."""
    rows = []
    # Alpha value column might be ITM_VAL_TXT or similar
    val_cols = ["ITM_VAL_TXT", "ITEM_VAL", "Item_Value", "Value"] + [
        c for c in df.columns if "VAL" in c.upper() or "TEXT" in c.upper()
    ]
    for _, r in df.iterrows():
        row = r.to_dict()
        key = _pick_col(row, NMRC_KEY_COLS)
        wksht = _pick_col(row, NMRC_WKSHT_COLS)
        line = _pick_col(row, NMRC_LINE_COLS)
        clmn = _pick_col(row, NMRC_CLMN_COLS)
        val = _pick_col(row, val_cols[:5])
        if key is None:
            continue
        try:
            line_int = int(float(line)) if line is not None and str(line).strip() else None
        except (ValueError, TypeError):
            line_int = None
        try:
            clmn_int = int(float(clmn)) if clmn is not None and str(clmn).strip() else None
        except (ValueError, TypeError):
            clmn_int = None
        rows.append({
            "report_record_key": str(key).strip(),
            "worksheet": str(wksht).strip() if wksht is not None else None,
            "line": line_int,
            "column": clmn_int,
            "value": str(val).strip() if val is not None else None,
        })
    return rows


def find_in_zip(
    zip_path: str | io.BytesIO,
    pattern: str,
    exclude: list[str] | None = None,
) -> str | None:
    """Return first member name in zip that contains pattern (case-insensitive). Optionally exclude names containing any of exclude."""
    exclude = exclude or []
    with zipfile.ZipFile(zip_path, "r") as z:
        for name in z.namelist():
            nlower = name.lower()
            if pattern.lower() not in nlower:
                continue
            if any(e.lower() in nlower for e in exclude):
                continue
            return name
    return None


def read_csv_from_zip(zip_path: str | io.BytesIO, member_name: str, header: bool = True) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path, "r") as z:
        with z.open(member_name) as f:
            if header:
                return pd.read_csv(f, dtype=str, low_memory=False)
            try:
                return pd.read_csv(f, dtype=str, header=None, low_memory=False)
            except pd.errors.EmptyDataError:
                return pd.DataFrame()


def _find_all_in_zip(zip_path: str | io.BytesIO, pattern: str, exclude: list[str] | None = None) -> list[str]:
    exclude = exclude or []
    with zipfile.ZipFile(zip_path, "r") as z:
        return [
            n for n in z.namelist()
            if pattern.lower() in n.lower() and not any(e.lower() in n.lower() for e in exclude)
        ]


def parse_rpt_positional(df: pd.DataFrame, form_vintage: str) -> list[dict]:
    """RPT with no header: col 0=report_record_key, 1=report_status, 2=provider_ccn, 5=fy_bgn, 6=fy_end (CMHC17)."""
    rows = []
    for _, r in df.iterrows():
        parts = list(r)
        if len(parts) < 7:
            continue
        key = parts[0] if parts[0] is not None and str(parts[0]).strip() else None
        if key is None:
            continue
        rows.append({
            "report_record_key": str(key).strip(),
            "provider_ccn": str(parts[2]).strip() if len(parts) > 2 and parts[2] else None,
            "fiscal_year_start": _parse_date(parts[5]) if len(parts) > 5 else None,
            "fiscal_year_end": _parse_date(parts[6]) if len(parts) > 6 else None,
            "report_status": str(parts[1]).strip() if len(parts) > 1 and parts[1] else None,
            "form_vintage": form_vintage,
        })
    return rows


def parse_nmrc_positional(df: pd.DataFrame) -> list[dict]:
    """NMRC with no header: col 0=report_record_key, 1=worksheet, 2=line, 3=column, 4=value (CMHC17)."""
    rows = []
    for _, r in df.iterrows():
        parts = list(r)
        if len(parts) < 5:
            continue
        key = parts[0] if parts[0] is not None and str(parts[0]).strip() else None
        if key is None:
            continue
        try:
            line_int = int(float(parts[2])) if parts[2] is not None and str(parts[2]).strip() else None
        except (ValueError, TypeError):
            line_int = None
        try:
            clmn_int = int(float(parts[3])) if parts[3] is not None and str(parts[3]).strip() else None
        except (ValueError, TypeError):
            clmn_int = None
        try:
            val_float = float(parts[4]) if parts[4] is not None and str(parts[4]).strip() else None
        except (ValueError, TypeError):
            val_float = None
        rows.append({
            "report_record_key": str(key).strip(),
            "worksheet": str(parts[1]).strip() if parts[1] is not None else None,
            "line": line_int,
            "column": clmn_int,
            "value": val_float,
        })
    return rows


def parse_alpha_positional(df: pd.DataFrame) -> list[dict]:
    """Alpha with no header: col 0=report_record_key, 1=worksheet, 2=line, 3=column, 4=value (CMHC17)."""
    rows = []
    for _, r in df.iterrows():
        parts = list(r)
        if len(parts) < 5:
            continue
        key = parts[0] if parts[0] is not None and str(parts[0]).strip() else None
        if key is None:
            continue
        try:
            line_int = int(float(parts[2])) if parts[2] is not None and str(parts[2]).strip() else None
        except (ValueError, TypeError):
            line_int = None
        try:
            clmn_int = int(float(parts[3])) if parts[3] is not None and str(parts[3]).strip() else None
        except (ValueError, TypeError):
            clmn_int = None
        rows.append({
            "report_record_key": str(key).strip(),
            "worksheet": str(parts[1]).strip() if parts[1] is not None else None,
            "line": line_int,
            "column": clmn_int,
            "value": str(parts[4]).strip() if parts[4] is not None else None,
        })
    return rows


def _has_header_row(zip_path: str | io.BytesIO, member_name: str) -> bool:
    """Heuristic: first cell of first row looks like a column name (letter) vs numeric."""
    with zipfile.ZipFile(zip_path, "r") as z:
        with z.open(member_name) as f:
            first = f.read(200).decode("utf-8", "replace").split("\n")[0]
    first_cell = first.split(",")[0].strip()
    return first_cell.isalpha() or "RPT" in first.upper() or "PRVDR" in first.upper()


def parse_hcris_zip(
    zip_path: str | io.BytesIO,
    form_vintage: str = "2088-17",
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Parse HCRIS zip; return (rpt_rows, nmrc_rows, alpha_rows).
    Supports: (1) one file per type with optional headers; (2) multiple per-year files (e.g. CMHC17_2018_rpt.csv) with no headers.
    """
    rpt_names = _find_all_in_zip(zip_path, "rpt", exclude=["nmrc", "alpha"])
    nmrc_names = _find_all_in_zip(zip_path, "nmrc")
    alpha_names = _find_all_in_zip(zip_path, "alpha")

    rpt_rows: list[dict] = []
    nmrc_rows: list[dict] = []
    alpha_rows: list[dict] = []

    for rpt_name in sorted(rpt_names):
        df = read_csv_from_zip(zip_path, rpt_name, header=False)
        if df.empty or len(df.columns) < 7:
            continue
        # CMHC17 per-year files have no header; first row is data
        rpt_rows.extend(parse_rpt_positional(df, form_vintage))

    for nmrc_name in sorted(nmrc_names):
        try:
            df = read_csv_from_zip(zip_path, nmrc_name, header=False)
        except pd.errors.EmptyDataError:
            continue
        if df.empty or len(df.columns) < 5:
            continue
        nmrc_rows.extend(parse_nmrc_positional(df))

    for alpha_name in sorted(alpha_names):
        try:
            df = read_csv_from_zip(zip_path, alpha_name, header=False)
        except pd.errors.EmptyDataError:
            continue
        if df.empty or len(df.columns) < 5:
            continue
        alpha_rows.extend(parse_alpha_positional(df))

    return rpt_rows, nmrc_rows, alpha_rows
