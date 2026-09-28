"""SDLC recommendation schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AlternativeSDLC(BaseModel):
    model: str
    score: int = Field(ge=0, le=100)
    rationale: str


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    recommended_sdlc: str
    confidence_score: float = Field(ge=0, le=100)
    justification: str
    risk_factors: list[str]
    alternatives: list[AlternativeSDLC]
    scoring_method: str
    created_at: datetime
