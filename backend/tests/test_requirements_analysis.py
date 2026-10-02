"""Requirements analysis API, persistence, evidence validation, and fallback tests."""
import json

from app.services.agents import requirements_agent as agent_module


def create_project(client, payload, questionnaire_payload=None):
    created = client.post("/api/projects", json=payload)
    assert created.status_code == 201, created.text
    project = created.json()
    if questionnaire_payload:
        saved = client.post(f"/api/projects/{project['id']}/questionnaire", json=questionnaire_payload)
        assert saved.status_code == 200, saved.text
    return project


class LLM:
    def __init__(self, response):
        self.response = response

    def generate(self, _system, _user):
        return self.response


class SourceDrivenLLM:
    def generate(self, _system, user):
        payload = json.loads(user)
        source = next(row for row in payload["evidence_sources"] if row["source_reference"] == "project:description")
        excerpt = source["evidence"][:100]
        result = {
            "summary": "The draft captures the stated project context and requires stakeholder review.",
            "requirements": [{
                "requirement_id": "ignored-by-server", "category": "functional", "title": "Project objective",
                "description": "The system shall support the stated project objective.", "priority": "medium",
                "confidence": 0.8, "source_type": "project_profile", "source_reference": "project:description",
                "evidence": excerpt, "acceptance_criteria": [], "ambiguities": [], "dependencies": [],
                "tags": [], "testability": "low", "missing_information": [],
            }],
            "ambiguities": [], "conflicts": [], "completeness": [], "clarification_questions": [],
            "quality_assessment": {}, "evidence_sources": [],
        }
        return json.dumps(result)


def test_analysis_generates_ids_persists_and_is_never_auto_approved(client, project_payload, questionnaire_payload, monkeypatch):
    project = create_project(client, project_payload, questionnaire_payload)
    monkeypatch.setattr(agent_module.requirements_analysis_agent, "llm", SourceDrivenLLM())

    response = client.post(f"/api/projects/{project['id']}/analyze-requirements", json={})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "needs_review"
    assert result["requirements"][0]["requirement_id"] == "REQ-F-001"
    assert result["requirements"][0]["source_reference"] == "project:description"
    assert result["quality_assessment"]
    assert client.get(f"/api/projects/{project['id']}/requirements-analysis").json() == result
    second = client.post(f"/api/projects/{project['id']}/analyze-requirements", json={})
    assert second.status_code == 200
    assert second.json()["version"] == 2


def test_analysis_falls_back_on_llm_failure_and_safely_handles_empty_interview(client, project_payload, questionnaire_payload, monkeypatch):
    project = create_project(client, project_payload, questionnaire_payload)
    monkeypatch.setattr(agent_module.requirements_analysis_agent, "llm", LLM(RuntimeError("provider unavailable")))

    response = client.post(f"/api/projects/{project['id']}/analyze-requirements", json={})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "partial"
    assert all(req["requirement_id"].startswith("REQ-") for req in result["requirements"])
    assert all(req["source_type"] != "inferred" or not req["evidence"] for req in result["requirements"])
    assert result["quality_assessment"]["completeness"] in {"low", "medium"}


def test_analysis_rejects_hallucinated_source_and_uses_fallback(client, project_payload, monkeypatch):
    project = create_project(client, project_payload)
    invalid = {
        "summary": "This is a plausible summary.",
        "requirements": [{"requirement_id": "REQ-F-001", "category": "functional", "title": "Need",
            "description": "The system shall do something.", "priority": "medium", "confidence": 0.7,
            "source_type": "project_profile", "source_reference": "made-up-source", "evidence": "Invented quote",
            "acceptance_criteria": [], "ambiguities": [], "dependencies": [], "tags": [],
            "testability": "low", "missing_information": []}],
        "ambiguities": [], "conflicts": [], "completeness": [], "clarification_questions": [],
        "quality_assessment": {}, "evidence_sources": [],
    }
    monkeypatch.setattr(agent_module.requirements_analysis_agent, "llm", LLM(json.dumps(invalid)))

    response = client.post(f"/api/projects/{project['id']}/analyze-requirements", json={})
    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert "deterministic draft" in response.json()["summary"]


