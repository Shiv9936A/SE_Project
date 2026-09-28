"""Project use cases over the repository layer."""
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.repositories import projects as project_repo


def require_project(db: Session, project_id: str):
    project = project_repo.get(db, project_id)
    if project is None:
        raise AppError("Project not found.", 404)
    return project


def create_project(db: Session, values: dict):
    return project_repo.create(db, values)


def get_project(db: Session, project_id: str):
    return require_project(db, project_id)


def list_projects(db: Session, limit: int, offset: int):
    return project_repo.list_all(db, limit, offset)


def update_project(db: Session, project_id: str, values: dict):
    project = require_project(db, project_id)
    return project_repo.update(db, project, values)
