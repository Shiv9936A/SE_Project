"""RAG orchestration, evaluation diagnostics, and persisted conversation history."""
import logging
import re
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError
from app.models import Conversation, Message, Project, QuestionnaireResponse
from app.services.llm_service import llm_service
from app.services.project_service import require_project
from app.services.prompt_service import PromptService
from app.services.retrieval_service import retrieval_service

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self, retriever=None, prompts: PromptService | None = None, llm=None):
        self.retriever = retriever or retrieval_service
        self.prompts = prompts or PromptService()
        self.llm = llm or llm_service

    @staticmethod
    def _project_context(project: Project) -> dict:
        return {
            "project_name": project.project_name,
            "description": project.description,
            "domain": project.domain,
            "organization_type": project.organization_type,
            "team_size": project.team_size,
            "stakeholders": project.stakeholders,
            "initial_requirements": project.initial_requirements,
        }

    @staticmethod
    def _token_estimate(text: str) -> int:
        return len(re.findall(r"\w+|[^\w\s]", text))

    def _prepare(self, db: Session, project_id: str, question: str, top_k: int,
                 score_threshold: float, filters: dict | None) -> dict:
        project = require_project(db, project_id)
        question = question.strip()
        if not question:
            raise AppError("Question cannot be empty.", 422)

        questionnaire = db.scalar(select(QuestionnaireResponse).where(
            QuestionnaireResponse.project_id == project_id,
        ))
        questionnaire_context = None
        if questionnaire is not None:
            questionnaire_context = {
                column.name: getattr(questionnaire, column.name)
                for column in QuestionnaireResponse.__table__.columns
                if column.name not in {"id", "project_id", "created_at"}
            }

        retrieval_started = perf_counter()
        chunks = self.retriever.search(
            db, project_id, question, top_k=top_k, filters=filters,
            score_threshold=score_threshold,
        )
        retrieval_time_ms = (perf_counter() - retrieval_started) * 1000
        system_prompt, user_prompt = self.prompts.build(
            self._project_context(project), questionnaire_context, chunks, question,
        )
        return {
            "project": project,
            "question": question,
            "chunks": chunks,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "retrieval_time_ms": retrieval_time_ms,
        }

    def _generate(self, prepared: dict) -> tuple[str, float]:
        started = perf_counter()
        try:
            answer = self.llm.generate(prepared["system_prompt"], prepared["user_prompt"])
        except Exception as exc:
            logger.error("RAG answer generation failed", extra={
                "project_id": prepared["project"].id,
                "failure_type": type(exc).__name__,
            })
            raise
        return answer, (perf_counter() - started) * 1000

    def _log_metrics(self, prepared: dict, answer: str, generation_time_ms: float) -> dict:
        full_prompt = prepared["system_prompt"] + "\n\n" + prepared["user_prompt"]
        metrics = {
            "retrieval_time_ms": round(prepared["retrieval_time_ms"], 3),
            "prompt_size_chars": len(full_prompt),
            "prompt_token_estimate": self._token_estimate(full_prompt),
            "answer_generation_time_ms": round(generation_time_ms, 3),
            "answer_token_estimate": self._token_estimate(answer),
        }
        logger.info(
            "RAG request metrics",
            extra={"project_id": prepared["project"].id,
                   "retrieved_chunk_count": len(prepared["chunks"]), **metrics},
        )
        return metrics

    def ask(self, db: Session, project_id: str, question: str, top_k: int = 5,
            score_threshold: float = 0.2, filters: dict | None = None,
            conversation_id: str | None = None) -> dict:
        conversation = None
        if conversation_id:
            conversation = db.scalar(select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.project_id == project_id,
            ))
            if conversation is None:
                raise AppError("Conversation not found for this project.", 404)
        prepared = self._prepare(db, project_id, question, top_k, score_threshold, filters)

        degraded = False
        try:
            answer, generation_time_ms = self._generate(prepared)
        except AppError as exc:
            if exc.status_code != 502:
                raise
            logger.warning(
                "LLM unavailable; returning retrieved evidence without synthesis",
                extra={"project_id": project_id, "retrieved_chunk_count": len(prepared["chunks"])},
            )
            answer = self._retrieval_only_answer(prepared["chunks"])
            generation_time_ms = 0.0
            degraded = True
        self._log_metrics(prepared, answer, generation_time_ms)
        if conversation is None:
            conversation = Conversation(project_id=project_id)
            db.add(conversation)
        conversation.messages.extend([
            Message(role="user", content=prepared["question"]),
            Message(role="assistant", content=answer),
        ])
        db.commit()
        db.refresh(conversation)
        return {
            "answer": answer,
            "sources": self._sources(prepared["chunks"]),
            "conversation_id": conversation.id,
            "degraded": degraded,
        }

    @staticmethod
    def _retrieval_only_answer(chunks: list[dict]) -> str:
        """Provide transparent evidence during a provider outage; do not imply LLM synthesis."""
        notice = (
            "The language model is temporarily unavailable, so I could not synthesize an answer. "
            "The excerpts below are retrieved project evidence only; review them directly."
        )
        if not chunks:
            return (
                notice + " No relevant embedded document chunks were retrieved, so there is no "
                "document evidence to show. Try again when the language model is available."
            )
        excerpts = []
        for chunk in chunks:
            filename = chunk.get("filename") or chunk.get("document_id")
            text = " ".join(str(chunk.get("text", "")).split())
            if len(text) > 600:
                text = text[:597].rstrip() + "..."
            excerpts.append(f"- {filename} [chunk_id={chunk['chunk_id']}]: {text}")
        return notice + "\n\nRetrieved excerpts:\n" + "\n".join(excerpts)

    def evaluate(self, db: Session, project_id: str, question: str, top_k: int = 5,
                 score_threshold: float = 0.2, filters: dict | None = None) -> dict:
        prepared = self._prepare(db, project_id, question, top_k, score_threshold, filters)
        answer, generation_time_ms = self._generate(prepared)
        metrics = self._log_metrics(prepared, answer, generation_time_ms)
        return {
            "project_id": project_id,
            "question": prepared["question"],
            "retrieved_chunks": self._ranked_chunks(prepared["chunks"]),
            "selected_context": self.prompts.render_context(prepared["chunks"]),
            "final_prompt": {
                "system": prepared["system_prompt"],
                "user": prepared["user_prompt"],
            },
            "answer": answer,
            "metrics": metrics,
        }

    def debug_retrieval(self, db: Session, project_id: str, question: str, top_k: int = 5,
                        score_threshold: float = 0.2, filters: dict | None = None) -> dict:
        project = require_project(db, project_id)
        started = perf_counter()
        chunks = self.retriever.search(
            db, project_id, question, top_k=top_k, filters=filters,
            score_threshold=score_threshold,
        )
        retrieval_time_ms = (perf_counter() - started) * 1000
        logger.info("RAG retrieval debug", extra={
            "project_id": project_id,
            "retrieval_time_ms": round(retrieval_time_ms, 3),
            "retrieved_chunk_count": len(chunks),
        })
        return {
            "project_id": project.id,
            "question": question,
            "top_k": top_k,
            "score_threshold": score_threshold,
            "retrieval_time_ms": round(retrieval_time_ms, 3),
            "retrieved_chunks": self._ranked_chunks(chunks),
        }

    @staticmethod
    def recent_conversations(db: Session, project_id: str, limit: int = 5) -> list[Conversation]:
        require_project(db, project_id)
        statement = (select(Conversation).options(selectinload(Conversation.messages))
                     .where(Conversation.project_id == project_id)
                     .order_by(Conversation.created_at.desc())
                     .limit(limit))
        return list(db.scalars(statement).all())

    @staticmethod
    def _ranked_chunks(chunks: list[dict]) -> list[dict]:
        return [
            {"rank": index, "chunk_id": str(chunk["chunk_id"]),
             "document_id": chunk["document_id"], "score": chunk["score"],
             "text": chunk["text"], "metadata": chunk.get("metadata", {})}
            for index, chunk in enumerate(chunks, start=1)
        ]

    @staticmethod
    def _sources(chunks: list[dict]) -> list[dict]:
        return [
            {"chunk_id": str(chunk["chunk_id"]), "document_id": chunk["document_id"], "score": chunk["score"]}
            for chunk in chunks
        ]

    @staticmethod
    def get_conversation(db: Session, project_id: str, conversation_id: str) -> Conversation:
        require_project(db, project_id)
        conversation = db.scalar(
            select(Conversation).options(selectinload(Conversation.messages)).where(
                Conversation.project_id == project_id,
                Conversation.id == conversation_id,
            )
        )
        if conversation is None:
            raise AppError("Conversation not found for this project.", 404)
        return conversation


rag_service = RAGService()
