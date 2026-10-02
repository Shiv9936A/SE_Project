"""Project-scoped similarity search over persisted ChromaDB vectors."""
import logging

from langchain_core.embeddings import Embeddings
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.services.embedding_service import create_embeddings
from app.services.project_service import require_project
from app.services.vector_store_service import ChromaVectorStore

logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(self, embeddings: Embeddings | None = None, vector_store: ChromaVectorStore | None = None):
        self.embeddings = embeddings
        self.vector_store = vector_store or ChromaVectorStore()

    def search(self, db: Session, project_id: str, query: str, top_k: int = 5,
               filters: dict | None = None, score_threshold: float | None = None) -> list[dict]:
        require_project(db, project_id)
        query = query.strip()
        if not query:
            raise AppError("Search query cannot be empty.", 422)
        if top_k < 1 or top_k > 50:
            raise AppError("top_k must be between 1 and 50.", 422)
        if filters and "project_id" in filters:
            raise AppError("Metadata filters cannot override project_id.", 422)
        try:
            if self.embeddings is None:
                self.embeddings = create_embeddings()
            vector = self.embeddings.embed_query(query)
            where = {"project_id": project_id}
            if filters:
                where = {"$and": [{"project_id": project_id}, filters]}
            results = self.vector_store.search(vector, top_k, where)
        except AppError:
            raise
        except Exception as exc:
            logger.exception("Project vector retrieval failed", extra={
                "project_id": project_id,
                "embedding_provider": settings.embedding_provider,
                "embedding_model": settings.embedding_model,
                "failure_type": type(exc).__name__,
            })
            raise AppError("Project document search is temporarily unavailable.", 503) from exc
        if score_threshold is not None:
            results = [result for result in results if result["score"] >= score_threshold]
        return results


retrieval_service = RetrievalService()
