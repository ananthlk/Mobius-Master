# Medicaid NPI — Unified landing (state + product)

PML, TML, and Pending PPL files from any state feed **one set of landing tables** with **state** and **product** as columns. New states: load data into these same tables with new `state`/`product` values; the dbt pipeline is unchanged and filters by run vars.

---

## Design

| Concept | Meaning |
|--------|--------|
| **state** | Program state (e.g. `FL`, `TX`). Every row has this. |
| **product** | Product/program (e.g. `medicaid`). Enables multiple products per state later if needed. |
| **Landing tables** | `stg_pml`, `stg_tml`, `stg_ppl` — same structure for all states; load scripts set `state` and `product` per load. |
| **Run filter** | dbt vars `state_code` and `product` (defaults `FL`, `medicaid`). Staging models `stg_pml_run`, `stg_tml_run`, `stg_ppl_run` filter to one state/product so the rest of the pipeline is unchanged. |

---

## Table: stg_pml (Provider Master List)

All columns from state PML files; add **program_state** and **product** on load. Use **state** for address state (existing B1 logic).

| Column | Type | Description |
|--------|------|-------------|
| **program_state** | STRING | Program state (e.g. FL, TX). Set on load. Filter column. |
| **product** | STRING | Product (e.g. medicaid). Set on load. Filter column. |
| npi | STRING | NPI. Required. |
| medicaid_provider_id | STRING | State Medicaid provider ID. |
| provider_name | STRING | Provider name on file. |
| provider_type | STRING | Provider type. |
| specialty_type | STRING | Specialty. |
| address_line_1 | STRING | Service location address line 1. |
| city | STRING | City. |
| state | STRING | Address state (e.g. FL). Used by B1/address logic. |
| zip | STRING | ZIP (digits). |
| zip_plus_4 | STRING | ZIP+4 (digits). |
| contract_effective_date | DATE or STRING | Contract start. |
| contract_end_date | DATE or STRING | Contract end. NULL = no end. |
| status | STRING | Enrollment status. |
| taxonomy_code | STRING | Taxonomy on file (C2 comparison). |

Load pattern: one state’s PML file → insert into `stg_pml` with `state = 'FL'`, `product = 'medicaid'` (or append for incremental). For TX, load with `state = 'TX'`, same columns.

---

## Table: stg_tml (Taxonomy Master List)

Valid taxonomy codes per state/product.

| Column | Type | Description |
|--------|------|-------------|
| **program_state** | STRING | Program state (e.g. FL, TX). Set on load. |
| **product** | STRING | Product (e.g. medicaid). Set on load. |
| taxonomy_code | STRING | Valid taxonomy code. |
| (optional) taxonomy_description | STRING | Human-readable description. |

Load pattern: one state’s TML file → insert into `stg_tml` with `state`, `product`. New state = new rows, same table.

---

## Table: stg_ppl (Pending Provider List)

Providers in enrollment pipeline.

| Column | Type | Description |
|--------|------|-------------|
| **program_state** | STRING | Program state (e.g. FL, TX). Set on load. |
| **product** | STRING | Product (e.g. medicaid). Set on load. |
| npi | STRING | NPI. Presence = pending. |
| (optional) submitted_date | DATE or STRING | When submitted. |
| (optional) status | STRING | Pending status. |

Load pattern: same as PML/TML — set `program_state` and `product` on load.

---

## Run-time filter (dbt)

Staging models used by the pipeline:

- **stg_pml_run** — `select * from landing_medicaid_npi.stg_pml where coalesce(program_state, 'FL') = var('state_code', 'FL') and coalesce(product, 'medicaid') = var('product', 'medicaid')`
- **stg_tml_run** — same filter for `stg_tml` (columns `program_state`, `product`).
- **stg_ppl_run** — same filter for `stg_ppl`.

All mart models reference `stg_pml_run`, `stg_tml_run`, `stg_ppl_run` (not the raw landing tables). Switching state: `dbt run --vars '{"state_code": "TX"}'`; ensure landing has TX rows with `program_state = 'TX'`.

---

## Backward compatibility (existing FL data)

If current tables have no `state`/`product` columns:

1. **Migration:** Add columns `program_state`, `product` to `stg_pml`, `stg_tml`, `stg_ppl`; backfill `program_state = 'FL'`, `product = 'medicaid'` for existing rows. Keep existing `state` column as address state if present.
2. **PML:** Use `program_state` for the program (FL/TX) and keep `state` as the address state column so existing B1/address logic continues to work.

---

## Create tables

To create `stg_pml`, `stg_tml`, `stg_ppl`, and `stg_doge` in each env (dev/staging/prod):

```bash
cd mobius-dbt
BQ_PROJECT=mobius-os-dev ./scripts/create_medicaid_tables.sh
```

Existing envs that did not have `stg_ppl` should run this once to add it. Then load data via the scripts below.

## Load all data (NPPES seed or CSV)

To **fill** the tables with real data (after tables exist):

```bash
cd mobius-dbt
uv run python scripts/load_medicaid_landing.py
```

This seeds **stg_tml** from the NPPES taxonomy code set and **stg_pml** from NPPES FL providers (adds `program_state=FL`, `product=medicaid`). **stg_ppl** is left as-is unless you pass a file.

To load from your own CSV files instead:

```bash
uv run python scripts/load_medicaid_landing.py --pml /path/to/pml.csv --tml /path/to/tml.csv --ppl /path/to/ppl.csv
```

- **PML CSV:** must have `npi` (or `NPI`); other columns mapped by name (e.g. `provider_name`, `address_line_1`, `state`, `zip`, `taxonomy_code`, `contract_effective_date`, `contract_end_date`).
- **TML CSV:** must have `taxonomy_code` and `taxonomy_description` (or `code` and `definition`).
- **PPL CSV:** must have `npi`; optional `submitted_date`, `status`. For FL prd19100 (Pending Provider List) format, use `scripts/cleanse_and_load_ppl_prd19100.py --source /path/to/prd19100.csv --load` to cleanse (Excel unquote, column map), backup current `stg_ppl`, and load.

Set `BQ_PROJECT`, `BQ_LANDING_MEDICAID_DATASET`, and optionally `PROGRAM_STATE` / `PRODUCT` (defaults FL, medicaid).

## Daily job (FL PML + PPL)

To download (or use pre-downloaded files), cleanse, backup, and load PML and PPL, then run dbt:

```bash
cd mobius-dbt
# Optional: download from portal (or place prw19000.csv / prd19100.csv in data/ and use --skip-download)
./scripts/run_fl_medicaid_daily_load.sh
# Or with pre-downloaded files only:
./scripts/run_fl_medicaid_daily_load.sh --skip-download
```

Requires `BQ_PROJECT`, `BQ_LANDING_MEDICAID_DATASET`, `BQ_MARTS_MEDICAID_DATASET`. Optional `FL_MEDICAID_DATA_DIR` (default `mobius-dbt/data`). Download uses `scripts/download_ahca_medicaid.py`; PML load uses `cleanse_and_load_pml_prw19000.py`; PPL load uses `cleanse_and_load_ppl_prd19100.py`.

## GCS / load scripts

- Keep or add paths like `raw/{state}/pml/`, `raw/{state}/tml/`, `raw/{state}/ppl/` (or flat with state in the filename).
- Load job: read file, set `state` and `product`, insert into BigQuery `stg_pml` / `stg_tml` / `stg_ppl`.
- New state: same job, different `state` (and same or different `product`); no pipeline code change.
