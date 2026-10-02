"""Governance agent schema, grounding, fallback, and persistence coverage."""
import json

import pytest

from app.core.exceptions import AppError
from app.services.agents import governance_agent as governance_module
from app.services.agents import requirements_agent as requirements_module
from app.services.sdlc_recommendation_service import score_sdlc_models


class RequirementsLLM:
    def __init__(self, *, empty=False, ambiguity=False, conflict=False, security=False):
        self.empty, self.ambiguity, self.conflict, self.security = empty, ambiguity, conflict, security

    def generate(self, _system, user):
        payload = json.loads(user)
        sources = {row["source_reference"]: row for row in payload["evidence_sources"]}
        requirements = []
        if not self.empty:
            ref, category = ("questionnaire:security_criticality", "security_privacy_compliance") if self.security else ("project:description", "functional")
            requirements.append({
                "requirement_id": "discard-this-id", "category": category,
                "title": "Stated project need", "description": "A user-facing project need is stated.",
                "priority": "medium", "confidence": 0.8,
                "source_type": sources[ref]["source_type"], "source_reference": ref,
                "evidence": sources[ref]["evidence"][:100], "acceptance_criteria": [],
                "ambiguities": [], "dependencies": [], "tags": [], "testability": "low",
                "missing_information": [],
            })
        ambiguities = []
        if self.ambiguity and requirements:
            ambiguities.append({"description": "Scope boundary remains unclear.",
                "related_requirement_id": "REQ-F-001", "severity": "critical",
                "clarification_question": "Which user workflows are in scope?",
                "source_reference": "questionnaire:risk_level"})
        conflicts = []
        if self.conflict:
            conflicts.append({"description": "The questionnaire and stakeholder note state different risk levels.",
                "severity": "high", "clarification_question": "Which risk level is correct?",
                "sources": [
                    {"source_type": "questionnaire", "source_reference": "questionnaire:risk_level", "evidence": "High"},
                    {"source_type": "questionnaire", "source_reference": "questionnaire:stakeholder_notes", "evidence": "risk is low"},
                ]})
        return json.dumps({"summary": "Draft from project evidence.", "requirements": requirements,
            "ambiguities": ambiguities, "conflicts": conflicts, "completeness": [],
            "clarification_questions": [], "quality_assessment": {}, "evidence_sources": []})


