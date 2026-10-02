"""Validated response contracts for governance and SDLC planning."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MethodologyName = Literal[
    "Agile", "Waterfall", "Iterative", "Spiral", "Hybrid",
    "V-Model", "Incremental", "Agile Scrum", "RAD",
]
Level = Literal["low", "medium", "high", "unknown"]
Severity = Literal["low", "medium", "high"]
PhaseName = Literal[
    "Requirements", "Architecture & Design", "Implementation", "Testing",
    "Security Validation", "User Acceptance", "Deployment", "Monitoring & Maintenance",
]
TestLevel = Literal[
    "unit_testing", "integration_testing", "system_testing",
    "acceptance_testing", "security_testing", "performance_testing",
]
BaselineMethod = Literal["Waterfall", "V-Model", "Incremental", "Iterative", "Spiral", "Agile Scrum", "RAD"]


class BaselineScore(BaseModel):
    model: BaselineMethod
    score: int = Field(ge=0, le=100)


class ReasoningFactor(BaseModel):
    factor: str = Field(min_length=2, max_length=100)
    observation: str = Field(min_length=3, max_length=700)
    impact: str = Field(min_length=3, max_length=700)
    source_references: list[str] = Field(min_length=1, max_length=12)


class MethodologyRecommendation(BaseModel):
    name: MethodologyName
    confidence: float = Field(ge=0, le=1)
    reasoning: list[ReasoningFactor] = Field(min_length=1, max_length=12)


class ProjectAssessment(BaseModel):
    complexity: Level
    risk_level: Level
    requirements_stability: Literal["stable", "moderate", "volatile", "unknown"]
    integration_complexity: Level
    security_sensitivity: Level
    compliance_impact: Level


class LifecyclePhase(BaseModel):
    phase: PhaseName
    activities: list[str] = Field(default_factory=list, max_length=16)
    deliverables: list[str] = Field(default_factory=list, max_length=12)
    exit_criteria: list[str] = Field(default_factory=list, max_length=12)
    requirement_references: list[str] = Field(default_factory=list, max_length=30)


class RecommendationItem(BaseModel):
    recommendation: str = Field(min_length=3, max_length=500)
    requirement_references: list[str] = Field(default_factory=list, max_length=30)


class TestingStrategy(BaseModel):
    unit_testing: list[RecommendationItem] = Field(default_factory=list, max_length=12)
    integration_testing: list[RecommendationItem] = Field(default_factory=list, max_length=12)
    system_testing: list[RecommendationItem] = Field(default_factory=list, max_length=12)
    acceptance_testing: list[RecommendationItem] = Field(default_factory=list, max_length=12)
    security_testing: list[RecommendationItem] = Field(default_factory=list, max_length=12)
    performance_testing: list[RecommendationItem] = Field(default_factory=list, max_length=12)


class SecurityActivity(BaseModel):
    activity: str = Field(min_length=3, max_length=500)
    requirement_references: list[str] = Field(default_factory=list, max_length=30)


class DocumentationItem(BaseModel):
    document: str = Field(min_length=2, max_length=160)
    rationale: str = Field(min_length=3, max_length=500)
    requirement_references: list[str] = Field(default_factory=list, max_length=30)


class GovernanceCheckpoint(BaseModel):
    checkpoint: str = Field(min_length=2, max_length=160)
    purpose: str = Field(min_length=3, max_length=500)
    entry_conditions: list[str] = Field(default_factory=list, max_length=12)
    exit_conditions: list[str] = Field(default_factory=list, max_length=12)
    required_artifacts: list[str] = Field(default_factory=list, max_length=12)


class GovernanceRisk(BaseModel):
    risk_id: str = Field(pattern=r"^RISK-\d{3}$")
    title: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=3, max_length=800)
    severity: Severity
    likelihood: Severity
    mitigation: str = Field(min_length=3, max_length=800)
    source_references: list[str] = Field(min_length=1, max_length=16)
    basis: Literal["observed", "potential"] = "potential"


class QualityGate(BaseModel):
    gate: str = Field(min_length=2, max_length=160)
    checks: list[str] = Field(min_length=1, max_length=16)
    requirement_references: list[str] = Field(default_factory=list, max_length=30)


class GovernanceEvidence(BaseModel):
    source_type: Literal["project_profile", "requirements_analysis", "questionnaire", "rag_evidence"]
    source_reference: str = Field(min_length=1, max_length=200)
    observation: str = Field(min_length=2, max_length=700)


class GovernanceAnalysisResult(BaseModel):
    project_id: str
    requirements_analysis_id: str
    methodology: MethodologyRecommendation
    project_assessment: ProjectAssessment
    baseline_scores: list[BaselineScore] = Field(default_factory=list, max_length=12)
    development_lifecycle: list[LifecyclePhase] = Field(min_length=1, max_length=8)
    testing_strategy: TestingStrategy
    security_governance: list[SecurityActivity] = Field(default_factory=list, max_length=20)
    documentation_requirements: list[DocumentationItem] = Field(default_factory=list, max_length=20)
    governance_checkpoints: list[GovernanceCheckpoint] = Field(default_factory=list, max_length=20)
    risks: list[GovernanceRisk] = Field(default_factory=list, max_length=40)
    quality_gates: list[QualityGate] = Field(default_factory=list, max_length=20)
    prerequisites: list[str] = Field(default_factory=list, max_length=100)
    evidence: list[GovernanceEvidence] = Field(default_factory=list, max_length=100)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=100)
    fallback_reason: str | None = Field(default=None, max_length=80)


class GovernanceAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    requirements_analysis_id: str
    version: int
    status: Literal["needs_review", "partial", "reviewed"]
    provider: str
    model: str
    created_at: datetime
    updated_at: datetime
    result: GovernanceAnalysisResult

