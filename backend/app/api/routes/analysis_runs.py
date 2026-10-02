"""Persistent orchestration run history endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.orchestration import AnalysisRunDetail, AnalysisRunSummary
from app.services.analysis_run_service import get_project_run, list_project_runs

router = APIRouter(prefix="/projects", tags=["analysis history"])


@router.get("/{project_id}/analysis-runs", response_model=list[AnalysisRunSummary],
            summary="List versioned analysis runs for a project")
def list_analysis_runs(project_id: str, limit: int = Query(50, ge=1, le=100),
                       offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    return list_project_runs(db, project_id, limit=limit, offset=offset)


@router.get("/{project_id}/analysis-runs/{run_id}", response_model=AnalysisRunDetail,
            summary="Get a persisted orchestration run and its agent outputs")
def get_analysis_run(project_id: str, run_id: str, db: Session = Depends(get_db)):
    return get_project_run(db, project_id, run_id)
