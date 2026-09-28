"""Request and response schemas for document ingestion and chunk inspection."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResult(BaseModel):
    document_id: str
    filename: str
    status: str
    chunk_count: int


class UploadedDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    page_count: int | None
    uploaded_at: datetime
    chunk_count: int = 0


class DocumentDetail(UploadedDocumentRead):
    stored_filename: str


class DocumentPreview(BaseModel):
    filename: str
    extracted_text: str
    page_count: int | None
    chunk_count: int


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: str
    chunk_index: int
    page_number: int | None
    chunk_text: str
    chunk_size: int
    metadata_json: dict = Field(default_factory=dict)
    embedding_model: str | None
    embedding_status: str | None
    chunk_hash: str | None
    token_count: int | None
    created_at: datetime


class DocumentChunkPage(BaseModel):
    items: list[DocumentChunkRead]
    total: int
    limit: int
    offset: int
