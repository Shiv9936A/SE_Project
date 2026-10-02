"""Persistence and orchestration for deterministic adaptive interviews."""
from datetime import datetime, timezone
import logging
from time import perf_counter
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.exceptions import AppError
from app.models.interview import InterviewSession
from app.models.project import Project
from app.services.interview.domain_detector import DOMAIN_KEYWORDS, detect_domain
from app.services.interview.question_bank import opener_for
from app.services.interview.question_selector import (
    DEFAULT_MAX_QUESTIONS,
    HIGH_COMPLEXITY_MAX_QUESTIONS,
    MIN_QUESTIONS,
    adaptive_topics,
    generate_question_candidates,
    known_topics,
)
from app.services.interview.llm_question_selector import llm_question_selector
from app.services.retrieval_service import retrieval_service

logger = logging.getLogger(__name__)
HIGH_RISK_DOMAINS = {"Banking", "Payments", "Lending", "Insurance", "Healthcare", "Government/public services"}
TRACKED_TOPICS = ["workflow_and_outcomes", "user_workflow", "business_rules", "exceptions", "failure_handling", "integration", "security_privacy", "risk_compliance", "scale_performance", "response_time", "testing", "delivery_operations", "success_metrics", "priority_scope", "authorization_roles", "auditability", "fraud_monitoring", "availability", "appointment_rules", "assessment_results", "delivery_tracking", "order_cancellation", "payment_methods"]
DOMAIN_MANDATORY = {
    "Banking": {"authorization_roles", "fraud_monitoring", "auditability"},
    "Payments": {"payment_methods", "failure_handling", "fraud_monitoring"},
    "Lending": {"business_rules", "authorization_roles", "auditability"},
    "Insurance": {"business_rules", "authorization_roles", "auditability"},
    "Healthcare": {"appointment_rules", "authorization_roles", "auditability"},
    "Education": {"assessment_results", "authorization_roles"},
    "Food delivery": {"order_cancellation", "payment_methods", "delivery_tracking"},
}

def _max_questions(domain: str, text: str) -> int:
    words = text.casefold()
    high_complexity = domain in HIGH_RISK_DOMAINS or any(term in words for term in (
        "high risk", "safety critical", "life-critical", "mission critical", "large scale",
        "strict compliance", "complex platform", "multiple legacy", "highly regulated",
    ))
    return HIGH_COMPLEXITY_MAX_QUESTIONS if high_complexity else DEFAULT_MAX_QUESTIONS


def _is_sufficient(domain: str, covered: set[str], question_number: int, answers: list[dict], idea: str, evidence_topics: set[str] | None = None) -> bool:
    """Completion remains a deterministic decision; Gemini cannot end an interview."""
    if question_number < MIN_QUESTIONS:
        return False
    evidence_topics = evidence_topics or set()
    supported = covered | evidence_topics
    essential = (
        "workflow_and_outcomes" in supported
        and "user_workflow" in supported
        and bool({"business_rules", "success_metrics"} & supported)
        and bool({"exceptions", "risk_compliance"} & supported)
        and bool({"scale_performance", "response_time", "delivery_operations"} & supported)
    )
    if not essential:
        return False
    if domain in HIGH_RISK_DOMAINS and not {"security_privacy", "risk_compliance"}.issubset(covered):
        return False
    if not DOMAIN_MANDATORY.get(domain, set()).issubset(supported):
        return False
    answered = [answer for answer in answers if not answer.get("skipped", False)]
    adaptive_needed = {topic for answer in answered for topic in adaptive_topics(answer.get("answer", ""))}
    # These follow-ups become essential only after project-specific evidence makes them relevant.
    answer_text = " ".join(row.get("answer", "") for row in answered).casefold()
    if any(term in answer_text for term in ("gateway", "external api", "legacy system", "integrat")):
        adaptive_needed.add("failure_handling")
    if any(term in answer_text for term in ("manual approval", "human approval", "above ", "threshold")):
        adaptive_needed.update(("authorization_roles", "auditability"))
    # Domain-critical security/compliance and answer-triggered follow-ups require user confirmation.
    return adaptive_needed.issubset(covered)


