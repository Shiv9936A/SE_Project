"""Offline end-to-end regression through project, interview, files, RAG, agents, and history."""
from pathlib import Path

from langchain_core.embeddings import Embeddings

from app.services import rag_service
from app.services.agents import governance_agent, requirements_agent
from app.services.embedding_service import embedding_service
from app.services.interview import interview_service
from app.services.retrieval_service import retrieval_service
from app.services.vector_store_service import ChromaVectorStore


class ScenarioEmbeddings(Embeddings):
    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        return [float("loan" in lowered), float("concurrent" in lowered), float("eligibility" in lowered)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def test_digital_loan_project_complete_offline_workflow(client, project_payload, monkeypatch, tmp_path: Path):
    embeddings = ScenarioEmbeddings()
    vector_store = ChromaVectorStore(tmp_path / "system-e2e-chroma")
    monkeypatch.setattr(embedding_service, "embeddings", embeddings)
    monkeypatch.setattr(embedding_service, "vector_store", vector_store)
    monkeypatch.setattr(retrieval_service, "embeddings", embeddings)
    monkeypatch.setattr(retrieval_service, "vector_store", vector_store)

    class DeterministicLLM:
        def generate(self, _system: str, user: str) -> str:
            assert "10,000 concurrent users" in user
            return "The source specifies 10,000 concurrent users."

    class UnavailableLLM:
        def generate(self, *_args, **_kwargs):
            raise TimeoutError("simulated provider outage")

    monkeypatch.setattr(rag_service.rag_service, "llm", DeterministicLLM())
    monkeypatch.setattr(requirements_agent.requirements_analysis_agent, "llm", UnavailableLLM())
    monkeypatch.setattr(governance_agent.governance_agent, "llm", UnavailableLLM())
    class OfflineQuestionSelector:
        def choose(self, **_kwargs):
            return None, "fallback"
    monkeypatch.setattr(interview_service, "llm_question_selector", OfflineQuestionSelector())

    created = client.post("/api/projects", json={
        **project_payload,
        "project_name": "Digital Loan Approval System",
        "description": "Allow customers to apply for loans, validate eligibility, integrate with external verification services, and provide approval decisions.",
        "domain": "Lending",
    })
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    questionnaire = client.post(f"/api/projects/{project_id}/questionnaire", json={
        "requirement_stability": "Moderately Changing", "risk_level": "High",
        "security_criticality": "High", "compliance_criticality": "High",
        "expected_changes": "Occasional", "continuous_delivery": "Yes",
        "legacy_integration": "Yes", "formal_verification": "Yes",
        "stakeholder_availability": "High", "complexity": "High", "project_size": "Large",
        "failure_impact": "High", "testing_requirement": "Extensive",
        "budget_constraint": "Medium", "timeline_constraint": "Moderate",
    })
    assert questionnaire.status_code in {200, 201}, questionnaire.text

    uploaded = client.post(f"/api/projects/{project_id}/documents", files={
        "file": ("loan-capacity.txt", b"The system must support 10,000 concurrent users. Loan eligibility is checked against external verification services.", "text/plain"),
    })
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["document_id"]
    embedded = client.post(f"/api/projects/{project_id}/documents/{document_id}/embed")
    assert embedded.status_code == 200, embedded.text
    assert embedded.json()["vectors_created"] >= 1

    interview = client.post(f"/api/projects/{project_id}/interview/start", json={
        "project_idea": "Digital loan approval system with online eligibility checks",
        "business_objective": "Shorten loan decisions with clear evidence and auditability",
        "users_roles": "Applicants, lending staff, compliance reviewers, verification providers",
    })
    assert interview.status_code == 200, interview.text
    state = interview.json()
    answered = 0
    while state["current_question"] is not None and answered < 15:
        question = state["current_question"]
        response = client.post(f"/api/projects/{project_id}/interview/answer", json={
            "question_id": question["id"],
            "answer": "Applicants provide loan details; staff validate eligibility, audit decisions, handle service failures, and protect personal information.",
        })
        assert response.status_code == 200, response.text
        state = response.json()
        answered += 1
    assert answered >= 6
    completed = client.post(f"/api/projects/{project_id}/interview/complete")
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"

    rag = client.post(f"/api/projects/{project_id}/ask", json={"question": "What concurrent user capacity is specified?"})
    assert rag.status_code == 200, rag.text
    assert "10,000" in rag.json()["answer"]
    assert rag.json()["sources"] and rag.json()["sources"][0]["document_id"] == document_id

    requirements = client.post(f"/api/projects/{project_id}/analyze-requirements", json={"top_k": 5})
    assert requirements.status_code == 200, requirements.text
    assert requirements.json()["status"] == "partial"
    assert all(item["requirement_id"].startswith("REQ-") for item in requirements.json()["requirements"])
    governance = client.post(f"/api/projects/{project_id}/governance-analysis")
    assert governance.status_code == 200, governance.text
    assert governance.json()["requirements_analysis_id"] == requirements.json()["analysis_id"]

    first = client.post(f"/api/projects/{project_id}/orchestrate", json={"top_k": 5})
    second = client.post(f"/api/projects/{project_id}/orchestrate", json={"top_k": 5})
    assert first.status_code == second.status_code == 200
    assert (first.json()["analysis_run_version"], second.json()["analysis_run_version"]) == (1, 2)
    history = client.get(f"/api/projects/{project_id}/analysis-runs").json()
    assert [item["version"] for item in history] == [2, 1]
    first_detail = client.get(f"/api/projects/{project_id}/analysis-runs/{first.json()['analysis_run_id']}").json()
    assert first_detail["requirements_analysis"]["analysis_id"] == requirements.json()["analysis_id"]
    assert first_detail["governance_analysis"]["requirements_analysis_id"] == requirements.json()["analysis_id"]
