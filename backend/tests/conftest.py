from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(settings, "upload_directory", tmp_path / "uploads")

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def project_payload() -> dict:
    return {
        "project_name": "Small business lending",
        "description": "Modernize the loan application and decision workflow for small businesses.",
        "domain": "Loan processing",
        "organization_type": "Retail bank",
        "team_size": 10,
        "stakeholders": "Applicants, lending operations, product, security, compliance",
        "initial_requirements": "Collect applications and show an auditable decision status.",
    }


@pytest.fixture
def questionnaire_payload() -> dict:
    return {
        "requirement_stability": "Moderately Changing",
        "risk_level": "High",
        "security_criticality": "High",
        "compliance_criticality": "High",
        "expected_changes": "Occasional",
        "continuous_delivery": "Yes",
        "legacy_integration": "Yes",
        "formal_verification": "Yes",
        "stakeholder_availability": "Medium",
        "complexity": "High",
        "project_size": "Large",
        "failure_impact": "High",
        "testing_requirement": "Extensive",
        "budget_constraint": "Medium",
        "timeline_constraint": "Strict",
    }
