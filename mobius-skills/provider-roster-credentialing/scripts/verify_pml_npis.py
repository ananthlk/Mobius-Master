#!/usr/bin/env python3
"""Verify whether given NPIs exist in PML. Usage: uv run python scripts/verify_pml_npis.py 1023795135 1043564222"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPT_DIR.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

for env_path in (_SKILL_ROOT.parent / "mobius-config" / ".env", _SKILL_ROOT.parent / ".env"):
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path, override=False)
        except Exception:
            pass
        break

npis = [str(a).strip().zfill(10) for a in sys.argv[1:] if a]
if not npis:
    print("Usage: uv run python scripts/verify_pml_npis.py <npi1> [npi2] ...")
    sys.exit(1)

try:
    from google.cloud import bigquery
    bq = bigquery.Client(project=os.environ.get("BQ_PROJECT", "mobius-os-dev"))
except Exception as e:
    print(f"BigQuery not available: {e}")
    sys.exit(1)

project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
landing = os.environ.get("BQ_LANDING_MEDICAID_DATASET") or "landing_medicaid_npi_dev"
in_list = ", ".join(f"'{n}'" for n in npis)
table = f"`{project}.{landing}.stg_pml`"
query = f"""
SELECT
  TRIM(CAST(npi AS STRING)) AS npi,
  TRIM(COALESCE(provider_name, '')) AS provider_name,
  TRIM(CAST(taxonomy_code AS STRING)) AS taxonomy_code,
  TRIM(COALESCE(address_line_1, '')) AS address_line_1,
  TRIM(COALESCE(city, '')) AS city,
  TRIM(COALESCE(state, '')) AS state,
  status
FROM {table}
WHERE TRIM(CAST(npi AS STRING)) IN ({in_list})
"""
rows = list(bq.query(query).result())

print(f"PML lookup: {table}")
print(f"NPIs queried: {npis}")
print(f"Rows found: {len(rows)}")
print()
for r in rows:
    print(f"  NPI {r.npi}: {r.provider_name or '(no name)'}")
    print(f"    taxonomy={r.taxonomy_code}  address={r.address_line_1 or ''} {r.city or ''} {r.state or ''}  status={r.status}")
    print()

for n in npis:
    if not any(str(r.npi) == n for r in rows):
        print(f"  NPI {n}: NOT FOUND in PML")
        print()
