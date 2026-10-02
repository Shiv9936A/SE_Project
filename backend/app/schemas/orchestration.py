"""Public response contract for one LangGraph orchestration run."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.governance_analysis import GovernanceAnalysisRead
from app.schemas.requirements_analysis import RequirementsAnalysisRead


class OrchestrationAgentStatus(BaseModel):
    name: Literal["requirements", "governance"]
    status: Literal["completed", "partial", "failed", "skipped"]


class OrchestrationIssue(BaseModel):
    code: str
    message: str
    recoverable: bool = False


class OrchestrationResult(BaseModel):
    orchestration_id: str
    analysis_run_id: str
    analysis_run_version: int
    project_id: str
    status: Literal["completed", "partial", "failed"]
    requirements_analysis_id: str | None = None
    governance_analysis_id: str | None = None
    agents: list[OrchestrationAgentStatus]
    requirements_analysis: RequirementsAnalysisRead | None = None
    governance_analysis: GovernanceAnalysisRead | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[OrchestrationIssue] = Field(default_factory=list)
    created_at: datetime


class AnalysisRunSummary(BaseModel):
    id: str
    project_id: str
    version: int
    status: Literal["running", "completed", "partial", "failed"]
    orchestration_version: str
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    requirements_analysis_id: str | None = None
    governance_analysis_id: str | None = None
    requirement_count: int = 0
    ambiguity_count: int = 0
    conflict_count: int = 0
    risk_count: int = 0
    methodology: str | None = None
    warnings: list = Field(default_factory=list)
    errors: list = Field(default_factory=list)


class AnalysisRunDetail(AnalysisRunSummary):
    agents: list[OrchestrationAgentStatus] = Field(default_factory=list)
    requirements_analysis: RequirementsAnalysisRead | None = None
    governance_analysis: GovernanceAnalysisRead | None = None
