from __future__ import annotations

import unittest

from src.contracts.result import failure, success
from src.ui.presenters.conversion_presenter import ConversionPresenter


class _FakeLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def emit(self, **payload: object) -> None:
        self.events.append(dict(payload))


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

    def test_build_conversion_config_accepts_valid_payload(self) -> None:
        logger = _FakeLogger()
        presenter = ConversionPresenter(logger=logger)

        result = presenter.build_conversion_config(
            engine="chatterbox_gpu",
            voice_id="default",
            language="fr",
            speech_rate="1.25",
            output_format="WAV",
            voice_catalog=[{"id": "default", "engine": "chatterbox_gpu", "language": "en"}],
            correlation_id="corr-cfg-ok",
            job_id="job-cfg-ok",
        )

        self.assertTrue(result.ok)
        assert result.data is not None
        self.assertEqual(
            result.data,
            {
                "engine": "chatterbox_gpu",
                "voice_id": "default",
                "language": "FR",
                "speech_rate": 1.25,
                "output_format": "wav",
            },
        )

        self.assertEqual(len(logger.events), 1)
        event = logger.events[0]
        self.assertEqual(event["event"], "configuration.saved")
        self.assertEqual(event["stage"], "configuration")

    def test_build_conversion_config_rejects_language_outside_fr_en(self) -> None:
        logger = _FakeLogger()
        presenter = ConversionPresenter(logger=logger)

        result = presenter.build_conversion_config(
            engine="chatterbox_gpu",
            voice_id="default",
            language="de",
            speech_rate=1.0,
            output_format="mp3",
            voice_catalog=[{"id": "default", "engine": "chatterbox_gpu", "language": "en"}],
            correlation_id="corr-cfg-bad-lang",
            job_id="job-cfg-bad-lang",
        )

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "configuration.language_not_supported")
        self.assertEqual(result.error.details["field"], "language")

        self.assertEqual(len(logger.events), 1)
        event = logger.events[0]
        self.assertEqual(event["event"], "configuration.rejected")
        self.assertEqual(event["stage"], "configuration")

    def test_build_conversion_config_rejects_out_of_range_speech_rate(self) -> None:
        presenter = ConversionPresenter()

        result = presenter.build_conversion_config(
            engine="chatterbox_gpu",
            voice_id="default",
            language="EN",
            speech_rate=5,
            output_format="mp3",
            voice_catalog=[{"id": "default", "engine": "chatterbox_gpu", "language": "en"}],
        )

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "configuration.speech_rate_out_of_bounds")
        self.assertEqual(result.error.details["field"], "speech_rate")

    def test_build_conversion_config_rejects_unsupported_engine(self) -> None:
        presenter = ConversionPresenter()

        result = presenter.build_conversion_config(
            engine="invalid_engine",
            voice_id="default",
            language="EN",
            speech_rate=1.0,
            output_format="mp3",
            voice_catalog=[{"id": "default", "engine": "chatterbox_gpu", "language": "en"}],
        )

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "configuration.engine_unsupported")
        self.assertEqual(result.error.details["field"], "engine")

    def test_build_conversion_config_rejects_unsupported_output_format(self) -> None:
        presenter = ConversionPresenter()

        result = presenter.build_conversion_config(
            engine="chatterbox_gpu",
            voice_id="default",
            language="EN",
            speech_rate=1.0,
            output_format="ogg",
            voice_catalog=[{"id": "default", "engine": "chatterbox_gpu", "language": "en"}],
        )

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "configuration.output_format_unsupported")
        self.assertEqual(result.error.details["field"], "output_format")

    def test_build_conversion_config_rejects_negative_speech_rate(self) -> None:
        presenter = ConversionPresenter()

        result = presenter.build_conversion_config(
            engine="chatterbox_gpu",
            voice_id="default",
            language="EN",
            speech_rate=-1.0,
            output_format="mp3",
            voice_catalog=[{"id": "default", "engine": "chatterbox_gpu", "language": "en"}],
        )

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "configuration.speech_rate_out_of_bounds")
        self.assertEqual(result.error.details["field"], "speech_rate")

    def test_build_conversion_config_rejects_empty_voice_catalog(self) -> None:
        presenter = ConversionPresenter()

        result = presenter.build_conversion_config(
            engine="chatterbox_gpu",
            voice_id="default",
            language="EN",
            speech_rate=1.0,
            output_format="mp3",
            voice_catalog=[],
        )

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "configuration.voice_catalog_empty")
        self.assertEqual(result.error.details["field"], "voice_catalog")

    def test_build_conversion_config_rejects_engine_with_no_voices_in_catalog(self) -> None:
        presenter = ConversionPresenter()

        result = presenter.build_conversion_config(
            engine="kokoro_cpu",
            voice_id="default",
            language="EN",
            speech_rate=1.0,
            output_format="mp3",
            voice_catalog=[{"id": "voice1", "engine": "chatterbox_gpu", "language": "en"}],
        )

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "configuration.engine_has_no_voices")
        self.assertEqual(result.error.details["field"], "engine")

    def test_build_conversion_config_rejects_incompatible_voice_id(self) -> None:
        presenter = ConversionPresenter()

        result = presenter.build_conversion_config(
            engine="chatterbox_gpu",
            voice_id="nonexistent_voice",
            language="EN",
            speech_rate=1.0,
            output_format="mp3",
            voice_catalog=[{"id": "default", "engine": "chatterbox_gpu", "language": "en"}],
        )

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "configuration.voice_not_compatible")
        self.assertEqual(result.error.details["field"], "voice_id")

    def test_map_conversion_progress_normalizes_payload(self) -> None:
        presenter = ConversionPresenter()
        result = presenter.map_conversion_progress(
            {
                "status": "running",
                "progress_percent": 45,
                "chunk_index": 2,
                "succeeded_chunks": 3,
                "total_chunks": 7,
            }
        )
        self.assertTrue(result.ok)
        assert result.data is not None
        self.assertEqual(result.data["status"], "running")
        self.assertEqual(result.data["progress_percent"], 45)
        self.assertEqual(result.data["chunk_index"], 2)

    def test_map_conversion_state_rejects_invalid_status(self) -> None:
        presenter = ConversionPresenter()
        result = presenter.map_conversion_state(
            {
                "status": "stalled",
                "progress_percent": 10,
                "chunk_index": 0,
            }
        )
        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "conversion.state_invalid")

    def test_map_conversion_error_returns_english_actionable_payload(self) -> None:
        presenter = ConversionPresenter()
        result = presenter.map_conversion_error(
            {
                "error": {
                    "code": "tts_orchestration.chunk_failed_unrecoverable",
                    "message": "Chunk synthesis failed for all configured providers",
                    "details": {"chunk_index": 1},
                    "retryable": False,
                }
            }
        )
        self.assertTrue(result.ok)
        assert result.data is not None
        self.assertEqual(result.data["code"], "tts_orchestration.chunk_failed_unrecoverable")
        self.assertIn("failed", result.data["summary"].lower())
        self.assertFalse(result.data["retryable"])

    def test_map_conversion_error_includes_stage_engine_and_retry_guidance(self) -> None:
        presenter = ConversionPresenter()
        result = presenter.map_conversion_error(
            {
                "job_id": "job-diag-1",
                "correlation_id": "corr-diag-1",
                "error": {
                    "code": "tts_orchestration.chunk_failed_unrecoverable",
                    "message": "Primary and fallback engines failed",
                    "details": {
                        "engine": "chatterbox_gpu",
                        "chunk_index": 2,
                        "job_id": "job-diag-1",
                        "correlation_id": "corr-diag-1",
                    },
                    "retryable": False,
                },
            }
        )
        self.assertTrue(result.ok)
        assert result.data is not None
        self.assertEqual(result.data["stage"], "tts")
        self.assertEqual(result.data["engine"], "chatterbox_gpu")
        self.assertEqual(result.data["job_id"], "job-diag-1")
        self.assertEqual(result.data["correlation_id"], "corr-diag-1")
        self.assertFalse(result.data["retry_enabled"])
        self.assertGreaterEqual(len(result.data["remediation"]), 2)

    def test_map_conversion_error_hides_unsafe_internal_trace_by_default(self) -> None:
        presenter = ConversionPresenter()
        result = presenter.map_conversion_error(
            {
                "error": {
                    "code": "persistence.write_failed",
                    "message": "Write failed",
                    "details": {
                        "stage": "persistence",
                        "traceback": "super sensitive internal stack",
                        "exception": "sqlite error",
                        "job_id": "job-2",
                    },
                    "retryable": True,
                }
            }
        )
        self.assertTrue(result.ok)
        assert result.data is not None
        self.assertNotIn("traceback", result.data["details"])
        self.assertNotIn("exception", result.data["details"])
        self.assertTrue(result.data["hidden_internal_details"])
        self.assertIn("traceback", result.data["hidden_internal_keys"])

    def test_map_conversion_error_allows_internal_trace_when_explicitly_safe(self) -> None:
        presenter = ConversionPresenter()
        result = presenter.map_conversion_error(
            {
                "error": {
                    "code": "conversion.failed",
                    "message": "failed",
                    "details": {
                        "safe_for_user_display": True,
                        "traceback": "sanitized trace allowed",
                    },
                    "retryable": False,
                }
            }
        )
        self.assertTrue(result.ok)
        assert result.data is not None
        self.assertIn("traceback", result.data["details"])
        self.assertFalse(result.data["hidden_internal_details"])

    def test_map_conversion_error_sanitizes_nested_unsafe_details_recursively(self) -> None:
        presenter = ConversionPresenter()
        result = presenter.map_conversion_error(
            {
                "error": {
                    "code": "conversion.failed",
                    "message": "failed",
                    "details": {
                        "stage": "tts",
                        "nested_error": {
                            "traceback": "nested sensitive trace",
                            "exception": "nested exception",
                            "safe_field": "this should remain",
                        },
                        "safe_top_level": "this should remain",
                    },
                    "retryable": False,
                }
            }
        )
        self.assertTrue(result.ok)
        assert result.data is not None
        # Top-level safe field should remain
        self.assertIn("safe_top_level", result.data["details"])
        # Nested dict should be present but sanitized
        self.assertIn("nested_error", result.data["details"])
        nested = result.data["details"]["nested_error"]
        self.assertNotIn("traceback", nested)
        self.assertNotIn("exception", nested)
        self.assertIn("safe_field", nested)
        # Hidden keys should include nested paths
        self.assertTrue(result.data["hidden_internal_details"])
        hidden_keys = result.data["hidden_internal_keys"]
        self.assertIn("nested_error.exception", hidden_keys)
        self.assertIn("nested_error.traceback", hidden_keys)
