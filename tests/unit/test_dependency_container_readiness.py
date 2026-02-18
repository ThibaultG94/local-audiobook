from __future__ import annotations

import unittest

from src.contracts.result import failure, success
from src.app.dependency_container import normalize_engine_health


class TestDependencyContainerReadiness(unittest.TestCase):
    def test_normalize_engine_health_preserves_expected_engine_when_health_fails(self) -> None:
        failed = failure(
            code="tts_engine_unavailable",
            message="engine failed health check",
            details={"reason": "model_not_available"},
            retryable=False,
        )

        normalized = normalize_engine_health(failed, expected_engine="chatterbox_gpu")

        self.assertEqual(normalized["engine"], "chatterbox_gpu")
        self.assertFalse(normalized["ok"])
        self.assertIsInstance(normalized["error"], dict)

    def test_normalize_engine_health_uses_provider_payload_when_available(self) -> None:
        healthy = success({"engine": "kokoro_cpu", "available": True})

        normalized = normalize_engine_health(healthy, expected_engine="kokoro_cpu")

        self.assertEqual(normalized["engine"], "kokoro_cpu")
        self.assertTrue(normalized["ok"])
        self.assertIsNone(normalized["error"])

    def test_normalize_engine_health_uses_expected_engine_when_payload_engine_missing(self) -> None:
        """Test that expected_engine is used when payload doesn't contain engine field."""
        healthy = success({"available": True})

        normalized = normalize_engine_health(healthy, expected_engine="chatterbox_gpu")

        self.assertEqual(normalized["engine"], "chatterbox_gpu")
        self.assertTrue(normalized["ok"])
        self.assertIsNone(normalized["error"])

    def test_normalize_engine_health_prefers_payload_engine_over_expected(self) -> None:
        """Test that payload engine takes precedence when both are present."""
        healthy = success({"engine": "actual_engine", "available": True})

        normalized = normalize_engine_health(healthy, expected_engine="expected_engine")

        # Payload engine should win
        self.assertEqual(normalized["engine"], "actual_engine")
        self.assertTrue(normalized["ok"])

    def test_normalize_engine_health_handles_unavailable_in_success_result(self) -> None:
        """Test that available=False in success result is correctly normalized."""
        not_available = success({"engine": "kokoro_cpu", "available": False})

        normalized = normalize_engine_health(not_available, expected_engine="kokoro_cpu")

        self.assertEqual(normalized["engine"], "kokoro_cpu")
        self.assertFalse(normalized["ok"])
        self.assertIsNone(normalized["error"])
