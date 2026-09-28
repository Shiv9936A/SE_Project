from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Project


def create(db: Session, values: dict) -> Project:
    project = Project(**values)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get(db: Session, project_id: str) -> Project | None:
    statement = (select(Project).options(selectinload(Project.questionnaire), selectinload(Project.documents), selectinload(Project.recommendations))
                 .where(Project.id == project_id))
    project = db.scalar(statement)
    if project and project.recommendations:
        project.recommendations.sort(key=lambda item: item.created_at, reverse=True)
    return project


def list_all(db: Session, limit: int = 100, offset: int = 0) -> list[Project]:
    statement = select(Project).order_by(Project.updated_at.desc()).offset(offset).limit(limit)
    return list(db.scalars(statement).all())


def update(db: Session, project: Project, values: dict) -> Project:
    for key, value in values.items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project
