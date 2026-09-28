"""LangGraph SDLC recommendation and comparison endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.sdlc_recommendations import (
    SDLCComparisonRequest, SDLCComparisonResponse, SDLCRecommendationRead,
    SDLCRecommendationRequest,
)
from app.services.sdlc_recommendation_service import sdlc_recommendation_service


router = APIRouter(prefix="/projects", tags=["SDLC recommendations"])


@router.post("/{project_id}/recommend-sdlc", response_model=SDLCRecommendationRead,
             summary="Generate a LangGraph SDLC recommendation")
def recommend_sdlc(project_id: str, payload: SDLCRecommendationRequest,
                   db: Session = Depends(get_db)):
    """Retrieve project evidence, score the SDLC models, generate a rationale, and persist the run."""
    return sdlc_recommendation_service.recommend(
        db, project_id, top_k=payload.top_k, filters=payload.filters,
    )


@router.get("/{project_id}/recommendation-history", response_model=list[SDLCRecommendationRead],
            summary="List persisted LangGraph recommendation runs")
def recommendation_history(project_id: str, limit: int = Query(default=20, ge=1, le=100),
                           offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    return sdlc_recommendation_service.history(db, project_id, limit, offset)


@router.post("/{project_id}/compare-sdlc", response_model=SDLCComparisonResponse,
             summary="Compare two SDLC models for a project")
def compare_sdlc(project_id: str, payload: SDLCComparisonRequest,
                 db: Session = Depends(get_db)):
    return sdlc_recommendation_service.compare(
        db, project_id, payload.model_a, payload.model_b,
        top_k=payload.top_k, filters=payload.filters,
    )
