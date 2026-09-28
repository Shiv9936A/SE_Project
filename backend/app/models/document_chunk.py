"""Persisted, page-aware text chunks for later vector indexing."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("uploaded_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    chunk_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    document: Mapped["UploadedDocument"] = relationship(back_populates="chunks")
