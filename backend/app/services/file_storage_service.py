"""Validated, uniquely named local storage for uploaded source files."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import AppError
from app.parsers.factory import PARSERS


@dataclass(frozen=True)
class SavedUpload:
    original_filename: str
    stored_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    path: Path


class FileStorageService:
    @staticmethod
    def storage_path(project_id: str, stored_filename: str) -> Path:
        return settings.upload_directory / project_id / stored_filename

    def save(self, project_id: str, upload: UploadFile) -> SavedUpload:
        original = Path(upload.filename or "").name[:255]
        if not original:
            raise AppError("A filename is required.", 422)
        extension = Path(original).suffix.lower()
        if extension not in PARSERS:
            raise AppError(f"Unsupported file type for '{original}'. Use PDF, DOCX, or TXT.", 415)

        maximum = settings.max_upload_size_mb * 1024 * 1024
        data = upload.file.read(maximum + 1)
        if len(data) > maximum:
            raise AppError(f"'{original}' exceeds the {settings.max_upload_size_mb} MB upload limit.", 413)
        if not data or not data.strip():
            raise AppError(f"'{original}' is empty.", 422)

        stored = f"{uuid4().hex}{extension}"
        directory = settings.upload_directory / project_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / stored
        try:
            path.write_bytes(data)
        except OSError as exc:
            raise AppError("Could not store the uploaded file.", 500) from exc
        return SavedUpload(original, stored, upload.content_type or "application/octet-stream",
                           len(data), sha256(data).hexdigest(), path)

    @staticmethod
    def remove(path: Path) -> None:
        path.unlink(missing_ok=True)
