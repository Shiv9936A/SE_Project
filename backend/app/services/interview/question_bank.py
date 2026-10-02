"""Curated domain openers and topic-focused questions."""
OPENERS = {
    "Banking": "For this banking workflow, what starts the customer journey, what account or transaction decisions occur, and what outcome should the customer receive?",
    "Payments": "For this payment journey, who initiates a payment, which parties or systems handle it, and what should a successful outcome look like?",
    "Lending": "For this lending journey, how does an applicant move from application to a lending decision, and what outcome should each party see?",
    "Insurance": "For this insurance workflow, what event starts a quote or claim, who makes the key decisions, and what outcome should the customer receive?",
    "Healthcare": "For this healthcare workflow, how does a patient or clinician begin the journey, what decisions happen, and what outcome is needed?",
    "Education": "For this education workflow, what do students or staff need to do, what decisions or checks are involved, and what result should they receive?",
    "E-commerce": "For this shopping journey, how does a customer discover and order an item, what decisions happen, and what should happen after purchase?",
    "Logistics": "For this logistics workflow, what starts a shipment or delivery, who handles each handoff, and how should completion be confirmed?",
    "Food delivery": "For this food delivery journey, how does an order move from customer to restaurant to courier, and what should happen at each handoff?",
    "Government/public services": "For this public service, how does a resident or staff member start a case, what decisions are made, and how is the outcome communicated?",
    "HR/recruitment": "For this people or recruitment workflow, how is a person or role introduced, what decisions follow, and what outcome should staff and candidates see?",
    "Manufacturing": "For this manufacturing workflow, what initiates production, what checks or handoffs occur, and how is a completed or rejected item recorded?",
    "Generic software system": "What is the main task someone should complete with this system, who performs it, and what result tells them it worked?",
}

TOPIC_QUESTIONS = {
    "business_rules": ("What rules, limits, eligibility conditions, or approvals determine how this process should proceed?", "This clarifies decisions and business rules."),
    "exceptions": ("What should the system do when a step fails, information is missing, or someone rejects or overrides a decision?", "This explores exceptions and recovery paths."),
    "integration": ("Which external or legacy systems, people, or data sources must exchange information with this solution?", "This focuses on integrations and handoffs."),
    "security_privacy": ("What sensitive information is handled, and who should be allowed to view or change it?", "This identifies privacy, security, and access needs."),
    "risk_compliance": ("Which regulations, audit records, or safety obligations must the project satisfy?", "This checks risk and compliance obligations."),
    "scale_performance": ("How many users or transactions should the system support, including expected peak periods?", "This estimates scale and performance expectations."),
    "testing": ("Which outcomes must be tested or independently verified before release?", "This identifies assurance and testing expectations."),
    "delivery_operations": ("How often should changes be released, and who will operate and support the system after launch?", "This covers release and operational needs."),
    "user_workflow": ("What information must users provide, and what should they be able to see or do at each stage?", "This fills in the user workflow and required information."),
    "success_metrics": ("How will the people funding or using this system know that it has succeeded?", "This makes the expected business and user outcomes measurable."),
    "priority_scope": ("If the first release could deliver only the most important capability, what must it include?", "This helps identify a useful first release and separate later scope."),
    "failure_handling": ("If an integrated service is unavailable or an approval is denied, should work pause, retry, route to a person, or use another path?", "Your earlier answer mentioned integration or approval, so this follows up on failure handling."),
    "authorization_roles": ("Which roles may approve, change, or view each type of record, and how should those permissions be checked?", "This clarifies role-based access and authorization."),
    "auditability": ("Which user actions and decisions need an audit trail, and who must be able to review it?", "This identifies audit and traceability expectations."),
    "fraud_monitoring": ("Which transaction patterns should trigger a fraud review, hold, or alert?", "This focuses on fraud indicators and review paths."),
    "availability": ("When must this service be available, and what should users experience during an outage?", "This clarifies availability and continuity needs."),
    "response_time": ("What response time should users expect during normal and peak demand?", "The documents describe expected load; this clarifies the performance target."),
    "appointment_rules": ("How should the system handle appointment conflicts, cancellations, and clinician availability?", "This follows the healthcare scheduling workflow."),
    "assessment_results": ("How should examinations be scheduled, graded, reviewed, and results released?", "This covers the education assessment and results workflow."),
    "delivery_tracking": ("How should customers and couriers track an order, and what proof confirms delivery?", "This clarifies delivery status and handoff evidence."),
    "order_cancellation": ("Who can cancel an order at each stage, and how should refunds or restaurant and courier updates work?", "This clarifies cancellation and recovery behavior."),
    "payment_methods": ("Which payment methods should customers be able to use, and when is a payment captured or refunded?", "This defines payment options and transaction timing."),
}