def _retrieve_document_evidence(db: Session, project_id: str, query: str) -> list[dict]:
    project = db.get(Project, project_id)
    if not project or not project.documents:
        return []
    started = perf_counter()
    try:
        evidence = retrieval_service.search(db, project_id, query, top_k=5, score_threshold=0.15)
        logger.info("Interview document evidence retrieved", extra={
            "project_id": project_id, "candidate_count": 0, "retrieved_chunk_count": len(evidence),
            "latency_ms": round((perf_counter() - started) * 1000, 2),
        })
        return evidence
    except Exception as exc:
        logger.warning("Interview retrieval unavailable; continuing without document evidence", extra={
            "project_id": project_id, "failure_type": type(exc).__name__,
            "latency_ms": round((perf_counter() - started) * 1000, 2),
        })
        return []

def start(db: Session, project_id: str, idea: str, objective: str, roles: str) -> InterviewSession:
    project = db.get(Project, project_id)
    if not project:
        raise AppError("Project not found.", 404)
    domain = detect_domain(" ".join((idea, objective, roles)))
    if domain == "Generic software system" and project.domain in DOMAIN_KEYWORDS:
        domain = project.domain
    question = opener_for(domain)
    known = known_topics(" ".join((idea, objective, roles)))
    session = db.scalar(select(InterviewSession).where(InterviewSession.project_id == project_id))
    if session:
        # Starting again with the same inputs resumes the saved state.
        if session.project_idea == idea and session.business_objective == objective and session.users_roles == roles and session.status == "in_progress":
            session.maximum_questions = max(session.maximum_questions, _max_questions(domain, " ".join((idea, objective))))
            db.commit()
            db.refresh(session)
            return session
        session.project_idea, session.business_objective, session.users_roles = idea, objective, roles
        session.detected_domain = domain
        session.asked_questions, session.answers = [question], []
        session.covered_topics, session.uncovered_topics = sorted(known), [topic for topic in TRACKED_TOPICS if topic not in known]
        session.current_question, session.question_number = question, 1
        session.maximum_questions, session.status = _max_questions(domain, " ".join((idea, objective))), "in_progress"
        session.completed_at = None
    else:
        session = InterviewSession(project_id=project_id, project_idea=idea, business_objective=objective, users_roles=roles,
            detected_domain=domain, asked_questions=[question], answers=[], covered_topics=sorted(known), uncovered_topics=[topic for topic in TRACKED_TOPICS if topic not in known],
            current_question=question, question_number=1, maximum_questions=_max_questions(domain, " ".join((idea, objective))))
        db.add(session)
    project.domain = domain
    project.description = idea
    project.initial_requirements = objective
    project.stakeholders = roles
    db.commit()
    db.refresh(session)
    return session

def get_state(db: Session, project_id: str) -> InterviewSession:
    session = db.scalar(select(InterviewSession).where(InterviewSession.project_id == project_id))
    if not session:
        raise AppError("No interview has been started for this project.", 404)
    return session

