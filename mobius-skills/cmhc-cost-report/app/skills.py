"""
CMHC Cost Report skills: query operations for MCP to wrap.
All functions take a bq client and dataset (landing or mart) and return structured data.
Use BQ_LANDING_DATASET or BQ_MART_DATASET; mart views (best report per CCN/FY) optional.
"""
from __future__ import annotations

from typing import Any

from google.cloud import bigquery

# State to CCN range (first 4 digits). Florida CMHCs: 4600-4999. Extend as needed.
STATE_CCN_RANGES: dict[str, tuple[int, int]] = {
    "FL": (4600, 4999),
    "FLORIDA": (4600, 4999),
}


def _get_client_and_dataset(project: str | None, dataset: str | None) -> tuple[Any, str]:
    from google.cloud import bigquery
    from app.config import BQ_PROJECT, BQ_LANDING_DATASET
    client = bigquery.Client(project=project or BQ_PROJECT)
    ds = dataset or BQ_LANDING_DATASET
    return client, ds


def find_reports_by_name(
    name_substring: str,
    state: str | None = None,
    *,
    project: str | None = None,
    dataset: str | None = None,
) -> list[dict[str, Any]]:
    """Find cost reports by provider name (search Alpha value). Optionally filter by state (CCN range)."""
    client, ds = _get_client_and_dataset(project, dataset)
    table_rpt = f"`{client.project}.{ds}.hcris_rpt`"
    table_alpha = f"`{client.project}.{ds}.hcris_alpha`"

    where_alpha = "UPPER(a.value) LIKE @pat"
    params: list[Any] = [bigquery.ScalarQueryParameter("pat", "STRING", f"%{name_substring.upper()}%")]
    join_rpt = f"INNER JOIN {table_rpt} r ON r.report_record_key = a.report_record_key"
    where_rpt = "1=1"
    if state:
        ccn_lo, ccn_hi = STATE_CCN_RANGES.get(state.upper(), (0, 99999))
        where_rpt = "SAFE_CAST(SUBSTR(r.provider_ccn, 1, 4) AS INT64) BETWEEN @ccn_lo AND @ccn_hi"
        params.extend([
            bigquery.ScalarQueryParameter("ccn_lo", "INT64", ccn_lo),
            bigquery.ScalarQueryParameter("ccn_hi", "INT64", ccn_hi),
        ])

    sql = f"""
    SELECT DISTINCT r.report_record_key, r.provider_ccn, r.fiscal_year_start, r.fiscal_year_end, r.report_status, r.form_vintage
    FROM {table_alpha} a
    {join_rpt}
    WHERE {where_alpha} AND {where_rpt}
    ORDER BY r.fiscal_year_end DESC
    """
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    rows = list(client.query(sql, job_config=job_config).result())
    return [
        {
            "report_record_key": r.report_record_key,
            "provider_ccn": r.provider_ccn,
            "fiscal_year_start": str(r.fiscal_year_start) if r.fiscal_year_start else None,
            "fiscal_year_end": str(r.fiscal_year_end) if r.fiscal_year_end else None,
            "report_status": r.report_status,
            "form_vintage": r.form_vintage,
        }
        for r in rows
    ]


