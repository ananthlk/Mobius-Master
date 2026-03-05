"""FastAPI app: Provider Roster / Credentialing report. POST /report returns full report JSON."""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.core import build_full_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Provider Roster / Credentialing API",
    version="0.1.0",
    description="Provider Roster / Credentialing report per organization (locations, NPIs, readiness, invalid combos, ghost billing).",
)


class ReportRequest(BaseModel):
    """Request body for report generation."""

    org_name: str
    location_ids: list[str] | None = None
    npi_overrides: dict[str, dict[str, Any]] | None = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "provider-roster-credentialing"}


@app.post("/report")
async def report(req: ReportRequest) -> dict[str, Any]:
    """
    Generate Provider Roster / Credentialing report for the given org name.
    Optional: location_ids to restrict locations, npi_overrides per location_id (add/remove NPIs).
    """
    org_name = (req.org_name or "").strip()
    if not org_name:
        raise HTTPException(status_code=400, detail="org_name is required")
    project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
    marts_dataset = os.environ.get("BQ_MARTS_MEDICAID_DATASET", "mobius_medicaid_npi_dev")
    landing_dataset = os.environ.get("BQ_LANDING_MEDICAID_DATASET", "landing_medicaid_npi_dev")
    try:
        from google.cloud import bigquery
        bq_client = bigquery.Client(project=project)
    except ImportError as e:
        logger.exception("BigQuery not available")
        raise HTTPException(status_code=503, detail="BigQuery client not available") from e
    except Exception as e:
        logger.exception("BigQuery client init failed")
        raise HTTPException(status_code=503, detail=str(e)) from e
    try:
        result = build_full_report(
            bq_client,
            org_name=org_name,
            project=project,
            marts_dataset=marts_dataset,
            landing_dataset=landing_dataset,
            location_ids=req.location_ids,
            npi_overrides=req.npi_overrides,
        )
        return result
    except Exception as e:
        logger.exception("Report build failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8010")))
