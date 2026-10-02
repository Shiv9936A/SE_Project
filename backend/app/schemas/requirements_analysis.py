"""Strict contracts for evidence-grounded requirements analysis."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RequirementCategory = Literal[
    "functional", "non_functional", "business_rule", "data", "integration",
    "security_privacy_compliance", "operational",
]
Priority = Literal["critical", "high", "medium", "low"]
SourceType = Literal["project_profile", "questionnaire", "interview", "uploaded_document", "rag_evidence", "inferred"]
QualityLevel = Literal["high", "medium", "low"]


class RequirementItem(BaseModel):
    requirement_id: str = Field(pattern=r"^REQ-[A-Z]+-\d{3}$")
    category: RequirementCategory
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(min_length=5, max_length=3000)
    priority: Priority
    confidence: float = Field(ge=0, le=1)
    source_type: SourceType
    source_reference: str | None = Field(default=None, max_length=200)
    evidence: str = Field(default="", max_length=700)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=12)
    ambiguities: list[str] = Field(default_factory=list, max_length=12)
    dependencies: list[str] = Field(default_factory=list, max_length=12)
    tags: list[str] = Field(default_factory=list, max_length=16)
    testability: QualityLevel
    missing_information: list[str] = Field(default_factory=list, max_length=12)


class AmbiguityItem(BaseModel):
    description: str = Field(min_length=3, max_length=1000)
    related_requirement_id: str | None = None
    severity: Priority
    clarification_question: str = Field(min_length=3, max_length=1000)
    source_reference: str | None = None


class EvidenceCitation(BaseModel):
    source_type: Literal["project_profile", "questionnaire", "interview", "uploaded_document", "rag_evidence"]
    source_reference: str = Field(min_length=1, max_length=200)
    evidence: str = Field(min_length=1, max_length=700)


class ConflictItem(BaseModel):
    description: str = Field(min_length=3, max_length=1000)
    severity: Priority
    sources: list[EvidenceCitation] = Field(min_length=2, max_length=6)
    clarification_question: str = Field(min_length=3, max_length=1000)


class CoverageItem(BaseModel):
    area: str = Field(min_length=2, max_length=100)
    status: Literal["covered", "partial", "missing"]
    note: str = Field(min_length=2, max_length=500)


class RequirementsAnalysisResult(BaseModel):
    summary: str = Field(min_length=3, max_length=3000)
    requirements: list[RequirementItem] = Field(default_factory=list, max_length=250)
    ambiguities: list[AmbiguityItem] = Field(default_factory=list, max_length=100)
    conflicts: list[ConflictItem] = Field(default_factory=list, max_length=100)
    completeness: list[CoverageItem] = Field(default_factory=list, max_length=30)
    clarification_questions: list[str] = Field(default_factory=list, max_length=100)
    quality_assessment: dict[str, QualityLevel] = Field(default_factory=dict)
    evidence_sources: list[EvidenceCitation] = Field(default_factory=list, max_length=100)


class RequirementsAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analysis_id: str
    project_id: str
    version: int
    status: Literal["needs_review", "partial", "reviewed"]
    provider: str
    model: str
    created_at: datetime
    summary: str
    requirements: list[RequirementItem]
    ambiguities: list[AmbiguityItem]
    conflicts: list[ConflictItem]
    completeness: list[CoverageItem]
    clarification_questions: list[str]
    quality_assessment: dict[str, QualityLevel]
    evidence_sources: list[EvidenceCitation]


class RequirementsAnalysisRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=10)
