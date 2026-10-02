"""Read and shape persisted orchestration history for API consumers."""
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import Project
from app.repositories import analysis_runs
from app.schemas.governance_analysis import GovernanceAnalysisRead
from app.schemas.orchestration import AnalysisRunDetail, AnalysisRunSummary, OrchestrationAgentStatus
from app.schemas.requirements_analysis import RequirementsAnalysisRead


def _requirement_read(record):
    if record is None:
        return None
    return RequirementsAnalysisRead.model_validate({
        "analysis_id": record.id, "project_id": record.project_id, "version": record.version,
        "status": record.status, "provider": record.provider, "model": record.model,
        "created_at": record.created_at, **(record.result_json or {}),
    })


def _governance_read(record):
    if record is None:
        return None
    return GovernanceAnalysisRead.model_validate({
        "id": record.id, "project_id": record.project_id,
        "requirements_analysis_id": record.requirements_analysis_id, "version": record.version,
        "status": record.status, "provider": record.provider, "model": record.model,
        "created_at": record.created_at, "updated_at": record.updated_at,
        "result": record.result_json,
    })


def _shape(run, detail=False):
    req = run.requirements_analysis
    gov = run.governance_analysis
    req_read = _requirement_read(req)
    gov_read = _governance_read(gov)
    req_result = req.result_json if req else {}
    gov_result = gov.result_json if gov else {}
    methodology = (gov_result.get("methodology") or {}).get("name") or (gov.methodology if gov else None)
    values = {
        "id": run.id, "project_id": run.project_id, "version": run.version,
        "status": run.status, "orchestration_version": run.orchestration_version,
        "started_at": run.started_at, "completed_at": run.completed_at, "created_at": run.created_at,
        "requirements_analysis_id": req.id if req else None,
        "governance_analysis_id": gov.id if gov else None,
        "requirement_count": len(req_result.get("requirements") or []),
        "ambiguity_count": len(req_result.get("ambiguities") or []),
        "conflict_count": len(req_result.get("conflicts") or []),
        "risk_count": len(gov_result.get("risks") or []), "methodology": methodology,
        "warnings": run.warnings_json or [], "errors": run.errors_json or [],
    }
    if not detail:
        return AnalysisRunSummary.model_validate(values)
    statuses = run.agent_statuses_json or []
    if not statuses:
        statuses = []
        for name, record in (("requirements", req), ("governance", gov)):
            status = "skipped" if record is None else ("partial" if record.status == "partial" else "completed")
            statuses.append({"name": name, "status": status})
    return AnalysisRunDetail.model_validate({
        **values, "agents": [OrchestrationAgentStatus.model_validate(status) for status in statuses],
        "requirements_analysis": req_read, "governance_analysis": gov_read,
    })


def list_project_runs(db: Session, project_id: str, limit=50, offset=0):
    if db.get(Project, project_id) is None:
        raise AppError("Project not found.", 404)
    return [_shape(run) for run in analysis_runs.list_for_project(db, project_id, limit, offset)]


def get_project_run(db: Session, project_id: str, run_id: str):
    if db.get(Project, project_id) is None:
        raise AppError("Project not found.", 404)
    run = analysis_runs.get(db, project_id, run_id)
    if run is None:
        raise AppError("Analysis run not found.", 404)
    return _shape(run, detail=True)