class GovernanceLLM:
    def __init__(self, methodology="Agile", mode="valid"):
        self.methodology, self.mode = methodology, mode

    def generate(self, _system, user):
        if self.mode == "timeout":
            raise TimeoutError("private provider detail")
        if self.mode == "quota":
            raise AppError("provider rate limited", 429)
        if self.mode == "unavailable":
            raise AppError("language model unavailable", 502)
        payload = json.loads(user)
        if self.mode == "invalid_json":
            return "not json"
        requirements = payload["requirements_analysis"]["requirements"]
        q = payload["questionnaire"]
        req_ids = [row["requirement_id"] for row in requirements]
        security_ids = [row["requirement_id"] for row in requirements if row["category"] == "security_privacy_compliance"]
        integration_ids = [row["requirement_id"] for row in requirements if row["category"] == "integration"]
        if q:
            reason_ref = "questionnaire:requirement_stability"
            reason_text = q["requirement_stability"]
        elif req_ids:
            reason_ref = req_ids[0]
            reason_text = requirements[0]["title"]
        else:
            missing = next((row for row in payload["requirements_analysis"]["completeness"]
                            if row["status"] != "covered"), None)
            reason_ref = f"analysis:missing:{missing['area']}" if missing else payload["allowed_evidence_reference_ids"][0]
            reason_text = f"{missing['area']}: {missing['note']}" if missing else payload["allowed_evidence_reference_ids"][0]
        phase_names = ["Requirements", "Architecture & Design", "Implementation", "Testing", "Deployment"]
        output = {
            "project_id": "llm-cannot-override-this", "requirements_analysis_id": "llm-cannot-override-this",
            "methodology": {"name": self.methodology, "confidence": 0.8,
                "reasoning": [{"factor": "requirement_change", "observation": "Saved stability response is used.",
                    "impact": "Select a lifecycle that can accommodate the observed change profile.",
                    "source_references": [reason_ref]}]},
            "project_assessment": {"complexity": "high", "risk_level": "high",
                "requirements_stability": "moderate", "integration_complexity": "unknown",
                "security_sensitivity": "high", "compliance_impact": "high"},
            "baseline_scores": [{"model": row["model"], "score": row["score"]} for row in payload["deterministic_sdlc_baseline"]],
            "development_lifecycle": [{"phase": name, "activities": ["Review the project evidence."],
                "deliverables": ["Reviewed project artifact"], "exit_criteria": ["Review is recorded."],
                "requirement_references": req_ids} for name in phase_names],
            "testing_strategy": {key: ([{"recommendation": f"Verify applicable {key.replace('_', ' ')} evidence.",
                "requirement_references": req_ids}] if req_ids else []) for key in (
                    "unit_testing", "integration_testing", "system_testing", "acceptance_testing",
                    "security_testing", "performance_testing")},
            "security_governance": ([{"activity": "Review the explicit security requirement.",
                "requirement_references": security_ids}] if security_ids else []),
            "documentation_requirements": [{"document": "SRS", "rationale": "Preserve the reviewed requirement baseline.",
                "requirement_references": req_ids}],
            "governance_checkpoints": [{"checkpoint": "Requirements review", "purpose": "Review scope and open items.",
                "entry_conditions": ["Draft is available."], "exit_conditions": ["Decisions are recorded."],
                "required_artifacts": ["Requirements Analysis"]}],
            "risks": [{"risk_id": "RISK-999", "title": "Potential delivery risk",
                "description": "Potential risk from the project risk response.", "severity": "medium",
                "likelihood": "medium", "mitigation": "Review and assign an owner.",
                "source_references": [reason_ref], "basis": "potential"}] if q else [],
            "quality_gates": [{"gate": "Requirements gate", "checks": ["Traceability is reviewed."],
                "requirement_references": req_ids}],
            "prerequisites": ["Resolve critical open questions."], "evidence": [],
            "unresolved_questions": payload["requirements_analysis"]["clarification_questions"],
            "fallback_reason": None,
        }
        if self.mode == "invalid_methodology":
            output["methodology"]["name"] = "RandomModel"
        if self.mode == "invalid_assessment":
            output["project_assessment"]["complexity"] = "extreme"
        if self.mode == "invalid_reference":
            output["methodology"]["reasoning"][0]["source_references"] = ["REQ-FAKE-001"]
        if self.mode == "invalid_requirement_reference":
            output["development_lifecycle"][0]["requirement_references"] = ["REQ-FAKE-001"]
        output["evidence"] = [{"source_type": "questionnaire", "source_reference": reason_ref,
                               "observation": reason_text}]
        return json.dumps(output)


def create_project(client, project_payload, questionnaire_payload=None):
    response = client.post("/api/projects", json=project_payload)
    assert response.status_code == 201, response.text
    project = response.json()
    if questionnaire_payload is not None:
        saved = client.post(f"/api/projects/{project['id']}/questionnaire", json=questionnaire_payload)
        assert saved.status_code == 200, saved.text
    return project


def create_requirements(client, project_id, monkeypatch, *, empty=False, ambiguity=False, conflict=False, security=False):
    monkeypatch.setattr(requirements_module.requirements_analysis_agent, "llm",
                        RequirementsLLM(empty=empty, ambiguity=ambiguity, conflict=conflict, security=security))
    response = client.post(f"/api/projects/{project_id}/analyze-requirements", json={})
    assert response.status_code == 200, response.text
    return response.json()


