"""Coordinated Requirements Studio workflow endpoint."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.orchestration import OrchestrationResult
from app.services.orchestration_service import orchestration_service

router = APIRouter(prefix="/projects", tags=["orchestration"])


class OrchestrationRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=10)


@router.post("/{project_id}/orchestrate", response_model=OrchestrationResult,
             summary="Run requirements and governance agents in sequence")
def orchestrate_project(project_id: str, payload: OrchestrationRequest = OrchestrationRequest(),
                        db: Session = Depends(get_db)):
    return orchestration_service.orchestrate(db, project_id, top_k=payload.top_k)
