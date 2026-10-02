"""Coverage for adaptive domain detection, interview persistence, and APIs."""
from app.services.interview.domain_detector import detect_domain
from app.services.interview import interview_service
from app.core.config import settings
import pytest


@pytest.fixture(autouse=True)
def mock_question_selector(monkeypatch):
    monkeypatch.setattr(settings, "interview_llm_selection_enabled", False)
    class OfflineSelector:
        def choose(self, **_kwargs):
            return None, "fallback"
    monkeypatch.setattr(interview_service, "llm_question_selector", OfflineSelector())


def create_project(client, project_payload):
    response = client.post("/api/projects", json=project_payload)
    assert response.status_code == 201
    return response.json()["id"]


def start(client, project_id, idea, objective="Help people complete their work efficiently", roles="Customers and staff"):
    return client.post(f"/api/projects/{project_id}/interview/start", json={
        "project_idea": idea, "business_objective": objective, "users_roles": roles,
    })


def test_domain_detection_examples():
    examples = {
        "online banking application": "Banking",
        "hospital appointment scheduling": "Healthcare",
        "food delivery platform": "Food delivery",
        "college examination portal": "Education",
        "inventory management": "Generic software system",
    }
    for idea, domain in examples.items():
        assert detect_domain(idea) == domain
    assert len({detect_domain(idea) for idea in examples}) == 5


def test_opener_is_idea_specific_and_generic_fallback(client, project_payload):
    project_id = create_project(client, project_payload)
    response = start(client, project_id, "Hospital appointment booking for local clinics")
    assert response.status_code == 200
    body = response.json()
    assert body["detected_domain"] == "Healthcare"
    assert "patient" in body["current_question"]["prompt"].lower()
    assert "healthcare" in body["current_question"]["explanation"].lower()

    generic_id = create_project(client, {**project_payload, "project_name": "Inventory tool"})
    generic = start(client, generic_id, "Simple inventory manager for a small shop").json()
    assert generic["detected_domain"] == "Generic software system"
    assert "main task" in generic["current_question"]["prompt"].lower()


def test_answer_adaptation_and_duplicate_question_prevention(client, project_payload):
    project_id = create_project(client, project_payload)
    state = start(client, project_id, "Food delivery application").json()
    first = state["current_question"]
    state = client.post(f"/api/projects/{project_id}/interview/answer", json={
        "question_id": first["id"], "answer": "The app calls an external payment gateway API and restaurant service.",
    }).json()
    assert state["current_question"]["topic"] == "failure_handling"
    ids = [question["id"] for question in state["asked_questions"]]
    assert len(ids) == len(set(ids))
    assert state["question_number"] == 2
    current_question_id = state["current_question"]["id"]
    revised = client.post(f"/api/projects/{project_id}/interview/answer", json={
        "question_id": first["id"], "answer": "Revised workflow: transactions above 50000 require manual approval by a manager.",
    }).json()
    assert revised["current_question"]["id"] != current_question_id
    assert revised["current_question"]["topic"] == "authorization_roles"
    assert len(revised["answers"]) == 1
    assert revised["answers"][0]["answer"].startswith("Revised workflow")


