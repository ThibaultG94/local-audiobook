"""Base TTS provider with shared functionality."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from contracts.result import Result, failure
from domain.ports.tts_provider import ProviderLogger, TtsProvider, TtsSynthesisData
from infrastructure.logging.event_schema import utc_now_iso


class BaseTtsProvider(TtsProvider):
    """Base class for TTS providers with shared validation and logging."""

    def __init__(
        self,
        *,
        healthy: bool = True,
        model_available: bool | None = None,
        logger: ProviderLogger | None = None,
    ) -> None:
        self._healthy = healthy
        # When model_available is explicitly set, it overrides the healthy flag
        # for health_check.  This allows the bootstrap to wire real model state
        # into the provider so health_check reflects asset reality.
        self._model_available = model_available
        self._logger = logger

    def _emit_event(
        self,
        *,
        event: str,
        stage: str,
        severity: str = "INFO",
        correlation_id: str,
        job_id: str,
        chunk_index: int,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Emit a structured event through the logger.

        Args:
            event: Event name in domain.action format (e.g., "tts.synthesis_started")
            stage: Processing stage (e.g., "tts")
            severity: Event severity level (INFO, ERROR, etc.)
            correlation_id: Correlation ID for request tracing
            job_id: Job identifier
            chunk_index: Chunk index within job
            extra: Additional event-specific data
        """
        if self._logger is None:
            return
        self._logger.emit(
            event=event,
            stage=stage,
            severity=severity,
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=chunk_index,
            engine=self.engine_name,
            timestamp=utc_now_iso(),
            extra=extra,
        )

    def _validate_text_input(self, text: str) -> Result[None]:
        """Validate text input for synthesis.

        Args:
            text: Text to validate

        Returns:
            Success if valid, failure with normalized error otherwise
        """
        if not text.strip():
            return failure(
                code="tts_input_invalid",
                message="Text input must be a non-empty string",
                details={
                    "engine": self.engine_name,
                    "category": "input",
                    "field": "text",
                },
                retryable=False,
            )
        return Result(ok=True, data=None, error=None)

    def _validate_voice_input(self, voice: str | None, available_voices: list[str]) -> Result[str]:
        """Validate and normalize voice input.

        Args:
            voice: Voice ID to validate (None means use default)
            available_voices: List of valid voice IDs for this engine

        Returns:
            Success with normalized voice ID, or failure with validation error
        """
        if voice is None:
            return Result(ok=True, data="default", error=None)

        # Validate voice is in available list
        if voice not in available_voices:
            return failure(
                code="tts_voice_invalid",
                message=f"Voice '{voice}' is not available for engine {self.engine_name}",
                details={
                    "engine": self.engine_name,
                    "category": "input",
                    "field": "voice",
                    "requested_voice": voice,
                    "available_voices": available_voices,
                },
                retryable=False,
            )

        return Result(ok=True, data=voice, error=None)

    def _build_health_failure(self, reason: str) -> Result[dict[str, object]]:
        """Build a standardized health check failure result.

        Args:
            reason: Reason for health check failure

        Returns:
            Failure result with normalized error structure
        """
        return failure(
            code="tts_engine_unavailable",
            message=f"{self.engine_name} engine failed health check: {reason}",
            details={
                "engine": self.engine_name,
                "reason": reason,
                "category": "availability",
            },
            retryable=False,
        )

    @abstractmethod
    def _synthesize_audio(self, text: str, voice: str) -> bytes:
        """Engine-specific audio synthesis implementation.

        Args:
            text: Text to synthesize (already validated)
            voice: Voice ID to use (already validated)

        Returns:
            Raw audio bytes in engine-specific format
        """

    @abstractmethod
    def _get_available_voice_ids(self) -> list[str]:
        """Get list of available voice IDs for this engine.

        Returns:
            List of voice ID strings
        """

    @abstractmethod
    def _get_sample_rate(self) -> int:
        """Get the sample rate for this engine's audio output.

        Returns:
            Sample rate in Hz
        """
