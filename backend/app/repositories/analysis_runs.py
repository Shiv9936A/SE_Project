"""Persistence operations for versioned orchestration executions."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.analysis_run import AnalysisRun
from app.models.governance_analysis import GovernanceAnalysis
from app.models.project import Project
from app.models.requirements_analysis import RequirementsAnalysis


def _stale_rows(db: Session, project_id: str | None = None) -> bool:
    timeout = max(5, min(int(settings.analysis_run_stale_after_minutes), 24 * 60))
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout)
    query = select(AnalysisRun).where(AnalysisRun.status == "running", AnalysisRun.started_at <= cutoff)
    if project_id:
        query = query.where(AnalysisRun.project_id == project_id)
    changed = False
    for run in db.scalars(query).all():
        run.status = "failed"
        run.active_project_id = None
        run.completed_at = datetime.now(timezone.utc)
        run.updated_at = run.completed_at
        run.errors_json = [*run.errors_json, {
            "code": "ANALYSIS_RUN_ABANDONED",
            "message": "Analysis did not finish and was marked failed after the recovery timeout.",
            "recoverable": True,
        }]
        changed = True
    return changed


def create(db: Session, project_id: str) -> AnalysisRun:
    """Allocate the next unique project version and reserve the project's active slot."""
    project = db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None:
        raise AppError("Project not found.", 404)
    _stale_rows(db, project_id)
    active = db.scalar(select(AnalysisRun).where(
        AnalysisRun.active_project_id == project_id,
    ).limit(1))
    if active is not None:
        db.rollback()
        raise AppError("An analysis is already running for this project. Wait for it to finish before starting another.", 409)

    latest_version = db.scalar(select(func.max(AnalysisRun.version)).where(AnalysisRun.project_id == project_id)) or 0
    run = AnalysisRun(project_id=project_id, version=int(latest_version) + 1,
                      status="running", active_project_id=project_id)
    db.add(run)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        active = db.scalar(select(AnalysisRun).where(AnalysisRun.active_project_id == project_id).limit(1))
        if active is not None:
            raise AppError("An analysis is already running for this project. Wait for it to finish before starting another.", 409) from exc
        raise AppError("A new analysis run could not be reserved. Please retry.", 409) from exc
    db.refresh(run)
    return run


def attach_requirements(db: Session, run_id: str, analysis_id: str) -> RequirementsAnalysis:
    run = db.get(AnalysisRun, run_id)
    analysis = db.get(RequirementsAnalysis, analysis_id)
    if run is None or analysis is None or run.project_id != analysis.project_id:
        raise AppError("Requirements analysis could not be linked to this run.", 409)
    if analysis.analysis_run_id not in (None, run_id):
        raise AppError("Requirements analysis is already linked to another run.", 409)
    analysis.analysis_run_id = run_id
    db.commit()
    db.refresh(analysis)
    return analysis


def attach_governance(db: Session, run_id: str, analysis_id: str) -> GovernanceAnalysis:
    run = db.get(AnalysisRun, run_id)
    analysis = db.get(GovernanceAnalysis, analysis_id)
    if run is None or analysis is None or run.project_id != analysis.project_id:
        raise AppError("Governance analysis could not be linked to this run.", 409)
    if analysis.analysis_run_id not in (None, run_id):
        raise AppError("Governance analysis is already linked to another run.", 409)
    analysis.analysis_run_id = run_id
    db.commit()
    db.refresh(analysis)
    return analysis


def finish(db: Session, run_id: str, status: str, warnings: list, errors: list,
           agent_statuses: list | None = None) -> AnalysisRun:
    if status not in {"completed", "partial", "failed"}:
        raise ValueError("Analysis run must finish in a terminal status")
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise AppError("Analysis run not found.", 404)
    if run.status == "running":
        now = datetime.now(timezone.utc)
        run.status = status
        run.active_project_id = None
        run.completed_at = now
        run.updated_at = now
        run.warnings_json = list(warnings)
        run.errors_json = list(errors)
        run.agent_statuses_json = list(agent_statuses or [])
        db.commit()
        db.refresh(run)
    return run


def list_for_project(db: Session, project_id: str, limit: int = 50, offset: int = 0) -> list[AnalysisRun]:
    if _stale_rows(db, project_id):
        db.commit()
    return list(db.scalars(
        select(AnalysisRun)
        .options(joinedload(AnalysisRun.requirements_analysis), joinedload(AnalysisRun.governance_analysis))
        .where(AnalysisRun.project_id == project_id)
        .order_by(AnalysisRun.version.desc(), AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
        .offset(offset).limit(limit)
    ).unique().all())


def get(db: Session, project_id: str, run_id: str) -> AnalysisRun | None:
    if _stale_rows(db, project_id):
        db.commit()
    return db.scalar(
        select(AnalysisRun)
        .options(joinedload(AnalysisRun.requirements_analysis), joinedload(AnalysisRun.governance_analysis))
        .where(AnalysisRun.project_id == project_id, AnalysisRun.id == run_id)
    )
