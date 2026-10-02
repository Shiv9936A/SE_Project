"""Direct LangGraph coordination tests plus endpoint precondition coverage."""
import json
from datetime import datetime, timezone

from app import models  # noqa: F401
from app.core.database import get_db
from app.core.config import settings
from app.models import GovernanceAnalysis, InterviewSession, Project, RequirementsAnalysis
from app.repositories import governance_analyses, requirements_analyses
from app.schemas.governance_analysis import GovernanceAnalysisRead, GovernanceAnalysisResult
from app.schemas.requirements_analysis import RequirementsAnalysisRead
from app.services.agents import governance_agent as governance_module
from app.services.agents import requirements_agent as requirements_module
from app.services.orchestration_service import orchestration_service


def _db_from_override():
    generator = get_db_override = __import__("app.main", fromlist=["app"]).app.dependency_overrides[get_db]()
    return next(generator), generator


def _seed_project(client, project_payload, *, completed=True):
    project = client.post("/api/projects", json=project_payload).json()
    db, generator = _db_from_override()
    row = db.get(Project, project["id"])
    row.interview = InterviewSession(
        project_id=row.id, project_idea="Build a project workflow.",
        business_objective="Help staff complete work.", users_roles="Staff and customers",
        detected_domain="Generic software system", asked_questions=[], answers=[{"answer": "Detailed workflow."}],
        covered_topics=["workflow"], uncovered_topics=[], current_question=None,
        question_number=1, maximum_questions=1, status="completed" if completed else "in_progress",
        completed_at=datetime.now(timezone.utc) if completed else None,
    )
    db.commit()
    db.close()
    generator.close()
    return project["id"]


def _valid_requirements(project_id, analysis_id="req-1"):
    return RequirementsAnalysisRead(
        analysis_id=analysis_id, project_id=project_id, version=1, status="needs_review",
        provider="mock", model="mock", created_at=datetime.now(timezone.utc),
        summary="Validated requirements draft.", requirements=[], ambiguities=[], conflicts=[],
        completeness=[], clarification_questions=[], quality_assessment={}, evidence_sources=[],
    ).model_dump(mode="json")


def _valid_governance(project_id, req_id="req-1", analysis_id="gov-1"):
    result = GovernanceAnalysisResult(
        project_id=project_id, requirements_analysis_id=req_id,
        methodology={"name": "Incremental", "confidence": 0.8,
                     "reasoning": [{"factor": "delivery", "observation": "Phased delivery fits.",
                                    "impact": "Supports staged release.", "source_references": ["project:description"]}]},
        project_assessment={"complexity": "medium", "risk_level": "medium",
                            "requirements_stability": "moderate", "integration_complexity": "unknown",
                            "security_sensitivity": "unknown", "compliance_impact": "unknown"},
        development_lifecycle=[{"phase": "Requirements", "activities": [], "deliverables": [], "exit_criteria": []}],
        testing_strategy={},
    )
    return GovernanceAnalysisRead(
        id=analysis_id, project_id=project_id, requirements_analysis_id=req_id, version=1,
        status="needs_review", provider="mock", model="mock", created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc), result=result,
    ).model_dump(mode="json")


def _insert_existing(db, project_id):
    req_data = _valid_requirements(project_id)
    req = RequirementsAnalysis(
        id=req_data["analysis_id"], project_id=project_id, version=1, status="needs_review",
        provider="mock", model="mock", result_json={key: req_data[key] for key in (
            "summary", "requirements", "ambiguities", "conflicts", "completeness",
            "clarification_questions", "quality_assessment", "evidence_sources",
        )},
    )
    db.add(req)
    gov_data = _valid_governance(project_id, req.id)
    db.add(GovernanceAnalysis(
        id=gov_data["id"], project_id=project_id, requirements_analysis_id=req.id,
        version=1, methodology="Incremental", status="needs_review", provider="mock", model="mock",
        result_json=gov_data["result"],
    ))
    db.commit()
    return req_data, gov_data


