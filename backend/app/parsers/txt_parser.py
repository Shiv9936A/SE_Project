"""UTF-8 plain text extraction."""
from pathlib import Path

from app.parsers.base import BaseParser, DocumentParseError, ensure_text


class TXTParser(BaseParser):
    def parse(self, path: Path) -> dict:
        try:
            text = ensure_text(path.read_text(encoding="utf-8-sig"), path.name)
        except UnicodeDecodeError as exc:
            raise DocumentParseError(f"'{path.name}' is not valid UTF-8 text.") from exc
        except OSError as exc:
            raise DocumentParseError(f"Could not read text file '{path.name}'.") from exc
        return {"text": text, "pages": [{"page_number": None, "text": text}],
                "metadata": {"format": "txt", "page_count": None, "encoding": "utf-8"}}
