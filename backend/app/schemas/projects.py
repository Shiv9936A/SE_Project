"""Project API schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.questionnaire import QuestionnaireResponseRead
from app.schemas.documents import UploadedDocumentRead
from app.schemas.recommendations import RecommendationRead


class ProjectFields(BaseModel):
    project_name: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=12)
    domain: str = Field(min_length=2, max_length=100)
    organization_type: str = Field(min_length=2, max_length=120)
    team_size: int = Field(ge=1, le=10000)
    stakeholders: str = Field(min_length=2)
    initial_requirements: str | None = None


class ProjectCreate(ProjectFields):
    pass


class ProjectUpdate(BaseModel):
    project_name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, min_length=12)
    domain: str | None = Field(default=None, min_length=2, max_length=100)
    organization_type: str | None = Field(default=None, min_length=2, max_length=120)
    team_size: int | None = Field(default=None, ge=1, le=10000)
    stakeholders: str | None = Field(default=None, min_length=2)
    initial_requirements: str | None = None


class ProjectRead(ProjectFields):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectRead):
    questionnaire: QuestionnaireResponseRead | None = None
    documents: list[UploadedDocumentRead] = Field(default_factory=list)
    recommendation: RecommendationRead | None = None
