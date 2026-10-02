"""Persistence queries for requirements analysis history."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.requirements_analysis import RequirementsAnalysis


def latest(db: Session, project_id: str) -> RequirementsAnalysis | None:
    return db.scalar(
        select(RequirementsAnalysis)
        .where(RequirementsAnalysis.project_id == project_id)
        .order_by(RequirementsAnalysis.version.desc(), RequirementsAnalysis.created_at.desc(), RequirementsAnalysis.id.desc())
        .limit(1)
    )


def create(db: Session, record: RequirementsAnalysis) -> RequirementsAnalysis:
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def next_version(db: Session, project_id: str) -> int:
    current = db.scalar(select(func.max(RequirementsAnalysis.version)).where(
        RequirementsAnalysis.project_id == project_id
    ))
    return int(current or 0) + 1
