"""Persistence queries for LangGraph recommendation history."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GeneratedRecommendation


def create(db: Session, recommendation: GeneratedRecommendation) -> GeneratedRecommendation:
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)
    return recommendation


def history(db: Session, project_id: str, limit: int = 20, offset: int = 0) -> list[GeneratedRecommendation]:
    statement = (select(GeneratedRecommendation)
                 .where(GeneratedRecommendation.project_id == project_id,
                        GeneratedRecommendation.scoring_method == "langgraph_v2")
                 .order_by(GeneratedRecommendation.created_at.desc(), GeneratedRecommendation.id.desc())
                 .limit(limit).offset(offset))
    return list(db.scalars(statement).all())
