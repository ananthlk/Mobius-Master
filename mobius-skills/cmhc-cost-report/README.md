# CMHC Cost Report Skill

Pipeline and skill layer for **Community Mental Health Center (CMHC) HCRIS cost report** data: extract from CMS → GCS → normalize → BigQuery, plus query operations for answering questions (single CMHC report, compare to peers, list CMHCs, worksheet/cell lookup). Designed to be wrapped by an MCP server later.

## Data map: HCRIS files

When you download CMHC cost report data, it is split into:

| File | Role | Contents |
|------|------|----------|
| **RPT** (Report) | Index | One row per cost report filing: provider CCN, fiscal year begin/end, report status (as-submitted, settled, amended). Read this first to get the report record key. |
| **NMRC** (Numeric) | Numbers | One row per numeric cell: worksheet code, line, column, value, and key tying back to the RPT record. |
| **Alpha** (Alphanumeric) | Text | Same structure for text cells (names, addresses, flags). |

To “read a worksheet”: filter NMRC (or Alpha) by report record key and worksheet code, sort by line then column, pivot into a grid (line = rows, column = columns).

## Form vintages

- **2088-17**: Reporting periods beginning on or after Oct 1, 2017. Data: `CMHC17-ALL-YEARS.zip` from CMS.
- **2088-92**: Older years; worksheet layouts can differ.

We store `form_vintage` on each row and use it in queries.

## Setup

```bash
cd mobius-skills/cmhc-cost-report
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env: GCS_BUCKET, BQ_PROJECT, BQ_LANDING_DATASET (e.g. landing_cmhc_dev)
```

## Pipeline

1. **Extract**: `python -m app.extract` — Downloads CMHC HCRIS zip from CMS and uploads to `gs://<bucket>/cmhc-hcris/raw/<vintage>/`.
2. **Normalize + load**: `python -m app.normalize_load [path] [vintage]` — Parses zip (local or gs://), creates dataset/tables if missing, loads into BigQuery. Example: `python -m app.normalize_load /tmp/CMHC17-ALL-YEARS.zip 2088-17`. **Data scope:** The CMS zip (e.g. `CMHC17-ALL-YEARS.zip`) contains **all CMHCs** that file cost reports and **all years** in that zip (e.g. 2018–2025). The parser reads every per-year file (`*_rpt.csv`, `*_nmrc.csv`, `*_alpha.csv`) and loads them all—no filtering to “latest year only.” One load = all providers, all years in the zip.
3. **Optional**: dbt models in `mobius_cmhc_*` for “best report per CCN/fiscal year” and worksheet views.

## Run queries (CLI)

After loading data, run: `python -m app.cli list_cmhcs --state FL`, `get_report --ccn CCN --fy YYYY-MM-DD`, `full_report_by_name --name "Provider Name" [--state FL] [--fy YYYY-MM-DD]`, `get_worksheet --key KEY --worksheet WKSHT`, `get_cell --key KEY --worksheet W --line L --column C`, `compare_to_peers --ccn CCN --fy YYYY-MM-DD --state FL` (optionally with `--worksheet`, `--line`, `--column` for a metric).

## BigQuery

Create datasets and tables (run from repo root or this skill root):

```bash
export BQ_PROJECT=mobiusos-new   # or your project
cd mobius-skills/cmhc-cost-report
./scripts/create_bq_datasets.sh
./scripts/create_env_tables.sh
```

**Landing tables** (written by `normalize_load`; read by skills or mart):

| Table | Description | Key columns |
|-------|-------------|-------------|
| `landing_cmhc_{env}.hcris_rpt` | One row per cost report filing. | `report_record_key`, `provider_ccn`, `fiscal_year_start`, `fiscal_year_end`, `report_status`, `form_vintage` |
| `landing_cmhc_{env}.hcris_nmrc` | Numeric cells. | `report_record_key`, `worksheet`, `line`, `column`, `value` (FLOAT64) |
| `landing_cmhc_{env}.hcris_alpha` | Alphanumeric cells. | `report_record_key`, `worksheet`, `line`, `column`, `value` (STRING) |

**Mart** (optional): `mobius_cmhc_{env}.best_report_per_ccn_fy` — view built by dbt; one row per (provider_ccn, fiscal_year_end) with best `report_record_key`. To build:

```bash
cd mobius-skills/cmhc-cost-report/dbt
BQ_PROJECT=... BQ_LANDING_DATASET=landing_cmhc_dev BQ_MART_DATASET=mobius_cmhc_dev dbt run
```

Skills use `BQ_LANDING_DATASET` by default; set `BQ_MART_DATASET` and pass `dataset=BQ_MART_DATASET` to skill calls if you want to read from the mart (e.g. for a “best report” view). Credentials: GCP project with BigQuery (and GCS for pipeline); use Application Default Credentials or `GOOGLE_APPLICATION_CREDENTIALS`.

## Skills surface (for MCP)

These operations are implemented in `app.skills` and can be exposed as MCP tools.

| Skill | Description | Inputs | Output |
|-------|-------------|--------|--------|
| **get_report** | Cost report for one CMHC for a fiscal year. | CCN (or name + city), fiscal year end. | Report record key + metadata; optional key worksheets/cells. |
| **compare_to_peers** | Compare one CMHC to others in the same state (e.g. Florida). | CCN (or name + city), fiscal year end, state, metric(s). | Aggregates/rankings; position of the requested CMHC. |
| **list_cmhcs** | List CMHCs with cost reports in a state and/or fiscal year. | State (optional), fiscal year end range (optional). | List of CCN, name, fiscal year, report status. |
| **get_full_report_by_name** | Load full cost report by provider name (searches Alpha). | Name substring, state (optional), fiscal year end (optional). | Full report: metadata + all worksheets with column_names and grid. |
| **get_worksheet** | One worksheet as a grid (line × column). | Report record key, worksheet code. | 2D grid from NMRC (and optionally Alpha). |
| **get_cell** | One cell value (numeric or alpha). | Report record key, worksheet, line, column. | Single value. |

Florida CCN range (e.g. 4600–4999) is applied as a filter when state is FL in **compare_to_peers** and **list_cmhcs**.

**Python usage (for MCP server author):**

```python
from app.skills import get_report, list_cmhcs, get_worksheet, get_cell, compare_to_peers, get_full_report_by_name

# Get report for CCN and fiscal year end
out = get_report(provider_ccn="4601", fiscal_year_end="2023-12-31")
# out["report_record_key"], out["metadata"]

# Load full report by provider name (optional state and FY)
full = get_full_report_by_name("Winchester", state="FL", fiscal_year_end="2024-12-31")
# full["metadata"], full["worksheets"] (each with column_names, grid)

# List CMHCs in Florida for a fiscal year
rows = list_cmhcs(state="FL", fiscal_year_end_start="2023-01-01", fiscal_year_end_end="2023-12-31")

# Get one worksheet as grid
grid = get_worksheet(report_record_key="...", worksheet_code="A")

# Get one cell
cell = get_cell(report_record_key="...", worksheet="A", line=10, column=2)

# Compare CMHC to FL peers on a metric (worksheet/line/column)
cmp = compare_to_peers(provider_ccn="4601", fiscal_year_end="2023-12-31", state="FL", worksheet="A", line=10, column=2)
# cmp["rank"], cmp["peer_count"], cmp["value"]
```
