from __future__ import annotations

import unittest

from infrastructure.logging.event_schema import validate_event_payload


def _valid_payload() -> dict[str, object]:
    return {
        "correlation_id": "corr-1",
        "job_id": "job-1",
        "chunk_index": 0,
        "engine": "engine-a",
        "stage": "tts",
        "event": "tts.chunk_started",
        "severity": "INFO",
        "timestamp": "2026-02-15T14:00:00+00:00",
    }


class TestEventSchema(unittest.TestCase):
    def test_accepts_valid_payload_with_nullable_optional_fields(self) -> None:
        payload = _valid_payload()
        payload["error"] = None
        payload["duration_ms"] = None

        validate_event_payload(payload)

    def test_rejects_invalid_event_name_when_domain_is_missing(self) -> None:
        payload = _valid_payload()
        payload["event"] = ".chunk_started"

        with self.assertRaisesRegex(ValueError, "domain.action"):
            validate_event_payload(payload)

    def test_rejects_invalid_event_name_when_action_is_missing(self) -> None:
        payload = _valid_payload()
        payload["event"] = "tts."

        with self.assertRaisesRegex(ValueError, "domain.action"):
            validate_event_payload(payload)

    def test_rejects_non_utc_timestamp(self) -> None:
        payload = _valid_payload()
        payload["timestamp"] = "2026-02-15T16:00:00+02:00"

        with self.assertRaisesRegex(ValueError, "UTC ISO-8601"):
            validate_event_payload(payload)