def test_analysis_rejects_unsupported_categories_and_bad_request_size(client, project_payload, monkeypatch):
    project = create_project(client, project_payload)
    monkeypatch.setattr(agent_module.requirements_analysis_agent, "llm", LLM('{"summary":"x","requirements":[{"category":"DevOps"}]}'))
    assert client.post(f"/api/projects/{project['id']}/analyze-requirements", json={}).json()["status"] == "partial"
    assert client.post(f"/api/projects/{project['id']}/analyze-requirements", json={"top_k": 99}).status_code == 422


def test_latest_analysis_returns_not_found_before_first_run(client, project_payload):
    project = create_project(client, project_payload)
    response = client.get(f"/api/projects/{project['id']}/requirements-analysis")
    assert response.status_code == 404


def test_unknown_project_is_not_found(client):
    assert client.post("/api/projects/missing/analyze-requirements", json={}).status_code == 404


def test_requirements_analysis_endpoints_are_in_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/projects/{project_id}/analyze-requirements" in paths
    assert "/api/projects/{project_id}/requirements-analysis" in paths


def test_deterministic_ambiguity_and_completeness_checks():
    from app.schemas.requirements_analysis import RequirementsAnalysisResult, RequirementItem

    result = RequirementsAnalysisResult(summary="Draft", requirements=[RequirementItem(
        requirement_id="REQ-F-001", category="functional", title="Fast response",
        description="The system shall respond quickly and be user-friendly.", priority="medium",
        confidence=0.7, source_type="inferred", source_reference=None, evidence="",
        acceptance_criteria=[], ambiguities=[], dependencies=[], tags=[], testability="low",
        missing_information=[],
    )])
    ambiguities = agent_module.requirements_analysis_agent._augment_ambiguities(result)
    assert len(ambiguities) >= 2
    assert result.clarification_questions
    coverage = agent_module.requirements_analysis_agent._coverage({})
    assert all(row.status == "missing" for row in coverage)
    assert agent_module.requirements_analysis_agent._quality(result)["testability"] == "low"


def test_citation_must_quote_real_source():
    from app.schemas.requirements_analysis import RequirementsAnalysisResult, RequirementItem

    result = RequirementsAnalysisResult(summary="Draft", requirements=[RequirementItem(
        requirement_id="REQ-F-001", category="functional", title="Need", description="The system shall help.",
        priority="medium", confidence=0.8, source_type="project_profile", source_reference="project:description",
        evidence="invented evidence", acceptance_criteria=[], ambiguities=[], dependencies=[], tags=[],
        testability="low", missing_information=[],
    )])
    try:
        agent_module.requirements_analysis_agent._validate_sources(
            result, {"project:description": {"source_type": "project_profile", "text": "Source text."}},
        )
    except ValueError as exc:
        assert "not present" in str(exc)
    else:
        raise AssertionError("Unsupported evidence citation should be rejected")


def test_conflicts_require_two_distinct_real_sources():
    from app.schemas.requirements_analysis import ConflictItem, EvidenceCitation, RequirementsAnalysisResult

    result = RequirementsAnalysisResult(summary="Draft", conflicts=[ConflictItem(
        description="The evidence differs.", severity="medium", clarification_question="Which value is correct?",
        sources=[
            EvidenceCitation(source_type="questionnaire", source_reference="questionnaire:risk_level", evidence="High"),
            EvidenceCitation(source_type="questionnaire", source_reference="questionnaire:risk_level", evidence="High"),
        ],
    )])
    try:
        agent_module.requirements_analysis_agent._validate_sources(result, {
            "questionnaire:risk_level": {"source_type": "questionnaire", "text": "High"},
        })
    except ValueError as exc:
        assert "distinct sources" in str(exc)
    else:
        raise AssertionError("Repeated citation must not be reported as a conflict")


def test_server_generates_stable_category_ids():
    rows = agent_module.requirements_analysis_agent._assign_ids([
        {"category": "functional", "requirement_id": "model-id"},
        {"category": "functional", "requirement_id": "duplicate-model-id"},
        {"category": "security_privacy_compliance", "requirement_id": "other-model-id"},
    ])
    assert [row["requirement_id"] for row in rows] == ["REQ-F-001", "REQ-F-002", "REQ-SEC-001"]
