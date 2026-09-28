"""Document ingestion and inspection endpoints."""
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.documents import (
    DocumentChunkPage, DocumentDetail, DocumentPreview, DocumentUploadResult,
    UploadedDocumentRead,
)
from app.schemas.vector_search import EmbeddingResult, EmbeddingStatus
from app.services.document_service import document_service
from app.services.embedding_service import embedding_service

router = APIRouter(prefix="/projects", tags=["documents"])


@router.post("/{project_id}/documents", response_model=DocumentUploadResult, status_code=status.HTTP_201_CREATED,
             summary="Upload, parse, and chunk a project document")
def upload_document(project_id: str, file: UploadFile = File(..., description="PDF, DOCX, or TXT; maximum 20 MB"),
                    db: Session = Depends(get_db)):
    """Save the original, extract text, split it into chunks, and persist document metadata and chunks."""
    document, count = document_service.ingest(db, project_id, file)
    return {"document_id": document.id, "filename": document.original_filename, "status": "processed", "chunk_count": count}


@router.get("/{project_id}/documents", response_model=list[UploadedDocumentRead], summary="List project documents")
def list_documents(project_id: str, db: Session = Depends(get_db)):
    """List uploaded documents with their parser and chunking metadata."""
    return document_service.list(db, project_id)


@router.get("/{project_id}/documents/{doc_id}", response_model=DocumentDetail, summary="Get document details")
def get_document(project_id: str, doc_id: str, db: Session = Depends(get_db)):
    """Return one document scoped to the specified project."""
    return document_service.get(db, project_id, doc_id)


@router.get("/{project_id}/documents/{doc_id}/preview", response_model=DocumentPreview,
            summary="Preview extracted document text")
def preview_document(project_id: str, doc_id: str, db: Session = Depends(get_db)):
    """Reparse the stored source and return extracted text, page count, and stored chunk count."""
    return document_service.preview(db, project_id, doc_id)


@router.get("/{project_id}/documents/{doc_id}/chunks", response_model=DocumentChunkPage,
            summary="List document chunks")
def list_document_chunks(project_id: str, doc_id: str, limit: int = Query(50, ge=1, le=100),
                         offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    """Return persisted chunks in order with limit/offset pagination."""
    return document_service.chunks(db, project_id, doc_id, limit, offset)


@router.delete("/{project_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a project document and its indexed chunks")
def delete_document(project_id: str, doc_id: str, db: Session = Depends(get_db)):
    """Remove original file, PostgreSQL chunks/metadata, and corresponding Chroma vectors."""
    document_service.delete(db, project_id, doc_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/documents/{doc_id}/embed", response_model=EmbeddingResult,
             summary="Generate and store document chunk embeddings")
def embed_document(project_id: str, doc_id: str, db: Session = Depends(get_db)):
    """Embed pending chunks, persist vectors in ChromaDB, and mark PostgreSQL chunk statuses."""
    return embedding_service.embed_document(db, project_id, doc_id)


@router.get("/{project_id}/documents/{doc_id}/embedding-status", response_model=EmbeddingStatus,
            summary="Get document embedding status")
def document_embedding_status(project_id: str, doc_id: str, db: Session = Depends(get_db)):
    """Summarize total, completed, and failed chunk embedding statuses."""
    return embedding_service.status(db, project_id, doc_id)
