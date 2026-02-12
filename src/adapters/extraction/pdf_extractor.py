"""PDF extraction adapter with deterministic page-order output.

Limitations:
- PyPDF2 does not perform OCR on scanned/image-only PDFs
- Encrypted PDFs require decryption before extraction
- Complex layouts may result in non-linear text order
- Very large PDFs (>500MB) are rejected to prevent memory issues
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, Union, runtime_checkable

from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

from contracts.result import Result, failure, success
from .text_normalization import CHUNK_INDEX_NOT_APPLICABLE, MAX_FILE_SIZE_BYTES, normalize_fragment


@runtime_checkable
class EventLoggerPort(Protocol):
    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: Any) -> None: ...


class _NoopLogger:
    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: Any) -> None:
        return None


class PdfExtractor:
    """Extract chunking-ready text from PDF files."""

    def __init__(self, *, logger: EventLoggerPort | None = None) -> None:
        self._logger = logger or _NoopLogger()

    def extract(self, source_path: Union[str, Path], *, correlation_id: str, job_id: str) -> Result[dict[str, Any]]:
        normalized_source_path = str(Path(source_path).resolve())
        
        # Validate file size before processing (same limit as EPUB)
        try:
            file_size = Path(normalized_source_path).stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                return self._fail(
                    correlation_id=correlation_id,
                    job_id=job_id,
                    code="extraction.file_too_large",
                    message=f"PDF file exceeds maximum size limit ({MAX_FILE_SIZE_BYTES // (1024*1024)}MB)",
                    details={
                        "source_path": normalized_source_path,
                        "source_format": "pdf",
                        "file_size": file_size,
                        "max_size": MAX_FILE_SIZE_BYTES,
                    },
                    retryable=False,
                )
        except OSError as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.unreadable_source",
                message="Unable to access PDF file",
                details={"source_path": normalized_source_path, "source_format": "pdf", "error": str(exc)},
                retryable=True,
            )
        
        self._logger.emit(
            event="extraction.started",
            stage="extraction",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=CHUNK_INDEX_NOT_APPLICABLE,
            engine="pdf",
            extra={"source_path": normalized_source_path},
        )

        try:
            reader = PdfReader(normalized_source_path)
            normalized_pages: list[str] = []
            page_diagnostics: list[dict[str, Any]] = []
            non_text_pages = 0

            for page_index, page in enumerate(reader.pages):
                page_text_raw = page.extract_text()
                normalized_page = normalize_fragment(page_text_raw or "", strip_html=False)
                has_text = bool(normalized_page)
                word_count = len(normalized_page.split()) if has_text else 0

                if has_text:
                    normalized_pages.append(normalized_page)
                else:
                    non_text_pages += 1

                page_diagnostics.append(
                    {
                        "page_index": page_index,
                        "has_text": has_text,
                        "chars": len(normalized_page),
                        "words": word_count,
                    }
                )

            normalized_text = "\n".join(normalized_pages).strip()
            pages_count = len(page_diagnostics)

            if not normalized_text:
                return self._fail(
                    correlation_id=correlation_id,
                    job_id=job_id,
                    code="extraction.no_text_content",
                    message="No readable text content found in PDF",
                    details={
                        "source_path": normalized_source_path,
                        "source_format": "pdf",
                        "pages": pages_count,
                        "non_text_pages": non_text_pages,
                        "page_diagnostics": page_diagnostics,
                    },
                    retryable=False,
                )

            self._logger.emit(
                event="extraction.succeeded",
                stage="extraction",
                severity="INFO",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=CHUNK_INDEX_NOT_APPLICABLE,
                engine="pdf",
                extra={
                    "source_path": normalized_source_path,
                    "pages": pages_count,
                    "non_text_pages": non_text_pages,
                    "text_length": len(normalized_text),
                },
            )

            return success(
                {
                    "source_path": normalized_source_path,
                    "source_format": "pdf",
                    "text": normalized_text,
                    "pages": pages_count,
                    "non_text_pages": non_text_pages,
                    "page_diagnostics": page_diagnostics,
                    "sections": pages_count,
                }
            )
        except FileNotFoundError as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.unreadable_source",
                message="PDF file could not be accessed",
                details={"source_path": normalized_source_path, "source_format": "pdf", "error": str(exc)},
                retryable=True,
            )
        except (OSError, PermissionError) as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.unreadable_source",
                message="PDF file could not be read",
                details={"source_path": normalized_source_path, "source_format": "pdf", "error": str(exc)},
                retryable=True,
            )
        except PdfReadError as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.malformed_pdf",
                message="PDF extraction failed due to malformed or unsupported content",
                details={"source_path": normalized_source_path, "source_format": "pdf", "error": str(exc)},
                retryable=False,
            )
        except (ValueError, KeyError, IndexError) as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.malformed_pdf",
                message="PDF structure is invalid or corrupted",
                details={"source_path": normalized_source_path, "source_format": "pdf", "error": str(exc)},
                retryable=False,
            )

    def _fail(
        self,
        *,
        correlation_id: str,
        job_id: str,
        code: str,
        message: str,
        details: dict[str, Any],
        retryable: bool,
    ) -> Result[dict[str, Any]]:
        self._logger.emit(
            event="extraction.failed",
            stage="extraction",
            severity="ERROR",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=CHUNK_INDEX_NOT_APPLICABLE,
            engine="pdf",
            extra={"error_code": code, **details},
        )
        return failure(code=code, message=message, details=details, retryable=retryable)
