"""FastAPI app: POST /healthcare/query. Mobius Healthcare skill API."""
import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.skills import answer_healthcare_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mobius Healthcare API", version="0.1.0")


class QueryRequest(BaseModel):
    """Request body for healthcare query."""

    question: str
    data_sources: list[str] | None = None


class QueryResponse(BaseModel):
    """Response for healthcare query."""

    answer: str
    question: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "mobius-healthcare-api"}


@app.post("/healthcare/query", response_model=QueryResponse)
async def healthcare_query(req: QueryRequest) -> QueryResponse:
    """Answer a healthcare question using CMS coverage, ICD-10, and NPI data."""
    try:
        answer = answer_healthcare_query(
            question=req.question,
            data_sources=req.data_sources,
        )
        return QueryResponse(answer=answer, question=req.question)
    except Exception as e:
        logger.exception("Healthcare query failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8007)
