from __future__ import annotations

import unittest

from adapters.tts.chatterbox_provider import ChatterboxProvider
from adapters.tts.kokoro_provider import KokoroProvider


class _InMemoryLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def emit(self, **payload: object) -> None:
        self.events.append(payload)


class TestTtsProviderContract(unittest.TestCase):
    def test_list_voices_returns_normalized_schema_for_both_engines(self) -> None:
        for provider in (ChatterboxProvider(), KokoroProvider()):
            result = provider.list_voices()

            self.assertTrue(result.ok)
            self.assertIsInstance(result.data, list)
            self.assertGreaterEqual(len(result.data), 1)

            first_voice = result.data[0]
            self.assertIsInstance(first_voice, dict)
            self.assertIn("id", first_voice)
            self.assertIn("name", first_voice)
            self.assertIn("engine", first_voice)
            self.assertIn("language", first_voice)
            self.assertIn("supports_streaming", first_voice)
            self.assertEqual(first_voice["engine"], provider.engine_name)

    def test_synthesize_chunk_returns_standardized_audio_payload(self) -> None:
        for provider in (ChatterboxProvider(), KokoroProvider()):
            voices = provider.list_voices()
            voice_id = voices.data[0]["id"]

            result = provider.synthesize_chunk("Bonjour le monde", voice=voice_id)

            self.assertTrue(result.ok)
            self.assertIsInstance(result.data, dict)
            self.assertIn("audio_bytes", result.data)
            self.assertIn("metadata", result.data)
            self.assertIsInstance(result.data["audio_bytes"], bytes)

            metadata = result.data["metadata"]
            self.assertIsInstance(metadata, dict)
            self.assertEqual(metadata["engine"], provider.engine_name)
            self.assertEqual(metadata["voice_id"], voice_id)
            self.assertIn("content_type", metadata)
            self.assertIn("sample_rate_hz", metadata)

    def test_synthesize_chunk_empty_text_returns_normalized_error(self) -> None:
        for provider in (ChatterboxProvider(), KokoroProvider()):
            result = provider.synthesize_chunk("   ")

            self.assertFalse(result.ok)
            error = result.error.to_dict()
            self.assertEqual(error["code"], "tts_input_invalid")
            self.assertFalse(error["retryable"])
            self.assertEqual(error["details"]["field"], "text")

    def test_health_failure_is_categorized_for_fallback_decisioning(self) -> None:
        for provider_cls in (ChatterboxProvider, KokoroProvider):
            unavailable = provider_cls(model_available=False)
            result = unavailable.health_check()

            self.assertFalse(result.ok)
            error = result.error.to_dict()
            self.assertEqual(error["code"], "tts_engine_unavailable")
            self.assertEqual(error["details"]["category"], "availability")

    def test_provider_emits_structured_events_for_synthesis_path(self) -> None:
        for provider_cls in (ChatterboxProvider, KokoroProvider):
            logger = _InMemoryLogger()
            provider = provider_cls(logger=logger)

            provider.synthesize_chunk(
                "Texte de démonstration",
                voice="default",
                correlation_id="corr-123",
                job_id="job-42",
                chunk_index=7,
            )

            self.assertGreaterEqual(len(logger.events), 2)
            first = logger.events[0]
            self.assertIn("event", first)
            self.assertIn("stage", first)
            self.assertIn("correlation_id", first)
            self.assertIn("job_id", first)
            self.assertIn("chunk_index", first)
            self.assertIn("engine", first)
            self.assertEqual(first["correlation_id"], "corr-123")
            self.assertEqual(first["job_id"], "job-42")
            self.assertEqual(first["chunk_index"], 7)

