# One environment for all of Mobius

Single setup: one Python venv, one env file, and one place to run everything (services, dbt, Medicaid NPI B0–B6, report scripts).

---

## What “one environment” means

| Piece | Where | Purpose |
|-------|--------|--------|
| **Python** | `Mobius/.venv` | Shared by mobius-chat, mobius-rag, mobius-dbt, mobius-skills, etc. |
| **Dependencies** | `Mobius/requirements.txt` | One `pip install -r requirements.txt` (includes dbt-bigquery, google-cloud-bigquery). |
| **Env vars** | **`mobius-config/.env`** | Single source: BQ, Postgres, Redis, Vertex, **and** FL Medicaid NPI (`BQ_MARTS_MEDICAID_DATASET`, `BQ_LANDING_MEDICAID_DATASET`). |
| **Services** | `./mstart` / `./mstop` | All backends, workers, and frontends; mstart loads `mobius-config/.env` where needed. |
| **dbt** | `mobius-dbt` | Run with same env: `source mobius-config/.env` then `cd mobius-dbt && dbt run`. Medicaid B0–B6 use `BQ_MARTS_MEDICAID_DATASET` / `BQ_LANDING_MEDICAID_DATASET`. |
| **B6 report** | `mobius-dbt/scripts/generate_b6_report.py` | Same env; query by org_id, npi, site_id, or name (e.g. `--name "Aspire Behavioral Health"`). |

---

## First-time setup

From **Mobius repo root**:

```bash
# 1. One-environment setup
./scripts/setup_one_env.sh
```

This will:

- Create `.venv` and install `requirements.txt` + editable `Mobius-user`
- Copy `mobius-config/.env.example` → `mobius-config/.env` if missing (includes Medicaid NPI vars)
- Create `mobius-dbt/.env` from `mobius-config/.env` if missing (so dbt and report scripts see BQ_*)
- Create BigQuery datasets (landing_rag, mobius_rag, landing_medicaid_npi_dev, mobius_medicaid_npi_dev) if `bq` is available
- Optionally run `dbt seed` and `dbt run --select +b6_integrated_report_fl` (prompted)

Then:

```bash
# 2. GCP auth (if not already)
gcloud auth application-default login

# 3. Start all services
./mstart
```

---

## Env vars (single source)

Use **`mobius-config/.env`** as the canonical env. It includes:

- Postgres, Redis, GCS, Vertex (for chat, RAG, OS, skills)
- **BigQuery:** `BQ_PROJECT`, `BQ_DATASET`, `BQ_LANDING_DATASET`
- **FL Medicaid NPI (B0–B6):** `BQ_MARTS_MEDICAID_DATASET`, `BQ_LANDING_MEDICAID_DATASET`

When you run dbt or Medicaid scripts from the command line, either:

- `source mobius-config/.env` then run the command, or  
- Ensure `mobius-dbt/.env` exists (setup script copies from mobius-config) and run from `mobius-dbt` so scripts that load `.env` see the vars.

---

## Running dbt and Medicaid NPI

```bash
source mobius-config/.env   # or: cd mobius-dbt && [.env is already there]
cd mobius-dbt
dbt seed
dbt run --select +b6_integrated_report_fl   # B0–B6
```

Generate B6 report (e.g. for Aspire Behavioral Health):

```bash
source mobius-config/.env
python mobius-dbt/scripts/generate_b6_report.py --name "Aspire Behavioral Health"
# Or: --org_id <id> | --npi <id> | --site_id <id>
```

---

## Summary

- **One env:** `mobius-config/.env` (and optional per-service copies created by setup).
- **One venv:** `Mobius/.venv` with everything from `requirements.txt`.
- **One start:** `./mstart` for all services; dbt and B6 report run manually with the same env.

See [DEVELOPER_SETUP.md](DEVELOPER_SETUP.md) for full details and troubleshooting.
