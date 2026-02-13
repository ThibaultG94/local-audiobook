from __future__ import annotations

import unittest

from contracts.result import failure, success
from ui.presenters.conversion_presenter import ConversionPresenter


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
