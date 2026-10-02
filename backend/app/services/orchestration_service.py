"""LangGraph coordination for the existing requirements and governance services."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Literal, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.models import Project
from app.repositories import governance_analyses, requirements_analyses
from app.repositories import analysis_runs
from app.schemas.governance_analysis import GovernanceAnalysisRead
from app.schemas.orchestration import OrchestrationResult
from app.schemas.requirements_analysis import RequirementsAnalysisRead
from app.services.agents.governance_agent import governance_agent
from app.services.agents.requirements_agent import requirements_analysis_agent

logger = logging.getLogger(__name__)


class RetryLimitReached(Exception):
    def __init__(self, original: Exception, retry_count: int):
        super().__init__(type(original).__name__)
        self.original = original
        self.retry_count = retry_count


class RequirementsStudioState(TypedDict, total=False):
    orchestration_id: str
    analysis_run_id: str
    analysis_run_version: int
    project_id: str
    project_context: dict
    interview_context: dict
    requirements_analysis_id: str | None
    governance_analysis_id: str | None
    requirements_result: dict | None
    governance_result: dict | None
    requirements_reused: bool
    governance_reused: bool
    requirements_valid: bool
    governance_valid: bool
    agent_statuses: dict[str, str]
    status: Literal["completed", "partial", "failed"]
    current_agent: str
    errors: list[dict]
    warnings: list[str]
    retry_count: int
    created_at: str


def _transient(exc: Exception) -> bool:
    exc = getattr(exc, "original", exc)
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    status = getattr(exc, "status_code", None)
    return status in {502, 503, 504}


class OrchestrationService:
    def build_graph(self, db: Session, top_k: int = 5):
        """Build per-request nodes around a request-scoped DB session; graph state stays serializable."""

        def log_start(state, node, agent=None):
            logger.info("Orchestration node started", extra={
                "orchestration_id": state.get("orchestration_id"), "project_id": state.get("project_id"),
                "node": node, "agent": agent, "retry_count": state.get("retry_count", 0),
            })
            return perf_counter()

        def log_end(state, node, started, success=True, fallback=False):
            logger.info("Orchestration node finished", extra={
                "orchestration_id": state.get("orchestration_id"), "project_id": state.get("project_id"),
                "node": node, "latency_ms": round((perf_counter() - started) * 1000, 2),
                "success": success, "fallback": fallback, "retry_count": state.get("retry_count", 0),
            })

        def load_project_context(state: RequirementsStudioState):
            started = log_start(state, "load_project_context")
            project = db.get(Project, state["project_id"])
            if project is None:
                raise AppError("Project not found.", 404)
            project_context = {key: getattr(project, key, None) for key in (
                "id", "project_name", "description", "domain", "organization_type", "team_size",
            )}
            log_end(state, "load_project_context", started)
            return {"project_context": project_context}

        def load_interview(state: RequirementsStudioState):
            started = log_start(state, "load_interview")
            project = db.get(Project, state["project_id"])
            interview = project.interview if project else None
            if interview is None or interview.status != "completed":
                raise AppError("Complete the adaptive requirements interview before running orchestration.", 409)
            context = {
                "interview_id": interview.id,
                "status": interview.status,
                "answer_count": len(interview.answers or []),
                "covered_topics": list(interview.covered_topics or []),
                "uncovered_topics": list(interview.uncovered_topics or []),
            }
            log_end(state, "load_interview", started)
            return {"interview_context": context}

        def call_agent(state, name, operation):
            max_retries = max(0, min(int(settings.orchestration_max_retries), 2))
            retries = state.get("retry_count", 0)
            for attempt in range(max_retries + 1):
                try:
                    return operation(), retries
                except Exception as exc:
                    if not _transient(exc):
                        raise
                    if attempt >= max_retries:
                        raise RetryLimitReached(exc, retries) from exc
                    retries += 1
                    logger.warning("Transient orchestration agent failure; retrying", extra={
                        "orchestration_id": state.get("orchestration_id"), "project_id": state.get("project_id"),
                        "node": f"run_{name}_agent", "agent": name,
                        "attempt": attempt + 1, "retry_count": retries, "failure_type": type(exc).__name__,
                    })
            return None

        def run_requirements_agent(state: RequirementsStudioState):
            started = log_start(state, "run_requirements_agent", "requirements")
            existing = requirements_analyses.latest(db, state["project_id"])
            if existing is not None and state.get("analysis_run_id") and existing.analysis_run_id is not None:
                existing = None
            if existing is not None:
                try:
                    result = requirements_analysis_agent.serialize(existing)
                    validated = RequirementsAnalysisRead.model_validate(result).model_dump(mode="json")
                except (ValidationError, ValueError, TypeError):
                    existing = None
            if existing is None:
                result, retries = call_agent(state, "requirements", lambda: requirements_analysis_agent.analyze(
                    db, state["project_id"], top_k=top_k
                ))
                reused = False
            else:
                reused = True
            result = validated if reused else result
            result_id = result.get("analysis_id")
            if state.get("analysis_run_id") and result_id:
                analysis_runs.attach_requirements(db, state["analysis_run_id"], result_id)
            log_end(state, "run_requirements_agent", started)
            return {
                "requirements_result": result,
                "requirements_reused": reused,
                "retry_count": retries if not reused else state.get("retry_count", 0),
                "current_agent": "requirements",
                "agent_statuses": {**state.get("agent_statuses", {}), "requirements": "running"},
            }

        def validate_requirements(state: RequirementsStudioState):
            started = log_start(state, "validate_requirements", "requirements")
            if state.get("agent_statuses", {}).get("requirements") == "failed":
                log_end(state, "validate_requirements", started, success=False)
                return {"requirements_valid": False}
            result = RequirementsAnalysisRead.model_validate(state.get("requirements_result"))
            if result.project_id != state["project_id"]:
                raise ValueError("Requirements analysis belongs to another project")
            normalized = result.model_dump(mode="json")
            status = "partial" if result.status == "partial" else "completed"
            log_end(state, "validate_requirements", started, fallback=status == "partial")
            return {
                "requirements_result": normalized, "requirements_analysis_id": result.analysis_id,
                "current_agent": "coordinator",
                "requirements_valid": True,
                "agent_statuses": {**state.get("agent_statuses", {}), "requirements": status},
                "warnings": state.get("warnings", []) + (["Requirements analysis used its deterministic fallback."] if status == "partial" else []),
            }

        def requirements_route(state):
            return "governance" if state.get("requirements_valid") else "finalize"

        def run_governance_agent(state: RequirementsStudioState):
            started = log_start(state, "run_governance_agent", "governance")
            # The agent service reads the persisted requirements record itself; require an exact ID match.
            existing = governance_analyses.latest(db, state["project_id"])
            if existing is not None and state.get("analysis_run_id") and existing.analysis_run_id is not None:
                existing = None
            if existing is not None and existing.requirements_analysis_id == state.get("requirements_analysis_id"):
                try:
                    result = governance_agent._serialize(existing)
                    validated = GovernanceAnalysisRead.model_validate(result).model_dump(mode="json")
                except (ValidationError, ValueError, TypeError):
                    existing = None
            else:
                existing = None
            if existing is None:
                result, retries = call_agent(state, "governance", lambda: governance_agent.analyze(
                    db, state["project_id"], top_k=top_k
                ))
                reused = False
            else:
                reused = True
            result = validated if reused else result
            result_id = result.get("id")
            if state.get("analysis_run_id") and result_id:
                analysis_runs.attach_governance(db, state["analysis_run_id"], result_id)
            log_end(state, "run_governance_agent", started)
            return {
                "governance_result": result,
                "governance_reused": reused,
                "retry_count": retries if not reused else state.get("retry_count", 0),
                "current_agent": "governance",
                "agent_statuses": {**state.get("agent_statuses", {}), "governance": "running"},
            }

        def validate_governance(state: RequirementsStudioState):
            started = log_start(state, "validate_governance", "governance")
            if state.get("agent_statuses", {}).get("governance") == "failed":
                log_end(state, "validate_governance", started, success=False)
                return {"governance_valid": False}
            result = GovernanceAnalysisRead.model_validate(state.get("governance_result"))
            if result.project_id != state["project_id"] or result.requirements_analysis_id != state.get("requirements_analysis_id"):
                raise ValueError("Governance analysis does not reference the validated requirements analysis")
            normalized = result.model_dump(mode="json")
            status = "partial" if result.status == "partial" else "completed"
            log_end(state, "validate_governance", started, fallback=status == "partial")
            return {
                "governance_result": normalized, "governance_analysis_id": result.id,
                "current_agent": "coordinator",
                "governance_valid": True,
                "agent_statuses": {**state.get("agent_statuses", {}), "governance": status},
                "warnings": state.get("warnings", []) + (["Governance analysis used its deterministic fallback."] if status == "partial" else []),
            }

        def finalize(state: RequirementsStudioState):
            started = log_start(state, "finalize")
            req = state.get("requirements_result")
            gov = state.get("governance_result")
            statuses = state.get("agent_statuses", {})
            errors = state.get("errors", [])
            status = "failed" if not state.get("requirements_valid") else (
                "completed" if state.get("governance_valid") and statuses.get("requirements") == "completed" and statuses.get("governance") == "completed" else "partial"
            )
            if req and not state.get("requirements_valid"):
                req = None
            if gov and not state.get("governance_valid"):
                gov = None
            log_end(state, "finalize", started, success=status != "failed")
            return {"status": status, "created_at": state.get("created_at") or datetime.now(timezone.utc).isoformat(),
                    "requirements_result": req, "governance_result": gov, "errors": errors}

        def safe_run_requirements(state):
            started = perf_counter()
            try:
                return run_requirements_agent(state)
            except Exception as exc:
                return self._failure(state, "requirements", exc, started)

        def safe_validate_requirements(state):
            started = perf_counter()
            try:
                return validate_requirements(state)
            except Exception as exc:
                return self._failure(state, "requirements_validation", exc, started)

        def safe_run_governance(state):
            started = perf_counter()
            try:
                return run_governance_agent(state)
            except Exception as exc:
                return self._failure(state, "governance", exc, started)

        def safe_validate_governance(state):
            started = perf_counter()
            try:
                return validate_governance(state)
            except Exception as exc:
                return self._failure(state, "governance_validation", exc, started)

        graph = StateGraph(RequirementsStudioState)
        graph.add_node("load_project_context", load_project_context)
        graph.add_node("load_interview", load_interview)
        graph.add_node("run_requirements_agent", safe_run_requirements)
        graph.add_node("validate_requirements", safe_validate_requirements)
        graph.add_node("run_governance_agent", safe_run_governance)
        graph.add_node("validate_governance", safe_validate_governance)
        graph.add_node("finalize", finalize)
        graph.add_edge(START, "load_project_context")
        graph.add_edge("load_project_context", "load_interview")
        graph.add_edge("load_interview", "run_requirements_agent")
        graph.add_edge("run_requirements_agent", "validate_requirements")
        graph.add_conditional_edges("validate_requirements", requirements_route,
                                    {"governance": "run_governance_agent", "finalize": "finalize"})
        graph.add_edge("run_governance_agent", "validate_governance")
        graph.add_edge("validate_governance", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    @staticmethod
    def _failure(state, stage, exc, started=None):
        req_stage = stage.startswith("requirements")
        agent = "requirements" if req_stage else "governance"
        transient = _transient(exc)
        retry_count = getattr(exc, "retry_count", state.get("retry_count", 0))
        code = ("REQUIREMENTS_VALIDATION_FAILED" if stage == "requirements_validation" else
                "GOVERNANCE_VALIDATION_FAILED" if stage == "governance_validation" else
                "REQUIREMENTS_AGENT_FAILED" if req_stage else "GOVERNANCE_AGENT_FAILED")
        message = ("Requirements analysis could not be validated." if stage == "requirements_validation" else
                   "Governance analysis could not be validated." if stage == "governance_validation" else
                   "Requirements analysis could not be completed." if req_stage else
                   "Governance analysis could not be completed.")
        logger.warning("Orchestration stage failed", extra={
            "orchestration_id": state.get("orchestration_id"), "project_id": state.get("project_id"),
            "node": stage, "agent": agent, "failure_type": type(exc).__name__,
            "retry_count": retry_count, "recoverable": transient,
            "latency_ms": round((perf_counter() - started) * 1000, 2) if started is not None else None,
            "success": False,
        })
        old_statuses = state.get("agent_statuses", {})
        # If the result failed schema validation, clear it so unsafe/untrusted data cannot reach governance or the client.
        return {
            "requirements_valid": False if req_stage else state.get("requirements_valid", False),
            "governance_valid": False if not req_stage else state.get("governance_valid", False),
            "requirements_result": None if req_stage else state.get("requirements_result"),
            "governance_result": None if not req_stage else state.get("governance_result"),
            "agent_statuses": {**old_statuses, agent: "failed"},
            "current_agent": "coordinator",
            "retry_count": retry_count,
            "errors": state.get("errors", []) + [{"code": code, "message": message, "recoverable": transient}],
        }

    def orchestrate(self, db: Session, project_id: str, top_k: int = 5) -> dict:
        if db.get(Project, project_id) is None:
            raise AppError("Project not found.", 404)
        project = db.get(Project, project_id)
        if project.interview is None or project.interview.status != "completed":
            raise AppError("Complete the adaptive requirements interview before running orchestration.", 409)
        orchestration_id = str(uuid4())
        run = analysis_runs.create(db, project_id)
        initial: RequirementsStudioState = {
            "orchestration_id": orchestration_id, "project_id": project_id,
            "analysis_run_id": run.id, "analysis_run_version": run.version,
            "status": "failed", "current_agent": "coordinator", "errors": [], "warnings": [],
            "agent_statuses": {"requirements": "skipped", "governance": "skipped"},
            "retry_count": 0, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Orchestration started", extra={"orchestration_id": orchestration_id, "project_id": project_id})
        try:
            state = self.build_graph(db, top_k).invoke(initial)
            response = OrchestrationResult(
                orchestration_id=orchestration_id, analysis_run_id=run.id,
                analysis_run_version=run.version, project_id=project_id,
                status=state.get("status", "failed"),
                requirements_analysis_id=state.get("requirements_analysis_id"),
                governance_analysis_id=state.get("governance_analysis_id"),
                agents=[{"name": name, "status": state.get("agent_statuses", {}).get(name, "skipped")}
                        for name in ("requirements", "governance")],
                requirements_analysis=state.get("requirements_result"),
                governance_analysis=state.get("governance_result"),
                warnings=state.get("warnings", []), errors=state.get("errors", []),
                created_at=state.get("created_at"),
            )
            analysis_runs.finish(db, run.id, response.status, response.warnings,
                                 [issue.model_dump(mode="json") for issue in response.errors],
                                 [agent.model_dump(mode="json") for agent in response.agents])
        except Exception:
            logger.exception("Unexpected orchestration failure", extra={
                "orchestration_id": orchestration_id, "analysis_run_id": run.id, "project_id": project_id,
            })
            safe_errors = [{"code": "ORCHESTRATION_FAILED", "message": "The analysis workflow could not be completed.", "recoverable": True}]
            analysis_runs.finish(db, run.id, "failed", [], safe_errors,
                                 [{"name": "requirements", "status": "failed"}, {"name": "governance", "status": "skipped"}])
            response = OrchestrationResult(
                orchestration_id=orchestration_id, analysis_run_id=run.id,
                analysis_run_version=run.version, project_id=project_id, status="failed",
                agents=[{"name": "requirements", "status": "failed"}, {"name": "governance", "status": "skipped"}],
                errors=safe_errors, created_at=datetime.now(timezone.utc),
            )
        logger.info("Orchestration finished", extra={
            "orchestration_id": orchestration_id, "project_id": project_id,
            "status": response.status, "retry_count": state.get("retry_count", 0),
        })
        return response.model_dump(mode="json")


orchestration_service = OrchestrationService()
