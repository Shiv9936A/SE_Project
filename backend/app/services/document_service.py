"""Document ingestion, metadata persistence, parsing, and chunk persistence."""
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import DocumentChunk, UploadedDocument
from app.parsers.base import DocumentParseError
from app.repositories import documents as document_repo
from app.services.chunking_service import ChunkingService
from app.services.file_storage_service import FileStorageService
from app.services.parser_service import ParserService
from app.services.project_service import require_project
from app.services.vector_store_service import ChromaVectorStore


class DocumentService:
    def __init__(self):
        self.storage = FileStorageService()
        self.parser = ParserService()
        self.chunker = ChunkingService()
        self.vector_store = ChromaVectorStore()

    def ingest(self, db: Session, project_id: str, upload: UploadFile) -> tuple[UploadedDocument, int]:
        require_project(db, project_id)
        saved = self.storage.save(project_id, upload)
        try:
            parsed = self.parser.parse(saved.path)
            chunk_payloads = self.chunker.split(parsed, saved.original_filename)
            if not chunk_payloads:
                raise AppError(f"'{saved.original_filename}' contains no text to index.", 422)

            document = UploadedDocument(
                project_id=project_id,
                original_filename=saved.original_filename,
                stored_filename=saved.stored_filename,
                content_type=saved.content_type,
                size_bytes=saved.size_bytes,
                sha256=saved.sha256,
                page_count=parsed.get("metadata", {}).get("page_count"),
            )
            document.chunks = [DocumentChunk(**chunk) for chunk in chunk_payloads]
            document_repo.create(db, document)
            return document, len(chunk_payloads)
        except DocumentParseError as exc:
            self.storage.remove(saved.path)
            raise AppError(str(exc), 422) from exc
        except Exception:
            db.rollback()
            self.storage.remove(saved.path)
            raise

    def list(self, db: Session, project_id: str) -> list[dict]:
        require_project(db, project_id)
        rows = []
        for item in document_repo.list_for_project(db, project_id):
            document = item["document"]
            rows.append({**{column.key: getattr(document, column.key) for column in document.__table__.columns},
                         "chunk_count": item["chunk_count"]})
        return rows

    def get(self, db: Session, project_id: str, document_id: str) -> UploadedDocument:
        require_project(db, project_id)
        document = document_repo.get(db, project_id, document_id)
        if document is None:
            raise AppError("Document not found for this project.", 404)
        return document

    def preview(self, db: Session, project_id: str, document_id: str) -> dict:
        document = self.get(db, project_id, document_id)
        path = self.storage.storage_path(project_id, document.stored_filename)
        if not path.is_file():
            raise AppError("Stored document file is missing.", 404)
        try:
            parsed = self.parser.parse(path)
        except DocumentParseError as exc:
            raise AppError(str(exc), 422) from exc
        return {"filename": document.original_filename, "extracted_text": parsed["text"],
                "page_count": parsed["metadata"].get("page_count"), "chunk_count": len(document.chunks)}

    def chunks(self, db: Session, project_id: str, document_id: str, limit: int, offset: int) -> dict:
        document = self.get(db, project_id, document_id)
        items, total = document_repo.list_chunks(db, document.id, limit, offset)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def delete(self, db: Session, project_id: str, document_id: str) -> None:
        document = self.get(db, project_id, document_id)
        chunk_ids = [str(chunk.id) for chunk in document.chunks]
        self.vector_store.delete(chunk_ids)
        stored_path = self.storage.storage_path(project_id, document.stored_filename)
        db.delete(document)
        db.commit()
        self.storage.remove(stored_path)

document_service = DocumentService()