def get_full_report(
    report_record_key: str,
    form_vintage: str = "2088-17",
    *,
    project: str | None = None,
    dataset: str | None = None,
) -> dict[str, Any]:
    """Get full report: RPT metadata plus all worksheets as grids (with column_names)."""
    client, ds = _get_client_and_dataset(project, dataset)
    table_rpt = f"`{client.project}.{ds}.hcris_rpt`"
    table_nmrc = f"`{client.project}.{ds}.hcris_nmrc`"
    table_alpha = f"`{client.project}.{ds}.hcris_alpha`"

    rpt_sql = f"SELECT report_record_key, provider_ccn, fiscal_year_start, fiscal_year_end, report_status, form_vintage FROM {table_rpt} WHERE report_record_key = @key"
    rpt_rows = list(client.query(rpt_sql, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("key", "STRING", report_record_key)]
    )).result())
    if not rpt_rows:
        return {"report_record_key": report_record_key, "metadata": None, "worksheets": [], "message": "Report not found."}
    r = rpt_rows[0]
    metadata = {
        "provider_ccn": r.provider_ccn,
        "fiscal_year_start": str(r.fiscal_year_start) if r.fiscal_year_start else None,
        "fiscal_year_end": str(r.fiscal_year_end) if r.fiscal_year_end else None,
        "report_status": r.report_status,
        "form_vintage": r.form_vintage,
    }

    wksht_sql = f"SELECT DISTINCT worksheet FROM (SELECT worksheet FROM {table_nmrc} WHERE report_record_key = @key UNION ALL SELECT worksheet FROM {table_alpha} WHERE report_record_key = @key)"
    wksht_rows = list(client.query(wksht_sql, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("key", "STRING", report_record_key)]
    )).result())
    worksheet_codes = [row.worksheet for row in wksht_rows if row.worksheet]

    worksheets = []
    for wksht in sorted(worksheet_codes):
        out = get_worksheet(report_record_key, wksht, include_alpha=True, form_vintage=form_vintage, project=project, dataset=dataset)
        worksheets.append({"worksheet": wksht, "column_names": out.get("column_names"), "column_labels": out.get("column_labels"), "line_labels": out.get("line_labels"), "grid": out.get("grid", []), "rows": out.get("rows", 0), "cols": out.get("cols", 0)})

    return {"report_record_key": report_record_key, "metadata": metadata, "worksheets": worksheets}


def get_full_report_by_name(
    name_substring: str,
    state: str | None = None,
    fiscal_year_end: str | None = None,
    *,
    project: str | None = None,
    dataset: str | None = None,
) -> dict[str, Any]:
    """
    Load full cost report by provider name. Searches Alpha for name, optionally filters by state (CCN range)
    and fiscal year end. Returns full report (metadata + all worksheets) for the best match.
    If fiscal_year_end is set, uses that FY when multiple reports exist; otherwise uses most recent.
    """
    matches = find_reports_by_name(name_substring, state=state, project=project, dataset=dataset)
    if not matches:
        return {
            "report_record_key": None,
            "metadata": None,
            "worksheets": [],
            "message": f"No cost report found for name containing '{name_substring}'" + (f" in state {state}" if state else "") + ".",
        }
    if fiscal_year_end:
        fy_str = str(fiscal_year_end).strip()
        for m in matches:
            if m.get("fiscal_year_end") and str(m["fiscal_year_end"]) == fy_str:
                return get_full_report(m["report_record_key"], form_vintage=m.get("form_vintage") or "2088-17", project=project, dataset=dataset)
        # No exact FY match; use first (already ordered by fiscal_year_end DESC)
    best = matches[0]
    return get_full_report(best["report_record_key"], form_vintage=best.get("form_vintage") or "2088-17", project=project, dataset=dataset)


