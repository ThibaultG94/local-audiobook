"""Append-only JSONL logger for startup and migration observability."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .event_schema import utc_now_iso, validate_event_payload


class JsonlLoggingError(Exception):
    """Structured local logging failure."""

    def __init__(self, *, code: str, message: str, details: dict[str, Any], retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
        }


class JsonlLogger:
    """Write structured events in JSONL format."""

    def __init__(self, file_path: str | Path) -> None:
        self._file_path = Path(file_path)
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(
        self,
        *,
        event: str,
        stage: str,
        severity: str = "INFO",
        correlation_id: str = "bootstrap",
        job_id: str = "",
        chunk_index: int = -1,
        engine: str = "bootstrap",
        timestamp: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "correlation_id": correlation_id,
            "job_id": job_id,
            "chunk_index": chunk_index,
            "engine": engine,
            "stage": stage,
            "event": event,
            "severity": severity,
            "timestamp": timestamp or utc_now_iso(),
            "extra": extra if extra is not None else None,
        }

        try:
            validate_event_payload(payload)
        except ValueError as exc:
            raise JsonlLoggingError(
                code="logging.invalid_event_payload",
                message="Event payload rejected by schema",
                details={"error": str(exc), "event": event, "stage": stage},
                retryable=False,
            ) from exc

        serialized = json.dumps(payload, ensure_ascii=False)
        try:
            with self._file_path.open("a", encoding="utf-8") as out:
                out.write(serialized + "\n")
        except OSError as exc:
            raise JsonlLoggingError(
                code="logging.write_failed",
                message="Failed to append event to local JSONL log",
                details={"path": str(self._file_path), "error": str(exc)},
                retryable=True,
            ) from exc
