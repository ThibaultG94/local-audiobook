"""PDF extraction adapter with deterministic page-order output."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from PyPDF2 import PdfReader

from contracts.result import Result, failure, success

_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")


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

    def extract(self, source_path: str, *, correlation_id: str, job_id: str) -> Result[dict[str, Any]]:
        normalized_source_path = str(Path(source_path).resolve())
        self._logger.emit(
            event="extraction.started",
            stage="extraction",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=-1,
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
                normalized_page = self._normalize_fragment(page_text_raw or "")
                has_text = bool(normalized_page)

                if has_text:
                    normalized_pages.append(normalized_page)
                else:
                    non_text_pages += 1

                page_diagnostics.append(
                    {
                        "page_index": page_index,
                        "has_text": has_text,
                        "chars": len(normalized_page),
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
                chunk_index=-1,
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
        except OSError as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.unreadable_source",
                message="PDF file could not be read",
                details={"source_path": normalized_source_path, "source_format": "pdf", "error": str(exc)},
                retryable=True,
            )
        except Exception as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.malformed_pdf",
                message="PDF extraction failed due to malformed or unsupported content",
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
            chunk_index=-1,
            engine="pdf",
            extra={"error_code": code, **details},
        )
        return failure(code=code, message=message, details=details, retryable=retryable)

    def _normalize_fragment(self, fragment: str) -> str:
        lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in fragment.split("\n")]
        non_empty_lines = [line for line in lines if line]
        return "\n".join(non_empty_lines)
