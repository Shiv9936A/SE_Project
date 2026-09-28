"""Contracts for the LangGraph SDLC recommendation and comparison APIs."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SDLCModel = Literal[
    "Waterfall", "V-Model", "Incremental", "Iterative", "Spiral",
    "Agile Scrum", "RAD",
]


class SDLCModelScore(BaseModel):
    model: SDLCModel
    score: int = Field(ge=0, le=100)


class SDLCAlternative(BaseModel):
    model: SDLCModel
    score: int = Field(ge=0, le=100)
    rationale: str


class RecommendationSource(BaseModel):
    chunk_id: str
    document_id: str
    score: float
    filename: str | None = None


class SDLCRecommendationRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=50)
    filters: dict | None = None


class SDLCRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    recommended_model: SDLCModel
    confidence: float = Field(ge=0, le=100)
    reasoning: str
    alternative_models: list[SDLCAlternative]
    strengths: list[str]
    risks: list[str]
    implementation_notes: list[str]
    model_scores: list[SDLCModelScore]
    sources: list[RecommendationSource]
    created_at: datetime


class SDLCComparisonRequest(BaseModel):
    model_a: SDLCModel
    model_b: SDLCModel
    top_k: int = Field(default=5, ge=1, le=50)
    filters: dict | None = None


class SDLCComparisonResponse(BaseModel):
    project_id: str
    model_a: SDLCModel
    model_b: SDLCModel
    score_a: int = Field(ge=0, le=100)
    score_b: int = Field(ge=0, le=100)
    why_model_a_fits: str
    why_model_b_fits: str
    tradeoffs: list[str]
    risk_analysis: list[str]
    sources: list[RecommendationSource]