def generate(client, project_id, monkeypatch, llm=None):
    monkeypatch.setattr(governance_module.governance_agent, "llm", llm or GovernanceLLM())
    return client.post(f"/api/projects/{project_id}/governance-analysis")


def test_valid_requirements_analysis_produces_persisted_governance_result(client, project_payload, questionnaire_payload, monkeypatch):
    project = create_project(client, project_payload, questionnaire_payload)
    ra = create_requirements(client, project["id"], monkeypatch)
    response = generate(client, project["id"], monkeypatch)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "needs_review"
    assert result["requirements_analysis_id"] == ra["analysis_id"]
    assert result["result"]["project_id"] == project["id"]
    assert result["result"]["methodology"]["name"] == "Agile"
    assert result["result"]["baseline_scores"]
    assert client.get(f"/api/projects/{project['id']}/governance-analysis").json() == result


@pytest.mark.parametrize("methodology", ["Agile", "Waterfall", "Iterative", "Spiral", "Hybrid"])
def test_supported_methodologies_are_returned(client, project_payload, questionnaire_payload, monkeypatch, methodology):
    project = create_project(client, project_payload, questionnaire_payload)
    create_requirements(client, project["id"], monkeypatch)
    response = generate(client, project["id"], monkeypatch, GovernanceLLM(methodology=methodology))
    assert response.status_code == 200
    assert response.json()["result"]["methodology"]["name"] == methodology


@pytest.mark.parametrize("mode,reason", [
    ("invalid_methodology", "invalid_output"),
    ("invalid_assessment", "invalid_output"),
    ("invalid_reference", "invalid_output"),
    ("invalid_requirement_reference", "invalid_output"),
    ("invalid_json", "invalid_output"),
    ("timeout", "timeout"),
    ("unavailable", "provider_unavailable"),
    ("quota", "rate_limited"),
])
def test_bad_or_unavailable_gemini_uses_deterministic_fallback(client, project_payload, questionnaire_payload, monkeypatch, mode, reason):
    project = create_project(client, project_payload, questionnaire_payload)
    create_requirements(client, project["id"], monkeypatch)
    response = generate(client, project["id"], monkeypatch, GovernanceLLM(mode=mode))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "partial"
    assert result["result"]["fallback_reason"] == reason
    expected = score_sdlc_models(questionnaire_payload)[0]["model"]
    assert result["result"]["methodology"]["name"] == expected
    assert "private provider detail" not in response.text


def test_project_assessment_is_derived_from_questionnaire_not_llm(client, project_payload, questionnaire_payload, monkeypatch):
    project = create_project(client, project_payload, questionnaire_payload)
    create_requirements(client, project["id"], monkeypatch)
    result = generate(client, project["id"], monkeypatch).json()["result"]
    assert result["project_assessment"] == {
        "complexity": "high", "risk_level": "high", "requirements_stability": "moderate",
        "integration_complexity": "high", "security_sensitivity": "high", "compliance_impact": "high",
    }


def test_governance_traceability_testing_security_docs_gates_and_checkpoints(client, project_payload, questionnaire_payload, monkeypatch):
    project = create_project(client, project_payload, questionnaire_payload)
    ra = create_requirements(client, project["id"], monkeypatch, security=True)
    result = generate(client, project["id"], monkeypatch).json()["result"]
    req_ids = {row["requirement_id"] for row in ra["requirements"]}
    assert result["development_lifecycle"]
    assert all(ref.startswith("REQ-") for phase in result["development_lifecycle"] for ref in phase["requirement_references"])
    assert result["testing_strategy"]["security_testing"]
    assert result["security_governance"]
    assert result["documentation_requirements"]
    assert result["quality_gates"]
    assert result["governance_checkpoints"]
    assert result["methodology"]["reasoning"][0]["source_references"] == ["questionnaire:requirement_stability"]
    assert req_ids and result["security_governance"][0]["requirement_references"] == list(req_ids)


