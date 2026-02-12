"""EPUB extraction adapter with deterministic reading-order output."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from contracts.result import Result, failure, success


@runtime_checkable
class EventLoggerPort(Protocol):
    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: Any) -> None: ...


class _NoopLogger:
    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: Any) -> None:
        return None


class EpubExtractor:
    """Extract chunking-ready text from EPUB files."""

    _TAG_RE = re.compile(r"<[^>]+>")
    _WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")

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
            engine="epub",
            extra={"source_path": normalized_source_path},
        )

        try:
            book = self._read_epub(normalized_source_path)
            text_sections: list[str] = []

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

                normalized_section = self._normalize_fragment(content.decode("utf-8", errors="ignore"))
                if normalized_section:
                    text_sections.append(normalized_section)

            normalized_text = "\n".join(text_sections).strip()
            if not normalized_text:
                return self._fail(
                    correlation_id=correlation_id,
                    job_id=job_id,
                    code="extraction.no_text_content",
                    message="No readable text content found in EPUB",
                    details={"source_path": normalized_source_path},
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
                extra={"source_path": normalized_source_path, "sections": len(text_sections)},
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
                details={"source_path": normalized_source_path, "error": str(exc)},
                retryable=True,
            )
        except ValueError as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.malformed_package",
                message="Malformed EPUB package metadata",
                details={"source_path": normalized_source_path, "error": str(exc)},
                retryable=False,
            )
        except Exception as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                code="extraction.runtime_error",
                message="EPUB extraction failed unexpectedly",
                details={"source_path": normalized_source_path, "error": str(exc)},
                retryable=True,
            )

    def _read_epub(self, source_path: str) -> Any:
        from ebooklib import epub

        return epub.read_epub(source_path)

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
        text = html.unescape(self._TAG_RE.sub(" ", fragment))
        lines = [self._WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
        non_empty_lines = [line for line in lines if line]
        return "\n".join(non_empty_lines)

