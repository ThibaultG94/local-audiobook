"""Base TTS provider with shared functionality."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from src.contracts.result import Result, failure, success
from src.domain.ports.tts_provider import ProviderLogger, TtsProvider, TtsSynthesisData, TtsVoice
from src.infrastructure.logging.event_schema import utc_now_iso


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

    def synthesize_chunk(
        self,
        text: str,
        voice: str | None = None,
        *,
        correlation_id: str = "",
        job_id: str = "",
        chunk_index: int = -1,
    ) -> Result[TtsSynthesisData]:
        """Synthesize one text chunk into canonical audio + metadata payload.
        
        This method implements the common synthesis flow for all providers.
        """
        self._emit_event(
            event="tts.synthesis_started",
            stage="tts",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=chunk_index,
            extra={"voice": voice or "default"},
        )

        # Check engine availability before synthesis
        if self._model_available is not None and not self._model_available:
            self._emit_event(
                event="tts.synthesis_failed",
                stage="tts",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
                extra={"code": "tts_engine_unavailable"},
            )
            return self._build_health_failure("model_not_available")

        if not self._healthy:
            self._emit_event(
                event="tts.synthesis_failed",
                stage="tts",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
                extra={"code": "tts_engine_unavailable"},
            )
            return self._build_health_failure("unhealthy")

        # Validate text input
        text_validation = self._validate_text_input(text)
        if not text_validation.ok:
            self._emit_event(
                event="tts.synthesis_failed",
                stage="tts",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
                extra={"code": text_validation.error.code},
            )
            return Result(ok=False, data=None, error=text_validation.error)

        # Validate voice input
        voice_validation = self._validate_voice_input(voice, self._get_available_voice_ids())
        if not voice_validation.ok:
            self._emit_event(
                event="tts.synthesis_failed",
                stage="tts",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
                extra={"code": voice_validation.error.code},
            )
            return Result(ok=False, data=None, error=voice_validation.error)

        selected_voice = voice_validation.data
        
        # Synthesize audio
        audio_bytes = self._synthesize_audio(text, selected_voice)
        
        data: TtsSynthesisData = {
            "audio_bytes": audio_bytes,
            "metadata": {
                "engine": self.engine_name,
                "voice_id": selected_voice,
                "content_type": "audio/wav",
                "sample_rate_hz": self._get_sample_rate(),
            },
        }

        self._emit_event(
            event="tts.synthesis_completed",
            stage="tts",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=chunk_index,
            extra={"voice": selected_voice, "audio_size_bytes": len(audio_bytes)},
        )
        return success(data)

    def list_voices(self) -> Result[list[TtsVoice]]:
        """Return locally available voices in canonical shape.
        
        This method implements the common voice listing flow for all providers.
        """
        self._emit_event(
            event="tts.list_voices_started",
            stage="tts",
            correlation_id="system",
            job_id="",
            chunk_index=-1,
        )
        
        voices = self._build_voice_list()
        
        self._emit_event(
            event="tts.list_voices_completed",
            stage="tts",
            correlation_id="system",
            job_id="",
            chunk_index=-1,
            extra={"voice_count": len(voices)},
        )
        return success(voices)

    def health_check(self) -> Result[dict[str, object]]:
        """Report local engine health and availability.
        
        This method implements the common health check flow for all providers.
        """
        self._emit_event(
            event="tts.health_check_started",
            stage="tts",
            correlation_id="system",
            job_id="",
            chunk_index=-1,
        )
        
        # If model availability was explicitly provided, use it to gate health
        if self._model_available is not None and not self._model_available:
            self._emit_event(
                event="tts.health_check_failed",
                stage="tts",
                severity="ERROR",
                correlation_id="system",
                job_id="",
                chunk_index=-1,
                extra={"code": "tts_engine_unavailable"},
            )
            return self._build_health_failure("model_not_available")

        if not self._healthy:
            self._emit_event(
                event="tts.health_check_failed",
                stage="tts",
                severity="ERROR",
                correlation_id="system",
                job_id="",
                chunk_index=-1,
                extra={"code": "tts_engine_unavailable"},
            )
            return self._build_health_failure("unhealthy")

        self._emit_event(
            event="tts.health_check_completed",
            stage="tts",
            correlation_id="system",
            job_id="",
            chunk_index=-1,
        )
        return success({"engine": self.engine_name, "available": True})

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

    @abstractmethod
    def _build_voice_list(self) -> list[TtsVoice]:
        """Build the list of available voices for this engine.

        Returns:
            List of TtsVoice dictionaries with id, name, engine, language, supports_streaming
        """

    def _generate_silence(self, text_length: int) -> bytes:
        """Generate silent WAV audio as fallback when engine is unavailable.
        
        Creates a silent audio buffer with duration proportional to text length.
        Used when the TTS engine is not loaded or fails initialization.
        
        Args:
            text_length: Length of text in characters (used to estimate duration)
            
        Returns:
            WAV-formatted audio bytes containing silence
            
        Note:
            Duration heuristic: 1 second per 100 characters of text
        """
        import io
        import wave
        
        sr = self._get_sample_rate()
        num_samples = sr * max(1, text_length // 100)
        
        # Generate silence efficiently using zero bytes
        silence_pcm = bytes(num_samples * 2)  # 2 bytes per 16-bit sample
        
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(silence_pcm)
        return buf.getvalue()
