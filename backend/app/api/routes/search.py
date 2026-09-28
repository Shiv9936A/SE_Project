"""Vector similarity search endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.vector_search import SearchRequest, SearchResult
from app.services.retrieval_service import retrieval_service

router = APIRouter(tags=["vector search"])


@router.post("/search", response_model=list[SearchResult], summary="Search indexed project chunks")
def search(request: SearchRequest, db: Session = Depends(get_db)):
    """Return the most similar indexed text chunks, always scoped to one project."""
    return retrieval_service.search(db, request.project_id, request.query, request.top_k, request.filters)
