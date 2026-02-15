"""Event schema contract for JSONL diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any

REQUIRED_EVENT_FIELDS = {
    "correlation_id",
    "job_id",
    "chunk_index",
    "engine",
    "stage",
    "event",
    "severity",
    "timestamp",
}

# Valid severity levels for structured logging
VALID_SEVERITY_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

# Event name pattern: domain.action with minimum 2 chars per part, no trailing/leading underscores
EVENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,}[a-z0-9]\.[a-z][a-z0-9_]{1,}[a-z0-9]$|^[a-z]{2,}\.[a-z]{2,}$")

# Maximum serialized size for extra field (10KB)
MAX_EXTRA_SIZE_BYTES = 10 * 1024


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_valid_utc_iso_8601(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    return parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def validate_event_payload(payload: dict[str, Any]) -> None:
    """Validate event payload against strict schema contract.
    
    Raises:
        ValueError: If payload violates schema requirements with specific error message
    """
    # Check required fields presence
    missing = REQUIRED_EVENT_FIELDS - payload.keys()
    if missing:
        raise ValueError(f"Missing required event fields: {sorted(missing)}")

    # Validate correlation_id type and non-empty
    correlation_id = payload.get("correlation_id")
    if not isinstance(correlation_id, str) or not correlation_id:
        raise ValueError("correlation_id must be a non-empty string")

    # Validate job_id type (can be empty string for bootstrap events)
    job_id = payload.get("job_id")
    if not isinstance(job_id, str):
        raise ValueError("job_id must be a string")

    # Validate chunk_index type
    chunk_index = payload.get("chunk_index")
    if not isinstance(chunk_index, int):
        raise ValueError("chunk_index must be an integer")

    # Validate engine type and non-empty
    engine = payload.get("engine")
    if not isinstance(engine, str) or not engine:
        raise ValueError("engine must be a non-empty string")

    # Validate stage type and non-empty
    stage = payload.get("stage")
    if not isinstance(stage, str) or not stage:
        raise ValueError("stage must be a non-empty string")

    # Validate event name format
    event_name = payload.get("event")
    if not isinstance(event_name, str) or EVENT_NAME_PATTERN.fullmatch(event_name) is None:
        raise ValueError("Event name must follow domain.action format with minimum 2 characters per part")

    # Validate severity against allowed values
    severity = payload.get("severity")
    if not isinstance(severity, str) or severity not in VALID_SEVERITY_LEVELS:
        raise ValueError(f"severity must be one of {sorted(VALID_SEVERITY_LEVELS)}")

    # Validate timestamp format and UTC requirement
    timestamp = payload.get("timestamp")
    if not isinstance(timestamp, str):
        raise ValueError("timestamp must be a string")
    if not is_valid_utc_iso_8601(timestamp):
        raise ValueError("timestamp must be UTC ISO-8601 format (e.g., '2026-02-15T14:00:00+00:00' or '2026-02-15T14:00:00Z')")

    # Validate extra field type and size
    extra = payload.get("extra")
    if "extra" in payload and extra is not None:
        if not isinstance(extra, dict):
            raise ValueError("extra must be an object or null")
        # Check serialized size to prevent log bloat
        try:
            extra_serialized = json.dumps(extra, ensure_ascii=False)
            if len(extra_serialized.encode("utf-8")) > MAX_EXTRA_SIZE_BYTES:
                raise ValueError(f"extra field exceeds maximum size of {MAX_EXTRA_SIZE_BYTES} bytes")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"extra field must be JSON-serializable: {exc}") from exc
