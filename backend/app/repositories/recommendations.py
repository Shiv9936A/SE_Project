from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GeneratedRecommendation


def create(db: Session, recommendation: GeneratedRecommendation) -> GeneratedRecommendation:
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)
    return recommendation


def latest(db: Session, project_id: str) -> GeneratedRecommendation | None:
    statement = (select(GeneratedRecommendation).where(
                    GeneratedRecommendation.project_id == project_id,
                    GeneratedRecommendation.scoring_method.in_(("rule_based_v2", "langgraph_v2")),
                 )
                 .order_by(GeneratedRecommendation.created_at.desc()).limit(1))
    return db.scalar(statement)
