"""Project, questionnaire, analysis, and recommendation endpoints."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.repositories import projects as project_repo
from app.repositories.questionnaires import upsert as upsert_questionnaire
from app.schemas.projects import ProjectCreate, ProjectDetail, ProjectRead, ProjectUpdate
from app.schemas.questionnaire import QuestionnaireResponseCreate, QuestionnaireResponseRead
from app.schemas.recommendations import RecommendationRead
from app.services import analysis_service, project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, summary="Create a project")
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    return project_service.create_project(db, payload.model_dump())


@router.get("", response_model=list[ProjectRead], summary="List projects")
def list_projects(limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    return project_service.list_projects(db, limit, offset)


@router.get("/{project_id}", response_model=ProjectDetail, summary="Get project details")
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = project_service.get_project(db, project_id)
    return {"id": project.id, "project_name": project.project_name, "description": project.description,
            "domain": project.domain, "organization_type": project.organization_type, "team_size": project.team_size,
            "stakeholders": project.stakeholders, "initial_requirements": project.initial_requirements,
            "created_at": project.created_at, "updated_at": project.updated_at,
            "questionnaire": project.questionnaire, "documents": project.documents,
            "recommendation": project.recommendation}


@router.put("/{project_id}", response_model=ProjectRead, summary="Update project details")
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)):
    values = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not values:
        raise AppError("Provide at least one project field to update.", 422)
    return project_service.update_project(db, project_id, values)


@router.post("/{project_id}/questionnaire", response_model=QuestionnaireResponseRead, summary="Save SDLC questionnaire answers")
def save_questionnaire(project_id: str, payload: QuestionnaireResponseCreate, db: Session = Depends(get_db)):
    project_service.require_project(db, project_id)
    return upsert_questionnaire(db, project_id, payload.model_dump())


@router.post("/{project_id}/analyze", response_model=RecommendationRead, summary="Generate a rule-based SDLC recommendation")
def analyze_project(project_id: str, db: Session = Depends(get_db)):
    """Phase 3 deterministic baseline. LLM explanation, RAG, and agents are deferred."""
    return analysis_service.generate_recommendation(db, project_id)


@router.get("/{project_id}/recommendation", response_model=RecommendationRead, summary="Get latest SDLC recommendation")
def get_recommendation(project_id: str, db: Session = Depends(get_db)):
    return analysis_service.get_recommendation(db, project_id)
