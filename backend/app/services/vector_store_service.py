"""Persistent ChromaDB storage for document chunk vectors."""
from pathlib import Path

import chromadb

from app.core.config import settings


class ChromaVectorStore:
    def __init__(self, persist_directory: Path | None = None, collection_name: str | None = None):
        self.persist_directory = Path(persist_directory or settings.chroma_persist_directory)
        self.collection_name = collection_name or settings.chroma_collection_name

    def collection(self):
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.persist_directory))
        return client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine", "description": "Requirements document chunks"},
        )

    def metadata_for_ids(self, ids: list[str]) -> dict[str, dict]:
        if not ids:
            return {}
        records = self.collection().get(ids=ids, include=["metadatas"])
        return {str(chunk_id): metadata or {}
                for chunk_id, metadata in zip(records.get("ids", []), records.get("metadatas", []))}

    def upsert(self, ids: list[str], texts: list[str], vectors: list[list[float]], metadata: list[dict]) -> None:
        if ids:
            self.collection().upsert(ids=ids, documents=texts, embeddings=vectors, metadatas=metadata)

    def delete(self, ids: list[str]) -> None:
        if ids:
            self.collection().delete(ids=ids)

    def search(self, query_vector: list[float], top_k: int, where: dict) -> list[dict]:
        result = self.collection().query(
            query_embeddings=[query_vector], n_results=top_k, where=where,
            include=["documents", "metadatas", "distances"],
        )
        rows = []
        for index, chunk_id in enumerate(result.get("ids", [[]])[0]):
            metadata = result["metadatas"][0][index]
            distance = result["distances"][0][index]
            rows.append({
                "chunk_id": chunk_id,
                "document_id": metadata["document_id"],
                "score": max(-1.0, min(1.0, 1.0 - float(distance))),
                "text": result["documents"][0][index],
                "filename": metadata.get("filename"),
                "page_number": metadata.get("page_number"),
                "metadata": metadata,
            })
        return rows
