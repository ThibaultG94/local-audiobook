"""EPUB extraction adapter with deterministic reading-order output."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ebooklib import epub

from contracts.result import Result, failure, success

# Maximum EPUB file size in bytes (500MB)
_MAX_EPUB_SIZE = 500 * 1024 * 1024

# Compiled regex patterns for text normalization
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")


@runtime_checkable
class EventLoggerPort(Protocol):
    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: Any) -> None: ...


class _NoopLogger:
    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: Any) -> None:
        return None


class EpubExtractor:
    """Extract chunking-ready text from EPUB files."""

    def __init__(self, *, logger: EventLoggerPort | None = None) -> None:
        self._logger = logger or _NoopLogger()

    def extract(self, source_path: str, *, correlation_id: str, job_id: str) -> Result[dict[str, Any]]:
        normalized_source_path = str(Path(source_path).resolve())
        
        # Validate file size before processing
        try:
            file_size = Path(normalized_source_path).stat().st_size
            if file_size > _MAX_EPUB_SIZE:
                return self._fail(
                    correlation_id=correlation_id,
                    job_id=job_id,
                    code="extraction.file_too_large",
                    message=f"EPUB file exceeds maximum size limit ({_MAX_EPUB_SIZE // (1024*1024)}MB)",
                    details={
                        "source_path": normalized_source_path,
                        "source_format": "epub",
                        "file_size": file_size,
                        "max_size": _MAX_EPUB_SIZE,
                    },
                    retryable=False,
                )
        except OSError as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.unreadable_archive",
                message="Unable to access EPUB file",
                details={"source_path": normalized_source_path, "source_format": "epub", "error": str(exc)},
                retryable=True,
            )
        self._logger.emit(
            event="extraction.started",
            stage="extraction",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=-1,
            engine="epub",
            extra={"source_path": normalized_source_path},
        )

        try:
            book = epub.read_epub(normalized_source_path)
            text_sections: list[str] = []
            encoding_warnings = 0

            for spine_item in getattr(book, "spine", []):
                item_id = spine_item[0] if isinstance(spine_item, (tuple, list)) and spine_item else ""
                if item_id in {"nav", "toc"}:
                    continue
                item = book.get_item_with_id(item_id) if hasattr(book, "get_item_with_id") else None
                if item is None:
                    continue

                content = item.get_content() if hasattr(item, "get_content") else b""
                if not isinstance(content, (bytes, bytearray)):
                    continue

                # Try UTF-8 first, then detect encoding issues
                try:
                    decoded_text = content.decode("utf-8")
                except UnicodeDecodeError:
                    # Fallback to replace mode and log warning
                    decoded_text = content.decode("utf-8", errors="replace")
                    encoding_warnings += 1
                    self._logger.emit(
                        event="extraction.encoding_warning",
                        stage="extraction",
                        severity="WARNING",
                        correlation_id=correlation_id,
                        job_id=job_id,
                        chunk_index=-1,
                        engine="epub",
                        extra={"source_path": normalized_source_path, "item_id": item_id},
                    )

                normalized_section = self._normalize_fragment(decoded_text)
                if normalized_section:
                    text_sections.append(normalized_section)

            normalized_text = "\n".join(text_sections).strip()
            if not normalized_text:
                return self._fail(
                    correlation_id=correlation_id,
                    job_id=job_id,
                    code="extraction.no_text_content",
                    message="No readable text content found in EPUB",
                    details={"source_path": normalized_source_path, "source_format": "epub"},
                    retryable=False,
                )

            self._logger.emit(
                event="extraction.succeeded",
                stage="extraction",
                severity="INFO",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=-1,
                engine="epub",
                extra={
                    "source_path": normalized_source_path,
                    "sections": len(text_sections),
                    "text_length": len(normalized_text),
                    "encoding_warnings": encoding_warnings,
                },
            )

            return success(
                {
                    "source_path": normalized_source_path,
                    "source_format": "epub",
                    "text": normalized_text,
                    "sections": len(text_sections),
                }
            )
        except OSError as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.unreadable_archive",
                message="Unable to read EPUB archive",
                details={"source_path": normalized_source_path, "source_format": "epub", "error": str(exc)},
                retryable=True,
            )
        except ValueError as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.malformed_package",
                message="Malformed EPUB package metadata",
                details={"source_path": normalized_source_path, "source_format": "epub", "error": str(exc)},
                retryable=False,
            )
        except Exception as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.runtime_error",
                message="EPUB extraction failed unexpectedly",
                details={"source_path": normalized_source_path, "source_format": "epub", "error": str(exc)},
                retryable=True,
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
            engine="epub",
            extra={"error_code": code, **details},
        )
        return failure(code=code, message=message, details=details, retryable=retryable)

    def _normalize_fragment(self, fragment: str) -> str:
        text = html.unescape(_TAG_RE.sub(" ", fragment))
        lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
        non_empty_lines = [line for line in lines if line]
        return "\n".join(non_empty_lines)
