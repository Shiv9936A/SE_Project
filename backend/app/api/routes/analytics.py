"""Project and AI usage summaries for the frontend dashboard."""
from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Conversation, DocumentChunk, GeneratedRecommendation, Project, UploadedDocument
from app.schemas.analytics import AnalyticsSummary


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary, summary="Get dashboard aggregate counts")
def dashboard_summary(db: Session = Depends(get_db)):
    completed_count = func.sum(case((DocumentChunk.embedding_status == "completed", 1), else_=0))
    fully_embedded = (select(DocumentChunk.document_id)
                      .group_by(DocumentChunk.document_id)
                      .having(func.count(DocumentChunk.id) == completed_count)
                      .subquery())
    return {
        "project_count": db.scalar(select(func.count()).select_from(Project)) or 0,
        "document_count": db.scalar(select(func.count()).select_from(UploadedDocument)) or 0,
        "embedded_document_count": db.scalar(select(func.count()).select_from(fully_embedded)) or 0,
        "recommendation_count": db.scalar(select(func.count()).select_from(GeneratedRecommendation)) or 0,
        "conversation_count": db.scalar(select(func.count()).select_from(Conversation)) or 0,
    }
