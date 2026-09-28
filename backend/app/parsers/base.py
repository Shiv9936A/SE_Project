"""Shared parser interface and normalized parsed-document shape."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class DocumentParseError(ValueError):
    """A supported file could not be safely parsed into text."""


class BaseParser(ABC):
    @abstractmethod
    def parse(self, path: Path) -> dict[str, Any]:
        """Return {'text': str, 'pages': list[dict], 'metadata': dict}."""


def ensure_text(text: str, filename: str) -> str:
    normalized = text.strip()
    if not normalized:
        raise DocumentParseError(f"'{filename}' contains no extractable text.")
    return normalized
