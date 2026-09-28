"""Embedding and vector search API schemas."""
from pydantic import BaseModel, Field


class EmbeddingResult(BaseModel):
    document_id: str
    chunks_processed: int
    vectors_created: int


class EmbeddingStatus(BaseModel):
    total_chunks: int
    completed_chunks: int
    failed_chunks: int
    status: str


class SearchRequest(BaseModel):
    project_id: str
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=50)
    filters: dict | None = None


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    score: float
    text: str
