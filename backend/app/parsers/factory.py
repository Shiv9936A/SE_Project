"""Choose the document parser from a validated filename extension."""
from pathlib import Path

from app.core.exceptions import AppError
from app.parsers.base import BaseParser
from app.parsers.docx_parser import DOCXParser
from app.parsers.pdf_parser import PDFParser
from app.parsers.txt_parser import TXTParser

PARSERS: dict[str, type[BaseParser]] = {".pdf": PDFParser, ".docx": DOCXParser, ".txt": TXTParser}


def parser_for(path_or_name: str | Path) -> BaseParser:
    extension = Path(path_or_name).suffix.lower()
    parser = PARSERS.get(extension)
    if parser is None:
        raise AppError("Unsupported file type. Use PDF, DOCX, or TXT.", 415)
    return parser()
