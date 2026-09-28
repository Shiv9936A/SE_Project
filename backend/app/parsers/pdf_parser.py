"""PDF text extraction using pypdf."""
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.parsers.base import BaseParser, DocumentParseError, ensure_text


class PDFParser(BaseParser):
    def parse(self, path: Path) -> dict:
        try:
            reader = PdfReader(str(path), strict=True)
            if reader.is_encrypted:
                raise DocumentParseError("Encrypted PDFs are not supported.")
            pages = []
            for index, page in enumerate(reader.pages, start=1):
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    pages.append({"page_number": index, "text": page_text})
            text = ensure_text("\n\n".join(page["text"] for page in pages), path.name)
            return {"text": text, "pages": pages, "metadata": {"format": "pdf", "page_count": len(reader.pages)}}
        except DocumentParseError:
            raise
        except (PdfReadError, OSError, ValueError, EOFError, KeyError) as exc:
            raise DocumentParseError(f"Could not parse PDF '{path.name}': {exc}") from exc