def test_interview_state_completion_limit_and_legacy_questionnaire(client, project_payload, questionnaire_payload):
    project_id = create_project(client, project_payload)
    state = start(client, project_id, "Simple inventory manager", "Track stock in a small shop", "Shop staff").json()
    assert 6 <= state["maximum_questions"] <= 12
    seen = set()
    while state["current_question"] is not None:
        question = state["current_question"]
        assert question["id"] not in seen
        seen.add(question["id"])
        response = client.post(f"/api/projects/{project_id}/interview/answer", json={
            "question_id": question["id"], "answer": f"Answer for {question['topic']} with enough detail.",
        })
        assert response.status_code == 200
        state = response.json()
        assert state["question_number"] <= state["maximum_questions"]
    assert state["question_number"] == state["maximum_questions"] or state["uncovered_topics"]
    completed = client.post(f"/api/projects/{project_id}/interview/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    saved = client.post(f"/api/projects/{project_id}/questionnaire", json=questionnaire_payload)
    assert saved.status_code == 200
    assert saved.json()["risk_level"] == questionnaire_payload["risk_level"]
    assert client.get(f"/api/projects/{project_id}/interview/state").json()["status"] == "completed"


def test_answer_requires_an_asked_question(client, project_payload):
    project_id = create_project(client, project_payload)
    start(client, project_id, "An unclassified internal software system")
    response = client.post(f"/api/projects/{project_id}/interview/answer", json={
        "question_id": "invented-question", "answer": "No.",
    })
    assert response.status_code == 404


def test_interview_stops_on_deterministic_sufficiency(client, project_payload, monkeypatch):
    sequence = ["user_workflow", "business_rules", "exceptions", "scale_performance", "security_privacy"]

    class TargetedSelector:
        def choose(self, *, candidates, **_kwargs):
            wanted = sequence.pop(0) if sequence else None
            chosen = next((candidate for candidate in candidates if candidate["topic"] == wanted), None)
            return (chosen, "llm") if chosen else (None, "fallback")

    monkeypatch.setattr(interview_service, "llm_question_selector", TargetedSelector())
    monkeypatch.setattr(settings, "interview_llm_selection_enabled", True)
    project_id = create_project(client, project_payload)
    state = start(client, project_id, "Internal inventory management system", "Track stock and reduce manual work", "Warehouse staff").json()
    while state["current_question"] is not None:
        question = state["current_question"]
        response = client.post(f"/api/projects/{project_id}/interview/answer", json={
            "question_id": question["id"], "answer": f"The team has a clear {question['topic']} requirement.",
        })
        assert response.status_code == 200
        state = response.json()
    assert state["question_number"] == 6
    assert state["status"] == "in_progress"
    assert client.post(f"/api/projects/{project_id}/interview/complete").status_code == 200


def test_changed_answer_changes_the_next_candidate(client, project_payload):
    plain_id = create_project(client, {**project_payload, "project_name": "Plain workflow"})
    integration_id = create_project(client, {**project_payload, "project_name": "Gateway workflow"})
    plain = start(client, plain_id, "Generic internal tool", "Help users finish work", "Staff").json()
    integration = start(client, integration_id, "Generic internal tool", "Help users finish work", "Staff").json()
    plain_next = client.post(f"/api/projects/{plain_id}/interview/answer", json={
        "question_id": plain["current_question"]["id"], "answer": "A staff member enters a request and sees its status.",
    }).json()
    integration_next = client.post(f"/api/projects/{integration_id}/interview/answer", json={
        "question_id": integration["current_question"]["id"], "answer": "The workflow sends data to an external payment gateway API.",
    }).json()
    assert plain_next["current_question"]["topic"] != integration_next["current_question"]["topic"]
    assert integration_next["current_question"]["topic"] == "failure_handling"


def test_skip_advances_without_marking_topic_as_covered(client, project_payload):
    project_id = create_project(client, project_payload)
    state = start(client, project_id, "Digital lending workflow", "Approve personal loans", "Applicants and loan officers").json()
    question = state["current_question"]

    response = client.post(f"/api/projects/{project_id}/interview/answer", json={
        "question_id": question["id"], "skipped": True,
    })

    assert response.status_code == 200
    updated = response.json()
    skipped_answer = next(item for item in updated["answers"] if item["question_id"] == question["id"])
    assert skipped_answer["skipped"] is True
    assert skipped_answer["answer"] == ""
    assert question["topic"] not in updated["covered_topics"]
    assert question["topic"] in updated["uncovered_topics"]
    assert updated["current_question"] is not None


def test_blank_interview_answer_requires_skip_flag(client, project_payload):
    project_id = create_project(client, project_payload)
    question = start(client, project_id, "Generic inventory management").json()["current_question"]

    response = client.post(f"/api/projects/{project_id}/interview/answer", json={
        "question_id": question["id"], "answer": "",
    })

    assert response.status_code == 422


def test_maximum_question_limit_stops_interview(client, project_payload, monkeypatch):
    monkeypatch.setattr(interview_service, "_max_questions", lambda *_args: 6)
    monkeypatch.setattr(interview_service, "_is_sufficient", lambda *_args, **_kwargs: False)
    project_id = create_project(client, {**project_payload, "project_name": "Limit check"})
    state = start(client, project_id, "Generic internal application", "Help the team track work", "Staff").json()
    assert state["maximum_questions"] == 6
    while state["question_number"] < 6:
        current = state["current_question"]
        state = client.post(f"/api/projects/{project_id}/interview/answer", json={
            "question_id": current["id"], "answer": "Still need more information about this requirement.",
        }).json()
        assert state["current_question"] is not None
    last = state["current_question"]
    state = client.post(f"/api/projects/{project_id}/interview/answer", json={
        "question_id": last["id"], "answer": "The final allowed answer is recorded.",
    }).json()
    assert state["current_question"] is None
    assert state["question_number"] == 6
