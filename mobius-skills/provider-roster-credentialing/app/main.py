"""FastAPI app: Provider Roster / Credentialing report. POST /report, POST /search/org-names, POST /search/org-by-address, POST /find-locations."""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.core import build_full_report
from app.location_identification import find_locations_for_org
from app.org_search import search_org_names, search_org_by_address

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Provider Roster / Credentialing API",
    version="0.1.0",
    description="Provider Roster / Credentialing report per organization (locations, NPIs, readiness, invalid combos, ghost billing). Org search by name or address.",
)


def _get_bq_client():
    from google.cloud import bigquery
    project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
    return bigquery.Client(project=project)


def _get_datasets():
    project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
    landing = os.environ.get("BQ_LANDING_MEDICAID_DATASET") or None
    return project, landing


class ReportRequest(BaseModel):
    """Request body for report generation."""

    org_name: str
    location_ids: list[str] | None = None
    locations_override: list[dict[str, Any]] | None = None
    npi_overrides: dict[str, dict[str, Any]] | None = None


class SearchOrgNamesRequest(BaseModel):
    """Request body for org name search."""

    name: str
    state: str = "FL"
    limit: int = 20
    include_pml: bool = True
    entity_type_filter: str | None = "2"


class SearchOrgByAddressRequest(BaseModel):
    """Request body for org address search."""

    address_raw: str | None = None
    address_line_1: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    limit: int = 20
    include_pml: bool = True
    use_google: bool = True
    entity_type_filter: str | None = "2"


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
            locations_override=req.locations_override,
            npi_overrides=req.npi_overrides,
            state_filter=getattr(req, "state", None) or "FL",
        )
        return result
    except Exception as e:
        logger.exception("Report build failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/search/org-names")
async def api_search_org_names(req: SearchOrgNamesRequest) -> dict[str, Any]:
    """Search NPPES and PML by org/provider name. Returns list of {npi, name, source, entity_type}."""
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        results = search_org_names(
            bq,
            name,
            state_filter=req.state,
            limit=req.limit,
            include_pml=req.include_pml,
            entity_type_filter=req.entity_type_filter,
            project=project,
            landing_dataset=landing,
        )
        return {"results": results}
    except ImportError as e:
        raise HTTPException(status_code=503, detail="BigQuery client not available") from e
    except Exception as e:
        logger.exception("Org name search failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/search/org-by-address")
async def api_search_org_by_address(req: SearchOrgByAddressRequest) -> dict[str, Any]:
    """Search NPPES and PML by address. Pass address_raw or address_line_1/city/state/postal_code."""
    if not req.address_raw and not any([req.address_line_1, req.city, req.postal_code]):
        raise HTTPException(status_code=400, detail="address_raw or (address_line_1, city, state, postal_code) required")
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        norm, results = search_org_by_address(
            bq,
            address_raw=req.address_raw,
            address_line_1=req.address_line_1,
            city=req.city,
            state=req.state or "FL",
            postal_code=req.postal_code,
            limit=req.limit,
            include_pml=req.include_pml,
            use_google=req.use_google,
            entity_type_filter=req.entity_type_filter,
            project=project,
            landing_dataset=landing,
        )
        if norm is None:
            return {"normalized_address": None, "results": [], "error": "Could not normalize address (need valid ZIP5)"}
        return {"normalized_address": norm, "results": results}
    except ImportError as e:
        raise HTTPException(status_code=503, detail="BigQuery client not available") from e
    except Exception as e:
        logger.exception("Org address search failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


class FindLocationsRequest(BaseModel):
    """Request body for find locations (Step 2)."""

    org_npis: list[str]
    initial_sites: list[dict[str, Any]] | None = None
    state: str = "FL"


@app.post("/find-locations")
async def api_find_locations(req: FindLocationsRequest) -> dict[str, Any]:
    """Find all practice locations for an org. Input: org_npis (from Step 1 find-org), optional initial_sites."""
    if not req.org_npis:
        raise HTTPException(status_code=400, detail="org_npis required")
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        locations = find_locations_for_org(
            bq,
            req.org_npis,
            initial_sites=req.initial_sites,
            state_filter=req.state,
            project=project,
            landing_dataset=landing,
        )
        return {"locations": locations, "count": len(locations)}
    except ImportError as e:
        raise HTTPException(status_code=503, detail="BigQuery client not available") from e
    except Exception as e:
        logger.exception("Find locations failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8010")))
