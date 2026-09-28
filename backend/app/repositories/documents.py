from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DocumentChunk, UploadedDocument


def create(db: Session, document: UploadedDocument) -> UploadedDocument:
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def list_for_project(db: Session, project_id: str) -> list[dict]:
    statement = (select(UploadedDocument, func.count(DocumentChunk.id))
                 .outerjoin(DocumentChunk, DocumentChunk.document_id == UploadedDocument.id)
                 .where(UploadedDocument.project_id == project_id)
                 .group_by(UploadedDocument.id)
                 .order_by(UploadedDocument.uploaded_at.desc()))
    return [{"document": row, "chunk_count": count} for row, count in db.execute(statement).all()]


def get(db: Session, project_id: str, document_id: str) -> UploadedDocument | None:
    return db.scalar(select(UploadedDocument).where(
        UploadedDocument.project_id == project_id, UploadedDocument.id == document_id
    ))


def list_chunks(db: Session, document_id: str, limit: int, offset: int) -> tuple[list[DocumentChunk], int]:
    total = db.scalar(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document_id)) or 0
    statement = (select(DocumentChunk).where(DocumentChunk.document_id == document_id)
                 .order_by(DocumentChunk.chunk_index).offset(offset).limit(limit))
    return list(db.scalars(statement).all()), total