def test_critical_ambiguity_becomes_risk_and_prerequisite(client, project_payload, questionnaire_payload, monkeypatch):
    project = create_project(client, project_payload, questionnaire_payload)
    ra = create_requirements(client, project["id"], monkeypatch, ambiguity=True)
    response = generate(client, project["id"], monkeypatch, GovernanceLLM(mode="unavailable"))
    result = response.json()["result"]
    assert ra["ambiguities"][0]["severity"] == "critical"
    assert any(risk["title"] == "Unresolved requirement ambiguity" for risk in result["risks"])
    assert any("Which user workflows" in item for item in result["prerequisites"])


def test_conflicts_are_carried_into_fallback_risks(client, project_payload, questionnaire_payload, monkeypatch):
    project = create_project(client, project_payload, {**questionnaire_payload, "stakeholder_notes": "risk is low"})
    ra = create_requirements(client, project["id"], monkeypatch, conflict=True)
    response = generate(client, project["id"], monkeypatch, GovernanceLLM(mode="unavailable"))
    assert ra["conflicts"]
    assert any(risk["title"] == "Conflicting project evidence" for risk in response.json()["result"]["risks"])


def test_empty_requirements_are_handled_without_fabrication(client, project_payload, monkeypatch):
    project = create_project(client, project_payload)
    ra = create_requirements(client, project["id"], monkeypatch, empty=True)
    assert ra["requirements"] == []
    response = generate(client, project["id"], monkeypatch, GovernanceLLM(mode="unavailable"))
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["development_lifecycle"]
    assert all(not phase["requirement_references"] for phase in result["development_lifecycle"])
    assert result["project_assessment"]["complexity"] == "unknown"


def test_partial_requirements_analysis_keeps_governance_marked_partial(client, project_payload, questionnaire_payload, monkeypatch):
    project = create_project(client, project_payload, questionnaire_payload)
    monkeypatch.setattr(requirements_module.requirements_analysis_agent, "llm", type("Offline", (), {
        "generate": lambda *_: (_ for _ in ()).throw(RuntimeError("offline"))
    })())
    ra = client.post(f"/api/projects/{project['id']}/analyze-requirements", json={}).json()
    assert ra["status"] == "partial"
    response = generate(client, project["id"], monkeypatch)
    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert response.json()["result"]["fallback_reason"] == "requirements_analysis_partial"


def test_missing_phase11_analysis_returns_clear_conflict(client, project_payload):
    project = create_project(client, project_payload)
    response = client.post(f"/api/projects/{project['id']}/governance-analysis")
    assert response.status_code == 409
    assert "Phase 11" in response.json()["detail"]


def test_get_without_prior_governance_and_unknown_project(client, project_payload):
    project = create_project(client, project_payload)
    assert client.get(f"/api/projects/{project['id']}/governance-analysis").status_code == 404
    assert client.get("/api/projects/missing/governance-analysis").status_code == 404


def test_governance_results_are_versioned_and_openapi_registered(client, project_payload, questionnaire_payload, monkeypatch):
    project = create_project(client, project_payload, questionnaire_payload)
    create_requirements(client, project["id"], monkeypatch)
    first = generate(client, project["id"], monkeypatch).json()
    second = generate(client, project["id"], monkeypatch).json()
    assert second["version"] == first["version"] + 1
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/projects/{project_id}/governance-analysis" in paths


def test_fallback_preserves_existing_deterministic_recommendation(client, project_payload, questionnaire_payload, monkeypatch):
    project = create_project(client, project_payload, questionnaire_payload)
    create_requirements(client, project["id"], monkeypatch)
    result = generate(client, project["id"], monkeypatch, GovernanceLLM(mode="unavailable")).json()["result"]
    expected = score_sdlc_models(questionnaire_payload)
    assert result["baseline_scores"] == expected
    assert result["methodology"]["name"] == expected[0]["model"]
    assert len(result["baseline_scores"]) == 7
