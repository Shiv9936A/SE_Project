"""Persist versioned governance plans associated with a requirements analysis."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class GovernanceAnalysis(Base):
    __tablename__ = "governance_analyses"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_governance_analysis_project_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    requirements_analysis_id: Mapped[str] = mapped_column(ForeignKey("requirements_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    methodology: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="needs_review")
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project: Mapped["Project"] = relationship(back_populates="governance_analyses")
    requirements_analysis: Mapped["RequirementsAnalysis"] = relationship(back_populates="governance_analyses")
    analysis_run: Mapped["AnalysisRun | None"] = relationship(back_populates="governance_analysis")
