"""Persistent, versioned orchestration executions for a project."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_analysis_runs_project_version"),
        UniqueConstraint("active_project_id", name="uq_analysis_runs_active_project"),
        CheckConstraint("status IN ('running', 'completed', 'partial', 'failed')", name="ck_analysis_runs_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="running")
    active_project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    orchestration_version: Mapped[str] = mapped_column(String(40), nullable=False, default="langgraph-v1")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    errors_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    agent_statuses_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    project: Mapped["Project"] = relationship(back_populates="analysis_runs")
    requirements_analysis: Mapped["RequirementsAnalysis | None"] = relationship(back_populates="analysis_run", uselist=False)
    governance_analysis: Mapped["GovernanceAnalysis | None"] = relationship(back_populates="analysis_run", uselist=False)
