"""Provider-swappable LangChain embeddings and PostgreSQL-to-Chroma indexing."""
from hashlib import sha256
import logging
import re

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.models import DocumentChunk
from app.services.document_service import DocumentService
from app.services.vector_store_service import ChromaVectorStore

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddings(Embeddings):
    """LangChain adapter for a locally hosted sentence-transformers model."""

    def __init__(self, model_name: str):
        # Import lazily so selecting OpenAI does not initialize the local ML stack.
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return vectors.tolist() if hasattr(vectors, "tolist") else [list(vector) for vector in vectors]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]


def create_embeddings() -> Embeddings:
    """Return the configured LangChain embedding provider."""
    provider = settings.embedding_provider.lower()
    if provider == "local":
        return SentenceTransformerEmbeddings(model_name=settings.embedding_model)
    if provider == "openai":
        if not settings.openai_api_key:
            raise AppError("OPENAI_API_KEY is required to generate embeddings.", 503)
        return OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)
    raise AppError(f"Unsupported embedding provider '{settings.embedding_provider}'.", 503)


class EmbeddingService:
    def __init__(self, embeddings: Embeddings | None = None, vector_store: ChromaVectorStore | None = None):
        self.embeddings = embeddings
        self.vector_store = vector_store or ChromaVectorStore()
        self.document_service = DocumentService()

    @staticmethod
    def _token_count(text: str) -> int:
        # Portable approximation: count word and punctuation units without downloading vocab files.
        return len(re.findall(r"\w+|[^\w\s]", text))

    def _provider(self) -> Embeddings:
        if self.embeddings is None:
            self.embeddings = create_embeddings()
        return self.embeddings

    def embed_document(self, db: Session, project_id: str, document_id: str) -> dict:
        document = self.document_service.get(db, project_id, document_id)
        chunks = list(db.scalars(select(DocumentChunk).where(
            DocumentChunk.document_id == document.id,
        ).order_by(DocumentChunk.chunk_index)).all())
        ids = [str(chunk.id) for chunk in chunks]
        existing_ids = self.vector_store.existing_ids(ids)
        model = settings.embedding_model
        pending = [chunk for chunk in chunks if not (
            chunk.embedding_status == "completed" and chunk.embedding_model == model
            and str(chunk.id) in existing_ids
        )]
        if not pending:
            return {"document_id": document.id, "chunks_processed": 0, "vectors_created": 0}

        for chunk in pending:
            chunk.embedding_status = "processing"
        db.commit()

        try:
            provider = self._provider()
            texts = [chunk.chunk_text for chunk in pending]
            vectors = provider.embed_documents(texts)
            if len(vectors) != len(pending):
                raise RuntimeError("Embedding provider returned an unexpected number of vectors.")
            metadata = []
            for chunk in pending:
                chunk.chunk_hash = sha256(chunk.chunk_text.encode("utf-8")).hexdigest()
                chunk.token_count = self._token_count(chunk.chunk_text)
                values = {
                    "project_id": project_id,
                    "document_id": document.id,
                    "chunk_id": chunk.id,
                    "filename": document.original_filename,
                }
                # Chroma metadata rejects null values; -1 means the source has no page number.
                values["page_number"] = chunk.page_number if chunk.page_number is not None else -1
                metadata.append(values)
            self.vector_store.upsert(ids=[str(chunk.id) for chunk in pending], texts=texts,
                                     vectors=vectors, metadata=metadata)
            for chunk in pending:
                chunk.embedding_model = model
                chunk.embedding_status = "completed"
            db.commit()
        except Exception as exc:
            logger.exception(
                "Document embedding or ChromaDB storage failed",
                extra={
                    "project_id": project_id,
                    "document_id": document_id,
                    "chunk_count": len(pending),
                    "embedding_provider": settings.embedding_provider,
                    "embedding_model": settings.embedding_model,
                },
            )
            db.rollback()
            failed = list(db.scalars(select(DocumentChunk).where(
                DocumentChunk.id.in_([chunk.id for chunk in pending]),
            )).all())
            for chunk in failed:
                chunk.embedding_status = "failed"
            db.commit()
            if isinstance(exc, AppError):
                raise
            if settings.app_environment.lower() in {"development", "dev", "local"}:
                raise AppError(f"Embedding generation or ChromaDB storage failed: {exc}", 502) from exc
            raise AppError("Embedding generation or ChromaDB storage failed.", 502) from exc

        return {"document_id": document.id, "chunks_processed": len(pending), "vectors_created": len(pending)}

    def status(self, db: Session, project_id: str, document_id: str) -> dict:
        document = self.document_service.get(db, project_id, document_id)
        chunks = list(db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document.id)).all())
        total = len(chunks)
        completed = sum(chunk.embedding_status == "completed" for chunk in chunks)
        failed = sum(chunk.embedding_status == "failed" for chunk in chunks)
        if total > 0 and completed == total:
            overall = "completed"
        elif any(chunk.embedding_status == "processing" for chunk in chunks):
            overall = "processing"
        elif failed:
            overall = "failed"
        else:
            overall = "pending"
        return {"total_chunks": total, "completed_chunks": completed,
                "failed_chunks": failed, "status": overall}


embedding_service = EmbeddingService()
