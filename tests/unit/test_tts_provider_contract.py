from __future__ import annotations

import unittest
import wave
from io import BytesIO

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

    def test_synthesize_chunk_produces_valid_wav_audio(self) -> None:
        """Validate that audio_bytes contain valid WAV format audio."""
        for provider in (ChatterboxProvider(), KokoroProvider()):
            result = provider.synthesize_chunk("Test audio synthesis")

            self.assertTrue(result.ok)
            audio_bytes = result.data["audio_bytes"]
            
            # Validate WAV format by parsing with wave module
            buffer = BytesIO(audio_bytes)
            with wave.open(buffer, 'rb') as wav_file:
                # Verify WAV properties
                self.assertEqual(wav_file.getnchannels(), 1, "Audio should be mono")
                self.assertEqual(wav_file.getsampwidth(), 2, "Audio should be 16-bit")
                self.assertGreater(wav_file.getnframes(), 0, "Audio should have frames")
                
                # Verify sample rate matches metadata
                expected_rate = result.data["metadata"]["sample_rate_hz"]
                self.assertEqual(wav_file.getframerate(), expected_rate)

    def test_synthesize_chunk_empty_text_returns_normalized_error(self) -> None:
        for provider in (ChatterboxProvider(), KokoroProvider()):
            result = provider.synthesize_chunk("   ")

            self.assertFalse(result.ok)
            error = result.error.to_dict()
            self.assertEqual(error["code"], "tts_input_invalid")
            self.assertFalse(error["retryable"])
            self.assertEqual(error["details"]["field"], "text")

    def test_synthesize_chunk_invalid_voice_returns_normalized_error(self) -> None:
        """Validate that invalid voice IDs are rejected with proper error."""
        for provider in (ChatterboxProvider(), KokoroProvider()):
            result = provider.synthesize_chunk("Test text", voice="nonexistent_voice")

            self.assertFalse(result.ok)
            error = result.error.to_dict()
            self.assertEqual(error["code"], "tts_voice_invalid")
            self.assertFalse(error["retryable"])
            self.assertEqual(error["details"]["field"], "voice")
            self.assertEqual(error["details"]["category"], "input")

    def test_synthesize_chunk_with_unicode_text(self) -> None:
        """Test synthesis with various Unicode characters."""
        test_cases = [
            "Hello 世界",  # CJK characters
            "Émojis: 😀🎉🚀",  # Emojis
            "Français: café, naïve",  # Accented characters
            "Math: π ≈ 3.14",  # Mathematical symbols
        ]
        
        for provider in (ChatterboxProvider(), KokoroProvider()):
            for text in test_cases:
                result = provider.synthesize_chunk(text)
                self.assertTrue(result.ok, f"Failed for text: {text}")
                self.assertGreater(len(result.data["audio_bytes"]), 0)

    def test_synthesize_chunk_with_long_text(self) -> None:
        """Test synthesis with very long text."""
        long_text = "This is a test sentence. " * 500  # ~12,500 characters
        
        for provider in (ChatterboxProvider(), KokoroProvider()):
            result = provider.synthesize_chunk(long_text)
            self.assertTrue(result.ok)
            self.assertGreater(len(result.data["audio_bytes"]), 0)

    def test_synthesize_chunk_with_special_characters(self) -> None:
        """Test synthesis with control characters and whitespace."""
        test_cases = [
            "Line one\nLine two",  # Newlines
            "Tab\tseparated\ttext",  # Tabs
            "Multiple   spaces",  # Multiple spaces
        ]
        
        for provider in (ChatterboxProvider(), KokoroProvider()):
            for text in test_cases:
                result = provider.synthesize_chunk(text)
                self.assertTrue(result.ok, f"Failed for text: {repr(text)}")

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

    def test_list_voices_emits_start_and_complete_events(self) -> None:
        """Validate that list_voices emits both start and complete events."""
        for provider_cls in (ChatterboxProvider, KokoroProvider):
            logger = _InMemoryLogger()
            provider = provider_cls(logger=logger)

            provider.list_voices()

            self.assertGreaterEqual(len(logger.events), 2)
            event_names = [e["event"] for e in logger.events]
            self.assertIn("tts.list_voices_started", event_names)
            self.assertIn("tts.list_voices_completed", event_names)

    def test_health_check_uses_system_correlation_id(self) -> None:
        """Validate that health_check uses 'system' correlation_id instead of empty string."""
        for provider_cls in (ChatterboxProvider, KokoroProvider):
            logger = _InMemoryLogger()
            provider = provider_cls(logger=logger)

            provider.health_check()

            self.assertGreater(len(logger.events), 0)
            for event in logger.events:
                self.assertEqual(event["correlation_id"], "system")
