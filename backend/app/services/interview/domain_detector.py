"""Deterministic project domain detection with a safe generic fallback."""
import re

DOMAIN_KEYWORDS = {
    "Banking": ("bank", "banking", "account", "branch", "digital banking"),
    "Payments": ("payment", "payments", "checkout", "transaction", "payment gateway"),
    "Lending": ("loan", "lending", "credit application", "underwriting", "borrower"),
    "Insurance": ("insurance", "claim", "policyholder", "premium", "underwriting"),
    "Healthcare": ("hospital", "healthcare", "patient", "clinic", "appointment", "medical"),
    "Education": ("college", "school", "exam", "examination", "student", "course", "education"),
    "E-commerce": ("e-commerce", "ecommerce", "online store", "shopping cart", "catalogue", "catalog"),
    "Logistics": ("logistics", "shipment", "shipping", "fleet", "warehouse delivery", "tracking"),
    "Food delivery": ("food delivery", "restaurant delivery", "meal delivery", "food ordering"),
    "Government/public services": ("government", "public service", "citizen", "municipal", "permit"),
    "HR/recruitment": ("recruitment", "hiring", "applicant tracking", "payroll", "human resources", "hr system"),
    "Manufacturing": ("manufacturing", "factory", "production line", "plant operations"),
}


def detect_domain(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    matches = [(len(keyword), domain) for domain, words in DOMAIN_KEYWORDS.items() for keyword in words if re.search(rf"\b{re.escape(keyword)}\b", normalized)]
    if not matches:
        return "Generic software system"
    # Prefer the most specific phrase, with stable domain order for ties.
    return max(matches, key=lambda item: item[0])[1]
