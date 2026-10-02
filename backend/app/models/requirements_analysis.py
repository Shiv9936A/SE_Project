"""Persisted requirements analysis runs awaiting stakeholder review."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RequirementsAnalysis(Base):
    __tablename__ = "requirements_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="needs_review")
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    project: Mapped["Project"] = relationship(back_populates="requirements_analyses")
    analysis_run: Mapped["AnalysisRun | None"] = relationship(back_populates="requirements_analysis")
    governance_analyses: Mapped[list["GovernanceAnalysis"]] = relationship(back_populates="requirements_analysis", cascade="all, delete-orphan")
