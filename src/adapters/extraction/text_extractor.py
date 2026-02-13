"""TXT/Markdown extraction adapter with deterministic normalization output."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol, Union, runtime_checkable

from contracts.result import Result, failure, success

from .text_normalization import CHUNK_INDEX_NOT_APPLICABLE, MAX_FILE_SIZE_BYTES, normalize_fragment

_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_ORDERED_LIST_RE = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^\s*>\s?", re.MULTILINE)
_EMPHASIS_RE = re.compile(r"([*_]{1,3})(.*?)\1")


@runtime_checkable
class EventLoggerPort(Protocol):
    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: Any) -> None: ...


class _NoopLogger:
    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: Any) -> None:
        return None


class TextExtractor:
    """Extract chunking-ready text from TXT and Markdown files."""

    def __init__(self, *, logger: EventLoggerPort | None = None) -> None:
        self._logger = logger or _NoopLogger()

    def extract(self, source_path: Union[str, Path], *, correlation_id: str, job_id: str) -> Result[dict[str, Any]]:
        normalized_source_path = str(Path(source_path).resolve())
        source_format = Path(normalized_source_path).suffix.lower().lstrip(".")

        if source_format not in {"txt", "md"}:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                source_format=source_format or "unknown",
                code="extraction.unsupported_source_format",
                message="Unsupported source format for text extraction",
                details={"source_path": normalized_source_path, "source_format": source_format or "unknown"},
                retryable=False,
            )

        try:
            file_size = Path(normalized_source_path).stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                return self._fail(
                    correlation_id=correlation_id,
                    job_id=job_id,
                    source_format=source_format,
                    code="extraction.file_too_large",
                    message=f"Text file exceeds maximum size limit ({MAX_FILE_SIZE_BYTES // (1024*1024)}MB)",
                    details={
                        "source_path": normalized_source_path,
                        "source_format": source_format,
                        "file_size": file_size,
                        "max_size": MAX_FILE_SIZE_BYTES,
                    },
                    retryable=False,
                )
        except OSError as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                source_format=source_format,
                code="extraction.unreadable_source",
                message="Unable to access text source file",
                details={"source_path": normalized_source_path, "source_format": source_format, "error": str(exc)},
                retryable=True,
            )

        self._logger.emit(
            event="extraction.started",
            stage="extraction",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=CHUNK_INDEX_NOT_APPLICABLE,
            engine="text",
            extra={"source_path": normalized_source_path, "source_format": source_format},
        )

        try:
            raw_bytes = Path(normalized_source_path).read_bytes()
        except OSError as exc:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                source_format=source_format,
                code="extraction.unreadable_source",
                message="Text source file could not be read",
                details={"source_path": normalized_source_path, "source_format": source_format, "error": str(exc)},
                retryable=True,
            )

        encoding_warnings: list[str] = []
        normalization_warnings: list[str] = []
        try:
            decoded_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            decoded_text = raw_bytes.decode("utf-8", errors="replace")
            replacements = decoded_text.count("\ufffd")
            if replacements:
                encoding_warnings.append(f"utf8_decode_replaced_bytes:{replacements}")
            if decoded_text and replacements / max(len(decoded_text), 1) > 0.2:
                return self._fail(
                    correlation_id=correlation_id,
                    job_id=job_id,
                    source_format=source_format,
                    code="extraction.encoding_invalid",
                    message="Text source contains unreadable byte sequences",
                    details={
                        "source_path": normalized_source_path,
                        "source_format": source_format,
                        "replacement_chars": replacements,
                    },
                    retryable=False,
                )

        reading_text = self._markdown_to_reading_text(decoded_text) if source_format == "md" else decoded_text
        normalized_text = normalize_fragment(reading_text, strip_html=False)

        if not normalized_text:
            return self._fail(
                correlation_id=correlation_id,
                job_id=job_id,
                source_format=source_format,
                code="extraction.no_text_content",
                message="No readable text content found in source",
                details={"source_path": normalized_source_path, "source_format": source_format},
                retryable=False,
            )

        sections = len(normalized_text.split("\n"))

        self._logger.emit(
            event="extraction.succeeded",
            stage="extraction",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=CHUNK_INDEX_NOT_APPLICABLE,
            engine="text",
            extra={
                "source_path": normalized_source_path,
                "source_format": source_format,
                "sections": sections,
                "text_length": len(normalized_text),
                "encoding_warnings": len(encoding_warnings),
                "normalization_warnings": len(normalization_warnings),
            },
        )

        return success(
            {
                "source_path": normalized_source_path,
                "source_format": source_format,
                "text": normalized_text,
                "sections": sections,
                "text_length": len(normalized_text),
                "warnings": {
                    "encoding_warnings": encoding_warnings,
                    "normalization_warnings": normalization_warnings,
                },
            }
        )

    @staticmethod
    def _markdown_to_reading_text(content: str) -> str:
        text = _CODE_FENCE_RE.sub(" ", content)
        text = _INLINE_CODE_RE.sub(r"\1", text)
        text = _LINK_RE.sub(r"\1", text)
        text = _HEADING_RE.sub("", text)
        text = _BULLET_RE.sub("", text)
        text = _ORDERED_LIST_RE.sub("", text)
        text = _BLOCKQUOTE_RE.sub("", text)
        text = _EMPHASIS_RE.sub(r"\2", text)
        return text

    def _fail(
        self,
        *,
        correlation_id: str,
        job_id: str,
        source_format: str,
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
            engine="text",
            extra={"error_code": code, "source_format": source_format, **details},
        )
        return failure(code=code, message=message, details=details, retryable=retryable)
