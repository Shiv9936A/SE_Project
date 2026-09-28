from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(tags=["system"])


@router.get("/health", summary="Check API and database health")
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable.") from exc
    return {"status": "ok", "database": "ok", "service": "requirements-studio-api"}