DOMAIN_TOPICS = {
    "Banking": ["authorization_roles", "fraud_monitoring", "auditability", "security_privacy", "risk_compliance", "integration", "exceptions", "availability", "scale_performance", "testing", "delivery_operations"],
    "Payments": ["payment_methods", "failure_handling", "fraud_monitoring", "auditability", "security_privacy", "risk_compliance", "integration", "exceptions", "availability", "scale_performance", "testing", "delivery_operations"],
    "Lending": ["business_rules", "authorization_roles", "auditability", "risk_compliance", "integration", "exceptions", "security_privacy", "testing", "delivery_operations"],
    "Insurance": ["business_rules", "authorization_roles", "auditability", "risk_compliance", "exceptions", "integration", "security_privacy", "testing", "delivery_operations"],
    "Healthcare": ["appointment_rules", "authorization_roles", "auditability", "security_privacy", "risk_compliance", "integration", "exceptions", "availability", "scale_performance", "testing", "delivery_operations"],
    "Education": ["assessment_results", "authorization_roles", "auditability", "user_workflow", "security_privacy", "integration", "exceptions", "scale_performance", "testing", "delivery_operations"],
    "E-commerce": ["user_workflow", "integration", "exceptions", "security_privacy", "scale_performance", "testing", "delivery_operations"],
    "Logistics": ["integration", "exceptions", "scale_performance", "user_workflow", "testing", "delivery_operations"],
    "Food delivery": ["order_cancellation", "payment_methods", "delivery_tracking", "integration", "exceptions", "scale_performance", "user_workflow", "testing", "delivery_operations"],
    "Government/public services": ["risk_compliance", "security_privacy", "business_rules", "integration", "exceptions", "testing", "delivery_operations"],
    "HR/recruitment": ["security_privacy", "business_rules", "integration", "exceptions", "user_workflow", "testing", "delivery_operations"],
    "Manufacturing": ["safety", "integration", "exceptions", "scale_performance", "testing", "delivery_operations"],
    "Generic software system": ["user_workflow", "business_rules", "exceptions", "integration", "security_privacy", "scale_performance", "testing", "delivery_operations"],
}

def question_for(topic: str, domain: str) -> dict:
    prompt, explanation = TOPIC_QUESTIONS.get(topic, TOPIC_QUESTIONS["risk_compliance"])
    if topic == "safety":
        prompt, explanation = "What safety controls or production quality checks must be applied before work can continue?", "This checks production safety and quality controls."
    return {"id": f"{domain.casefold().replace('/', '-').replace(' ', '-')}-{topic}", "topic": topic, "prompt": prompt, "explanation": explanation}

def opener_for(domain: str) -> dict:
    return {"id": f"{domain.casefold().replace('/', '-').replace(' ', '-')}-workflow-opener", "topic": "workflow_and_outcomes", "prompt": OPENERS.get(domain, OPENERS["Generic software system"]), "explanation": f"Based on your project idea, this question focuses on {domain.casefold()} workflow and outcomes."}
