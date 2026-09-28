"""Questionnaire-only SDLC baseline using the canonical lifecycle model set."""
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import GeneratedRecommendation
from app.repositories import recommendations as recommendation_repo
from app.services.project_service import require_project
from app.services.sdlc_recommendation_service import score_sdlc_models


def _rank(questionnaire) -> list[dict]:
    answers = {
        column.name: getattr(questionnaire, column.name)
        for column in questionnaire.__table__.columns
        if column.name not in {"id", "project_id", "created_at"}
    }
    return score_sdlc_models(answers)


def _risk_factors(project, q) -> list[str]:
    risks = []
    if q.compliance_criticality == "High": risks.append("High compliance criticality requires an authorised compliance review.")
    if q.security_criticality == "High": risks.append("High security criticality requires threat modelling and security approval.")
    if q.legacy_integration == "Yes": risks.append("Legacy integration may increase dependency and migration risk.")
    if q.risk_level == "High" or q.failure_impact == "High": risks.append("High project risk or failure impact calls for explicit validation and rollback gates.")
    if q.requirement_stability == "Frequently Changing" and q.stakeholder_availability == "Low": risks.append("Frequent requirement change with low stakeholder availability may slow clarification and acceptance.")
    if q.timeline_constraint == "Strict" and q.testing_requirement == "Extensive": risks.append("A strict timeline combined with extensive testing needs early scope and capacity planning.")
    if not risks: risks.append("No high-severity factors were identified by the questionnaire; validate assumptions with stakeholders.")
    return risks


def generate_recommendation(db: Session, project_id: str):
    project = require_project(db, project_id)
    q = project.questionnaire
    if q is None:
        raise AppError("Submit the SDLC questionnaire before requesting an analysis.", 409)
    ranking = _rank(q)
    best, runner_up = ranking[0], ranking[1]
    confidence = min(92.0, round(55 + max(0, best["score"] - runner_up["score"]) * 0.8, 1))
    reasons = [
        f"The recommendation reflects {q.requirement_stability.lower()} requirements and {q.expected_changes.lower()} expected changes.",
        f"It accounts for {q.security_criticality.lower()} security and {q.compliance_criticality.lower()} compliance criticality.",
        f"The delivery fit includes {q.continuous_delivery.lower()} continuous delivery, {q.legacy_integration.lower()} legacy integration, and {q.testing_requirement.lower()} testing.",
        "This is a rule-based planning estimate, not a probability or final decision; project leadership must approve the SDLC choice.",
    ]
    recommendation = GeneratedRecommendation(
        project_id=project_id,
        recommended_sdlc=best["model"],
        confidence_score=confidence,
        justification=" ".join(reasons),
        risk_factors=_risk_factors(project, q),
        alternatives=[{"model": row["model"], "score": row["score"], "rationale": f"Comparative fit based on the questionnaire; score {row['score']} of the leading option."} for row in ranking[1:4]],
        scoring_method="rule_based_v2",
    )
    return recommendation_repo.create(db, recommendation)


def get_recommendation(db: Session, project_id: str):
    project = require_project(db, project_id)
    recommendation = recommendation_repo.latest(db, project_id)
    if recommendation is None:
        raise AppError("No recommendation exists yet. Run project analysis first.", 404)
    return recommendation
