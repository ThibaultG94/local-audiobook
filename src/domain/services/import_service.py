"""Import service for local document intake validation and persistence."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from src.contracts.result import Result, failure, success


@runtime_checkable
class DocumentsRepositoryPort(Protocol):
    def create_document(self, record: dict[str, str]) -> dict[str, str]: ...


@runtime_checkable
class EventLoggerPort(Protocol):
    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: Any) -> None: ...


@runtime_checkable
class EpubExtractorPort(Protocol):
    def extract(self, source_path: str, *, correlation_id: str, job_id: str) -> Result[dict[str, Any]]: ...


@runtime_checkable
class PdfExtractorPort(Protocol):
    def extract(self, source_path: str, *, correlation_id: str, job_id: str) -> Result[dict[str, Any]]: ...


@runtime_checkable
class TextExtractorPort(Protocol):
    def extract(self, source_path: str, *, correlation_id: str, job_id: str) -> Result[dict[str, Any]]: ...


class ImportService:
    """Validate import metadata and persist accepted documents."""

    def __init__(
        self,
        *,
        documents_repository: DocumentsRepositoryPort,
        logger: EventLoggerPort,
        epub_extractor: EpubExtractorPort | None = None,
        pdf_extractor: PdfExtractorPort | None = None,
        text_extractor: TextExtractorPort | None = None,
    ) -> None:
        self._documents_repository = documents_repository
        self._logger = logger
        self._epub_extractor = epub_extractor
        self._pdf_extractor = pdf_extractor
        self._text_extractor = text_extractor

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

    def extract_document(
        self,
        *,
        document: dict[str, str],
        correlation_id: str,
        job_id: str,
    ) -> Result[dict[str, Any]]:
        """Extract text content from a document using the appropriate extractor.
        
        Args:
            document: Document record with source_path and source_format
            correlation_id: Correlation ID for tracing (must be non-empty)
            job_id: Job ID for tracing (must be non-empty)
            
        Returns:
            Result with extracted content or normalized error with guaranteed fields:
            - source_path: str
            - source_format: str
            - correlation_id: str
            - job_id: str
        """
        if not correlation_id or not correlation_id.strip():
            return failure(
                code="extraction.invalid_correlation_id",
                message="Correlation ID must be non-empty for extraction traceability",
                details={"correlation_id": correlation_id},
                retryable=False,
            )
        
        if not job_id or not job_id.strip():
            return failure(
                code="extraction.invalid_job_id",
                message="Job ID must be non-empty for extraction traceability",
                details={"job_id": job_id, "correlation_id": correlation_id},
                retryable=False,
            )
        
        source_path = document.get("source_path", "")
        source_format = document.get("source_format", "").lower() or "unknown"

        if source_format == "epub":
            if self._epub_extractor is None:
                return self._normalized_extraction_failure(
                    code="extraction.extractor_unavailable",
                    message="No extractor configured for source format: epub",
                    source_path=source_path,
                    source_format=source_format,
                    correlation_id=correlation_id,
                    job_id=job_id,
                    retryable=False,
                )
            result = self._epub_extractor.extract(source_path, correlation_id=correlation_id, job_id=job_id)
            return self._normalize_extraction_result(
                result,
                source_path=source_path,
                source_format=source_format,
                correlation_id=correlation_id,
                job_id=job_id,
            )

        if source_format == "pdf":
            if self._pdf_extractor is None:
                return self._normalized_extraction_failure(
                    code="extraction.extractor_unavailable",
                    message="No extractor configured for source format: pdf",
                    source_path=source_path,
                    source_format=source_format,
                    correlation_id=correlation_id,
                    job_id=job_id,
                    retryable=False,
                )
            result = self._pdf_extractor.extract(source_path, correlation_id=correlation_id, job_id=job_id)
            return self._normalize_extraction_result(
                result,
                source_path=source_path,
                source_format=source_format,
                correlation_id=correlation_id,
                job_id=job_id,
            )

        if source_format in {"txt", "md"}:
            if self._text_extractor is None:
                return self._normalized_extraction_failure(
                    code="extraction.extractor_unavailable",
                    message=f"No extractor configured for source format: {source_format}",
                    source_path=source_path,
                    source_format=source_format,
                    correlation_id=correlation_id,
                    job_id=job_id,
                    retryable=False,
                )
            result = self._text_extractor.extract(source_path, correlation_id=correlation_id, job_id=job_id)
            return self._normalize_extraction_result(
                result,
                source_path=source_path,
                source_format=source_format,
                correlation_id=correlation_id,
                job_id=job_id,
            )

        return self._normalized_extraction_failure(
            code="extraction.unsupported_source_format",
            message="Unsupported source format for extraction",
            source_path=source_path,
            source_format=source_format,
            correlation_id=correlation_id,
            job_id=job_id,
            retryable=False,
        )

    @staticmethod
    def _normalized_extraction_failure(
        *,
        code: str,
        message: str,
        source_path: str,
        source_format: str,
        correlation_id: str,
        job_id: str,
        retryable: bool,
    ) -> Result[dict[str, Any]]:
        return failure(
            code=code,
            message=message,
            details={
                "source_path": source_path,
                "source_format": source_format,
                "correlation_id": correlation_id,
                "job_id": job_id,
            },
            retryable=retryable,
        )

    def _normalize_extraction_result(
        self,
        extraction_result: Result[dict[str, Any]],
        *,
        source_path: str,
        source_format: str,
        correlation_id: str,
        job_id: str,
    ) -> Result[dict[str, Any]]:
        if extraction_result.ok:
            return extraction_result

        if extraction_result.error is None:
            # Log this anomaly - extractors should always provide error when ok=False
            self._logger.emit(
                event="extraction.contract_violation",
                stage="extraction",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=-1,
                engine=source_format,
                extra={
                    "source_path": source_path,
                    "source_format": source_format,
                    "violation": "extraction_result.ok=False but error=None",
                },
            )
            return self._normalized_extraction_failure(
                code="extraction.runtime_error",
                message="Extraction failed without a structured error payload",
                source_path=source_path,
                source_format=source_format,
                correlation_id=correlation_id,
                job_id=job_id,
                retryable=True,
            )

        # Validate that details is a dict before copying
        if not isinstance(extraction_result.error.details, dict):
            self._logger.emit(
                event="extraction.contract_violation",
                stage="extraction",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=-1,
                engine=source_format,
                extra={
                    "source_path": source_path,
                    "source_format": source_format,
                    "violation": f"error.details is not a dict: {type(extraction_result.error.details).__name__}",
                },
            )
            normalized_details = {}
        else:
            normalized_details = dict(extraction_result.error.details)
        
        normalized_details.setdefault("source_path", source_path)
        normalized_details.setdefault("source_format", source_format)
        normalized_details.setdefault("correlation_id", correlation_id)
        normalized_details.setdefault("job_id", job_id)

        return failure(
            code=extraction_result.error.code,
            message=extraction_result.error.message,
            details=normalized_details,
            retryable=extraction_result.error.retryable,
        )
