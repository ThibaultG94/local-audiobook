"""Event schema contract for JSONL diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone
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

EVENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


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
    missing = REQUIRED_EVENT_FIELDS - payload.keys()
    if missing:
        raise ValueError(f"Missing required event fields: {sorted(missing)}")

    event_name = payload.get("event")
    if not isinstance(event_name, str) or EVENT_NAME_PATTERN.fullmatch(event_name) is None:
        raise ValueError("Event name must follow domain.action format")

    timestamp = payload.get("timestamp")
    if not isinstance(timestamp, str) or not is_valid_utc_iso_8601(timestamp):
        raise ValueError("timestamp must be UTC ISO-8601")

    extra = payload.get("extra")
    if "extra" in payload and extra is not None and not isinstance(extra, dict):
        raise ValueError("extra must be an object or null")
