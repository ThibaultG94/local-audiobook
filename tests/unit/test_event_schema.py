from __future__ import annotations

import unittest

from infrastructure.logging.event_schema import validate_event_payload, MAX_EXTRA_SIZE_BYTES


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

    def test_accepts_timestamp_with_z_suffix(self) -> None:
        payload = _valid_payload()
        payload["timestamp"] = "2026-02-15T14:00:00Z"

        validate_event_payload(payload)

    def test_accepts_valid_severity_levels(self) -> None:
        for severity in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            payload = _valid_payload()
            payload["severity"] = severity
            validate_event_payload(payload)

    # Missing required fields tests
    def test_rejects_missing_correlation_id(self) -> None:
        payload = _valid_payload()
        del payload["correlation_id"]

        with self.assertRaisesRegex(ValueError, "Missing required event fields.*correlation_id"):
            validate_event_payload(payload)

    def test_rejects_missing_job_id(self) -> None:
        payload = _valid_payload()
        del payload["job_id"]

        with self.assertRaisesRegex(ValueError, "Missing required event fields.*job_id"):
            validate_event_payload(payload)

    def test_rejects_missing_chunk_index(self) -> None:
        payload = _valid_payload()
        del payload["chunk_index"]

        with self.assertRaisesRegex(ValueError, "Missing required event fields.*chunk_index"):
            validate_event_payload(payload)

    def test_rejects_missing_engine(self) -> None:
        payload = _valid_payload()
        del payload["engine"]

        with self.assertRaisesRegex(ValueError, "Missing required event fields.*engine"):
            validate_event_payload(payload)

    def test_rejects_missing_stage(self) -> None:
        payload = _valid_payload()
        del payload["stage"]

        with self.assertRaisesRegex(ValueError, "Missing required event fields.*stage"):
            validate_event_payload(payload)

    def test_rejects_missing_severity(self) -> None:
        payload = _valid_payload()
        del payload["severity"]

        with self.assertRaisesRegex(ValueError, "Missing required event fields.*severity"):
            validate_event_payload(payload)

    # Type validation tests
    def test_rejects_non_string_correlation_id(self) -> None:
        payload = _valid_payload()
        payload["correlation_id"] = 123

        with self.assertRaisesRegex(ValueError, "correlation_id must be a non-empty string"):
            validate_event_payload(payload)

    def test_rejects_empty_correlation_id(self) -> None:
        payload = _valid_payload()
        payload["correlation_id"] = ""

        with self.assertRaisesRegex(ValueError, "correlation_id must be a non-empty string"):
            validate_event_payload(payload)

    def test_rejects_non_string_job_id(self) -> None:
        payload = _valid_payload()
        payload["job_id"] = None

        with self.assertRaisesRegex(ValueError, "job_id must be a string"):
            validate_event_payload(payload)

    def test_rejects_non_integer_chunk_index(self) -> None:
        payload = _valid_payload()
        payload["chunk_index"] = "not-a-number"

        with self.assertRaisesRegex(ValueError, "chunk_index must be an integer"):
            validate_event_payload(payload)

    def test_rejects_non_string_engine(self) -> None:
        payload = _valid_payload()
        payload["engine"] = 12345

        with self.assertRaisesRegex(ValueError, "engine must be a non-empty string"):
            validate_event_payload(payload)

    def test_rejects_empty_engine(self) -> None:
        payload = _valid_payload()
        payload["engine"] = ""

        with self.assertRaisesRegex(ValueError, "engine must be a non-empty string"):
            validate_event_payload(payload)

    def test_rejects_non_string_stage(self) -> None:
        payload = _valid_payload()
        payload["stage"] = ["not", "a", "string"]

        with self.assertRaisesRegex(ValueError, "stage must be a non-empty string"):
            validate_event_payload(payload)

    # Severity validation tests
    def test_rejects_invalid_severity_value(self) -> None:
        payload = _valid_payload()
        payload["severity"] = "WARN"

        with self.assertRaisesRegex(ValueError, "severity must be one of"):
            validate_event_payload(payload)

    def test_rejects_lowercase_severity(self) -> None:
        payload = _valid_payload()
        payload["severity"] = "info"

        with self.assertRaisesRegex(ValueError, "severity must be one of"):
            validate_event_payload(payload)

    # Event name validation tests
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

    def test_rejects_event_name_with_trailing_underscore(self) -> None:
        payload = _valid_payload()
        payload["event"] = "domain_.action"

        with self.assertRaisesRegex(ValueError, "domain.action"):
            validate_event_payload(payload)

    def test_rejects_event_name_too_short(self) -> None:
        payload = _valid_payload()
        payload["event"] = "a.b"

        with self.assertRaisesRegex(ValueError, "domain.action"):
            validate_event_payload(payload)

    # Timestamp validation tests
    def test_rejects_non_utc_timestamp(self) -> None:
        payload = _valid_payload()
        payload["timestamp"] = "2026-02-15T16:00:00+02:00"

        with self.assertRaisesRegex(ValueError, "UTC ISO-8601"):
            validate_event_payload(payload)

    def test_rejects_non_string_timestamp(self) -> None:
        payload = _valid_payload()
        payload["timestamp"] = 1234567890

        with self.assertRaisesRegex(ValueError, "timestamp must be a string"):
            validate_event_payload(payload)

    def test_rejects_naive_timestamp_without_timezone(self) -> None:
        payload = _valid_payload()
        payload["timestamp"] = "2026-02-15T14:00:00"

        with self.assertRaisesRegex(ValueError, "UTC ISO-8601"):
            validate_event_payload(payload)

    # Extra field validation tests
    def test_rejects_non_dict_extra(self) -> None:
        payload = _valid_payload()
        payload["extra"] = "not-a-dict"

        with self.assertRaisesRegex(ValueError, "extra must be an object or null"):
            validate_event_payload(payload)

    def test_accepts_extra_as_none(self) -> None:
        payload = _valid_payload()
        payload["extra"] = None

        validate_event_payload(payload)

    def test_accepts_payload_without_extra_key(self) -> None:
        payload = _valid_payload()
        # No extra key at all
        validate_event_payload(payload)

    def test_rejects_extra_exceeding_size_limit(self) -> None:
        payload = _valid_payload()
        # Create a large extra payload exceeding MAX_EXTRA_SIZE_BYTES
        large_value = "x" * (MAX_EXTRA_SIZE_BYTES + 1)
        payload["extra"] = {"large_field": large_value}

        with self.assertRaisesRegex(ValueError, "extra field exceeds maximum size"):
            validate_event_payload(payload)

    def test_rejects_non_serializable_extra(self) -> None:
        payload = _valid_payload()
        payload["extra"] = {"func": lambda x: x}  # Functions are not JSON-serializable

        with self.assertRaisesRegex(ValueError, "extra field must be JSON-serializable"):
            validate_event_payload(payload)

