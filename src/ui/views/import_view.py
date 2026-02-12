"""Framework-neutral import entrypoint with extension filtering."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from contracts.import_constants import SUPPORTED_EXTENSIONS
from contracts.result import Result, failure


@runtime_checkable
class ImportServicePort(Protocol):
    def import_document(self, file_path: str, correlation_id: str | None = None) -> Result[dict[str, str]]: ...


class ImportView:
    """Validate selected file extension before routing to import service."""

    def __init__(self, *, import_service: ImportServicePort) -> None:
        self._import_service = import_service

    def submit_file(self, file_path: str, correlation_id: str | None = None) -> Result[dict[str, str]]:
        extension = Path(file_path).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            return failure(
                code="import.unsupported_extension",
                message="Unsupported file extension",
                details={"extension": extension, "supported_extensions": sorted(SUPPORTED_EXTENSIONS)},
                retryable=False,
            )
        return self._import_service.import_document(file_path, correlation_id=correlation_id)

