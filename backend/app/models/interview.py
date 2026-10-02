"""Persisted adaptive requirements interviews."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    __table_args__ = (UniqueConstraint("project_id", name="uq_interview_sessions_project_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    project_idea: Mapped[str] = mapped_column(Text, nullable=False)
    business_objective: Mapped[str] = mapped_column(Text, nullable=False)
    users_roles: Mapped[str] = mapped_column(Text, nullable=False)
    detected_domain: Mapped[str] = mapped_column(String(80), nullable=False)
    asked_questions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    answers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    covered_topics: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    uncovered_topics: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    current_question: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    question_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    maximum_questions: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="in_progress", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="interview")
