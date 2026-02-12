"""Import service for local document intake validation and persistence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from contracts.result import Result, failure, success


SUPPORTED_EXTENSIONS = {".epub", ".pdf", ".txt", ".md"}


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
        normalized = str(Path(file_path))
        extension = Path(normalized).suffix.lower()

        if extension not in SUPPORTED_EXTENSIONS:
            return self._reject(
                corr,
                code="import.unsupported_extension",
                message="Unsupported file extension",
                details={"extension": extension, "supported_extensions": sorted(SUPPORTED_EXTENSIONS)},
                retryable=False,
            )

        if not os.path.exists(normalized):
            return self._reject(
                corr,
                code="import.file_missing",
                message="Selected file does not exist",
                details={"source_path": normalized},
                retryable=True,
            )

        if not os.path.isfile(normalized) or not os.access(normalized, os.R_OK):
            return self._reject(
                corr,
                code="import.file_unreadable",
                message="Selected file is unreadable",
                details={"source_path": normalized},
                retryable=True,
            )

        if os.path.getsize(normalized) == 0:
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
            extra={"error_code": code, **details},
        )
        return failure(code=code, message=message, details=details, retryable=retryable)

