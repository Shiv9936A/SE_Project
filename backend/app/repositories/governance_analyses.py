"""Database operations for governance analysis history."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.governance_analysis import GovernanceAnalysis


def latest(db: Session, project_id: str) -> GovernanceAnalysis | None:
    return db.scalar(
        select(GovernanceAnalysis)
        .where(GovernanceAnalysis.project_id == project_id)
        .order_by(GovernanceAnalysis.version.desc(), GovernanceAnalysis.created_at.desc(), GovernanceAnalysis.id.desc())
        .limit(1)
    )


def next_version(db: Session, project_id: str) -> int:
    current = db.scalar(select(func.max(GovernanceAnalysis.version)).where(
        GovernanceAnalysis.project_id == project_id
    ))
    return int(current or 0) + 1


def create(db: Session, record: GovernanceAnalysis) -> GovernanceAnalysis:
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
