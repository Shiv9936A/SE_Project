"""Project and related persistence models."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    organization_type: Mapped[str] = mapped_column(String(120), nullable=False)
    team_size: Mapped[int] = mapped_column(Integer, nullable=False)
    stakeholders: Mapped[str] = mapped_column(Text, nullable=False)
    initial_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    questionnaire: Mapped["QuestionnaireResponse | None"] = relationship(back_populates="project", cascade="all, delete-orphan", uselist=False)
    documents: Mapped[list["UploadedDocument"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    recommendations: Mapped[list["GeneratedRecommendation"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    interview: Mapped["InterviewSession | None"] = relationship(back_populates="project", cascade="all, delete-orphan", uselist=False)
    requirements_analyses: Mapped[list["RequirementsAnalysis"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    governance_analyses: Mapped[list["GovernanceAnalysis"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="project", cascade="all, delete-orphan", order_by="AnalysisRun.version.desc()")

    @property
    def recommendation(self):
        current = [row for row in self.recommendations
                   if row.scoring_method in {"rule_based_v2", "langgraph_v2"}]
        return max(current, key=lambda item: item.created_at) if current else None
