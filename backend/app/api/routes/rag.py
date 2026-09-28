"""Grounded project question answering and conversation history."""
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.schemas.rag import (
    AskRequest, AskResponse, ConversationRead, RAGEvaluationRequest,
    RAGEvaluationResponse, RetrievalDebugResponse,
)
from app.services.rag_service import rag_service

router = APIRouter(prefix="/projects", tags=["RAG"])


@router.post("/{project_id}/ask", response_model=AskResponse, summary="Ask a grounded project question")
def ask_project(project_id: str, payload: AskRequest, db: Session = Depends(get_db)):
    """Answer from project metadata, questionnaire responses, and thresholded retrieved chunks."""
    return rag_service.ask(
        db, project_id, payload.question, top_k=payload.top_k,
        score_threshold=payload.score_threshold, filters=payload.filters,
        conversation_id=payload.conversation_id,
    )


@router.post("/{project_id}/evaluate-rag", response_model=RAGEvaluationResponse,
             summary="Evaluate and inspect a RAG answer")
def evaluate_rag(project_id: str, payload: RAGEvaluationRequest, db: Session = Depends(get_db)):
    """Return retrieved chunks, selected context, rendered prompt, answer, and timing/token metrics."""
    return rag_service.evaluate(
        db, project_id, payload.question, top_k=payload.top_k,
        score_threshold=payload.score_threshold, filters=payload.filters,
    )


@router.get("/{project_id}/retrieval-debug", response_model=RetrievalDebugResponse,
            summary="Inspect ranked retrieval results")
def retrieval_debug(
    project_id: str,
    question: str = Query(min_length=1, max_length=10000),
    top_k: int = Query(default=5, ge=1, le=50),
    score_threshold: float = Query(default=0.2, ge=-1.0, le=1.0),
    filters: str | None = Query(default=None, description="Optional metadata filter encoded as a JSON object"),
    db: Session = Depends(get_db),
):
    """Return retrieved chunk text, scores, metadata, and one-based rank without calling the LLM."""
    metadata_filters = None
    if filters:
        try:
            metadata_filters = json.loads(filters)
        except json.JSONDecodeError as exc:
            raise AppError("filters must be a valid JSON object.", 422) from exc
        if not isinstance(metadata_filters, dict):
            raise AppError("filters must be a JSON object.", 422)
    return rag_service.debug_retrieval(project_id=project_id, db=db, question=question,
                                       top_k=top_k, score_threshold=score_threshold,
                                       filters=metadata_filters)


@router.get("/{project_id}/conversations/{conversation_id}", response_model=ConversationRead,
            summary="Get persisted conversation history")
def get_conversation(project_id: str, conversation_id: str, db: Session = Depends(get_db)):
    """Return a project's conversation and its ordered user/assistant messages."""
    return rag_service.get_conversation(db, project_id, conversation_id)


@router.get("/{project_id}/conversations", response_model=list[ConversationRead],
            summary="List recent project conversations")
def list_project_conversations(project_id: str, limit: int = Query(default=5, ge=1, le=50),
                               db: Session = Depends(get_db)):
    """List recent conversations with ordered messages for project dashboards."""
    return rag_service.recent_conversations(db, project_id, limit)
