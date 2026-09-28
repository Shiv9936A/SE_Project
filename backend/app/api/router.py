"""Top-level API router."""
from fastapi import APIRouter

from app.api.routes import analytics, documents, health, projects, rag, search, sdlc_recommendations

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(analytics.router)
api_router.include_router(projects.router)
api_router.include_router(documents.router)
api_router.include_router(search.router)
api_router.include_router(rag.router)
api_router.include_router(sdlc_recommendations.router)
