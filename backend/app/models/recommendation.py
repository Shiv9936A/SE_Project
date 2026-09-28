"""Persisted SDLC recommendation results."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class GeneratedRecommendation(Base):
    __tablename__ = "generated_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    recommended_sdlc: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    risk_factors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    alternatives: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    scoring_method: Mapped[str] = mapped_column(String(80), default="rule_based_v1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="recommendations")
