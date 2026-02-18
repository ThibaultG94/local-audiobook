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