def test_graph_reuses_valid_results_without_duplicate_rows(client, project_payload, monkeypatch):
    project_id = _seed_project(client, project_payload)
    db, generator = _db_from_override()
    req_data, gov_data = _insert_existing(db, project_id)
    monkeypatch.setattr(requirements_module.requirements_analysis_agent, "analyze", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must reuse")))
    monkeypatch.setattr(governance_module.governance_agent, "analyze", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must reuse")))

    state = orchestration_service.build_graph(db).invoke({
        "orchestration_id": "orch-test", "project_id": project_id, "retry_count": 0,
        "agent_statuses": {"requirements": "skipped", "governance": "skipped"},
        "errors": [], "warnings": [],
    })
    assert state["status"] == "completed"
    assert state["requirements_analysis_id"] == req_data["analysis_id"]
    assert state["governance_analysis_id"] == gov_data["id"]
    assert state["requirements_reused"] and state["governance_reused"]
    assert state["project_context"]["project_name"] == project_payload["project_name"]
    assert state["interview_context"]["status"] == "completed"
    json.dumps(state)
    assert db.query(RequirementsAnalysis).filter_by(project_id=project_id).count() == 1
    assert db.query(GovernanceAnalysis).filter_by(project_id=project_id).count() == 1
    db.close()
    generator.close()


def test_requirements_failure_routes_around_governance(client, project_payload, monkeypatch):
    project_id = _seed_project(client, project_payload)
    db, generator = _db_from_override()
    called = []
    monkeypatch.setattr(requirements_module.requirements_analysis_agent, "analyze", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("private detail")))
    monkeypatch.setattr(governance_module.governance_agent, "analyze", lambda *_a, **_k: called.append(True))
    state = orchestration_service.build_graph(db).invoke({
        "orchestration_id": "orch-fail", "project_id": project_id, "retry_count": 0,
        "agent_statuses": {"requirements": "skipped", "governance": "skipped"}, "errors": [], "warnings": [],
    })
    assert state["status"] == "failed"
    assert not called
    assert state["governance_result"] is None
    assert state["errors"][0]["code"] == "REQUIREMENTS_AGENT_FAILED"
    assert "private detail" not in str(state["errors"])
    db.close()
    generator.close()


def test_transient_agent_failure_retries_once_then_completes(client, project_payload, monkeypatch):
    project_id = _seed_project(client, project_payload)
    db, generator = _db_from_override()
    attempts = []
    req_result, gov_result = _valid_requirements(project_id), _valid_governance(project_id)

    def requirements(*_args, **_kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise TimeoutError("private provider text")
        return req_result

    monkeypatch.setattr(requirements_module.requirements_analysis_agent, "analyze", requirements)
    monkeypatch.setattr(governance_module.governance_agent, "analyze", lambda *_a, **_k: gov_result)
    state = orchestration_service.build_graph(db).invoke({
        "orchestration_id": "orch-retry", "project_id": project_id, "retry_count": 0,
        "agent_statuses": {"requirements": "skipped", "governance": "skipped"}, "errors": [], "warnings": [],
    })
    assert len(attempts) == 2
    assert state["status"] == "completed"
    assert state["retry_count"] == 1
    assert state["governance_result"]["requirements_analysis_id"] == state["requirements_analysis_id"]
    db.close()
    generator.close()


def test_retry_limit_is_bounded_and_error_is_safe(client, project_payload, monkeypatch):
    project_id = _seed_project(client, project_payload)
    db, generator = _db_from_override()
    monkeypatch.setattr(settings, "orchestration_max_retries", 1)
    attempts = []

    def unavailable(*_args, **_kwargs):
        attempts.append(1)
        raise TimeoutError("provider secret or prompt must not escape")

    monkeypatch.setattr(requirements_module.requirements_analysis_agent, "analyze", unavailable)
    state = orchestration_service.build_graph(db).invoke({
        "orchestration_id": "orch-limit", "project_id": project_id, "retry_count": 0,
        "agent_statuses": {"requirements": "skipped", "governance": "skipped"}, "errors": [], "warnings": [],
    })
    assert len(attempts) == 2
    assert state["retry_count"] == 1
    assert state["status"] == "failed"
    assert state["errors"][0]["recoverable"] is True
    assert "provider secret" not in str(state["errors"])
    db.close()
    generator.close()


def test_governance_exception_returns_partial_without_losing_requirements(client, project_payload, monkeypatch):
    project_id = _seed_project(client, project_payload)
    db, generator = _db_from_override()
    req_data = _valid_requirements(project_id)
    monkeypatch.setattr(requirements_module.requirements_analysis_agent, "analyze", lambda *_a, **_k: req_data)
    monkeypatch.setattr(governance_module.governance_agent, "analyze", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("private provider details")))
    state = orchestration_service.build_graph(db).invoke({
        "orchestration_id": "orch-gov-fail", "project_id": project_id, "retry_count": 0,
        "agent_statuses": {"requirements": "skipped", "governance": "skipped"}, "errors": [], "warnings": [],
    })
    assert state["status"] == "partial"
    assert state["requirements_result"]["analysis_id"] == "req-1"
    assert state["governance_result"] is None
    assert state["errors"][0]["code"] == "GOVERNANCE_AGENT_FAILED"
    assert "private provider details" not in str(state["errors"])
    db.close()
    generator.close()


def test_governance_validation_failure_cannot_return_unvalidated_result(client, project_payload, monkeypatch):
    project_id = _seed_project(client, project_payload)
    db, generator = _db_from_override()
    monkeypatch.setattr(requirements_module.requirements_analysis_agent, "analyze", lambda *_a, **_k: _valid_requirements(project_id))
    monkeypatch.setattr(governance_module.governance_agent, "analyze", lambda *_a, **_k: {"id": "invalid", "requirements_analysis_id": "wrong"})
    state = orchestration_service.build_graph(db).invoke({
        "orchestration_id": "orch-gov-invalid", "project_id": project_id, "retry_count": 0,
        "agent_statuses": {"requirements": "skipped", "governance": "skipped"}, "errors": [], "warnings": [],
    })
    assert state["status"] == "partial"
    assert state["governance_result"] is None
    assert state["errors"][0]["code"] == "GOVERNANCE_VALIDATION_FAILED"
    db.close()
    generator.close()


def test_schema_failure_skips_governance_with_safe_structured_error(client, project_payload, monkeypatch):
    project_id = _seed_project(client, project_payload)
    db, generator = _db_from_override()
    called = []
    monkeypatch.setattr(requirements_module.requirements_analysis_agent, "analyze", lambda *_a, **_k: {"analysis_id": "bad"})
    monkeypatch.setattr(governance_module.governance_agent, "analyze", lambda *_a, **_k: called.append(True))
    state = orchestration_service.build_graph(db).invoke({
        "orchestration_id": "orch-invalid", "project_id": project_id, "retry_count": 0,
        "agent_statuses": {"requirements": "skipped", "governance": "skipped"}, "errors": [], "warnings": [],
    })
    assert state["status"] == "failed"
    assert not called
    assert state["errors"][0]["code"] == "REQUIREMENTS_VALIDATION_FAILED"
    assert state["requirements_result"] is None
    db.close()
    generator.close()


def test_api_rejects_missing_project_or_unfinished_interview(client, project_payload):
    assert client.post("/api/projects/missing/orchestrate").status_code == 404
    project_id = _seed_project(client, project_payload, completed=False)
    response = client.post(f"/api/projects/{project_id}/orchestrate")
    assert response.status_code == 409
    assert "Complete the adaptive requirements interview" in response.json()["detail"]


def test_orchestration_api_returns_combined_result_and_is_registered(client, project_payload):
    project_id = _seed_project(client, project_payload)
    db, generator = _db_from_override()
    _insert_existing(db, project_id)
    db.close()
    generator.close()
    response = client.post(f"/api/projects/{project_id}/orchestrate")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["requirements_analysis_id"] == body["requirements_analysis"]["analysis_id"]
    assert body["governance_analysis_id"] == body["governance_analysis"]["id"]
    assert body["governance_analysis"]["requirements_analysis_id"] == body["requirements_analysis_id"]
    assert body["analysis_run_version"] == 1
    assert body["analysis_run_id"]
    history = client.get(f"/api/projects/{project_id}/analysis-runs").json()
    assert history[0]["id"] == body["analysis_run_id"]
    assert history[0]["requirements_analysis_id"] == body["requirements_analysis_id"]
    assert history[0]["governance_analysis_id"] == body["governance_analysis_id"]
    assert client.get(f"/api/projects/{project_id}/analysis-runs/{body['analysis_run_id']}").json()["version"] == 1
    assert client.post("/openapi.json").status_code == 405
    assert "/api/projects/{project_id}/orchestrate" in client.get("/openapi.json").json()["paths"]


def test_service_fallbacks_are_visible_as_partial_orchestration(client, project_payload, monkeypatch):
    project_id = _seed_project(client, project_payload)

    class BrokenLLM:
        def generate(self, *_args, **_kwargs):
            raise TimeoutError("provider details must remain private")

    monkeypatch.setattr(requirements_module.requirements_analysis_agent, "llm", BrokenLLM())
    monkeypatch.setattr(governance_module.governance_agent, "llm", BrokenLLM())
    response = client.post(f"/api/projects/{project_id}/orchestrate")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "partial"
    assert body["requirements_analysis"]["status"] == "partial"
    assert body["governance_analysis"]["status"] == "partial"
    assert body["governance_analysis"]["requirements_analysis_id"] == body["requirements_analysis_id"]
    assert "provider details" not in response.text
    assert len(body["warnings"]) == 2


def test_repeated_orchestration_creates_immutable_versioned_agent_outputs(client, project_payload, monkeypatch):
    project_id = _seed_project(client, project_payload)

    def save_requirements(db, target_project_id, **_kwargs):
        version = requirements_analyses.next_version(db, target_project_id)
        payload = _valid_requirements(target_project_id, f"req-v{version}")
        db.add(RequirementsAnalysis(
            id=payload["analysis_id"], project_id=target_project_id, version=version,
            status="needs_review", provider="test", model="test",
            result_json={key: payload[key] for key in ("summary", "requirements", "ambiguities", "conflicts", "completeness", "clarification_questions", "quality_assessment", "evidence_sources")},
        ))
        db.commit()
        return payload

    def save_governance(db, target_project_id, **_kwargs):
        req = requirements_analyses.latest(db, target_project_id)
        version = governance_analyses.next_version(db, target_project_id)
        payload = _valid_governance(target_project_id, req.id, f"gov-v{version}")
        db.add(GovernanceAnalysis(
            id=payload["id"], project_id=target_project_id, requirements_analysis_id=req.id,
            version=version, methodology=payload["result"]["methodology"]["name"], status="needs_review",
            provider="test", model="test", result_json=payload["result"],
        ))
        db.commit()
        return payload

    monkeypatch.setattr(requirements_module.requirements_analysis_agent, "analyze", save_requirements)
    monkeypatch.setattr(governance_module.governance_agent, "analyze", save_governance)
    first = client.post(f"/api/projects/{project_id}/orchestrate").json()
    second = client.post(f"/api/projects/{project_id}/orchestrate").json()
    assert (first["analysis_run_version"], second["analysis_run_version"]) == (1, 2)
    assert first["analysis_run_id"] != second["analysis_run_id"]
    assert first["requirements_analysis_id"] != second["requirements_analysis_id"]
    assert first["governance_analysis_id"] != second["governance_analysis_id"]
    history = client.get(f"/api/projects/{project_id}/analysis-runs").json()
    assert [entry["version"] for entry in history] == [2, 1]
    assert history[1]["requirements_analysis_id"] == first["requirements_analysis_id"]
    first_detail = client.get(f"/api/projects/{project_id}/analysis-runs/{first['analysis_run_id']}").json()
    second_detail = client.get(f"/api/projects/{project_id}/analysis-runs/{second['analysis_run_id']}").json()
    assert first_detail["requirements_analysis"]["analysis_id"] == "req-v1"
    assert second_detail["requirements_analysis"]["analysis_id"] == "req-v2"
    assert first_detail["governance_analysis"]["result"]["requirements_analysis_id"] == "req-v1"