def get_report(
    provider_ccn: str | None = None,
    name_or_city: str | None = None,
    fiscal_year_end: str | None = None,
    *,
    project: str | None = None,
    dataset: str | None = None,
) -> dict[str, Any]:
    """
    Get the cost report for one CMHC for a given fiscal year.
    Returns report record key + metadata; optional key worksheets/cells can be added by caller using get_worksheet/get_cell.
    """
    client, ds = _get_client_and_dataset(project, dataset)
    table_rpt = f"`{client.project}.{ds}.hcris_rpt`"

    # Prefer best status: settled > amended > as-submitted (order by status preference)
    status_order = "CASE report_status WHEN '3' THEN 1 WHEN '4' THEN 2 WHEN '1' THEN 3 ELSE 4 END"
    where_parts = ["1=1"]
    params: list[Any] = []

    if provider_ccn:
        where_parts.append("provider_ccn = @ccn")
        params.append(bigquery.ScalarQueryParameter("ccn", "STRING", provider_ccn))
    if fiscal_year_end:
        where_parts.append("CAST(fiscal_year_end AS STRING) = @fy_end")
        params.append(bigquery.ScalarQueryParameter("fy_end", "STRING", str(fiscal_year_end).strip()))

    # Name/city: would require joining Alpha and filtering by value; if provided we try Alpha for provider name
    if name_or_city and not provider_ccn:
        # Resolve CCN from Alpha (e.g. provider name) - simplified: we need report_record_key from RPT then Alpha value match
        # For now, require CCN for precise lookup; name_or_city can be used in list_cmhcs and then user picks CCN
        pass

    sql = f"""
    SELECT report_record_key, provider_ccn, fiscal_year_start, fiscal_year_end, report_status, form_vintage
    FROM {table_rpt}
    WHERE {" AND ".join(where_parts)}
    ORDER BY {status_order}
    LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(query_parameters=params) if params else None
    rows = list(client.query(sql, job_config=job_config).result())
    if not rows:
        return {"report_record_key": None, "metadata": {}, "message": "No report found for given CCN/fiscal year."}
    r = rows[0]
    return {
        "report_record_key": r.report_record_key,
        "metadata": {
            "provider_ccn": r.provider_ccn,
            "fiscal_year_start": str(r.fiscal_year_start) if r.fiscal_year_start else None,
            "fiscal_year_end": str(r.fiscal_year_end) if r.fiscal_year_end else None,
            "report_status": r.report_status,
            "form_vintage": r.form_vintage,
        },
    }


def compare_to_peers(
    provider_ccn: str,
    fiscal_year_end: str,
    state: str,
    worksheet: str | None = None,
    line: int | None = None,
    column: int | None = None,
    *,
    project: str | None = None,
    dataset: str | None = None,
) -> dict[str, Any]:
    """
    Compare one CMHC to others in the same state. Metric = one cell (worksheet/line/column) or all peers in state.
    Returns aggregates/rankings and position of the requested CMHC.
    """
    client, ds = _get_client_and_dataset(project, dataset)
    table_rpt = f"`{client.project}.{ds}.hcris_rpt`"
    table_nmrc = f"`{client.project}.{ds}.hcris_nmrc`"

    ccn_lo, ccn_hi = STATE_CCN_RANGES.get(state.upper(), (0, 99999))
    if state.upper() not in ("FL", "FLORIDA") and state.upper() not in STATE_CCN_RANGES:
        # Unknown state: use CCN range 0-99999 (all) or require known state
        ccn_lo, ccn_hi = 0, 99999

    # Get report record key for the requested CCN/fy
    rpt_sql = f"""
    SELECT report_record_key FROM {table_rpt}
    WHERE provider_ccn = @ccn AND CAST(fiscal_year_end AS STRING) = @fy_end
    ORDER BY CASE report_status WHEN '3' THEN 1 WHEN '4' THEN 2 ELSE 3 END
    LIMIT 1
    """
    rpt_job = client.query(
        rpt_sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ccn", "STRING", provider_ccn),
                bigquery.ScalarQueryParameter("fy_end", "STRING", str(fiscal_year_end)),
            ]
        ),
    )
    rpt_rows = list(rpt_job.result())
    if not rpt_rows:
        return {"requested_ccn": provider_ccn, "message": "No report found for this CCN/fiscal year.", "rank": None, "peer_count": 0}

    target_key = rpt_rows[0].report_record_key

    # All reports in state (CCN range) for this fiscal year
    peer_rpt_sql = f"""
    SELECT report_record_key, provider_ccn FROM {table_rpt}
    WHERE SAFE_CAST(SUBSTR(provider_ccn, 1, 4) AS INT64) BETWEEN @lo AND @hi
      AND CAST(fiscal_year_end AS STRING) = @fy_end
    """
    peer_job = client.query(
        peer_rpt_sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("lo", "INT64", ccn_lo),
                bigquery.ScalarQueryParameter("hi", "INT64", ccn_hi),
                bigquery.ScalarQueryParameter("fy_end", "STRING", str(fiscal_year_end)),
            ]
        ),
    )
    peer_rows = list(peer_job.result())
    peer_count = len(peer_rows)
    peer_keys = [r.report_record_key for r in peer_rows]

    if not worksheet or line is None or column is None:
        return {
            "requested_ccn": provider_ccn,
            "report_record_key": target_key,
            "state": state,
            "fiscal_year_end": fiscal_year_end,
            "peer_count": peer_count,
            "message": "Specify worksheet, line, column for metric comparison.",
        }

    # Get numeric value for each report (same worksheet/line/column)
    nmrc_sql = f"""
    SELECT report_record_key, value FROM {table_nmrc}
    WHERE report_record_key IN UNNEST(@keys) AND worksheet = @wksht AND line = @line AND `column` = @col
    """
    nmrc_job = client.query(
        nmrc_sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("keys", "STRING", peer_keys),
                bigquery.ScalarQueryParameter("wksht", "STRING", worksheet),
                bigquery.ScalarQueryParameter("line", "INT64", line),
                bigquery.ScalarQueryParameter("col", "INT64", column),
            ]
        ),
    )
    values_by_key = {r.report_record_key: r.value for r in nmrc_job.result()}
    target_value = values_by_key.get(target_key)

    # Rank by value descending (higher = better for costs); ties get same rank
    sorted_keys = sorted(values_by_key.keys(), key=lambda k: (values_by_key.get(k) or 0), reverse=True)
    rank = next((i + 1 for i, k in enumerate(sorted_keys) if k == target_key), None)

    return {
        "requested_ccn": provider_ccn,
        "report_record_key": target_key,
        "state": state,
        "fiscal_year_end": fiscal_year_end,
        "metric": {"worksheet": worksheet, "line": line, "column": column},
        "value": target_value,
        "rank": rank,
        "peer_count": peer_count,
    }


def list_cmhcs(
    state: str | None = None,
    fiscal_year_end_start: str | None = None,
    fiscal_year_end_end: str | None = None,
    *,
    project: str | None = None,
    dataset: str | None = None,
) -> list[dict[str, Any]]:
    """List CMHCs with cost reports in a state and/or fiscal year range. Returns CCN, name (if from Alpha), fiscal year, report status."""
    client, ds = _get_client_and_dataset(project, dataset)
    table_rpt = f"`{client.project}.{ds}.hcris_rpt`"

    where_parts = ["1=1"]
    params: list[Any] = []

    if state:
        ccn_lo, ccn_hi = STATE_CCN_RANGES.get(state.upper(), (0, 99999))
        where_parts.append("SAFE_CAST(SUBSTR(provider_ccn, 1, 4) AS INT64) BETWEEN @ccn_lo AND @ccn_hi")
        params.extend([
            bigquery.ScalarQueryParameter("ccn_lo", "INT64", ccn_lo),
            bigquery.ScalarQueryParameter("ccn_hi", "INT64", ccn_hi),
        ])
    if fiscal_year_end_start:
        where_parts.append("fiscal_year_end >= @fy_start")
        params.append(bigquery.ScalarQueryParameter("fy_start", "DATE", fiscal_year_end_start))
    if fiscal_year_end_end:
        where_parts.append("fiscal_year_end <= @fy_end")
        params.append(bigquery.ScalarQueryParameter("fy_end", "DATE", fiscal_year_end_end))

    sql = f"""
    SELECT report_record_key, provider_ccn, fiscal_year_start, fiscal_year_end, report_status, form_vintage
    FROM {table_rpt}
    WHERE {" AND ".join(where_parts)}
    ORDER BY provider_ccn, fiscal_year_end
    """
    job_config = bigquery.QueryJobConfig(query_parameters=params) if params else None
    rows = list(client.query(sql, job_config=job_config).result())
    out = []
    for r in rows:
        out.append({
            "report_record_key": r.report_record_key,
            "provider_ccn": r.provider_ccn,
            "fiscal_year_start": str(r.fiscal_year_start) if r.fiscal_year_start else None,
            "fiscal_year_end": str(r.fiscal_year_end) if r.fiscal_year_end else None,
            "report_status": r.report_status,
            "form_vintage": r.form_vintage,
            "name": None,  # Could join Alpha for provider name in a follow-up
        })
    return out


def get_worksheet(
    report_record_key: str,
    worksheet_code: str,
    include_alpha: bool = True,
    form_vintage: str | None = None,
    *,
    project: str | None = None,
    dataset: str | None = None,
) -> dict[str, Any]:
    """Return one worksheet as a grid (line x column). Numeric from NMRC; optionally merge Alpha. Returns column_names for headers."""
    client, ds = _get_client_and_dataset(project, dataset)
    table_nmrc = f"`{client.project}.{ds}.hcris_nmrc`"
    table_alpha = f"`{client.project}.{ds}.hcris_alpha`"

    nmrc_sql = f"""
    SELECT line, `column`, value FROM {table_nmrc}
    WHERE report_record_key = @key AND worksheet = @wksht
    ORDER BY line, `column`
    """
    nmrc_job = client.query(
        nmrc_sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("key", "STRING", report_record_key),
                bigquery.ScalarQueryParameter("wksht", "STRING", worksheet_code),
            ]
        ),
    )
    nmrc_rows = list(nmrc_job.result())

    grid: dict[tuple[int, int], Any] = {}
    for r in nmrc_rows:
        grid[(r.line or 0, r.column or 0)] = r.value

    if include_alpha:
        alpha_sql = f"""
        SELECT line, `column`, value FROM {table_alpha}
        WHERE report_record_key = @key AND worksheet = @wksht
        ORDER BY line, `column`
        """
        alpha_job = client.query(
            alpha_sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("key", "STRING", report_record_key),
                    bigquery.ScalarQueryParameter("wksht", "STRING", worksheet_code),
                ]
            ),
        )
        for r in alpha_job.result():
            k = (r.line or 0, r.column or 0)
            if k not in grid:
                grid[k] = r.value

    if not grid:
        return {"report_record_key": report_record_key, "worksheet": worksheet_code, "grid": [], "rows": 0, "cols": 0}

    lines = sorted({k[0] for k in grid})
    cols = sorted({k[1] for k in grid})
    rows_list = []
    for line in lines:
        row_list = [grid.get((line, c)) for c in cols]
        rows_list.append(row_list)

    from app.column_names import get_column_names
    column_names = get_column_names(worksheet_code, cols, form_vintage or "2088-17")

    return {
        "report_record_key": report_record_key,
        "worksheet": worksheet_code,
        "grid": rows_list,
        "line_labels": lines,
        "column_labels": cols,
        "column_names": column_names,
        "rows": len(lines),
        "cols": len(cols),
    }


def get_cell(
    report_record_key: str,
    worksheet: str,
    line: int,
    column: int,
    *,
    project: str | None = None,
    dataset: str | None = None,
) -> dict[str, Any]:
    """Return one cell value (numeric or alpha). Tries NMRC first, then Alpha."""
    client, ds = _get_client_and_dataset(project, dataset)
    table_nmrc = f"`{client.project}.{ds}.hcris_nmrc`"
    table_alpha = f"`{client.project}.{ds}.hcris_alpha`"

    nmrc_sql = f"""
    SELECT value FROM {table_nmrc}
    WHERE report_record_key = @key AND worksheet = @wksht AND line = @line AND `column` = @col
    LIMIT 1
    """
    nmrc_job = client.query(
        nmrc_sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("key", "STRING", report_record_key),
                bigquery.ScalarQueryParameter("wksht", "STRING", worksheet),
                bigquery.ScalarQueryParameter("line", "INT64", line),
                bigquery.ScalarQueryParameter("col", "INT64", column),
            ]
        ),
    )
    nmrc_rows = list(nmrc_job.result())
    if nmrc_rows:
        return {"report_record_key": report_record_key, "worksheet": worksheet, "line": line, "column": column, "value": nmrc_rows[0].value, "type": "numeric"}

    alpha_sql = f"""
    SELECT value FROM {table_alpha}
    WHERE report_record_key = @key AND worksheet = @wksht AND line = @line AND `column` = @col
    LIMIT 1
    """
    alpha_job = client.query(
        alpha_sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("key", "STRING", report_record_key),
                bigquery.ScalarQueryParameter("wksht", "STRING", worksheet),
                bigquery.ScalarQueryParameter("line", "INT64", line),
                bigquery.ScalarQueryParameter("col", "INT64", column),
            ]
        ),
    )
    alpha_rows = list(alpha_job.result())
    if alpha_rows:
        return {"report_record_key": report_record_key, "worksheet": worksheet, "line": line, "column": column, "value": alpha_rows[0].value, "type": "alpha"}

    return {"report_record_key": report_record_key, "worksheet": worksheet, "line": line, "column": column, "value": None, "type": None}
