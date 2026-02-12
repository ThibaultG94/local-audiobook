from __future__ import annotations

import unittest

from contracts.result import failure, success
from ui.presenters.conversion_presenter import ConversionPresenter


class TestConversionPresenter(unittest.TestCase):
    def test_maps_ready_state_and_engine_availability(self) -> None:
        presenter = ConversionPresenter()
        readiness = success(
            {
                "status": "ready",
                "engines": [
                    {"engine": "chatterbox_gpu", "ok": True},
                    {"engine": "kokoro_cpu", "ok": True},
                ],
                "remediation": [],
            }
        )

        result = presenter.map_readiness(readiness)
        self.assertTrue(result.ok)
        self.assertEqual(result.data["status"], "ready")
        self.assertTrue(result.data["start_enabled"])
        self.assertTrue(result.data["engine_availability"]["chatterbox_gpu"])
        self.assertTrue(result.data["engine_availability"]["kokoro_cpu"])

    def test_maps_not_ready_state_and_remediation(self) -> None:
        presenter = ConversionPresenter()
        readiness = success(
            {
                "status": "not_ready",
                "engines": [
                    {"engine": "chatterbox_gpu", "ok": False},
                    {"engine": "kokoro_cpu", "ok": True},
                ],
                "remediation": ["Install missing model file"],
            }
        )

        result = presenter.map_readiness(readiness)
        self.assertTrue(result.ok)
        self.assertEqual(result.data["status"], "not_ready")
        self.assertFalse(result.data["start_enabled"])
        self.assertFalse(result.data["engine_availability"]["chatterbox_gpu"])
        self.assertTrue(result.data["engine_availability"]["kokoro_cpu"])
        self.assertEqual(result.data["remediation_items"], ["Install missing model file"])

    def test_normalizes_presenter_failures_with_result_contract(self) -> None:
        presenter = ConversionPresenter()
        readiness = failure(
            code="startup_model_registry_failed",
            message="validation failed",
            details={"manifest_path": "config/model_manifest.yaml"},
        )

        result = presenter.map_readiness(readiness)
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "readiness_presenter_mapping_failed")
        self.assertIn("code", result.error.details)

