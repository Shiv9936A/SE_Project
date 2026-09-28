"""LangGraph SDLC recommendation API, scoring, comparison, and persistence tests."""
import json

from app.services.sdlc_recommendation_service import (
    RecommendationNarrative, SDLCRecommendationService, _json_response,
    sdlc_recommendation_service, score_sdlc_models,
)
from app.core.exceptions import AppError


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def search(self, db, project_id, query, top_k=5, filters=None, score_threshold=None):
        self.calls.append({"project_id": project_id, "query": query, "top_k": top_k,
                           "filters": filters, "score_threshold": score_threshold})
        return [{"chunk_id": "chunk-1", "document_id": "doc-1", "score": 0.88,
                 "filename": "delivery-notes.txt", "page_number": 1,
                 "text": "Security, audit validation, and continuous delivery are required."}]


class FakeLLM:
    def __init__(self):
        self.calls = []

    def generate(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        if '"model_a"' in user_prompt:
            return json.dumps({
                "why_model_a_fits": "Model A fits the project evidence [chunk_id=chunk-1].",
                "why_model_b_fits": "Model B supports documented assurance needs [chunk_id=chunk-1].",
                "tradeoffs": ["Model A adapts faster; Model B defines more formal verification gates."],
                "risk_analysis": ["Keep security and compliance reviews in both approaches."],
            })
        return json.dumps({
            "reasoning": "Kanban and DevOps tie for the highest score of 100.",
            "strengths": ["Supports continuous delivery with security checks."],
            "risks": ["Compliance controls need explicit ownership."],
            "implementation_notes": ["Start with a small release and automate audit evidence."],
        })


def create_project_with_answers(client, project_payload, questionnaire_payload):
    project_response = client.post("/api/projects", json=project_payload)
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()
    questionnaire_response = client.post(
        f"/api/projects/{project['id']}/questionnaire", json=questionnaire_payload,
    )
    assert questionnaire_response.status_code == 200, questionnaire_response.text
    return project


def configure_service(monkeypatch):
    retriever, llm = FakeRetriever(), FakeLLM()
    monkeypatch.setattr(sdlc_recommendation_service, "retriever", retriever)
    monkeypatch.setattr(sdlc_recommendation_service, "llm", llm)
    return retriever, llm


def test_scorer_returns_only_supported_sdlc_models_and_uses_document_evidence(questionnaire_payload):
    questionnaire_only = score_sdlc_models(questionnaire_payload)
    assert questionnaire_only == score_sdlc_models(questionnaire_payload, [])
    scores = score_sdlc_models(questionnaire_payload, [{
        "text": "Security controls and audit validation use continuous delivery."
    }])

    assert len(scores) == 7
    assert {item["model"] for item in scores} == {
        "Waterfall", "V-Model", "Incremental", "Iterative", "Spiral",
        "Agile Scrum", "RAD",
    }
    assert all(0 <= item["score"] <= 100 for item in scores)
    assert scores[0]["model"] == "V-Model"
    assert scores != questionnaire_only


def test_model_authored_text_cannot_reintroduce_removed_models():
    narrative = _json_response(json.dumps({
        "reasoning": "DevOps, DevSecOps and Kanban fit the release process.",
        "strengths": ["DevOps automation"],
        "risks": ["Kanban boards need ownership."],
        "implementation_notes": ["Use delivery automation."],
    }), RecommendationNarrative)

    rendered = json.dumps(narrative)
    assert "DevOps" not in rendered
    assert "DevSecOps" not in rendered
    assert "Kanban" not in rendered


def test_recommendation_runs_langgraph_and_persists_history(
    client, project_payload, questionnaire_payload, monkeypatch,
):
    retriever, llm = configure_service(monkeypatch)
    project = create_project_with_answers(client, project_payload, questionnaire_payload)

    response = client.post(f"/api/projects/{project['id']}/recommend-sdlc", json={"top_k": 3})

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["project_id"] == project["id"]
    assert result["recommended_model"] == "V-Model"
    assert 0 <= result["confidence"] <= 100
    assert len(result["model_scores"]) == 7
    assert {row["model"] for row in result["model_scores"]}.isdisjoint({"DevOps", "Kanban"})
    assert result["reasoning"].startswith("V-Model ranks first with a comparative fit score of")
    assert "highest score of 100" not in result["reasoning"]
    assert len(result["alternative_models"]) == 3
    assert result["sources"][0]["chunk_id"] == "chunk-1"
    assert "chunk_id=chunk-1" in result["reasoning"]
    assert retriever.calls[0]["top_k"] == 3
    assert "High" in retriever.calls[0]["query"]
    assert "SCORED SDLC MODELS" in llm.calls[0][1]

    legacy_latest = client.get(f"/api/projects/{project['id']}/recommendation")
    assert legacy_latest.status_code == 200, legacy_latest.text
    assert legacy_latest.json()["id"] == result["id"]
    assert "_phase7" not in legacy_latest.json()["alternatives"][0]

    history = client.get(f"/api/projects/{project['id']}/recommendation-history")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["id"] == result["id"]

    client.post(f"/api/projects/{project['id']}/recommend-sdlc", json={})
    history_again = client.get(f"/api/projects/{project['id']}/recommendation-history")
    assert len(history_again.json()) == 2


def test_compare_sdlc_returns_fits_tradeoffs_and_risks(
    client, project_payload, questionnaire_payload, monkeypatch,
):
    retriever, llm = configure_service(monkeypatch)
    project = create_project_with_answers(client, project_payload, questionnaire_payload)

    response = client.post(f"/api/projects/{project['id']}/compare-sdlc", json={
        "model_a": "Agile Scrum", "model_b": "V-Model", "top_k": 4,
    })

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["model_a"] == "Agile Scrum"
    assert result["model_b"] == "V-Model"
    assert 0 <= result["score_a"] <= 100
    assert 0 <= result["score_b"] <= 100
    assert result["why_model_a_fits"]
    assert result["why_model_b_fits"]
    assert result["tradeoffs"] and result["risk_analysis"]
    assert result["sources"][0]["document_id"] == "doc-1"
    assert len(retriever.calls) == 1
    assert len(llm.calls) == 1


def test_recommendation_requires_questionnaire(client, project_payload, monkeypatch):
    configure_service(monkeypatch)
    project_response = client.post("/api/projects", json=project_payload)
    project_id = project_response.json()["id"]

    response = client.post(f"/api/projects/{project_id}/recommend-sdlc", json={})

    assert response.status_code == 409
    assert "questionnaire" in response.json()["detail"].lower()


def test_recommendation_survives_temporary_llm_outage(
    client, project_payload, questionnaire_payload, monkeypatch,
):
    configure_service(monkeypatch)

    class UnavailableLLM:
        def generate(self, *_args):
            raise AppError("Gemini is temporarily unavailable.", 502)

    monkeypatch.setattr(sdlc_recommendation_service, "llm", UnavailableLLM())
    project = create_project_with_answers(client, project_payload, questionnaire_payload)

    response = client.post(f"/api/projects/{project['id']}/recommend-sdlc", json={})

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["recommended_model"] in {row["model"] for row in result["model_scores"]}
    assert any("language model was unavailable" in risk.lower() for risk in result["risks"])
    assert result["strengths"] and result["implementation_notes"]


def test_compare_rejects_same_model(client, project_payload, questionnaire_payload, monkeypatch):
    configure_service(monkeypatch)
    project = create_project_with_answers(client, project_payload, questionnaire_payload)

    response = client.post(f"/api/projects/{project['id']}/compare-sdlc", json={
        "model_a": "Agile Scrum", "model_b": "Agile Scrum",
    })

    assert response.status_code == 422


def test_compare_rejects_removed_models(client, project_payload, questionnaire_payload, monkeypatch):
    configure_service(monkeypatch)
    project = create_project_with_answers(client, project_payload, questionnaire_payload)

    response = client.post(f"/api/projects/{project['id']}/compare-sdlc", json={
        "model_a": "DevOps", "model_b": "Kanban",
    })

    assert response.status_code == 422
