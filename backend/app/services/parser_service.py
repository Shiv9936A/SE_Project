"""Dispatch supported stored files to reusable parser implementations."""
from pathlib import Path

from app.parsers.factory import parser_for


class ParserService:
    def parse(self, path: Path) -> dict:
        return parser_for(path).parse(path)
