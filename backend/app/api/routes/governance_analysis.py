"""Governance & SDLC analysis endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.governance_analysis import GovernanceAnalysisRead
from app.services.agents.governance_agent import governance_agent

router = APIRouter(prefix="/projects", tags=["governance analysis"])


@router.post("/{project_id}/governance-analysis", response_model=GovernanceAnalysisRead,
             summary="Generate a reviewable governance and SDLC plan")
def generate_governance_analysis(project_id: str, db: Session = Depends(get_db)):
    return governance_agent.analyze(db, project_id)


@router.get("/{project_id}/governance-analysis", response_model=GovernanceAnalysisRead,
            summary="Get the latest governance and SDLC plan")
def get_governance_analysis(project_id: str, db: Session = Depends(get_db)):
    return governance_agent.latest(db, project_id)
