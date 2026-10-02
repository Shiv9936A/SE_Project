"""Requirements analysis generation and retrieval."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.requirements_analysis import RequirementsAnalysisRead, RequirementsAnalysisRequest
from app.services.agents.requirements_agent import requirements_analysis_agent

router = APIRouter(prefix="/projects", tags=["requirements analysis"])


@router.post("/{project_id}/analyze-requirements", response_model=RequirementsAnalysisRead,
             summary="Analyze project requirements and save a reviewable draft")
def analyze_requirements(project_id: str, payload: RequirementsAnalysisRequest,
                         db: Session = Depends(get_db)):
    """Use project inputs and available document evidence to create a draft for human review."""
    return requirements_analysis_agent.analyze(db, project_id, top_k=payload.top_k)


@router.get("/{project_id}/requirements-analysis", response_model=RequirementsAnalysisRead,
            summary="Get the latest persisted requirements analysis")
def get_requirements_analysis(project_id: str, db: Session = Depends(get_db)):
    return requirements_analysis_agent.latest(db, project_id)
