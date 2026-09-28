"""Page-aware text splitting with LangChain's recursive character splitter."""
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings


class ChunkingService:
    def split(self, parsed_document: dict, source_filename: str) -> list[dict]:
        size, overlap = settings.chunk_size, settings.chunk_overlap
        if size < 1 or overlap < 0 or overlap >= size:
            raise ValueError("Chunk settings require chunk_size > chunk_overlap >= 0.")
        splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap, add_start_index=True)
        pages = parsed_document.get("pages") or [{"page_number": None, "text": parsed_document["text"]}]
        chunks: list[dict] = []
        for page in pages:
            page_text = (page.get("text") or "").strip()
            if not page_text:
                continue
            page_number = page.get("page_number")
            docs = splitter.create_documents([page_text], metadatas=[{
                "source_filename": source_filename,
                "format": parsed_document.get("metadata", {}).get("format", "unknown"),
                "page_number": page_number,
            }])
            for doc in docs:
                chunks.append({
                    "chunk_index": len(chunks),
                    "page_number": page_number,
                    "chunk_text": doc.page_content,
                    "chunk_size": len(doc.page_content),
                    "metadata_json": {**doc.metadata, "start_index": doc.metadata.get("start_index", 0)},
                })
        return chunks
