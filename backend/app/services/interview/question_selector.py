"""Rule-based candidate generation and deterministic fallback selection."""
import re

from app.services.interview.question_bank import DOMAIN_TOPICS, question_for

MIN_QUESTIONS = 6
DEFAULT_MAX_QUESTIONS = 12
HIGH_COMPLEXITY_MAX_QUESTIONS = 15

EVIDENCE_SIGNALS = {
    "security_privacy": ("sensitive data", "personal data", "encryption", "access control", "privacy policy", "patient records"),
    "risk_compliance": ("regulation", "regulatory", "audit log", "compliance requirement", "safety standard"),
    "integration": ("integrates with", "integration with", "connects to", "api with", "legacy system"),
    "scale_performance": ("peak volume", "concurrent users", "transactions per", "response time target", "10,000 users", "10000 users"),
    "testing": ("test plan", "testing strategy", "formal verification", "acceptance test"),
    "delivery_operations": ("continuous deployment", "release every", "operations team", "on call support"),
    "business_rules": ("eligibility rules", "approval threshold", "business rule", "spending limit"),
    "exceptions": ("retry on failure", "rollback on failure", "failure recovery", "manual fallback"),
    "authorization_roles": ("role based access", "role-based access", "approval roles", "authorized approver"),
    "auditability": ("audit trail", "audit log", "decision history"),
    "fraud_monitoring": ("fraud monitoring", "fraud detection", "fraud alert"),
    "availability": ("availability target", "uptime target", "disaster recovery"),
    "payment_methods": ("visa and mastercard", "payment methods include", "supports card and wallet"),
    "delivery_tracking": ("live courier tracking", "delivery tracking", "proof of delivery"),
}

DOMAIN_PRIORITIES = {
    "Banking": ["authorization_roles", "fraud_monitoring", "auditability", "security_privacy", "risk_compliance", "exceptions", "availability"],
    "Payments": ["payment_methods", "failure_handling", "fraud_monitoring", "auditability", "security_privacy", "exceptions", "availability"],
    "Lending": ["business_rules", "authorization_roles", "auditability", "risk_compliance", "exceptions", "security_privacy"],
    "Insurance": ["business_rules", "authorization_roles", "auditability", "risk_compliance", "exceptions", "security_privacy"],
    "Healthcare": ["appointment_rules", "authorization_roles", "auditability", "security_privacy", "risk_compliance", "integration", "exceptions"],
    "Education": ["assessment_results", "authorization_roles", "security_privacy", "auditability", "user_workflow"],
    "Food delivery": ["order_cancellation", "payment_methods", "delivery_tracking", "integration", "exceptions"],
}


def adaptive_topics(answer: str) -> list[str]:
    text = answer.casefold()
    topics: list[str] = []
    if any(word in text for word in ("gateway", "payment provider", "external api", "external system", "vendor", "legacy system", "integrat")):
        topics.append("failure_handling")
    if any(word in text for word in ("manual approval", "human approval", "approval by", "above ", "threshold", "approver")):
        topics.extend(("authorization_roles", "auditability", "business_rules"))
    if any(word in text for word in ("fail", "error", "reject", "exception", "unavailable", "override")):
        topics.append("exceptions")
    if any(word in text for word in ("fraud", "suspicious transaction")):
        topics.append("fraud_monitoring")
    if any(word in text for word in ("audit", "traceability", "decision history")):
        topics.append("auditability")
    if any(word in text for word in ("personal data", "sensitive", "security", "privacy", "patient", "financial data")):
        topics.append("security_privacy")
    if any(word in text for word in ("cancel", "cancellation")):
        topics.append("order_cancellation")
    return list(dict.fromkeys(topics))


def known_topics(text: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return {topic for topic, phrases in EVIDENCE_SIGNALS.items() if any(phrase in normalized for phrase in phrases)}


def generate_question_candidates(domain: str, answers: list[dict], asked: list[dict], known_text: str = "",
                                 document_evidence: list[dict] | None = None, limit: int = 6) -> list[dict]:
    """Return a small, ordered set of unseen candidates from the approved question bank."""
    asked_ids = {item["id"] for item in asked}
    answered_topics = {item["topic"] for item in answers}
    evidence_text = " ".join(str(item.get("text", "")) for item in document_evidence or [])
    context_covered = known_topics(known_text)
    document_covered = known_topics(evidence_text)
    covered = answered_topics | context_covered | document_covered
    latest = answers[-1]["answer"] if answers else ""
    topics = adaptive_topics(latest)
    topics.extend(DOMAIN_PRIORITIES.get(domain, []))
    topics.extend(DOMAIN_TOPICS.get(domain, DOMAIN_TOPICS["Generic software system"]))
    topics.extend(("user_workflow", "business_rules", "exceptions", "integration", "security_privacy",
                   "risk_compliance", "scale_performance", "response_time", "testing", "delivery_operations",
                   "success_metrics", "priority_scope"))
    # A documented load target should lead to a gap question about performance, not repeat the load question.
    if "scale_performance" in document_covered:
        topics.insert(0, "response_time")
    candidates = []
    seen_topics = set()
    for topic in topics:
        if topic in seen_topics or topic in answered_topics:
            continue
        seen_topics.add(topic)
        # Evidence can make a detail redundant. Leave it unverified in coverage; it only suppresses a duplicate ask.
        if topic in context_covered or topic in document_covered:
            continue
        candidate = question_for(topic, domain)
        if candidate["id"] in asked_ids:
            continue
        candidate["priority"] = "high" if topic in DOMAIN_PRIORITIES.get(domain, []) or topic in adaptive_topics(latest) else "medium"
        candidates.append(candidate)
        if len(candidates) >= limit:
            break
    # Keep the Phase 9 six-question minimum even for projects whose initial description covers many topics.
    if len(asked) < MIN_QUESTIONS:
        for topic in ("success_metrics", "priority_scope", "user_workflow"):
            candidate = question_for(topic, domain)
            if candidate["id"] not in asked_ids and all(item["id"] != candidate["id"] for item in candidates):
                candidates.append({**candidate, "priority": "medium"})
            if len(candidates) >= limit:
                break
    return candidates[:limit]


def select_next_question(domain: str, answers: list[dict], asked: list[dict], known_text: str = "") -> dict | None:
    """Deterministic fallback kept for Gemini failure and Phase 9 compatibility."""
    candidates = generate_question_candidates(domain, answers, asked, known_text)
    return candidates[0] if candidates else None
