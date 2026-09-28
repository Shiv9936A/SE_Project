"""SDLC questionnaire schemas and enums."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QuestionnaireResponseCreate(BaseModel):
    requirement_stability: Literal["Stable", "Moderately Changing", "Frequently Changing"]
    risk_level: Literal["Low", "Medium", "High"]
    security_criticality: Literal["Low", "Medium", "High"]
    compliance_criticality: Literal["Low", "Medium", "High"]
    expected_changes: Literal["Rare", "Occasional", "Frequent"]
    continuous_delivery: Literal["Yes", "No"]
    legacy_integration: Literal["Yes", "No"]
    formal_verification: Literal["Yes", "No"]
    stakeholder_availability: Literal["Low", "Medium", "High"]
    complexity: Literal["Low", "Medium", "High"]
    project_size: Literal["Small", "Medium", "Large"]
    failure_impact: Literal["Low", "Medium", "High"]
    testing_requirement: Literal["Basic", "Moderate", "Extensive"]
    budget_constraint: Literal["Low", "Medium", "High"]
    timeline_constraint: Literal["Flexible", "Moderate", "Strict"]
    stakeholder_notes: str | None = Field(default=None, max_length=10000)


class QuestionnaireResponseRead(QuestionnaireResponseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: str
    created_at: datetime
