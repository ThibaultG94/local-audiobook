from __future__ import annotations

import unittest

from contracts.result import failure, success
from domain.services.startup_readiness_service import StartupReadinessService


class TestStartupReadinessService(unittest.TestCase):
    def test_status_not_ready_when_models_invalid_or_missing(self) -> None:
        models_result = success(
            {
                "models": [
                    {
                        "name": "required-a",
                        "status": "installed",
                        "remediation": "No remediation required",
                    },
                    {
                        "name": "required-b",
                        "status": "missing",
                        "remediation": "Provide model file at runtime/models/required-b.bin",
                    },
                ]
            }
        )
        engines = [
            {"engine": "chatterbox_gpu", "ok": True, "error": None},
            {"engine": "kokoro_cpu", "ok": True, "error": None},
        ]

        result = StartupReadinessService.compute(models_result=models_result, engines=engines)
        self.assertTrue(result.ok)
        self.assertEqual(result.data["status"], "not_ready")
        self.assertGreaterEqual(len(result.data["remediation"]), 1)

    def test_status_not_ready_when_engine_health_fails(self) -> None:
        models_result = success(
            {
                "models": [
                    {
                        "name": "required-a",
                        "status": "installed",
                        "remediation": "No remediation required",
                    }
                ]
            }
        )
        engines = [
            {"engine": "chatterbox_gpu", "ok": False, "error": {"details": {"engine": "chatterbox_gpu"}}},
            {"engine": "kokoro_cpu", "ok": True, "error": None},
        ]

        result = StartupReadinessService.compute(models_result=models_result, engines=engines)
        self.assertTrue(result.ok)
        self.assertEqual(result.data["status"], "not_ready")
        self.assertIn("Fix engine availability for chatterbox_gpu", result.data["remediation"])

    def test_returns_normalized_failure_if_model_registry_failed(self) -> None:
        models_result = failure(
            code="model_manifest_parse_error",
            message="broken manifest",
            details={"manifest_path": "config/model_manifest.yaml"},
        )

        result = StartupReadinessService.compute(models_result=models_result, engines=[])
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "startup_model_registry_failed")

