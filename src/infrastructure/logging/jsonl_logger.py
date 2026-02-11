"""Append-only JSONL logger for startup and migration observability."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .event_schema import utc_now_iso, validate_event_payload


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
        }
        if extra:
            payload.update(extra)

        validate_event_payload(payload)

        with self._file_path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(payload, ensure_ascii=False) + "\n")

