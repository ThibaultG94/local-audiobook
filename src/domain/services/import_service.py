"""Import service for local document intake validation and persistence."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from contracts.result import Result, failure, success


@runtime_checkable
class DocumentsRepositoryPort(Protocol):
    def create_document(self, record: dict[str, str]) -> dict[str, str]: ...


@runtime_checkable
class EventLoggerPort(Protocol):
    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: Any) -> None: ...


class ImportService:
    """Validate import metadata and persist accepted documents."""

    def __init__(self, *, documents_repository: DocumentsRepositoryPort, logger: EventLoggerPort) -> None:
        self._documents_repository = documents_repository
        self._logger = logger

    def import_document(self, file_path: str, correlation_id: str | None = None) -> Result[dict[str, str]]:
        corr = correlation_id or str(uuid4())
        normalized = str(Path(file_path).resolve())
        extension = Path(normalized).suffix.lower()

        # Validation: file must exist and be a regular file
        if not os.path.exists(normalized):
            return self._reject(
                corr,
                code="import.file_missing",
                message="Selected file does not exist",
                details={"source_path": normalized},
                retryable=True,
            )

        # Check if it's a regular file (not directory, symlink, device, etc.)
        try:
            file_stat = os.stat(normalized)
            if not stat.S_ISREG(file_stat.st_mode):
                return self._reject(
                    corr,
                    code="import.file_unreadable",
                    message="Selected path is not a regular file",
                    details={"source_path": normalized, "file_type": "special"},
                    retryable=False,
                )
        except (OSError, PermissionError) as e:
            return self._reject(
                corr,
                code="import.file_unreadable",
                message="Cannot access file metadata",
                details={"source_path": normalized, "error": str(e)},
                retryable=True,
            )

        # Check readability
        if not os.access(normalized, os.R_OK):
            return self._reject(
                corr,
                code="import.file_unreadable",
                message="Selected file is not readable",
                details={"source_path": normalized},
                retryable=True,
            )

        # Check file is non-empty
        if file_stat.st_size == 0:
            return self._reject(
                corr,
                code="import.file_empty",
                message="Selected file is empty",
                details={"source_path": normalized},
                retryable=True,
            )

        title = Path(normalized).stem
        record = self._documents_repository.create_document(
            {
                "source_path": normalized,
                "title": title,
                "source_format": extension.lstrip("."),
            }
        )
        self._logger.emit(
            event="import.accepted",
            stage="import",
            severity="INFO",
            correlation_id=corr,
            job_id="",
            chunk_index=-1,
            engine="import",
            extra={"source_path": normalized, "source_format": extension.lstrip(".")},
        )
        return success(record)

    def _reject(
        self,
        correlation_id: str,
        *,
        code: str,
        message: str,
        details: dict[str, Any],
        retryable: bool,
    ) -> Result[dict[str, str]]:
        self._logger.emit(
            event="import.rejected",
            stage="import",
            severity="ERROR",
            correlation_id=correlation_id,
            job_id="",
            chunk_index=-1,
            engine="import",
            extra={"error_code": code, **details},
        )
        return failure(code=code, message=message, details=details, retryable=retryable)

