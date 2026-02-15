"""Health check router."""
from fastapi import APIRouter, HTTPException

from app.db import qa_session

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Check QA DB connectivity."""
    try:
        with qa_session() as c:
            cur = c.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"qa_db unhealthy: {type(e).__name__}: {e}")
