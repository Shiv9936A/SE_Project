"""SDLC questionnaire answers attached to a project."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class QuestionnaireResponse(Base):
    __tablename__ = "questionnaire_responses"
    __table_args__ = (UniqueConstraint("project_id", name="uq_questionnaire_project"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_stability: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    security_criticality: Mapped[str] = mapped_column(String(20), nullable=False)
    compliance_criticality: Mapped[str] = mapped_column(String(20), nullable=False)
    expected_changes: Mapped[str] = mapped_column(String(20), nullable=False)
    continuous_delivery: Mapped[str] = mapped_column(String(3), nullable=False)
    legacy_integration: Mapped[str] = mapped_column(String(3), nullable=False)
    formal_verification: Mapped[str] = mapped_column(String(3), nullable=False)
    stakeholder_availability: Mapped[str] = mapped_column(String(20), nullable=False)
    complexity: Mapped[str] = mapped_column(String(20), nullable=False)
    project_size: Mapped[str] = mapped_column(String(20), nullable=False)
    failure_impact: Mapped[str] = mapped_column(String(20), nullable=False)
    testing_requirement: Mapped[str] = mapped_column(String(20), nullable=False)
    budget_constraint: Mapped[str] = mapped_column(String(20), nullable=False)
    timeline_constraint: Mapped[str] = mapped_column(String(20), nullable=False)
    stakeholder_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="questionnaire")
