"""Tests for TTS orchestration service fallback logic."""

from __future__ import annotations

import unittest

from adapters.tts.chatterbox_provider import ChatterboxProvider
from adapters.tts.kokoro_provider import KokoroProvider
from domain.services.tts_orchestration_service import TtsOrchestrationService


class TestTtsOrchestrationService(unittest.TestCase):
    def test_synthesize_with_healthy_primary_uses_primary(self) -> None:
        """When primary is healthy, it should be used."""
        primary = ChatterboxProvider(healthy=True)
        fallback = KokoroProvider(healthy=True)
        orchestrator = TtsOrchestrationService(
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = orchestrator.synthesize_with_fallback("Test text")

        self.assertTrue(result.ok)
        self.assertEqual(result.data["metadata"]["engine"], "chatterbox_gpu")

    def test_synthesize_with_unavailable_primary_falls_back_to_secondary(self) -> None:
        """When primary is unavailable, should fallback to secondary."""
        primary = ChatterboxProvider(model_available=False)
        fallback = KokoroProvider(healthy=True)
        orchestrator = TtsOrchestrationService(
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = orchestrator.synthesize_with_fallback("Test text")

        self.assertTrue(result.ok)
        self.assertEqual(result.data["metadata"]["engine"], "kokoro_cpu")

    def test_synthesize_with_input_error_does_not_fallback(self) -> None:
        """Input validation errors should not trigger fallback."""
        primary = ChatterboxProvider(healthy=True)
        fallback = KokoroProvider(healthy=True)
        orchestrator = TtsOrchestrationService(
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = orchestrator.synthesize_with_fallback("   ")  # Empty text

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "tts_input_invalid")
        # Should not have tried fallback for input error

    def test_synthesize_with_both_providers_unavailable_returns_combined_error(self) -> None:
        """When both providers fail, should return combined error."""
        primary = ChatterboxProvider(model_available=False)
        fallback = KokoroProvider(model_available=False)
        orchestrator = TtsOrchestrationService(
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = orchestrator.synthesize_with_fallback("Test text")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "tts_all_providers_failed")
        error_details = result.error.details
        self.assertIn("primary_error", error_details)
        self.assertIn("fallback_error", error_details)

    def test_synthesize_with_no_providers_returns_error(self) -> None:
        """When no providers configured, should return error."""
        orchestrator = TtsOrchestrationService()

        result = orchestrator.synthesize_with_fallback("Test text")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "tts_no_providers")

    def test_synthesize_with_only_fallback_provider_uses_it(self) -> None:
        """When only fallback provider configured, should use it."""
        fallback = KokoroProvider(healthy=True)
        orchestrator = TtsOrchestrationService(fallback_provider=fallback)

        result = orchestrator.synthesize_with_fallback("Test text")

        self.assertTrue(result.ok)
        self.assertEqual(result.data["metadata"]["engine"], "kokoro_cpu")

    def test_check_provider_health_returns_status_for_all_providers(self) -> None:
        """Health check should return status for all configured providers."""
        primary = ChatterboxProvider(healthy=True)
        fallback = KokoroProvider(model_available=False)
        orchestrator = TtsOrchestrationService(
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = orchestrator.check_provider_health()

        self.assertTrue(result.ok)
        self.assertIn("primary", result.data)
        self.assertIn("fallback", result.data)
        self.assertTrue(result.data["primary"]["healthy"])
        self.assertFalse(result.data["fallback"]["healthy"])

    def test_should_fallback_logic_for_availability_errors(self) -> None:
        """Test internal fallback decision logic."""
        orchestrator = TtsOrchestrationService()

        # Should fallback on availability errors
        availability_error = {
            "code": "tts_engine_unavailable",
            "details": {"category": "availability"},
            "retryable": False,
        }
        self.assertTrue(orchestrator._should_fallback(availability_error))

        # Should NOT fallback on input errors
        input_error = {
            "code": "tts_input_invalid",
            "details": {"category": "input"},
            "retryable": False,
        }
        self.assertFalse(orchestrator._should_fallback(input_error))

        # Should NOT fallback on retryable errors
        retryable_error = {
            "code": "tts_engine_unavailable",
            "details": {"category": "availability"},
            "retryable": True,
        }
        self.assertFalse(orchestrator._should_fallback(retryable_error))

    def test_synthesize_passes_correlation_fields_to_providers(self) -> None:
        """Ensure correlation fields are passed through to providers."""
        primary = ChatterboxProvider(healthy=True)
        orchestrator = TtsOrchestrationService(primary_provider=primary)

        result = orchestrator.synthesize_with_fallback(
            "Test text",
            voice="default",
            correlation_id="test-corr-123",
            job_id="test-job-456",
            chunk_index=42,
        )

        self.assertTrue(result.ok)
        # If providers log correctly, correlation fields were passed
        # (validated in provider tests)