def answer(db: Session, project_id: str, question_id: str, response: str, skipped: bool = False) -> InterviewSession:
    request_started = perf_counter()
    session = get_state(db, project_id)
    if session.status == "completed":
        raise AppError("This interview is already complete.", 409)
    question = next((item for item in session.asked_questions if item["id"] == question_id), None)
    if question is None:
        raise AppError("Question does not belong to this interview.", 404)
    record = {"question_id": question_id, "topic": question["topic"], "answer": "" if skipped else response.strip(), "skipped": skipped}
    updated_answers = [dict(item) for item in session.answers]
    existing_index = next((index for index, item in enumerate(updated_answers) if item["question_id"] == question_id), None)
    if existing_index is None:
        updated_answers.append(record)
    else:
        updated_answers.pop(existing_index)
        updated_answers.append(record)
    session.answers = updated_answers
    known_context = " ".join((session.project_idea, session.business_objective, session.users_roles))
    project = db.get(Project, project_id)
    session.covered_topics = list(dict.fromkeys([*(item["topic"] for item in session.answers if not item.get("skipped", False)), *known_topics(known_context)]))
    candidate_count = 0
    selector_name = "saved_answer"
    is_current_answer = bool(session.current_question and session.current_question["id"] == question_id)
    is_answer_revision = existing_index is not None and session.current_question is not None
    if is_current_answer or is_answer_revision:
        if session.question_number >= session.maximum_questions:
            session.current_question = None
            selector_name = "question_limit"
        else:
            covered = set(session.covered_topics)
            evidence_query = " ".join((session.project_idea, session.business_objective, question["topic"], response[:700]))
            document_evidence = [] if skipped else _retrieve_document_evidence(db, project_id, evidence_query)
            evidence_topics = known_topics(" ".join(item.get("text", "") for item in document_evidence))
            if _is_sufficient(session.detected_domain, covered, session.question_number, session.answers, session.project_idea, evidence_topics):
                session.current_question = None
                selector_name = "sufficiency"
            else:
                candidates = generate_question_candidates(
                    session.detected_domain,
                    [item for item in session.answers if not item.get("skipped", False)],
                    session.asked_questions, known_context,
                    document_evidence=document_evidence, limit=6,
                )
                candidate_count = len(candidates)
                selector_state = {
                    "project_idea": session.project_idea,
                    "business_objective": session.business_objective,
                    "users_roles": session.users_roles,
                    "detected_domain": session.detected_domain,
                    "previous_questions": session.asked_questions,
                    "previous_answers": [item for item in session.answers if not item.get("skipped", False)],
                    "covered_topics": session.covered_topics,
                    "uncovered_topics": session.uncovered_topics,
                    "document_evidence": document_evidence,
                }
                if settings.interview_llm_selection_enabled:
                    selected, selector_name = llm_question_selector.choose(
                        interview_id=session.id, project_id=project_id, state=selector_state,
                        candidates=candidates, asked_ids={item["id"] for item in session.asked_questions},
                    )
                else:
                    # Keep the request path local and responsive; candidate generation is already
                    # domain-aware and ranked by evidence, priority, and prior answers.
                    selected, selector_name = None, "deterministic"
                if selected is None and candidates:
                    # Candidate ordering is deterministic and already accounts for evidence and asked IDs.
                    selected = candidates[0]
                    selector_name = "deterministic"
                    logger.info("Interview question selected", extra={
                        "interview_id": session.id, "project_id": project_id,
                        "detected_domain": session.detected_domain, "candidate_count": len(candidates),
                        "selected_question_id": selected["id"], "selector": selector_name,
                        "latency_ms": round((perf_counter() - request_started) * 1000, 2),
                    })
                if selected:
                    session.asked_questions = [*session.asked_questions, selected]
                    session.question_number += 1
                    session.current_question = selected
                else:
                    session.current_question = None
                    selector_name = "deterministic"
    logger.info("Interview answer processed", extra={
        "interview_id": session.id, "project_id": project_id,
        "detected_domain": session.detected_domain,
        "candidate_count": candidate_count,
        "selected_question_id": session.current_question.get("id") if session.current_question else None,
        "selector": selector_name,
        "latency_ms": round((perf_counter() - request_started) * 1000, 2),
    })
    session.uncovered_topics = [topic for topic in TRACKED_TOPICS if topic not in session.covered_topics]
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session

def complete(db: Session, project_id: str) -> InterviewSession:
    session = get_state(db, project_id)
    if session.current_question is not None:
        raise AppError("Answer the current interview question before completing the interview.", 409)
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session
