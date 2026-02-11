"""Event schema contract for JSONL diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone

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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_valid_utc_iso_8601(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_event_payload(payload: dict[str, object]) -> None:
    missing = REQUIRED_EVENT_FIELDS - payload.keys()
    if missing:
        raise ValueError(f"Missing required event fields: {sorted(missing)}")

    event_name = payload.get("event")
    if not isinstance(event_name, str) or "." not in event_name:
        raise ValueError("Event name must follow domain.action format")

    timestamp = payload.get("timestamp")
    if not isinstance(timestamp, str) or not is_valid_utc_iso_8601(timestamp):
        raise ValueError("timestamp must be UTC ISO-8601")

