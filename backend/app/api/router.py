"""Top-level API router."""
from fastapi import APIRouter

from app.api.routes import analysis_runs, analytics, documents, governance_analysis, health, interviews, orchestration, projects, rag, requirements_analysis, search, sdlc_recommendations

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(analytics.router)
api_router.include_router(projects.router)
api_router.include_router(interviews.router)
api_router.include_router(documents.router)
api_router.include_router(search.router)
api_router.include_router(rag.router)
api_router.include_router(sdlc_recommendations.router)
api_router.include_router(requirements_analysis.router)
api_router.include_router(governance_analysis.router)
api_router.include_router(orchestration.router)
api_router.include_router(analysis_runs.router)
