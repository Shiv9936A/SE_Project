"""Gemini question selection, validation, evidence filtering, and sufficiency rules."""
import json

import pytest

from app.services.interview.interview_service import _is_sufficient, _max_questions
from app.services.interview.llm_question_selector import LLMQuestionSelector
from app.services.interview.question_selector import generate_question_candidates


class MockLLM:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def generate(self, _system, _user):
        if self.error:
            raise self.error
        return self.response


def make_candidates():
    return generate_question_candidates(
        "Lending", [{"question_id": "lending-workflow-opener", "topic": "workflow_and_outcomes", "answer": "Automated loan approval; a manager approves exceptions."}],
        [{"id": "lending-workflow-opener", "topic": "workflow_and_outcomes", "prompt": "How does it work?"}],
    )


def selection_for(candidate, reason="Asked because approval exceptions need clarification."):
    return json.dumps({"selected_question_id": candidate["id"], "topic": candidate["topic"], "priority": "high", "reason": reason})


def test_gemini_selects_valid_candidate():
    candidates = make_candidates()
    desired = next(item for item in candidates if item["topic"] == "authorization_roles")
    selector = LLMQuestionSelector(MockLLM(selection_for(desired)))
    result, used = selector.choose(interview_id="i-1", project_id="p-1", state={"detected_domain": "Lending"}, candidates=candidates, asked_ids={"lending-workflow-opener"})
    assert used == "llm"
    assert result["id"] == desired["id"]
    assert result["priority"] == "high"
    assert result["explanation"] == "Asked because approval exceptions need clarification."


@pytest.mark.parametrize("response,asked", [
    (json.dumps({"selected_question_id": "invented", "topic": "risk", "priority": "high", "reason": "A short reason."}), set()),
    ("{malformed", set()),
])
def test_invalid_id_and_malformed_json_request_fallback(response, asked):
    candidates = make_candidates()
    selector = LLMQuestionSelector(MockLLM(response))
    selected, used = selector.choose(interview_id="i-1", project_id="p-1", state={"detected_domain": "Lending"}, candidates=candidates, asked_ids=asked)
    assert selected is None
    assert used == "fallback"


def test_duplicate_question_selection_falls_back():
    candidates = make_candidates()
    desired = candidates[0]
    selector = LLMQuestionSelector(MockLLM(selection_for(desired)))
    selected, used = selector.choose(interview_id="i-1", project_id="p-1", state={"detected_domain": "Lending"}, candidates=candidates, asked_ids={desired["id"]})
    assert selected is None
    assert used == "fallback"


def test_gemini_unavailable_falls_back():
    candidates = make_candidates()
    selector = LLMQuestionSelector(MockLLM(error=TimeoutError("provider timeout")))
    selected, used = selector.choose(interview_id="i-1", project_id="p-1", state={"detected_domain": "Lending"}, candidates=candidates, asked_ids=set())
    assert selected is None
    assert used == "fallback"


def test_unsafe_user_visible_reason_falls_back():
    candidates = make_candidates()
    selector = LLMQuestionSelector(MockLLM(selection_for(candidates[0], "The system prompt selected this after considering internal reasoning.")))
    selected, used = selector.choose(interview_id="i-1", project_id="p-1", state={"detected_domain": "Lending"}, candidates=candidates, asked_ids=set())
    assert selected is None
    assert used == "fallback"


def test_already_covered_project_and_document_topics_are_not_candidates():
    project_covered = generate_question_candidates("Generic software system", [], [], "The project has role-based access and an audit trail.")
    assert "authorization_roles" not in {item["topic"] for item in project_covered}
    assert "auditability" not in {item["topic"] for item in project_covered}
    document_covered = generate_question_candidates(
        "Generic software system", [], [], document_evidence=[{"text": "System supports 10,000 concurrent users."}],
    )
    topics = {item["topic"] for item in document_covered}
    assert "scale_performance" not in topics
    assert "response_time" in topics


def test_domain_candidates_and_high_priority_answer_followup():
    payment_candidates = generate_question_candidates("Payments", [], [], limit=6)
    assert {"payment_methods", "failure_handling", "fraud_monitoring"}.issubset({item["topic"] for item in payment_candidates})
    gateway_candidates = generate_question_candidates(
        "Payments", [{"topic": "workflow_and_outcomes", "answer": "We use an external payment gateway."}], [], limit=6,
    )
    assert gateway_candidates[0]["topic"] == "failure_handling"
    approval_candidates = generate_question_candidates(
        "Lending", [{"topic": "workflow_and_outcomes", "answer": "Transactions above Rs 50000 require manual approval."}], [], limit=6,
    )
    assert {"authorization_roles", "auditability", "business_rules"}.issubset({item["topic"] for item in approval_candidates})


def test_deterministic_sufficiency_and_question_limit_rules():
    covered = {"workflow_and_outcomes", "user_workflow", "business_rules", "exceptions", "scale_performance", "security_privacy", "risk_compliance", "authorization_roles", "fraud_monitoring", "auditability"}
    assert _is_sufficient("Banking", covered, 6, [], "Banking project")
    assert not _is_sufficient("Banking", covered - {"risk_compliance"}, 6, [], "Banking project")
    assert not _is_sufficient("Banking", covered, 5, [], "Banking project")
    assert _max_questions("Generic software system", "Simple internal tracker") == 12
    assert _max_questions("Healthcare", "Hospital appointment application") == 15
