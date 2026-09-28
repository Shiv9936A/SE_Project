"""RAG question, answer, source, and conversation schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10000)
    conversation_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float = Field(default=0.2, ge=-1.0, le=1.0)
    filters: dict | None = None


class RAGSource(BaseModel):
    chunk_id: str
    document_id: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[RAGSource]
    conversation_id: str
    degraded: bool = False


class RAGEvaluationRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10000)
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float = Field(default=0.2, ge=-1.0, le=1.0)
    filters: dict | None = None


class RankedChunk(BaseModel):
    rank: int
    chunk_id: str
    document_id: str
    score: float
    text: str
    metadata: dict


class FinalPrompt(BaseModel):
    system: str
    user: str


class RAGMetrics(BaseModel):
    retrieval_time_ms: float
    prompt_size_chars: int
    prompt_token_estimate: int
    answer_generation_time_ms: float
    answer_token_estimate: int


class RAGEvaluationResponse(BaseModel):
    project_id: str
    question: str
    retrieved_chunks: list[RankedChunk]
    selected_context: str
    final_prompt: FinalPrompt
    answer: str
    metrics: RAGMetrics


class RetrievalDebugResponse(BaseModel):
    project_id: str
    question: str
    top_k: int
    score_threshold: float
    retrieval_time_ms: float
    retrieved_chunks: list[RankedChunk]


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conversation_id: str
    role: str
    content: str
    created_at: datetime


class ConversationRead(BaseModel):
    id: str
    project_id: str
    created_at: datetime
    messages: list[MessageRead]
