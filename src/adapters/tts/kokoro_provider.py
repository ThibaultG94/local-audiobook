"""Kokoro CPU fallback provider adapter (local stub for startup validation)."""

from __future__ import annotations

from typing import Any

from contracts.result import Result, failure, success
from domain.ports.tts_provider import ProviderLogger, TtsProvider, TtsSynthesisData, TtsVoice
from infrastructure.logging.event_schema import utc_now_iso


class KokoroProvider(TtsProvider):
    """Local-only Kokoro adapter."""

    engine_name = "kokoro_cpu"

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

    def synthesize_chunk(
        self,
        text: str,
        voice: str | None = None,
        *,
        correlation_id: str = "",
        job_id: str = "",
        chunk_index: int = -1,
    ) -> Result[TtsSynthesisData]:
        self._emit_event(
            event="tts.synthesis_started",
            stage="tts",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=chunk_index,
            extra={"voice": voice or "default"},
        )

        if not text.strip():
            self._emit_event(
                event="tts.synthesis_failed",
                stage="tts",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
                extra={"code": "tts_input_invalid"},
            )
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

        selected_voice = voice or "default"
        data: TtsSynthesisData = {
            "audio_bytes": text.encode("utf-8"),
            "metadata": {
                "engine": self.engine_name,
                "voice_id": selected_voice,
                "content_type": "audio/wav",
                "sample_rate_hz": 22050,
            },
        }

        self._emit_event(
            event="tts.synthesis_completed",
            stage="tts",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=chunk_index,
            extra={"voice": selected_voice},
        )
        return success(data)

    def list_voices(self) -> Result[list[TtsVoice]]:
        self._emit_event(
            event="tts.voices_listed",
            stage="tts",
            correlation_id="",
            job_id="",
            chunk_index=-1,
        )
        voices: list[TtsVoice] = [
            {
                "id": "default",
                "name": "Default Kokoro Voice",
                "engine": self.engine_name,
                "language": "en",
                "supports_streaming": False,
            }
        ]
        return success(voices)

    def health_check(self) -> Result[dict[str, object]]:
        self._emit_event(
            event="tts.health_check_started",
            stage="tts",
            correlation_id="",
            job_id="",
            chunk_index=-1,
        )
        # If model availability was explicitly provided, use it to gate health
        if self._model_available is not None and not self._model_available:
            self._emit_event(
                event="tts.health_check_failed",
                stage="tts",
                severity="ERROR",
                correlation_id="",
                job_id="",
                chunk_index=-1,
                extra={"code": "tts_engine_unavailable"},
            )
            return failure(
                code="tts_engine_unavailable",
                message="Kokoro engine model assets are missing or invalid",
                details={
                    "engine": self.engine_name,
                    "reason": "model_not_available",
                    "category": "availability",
                },
                retryable=False,
            )

        if self._healthy:
            self._emit_event(
                event="tts.health_check_completed",
                stage="tts",
                correlation_id="",
                job_id="",
                chunk_index=-1,
            )
            return success({"engine": self.engine_name, "available": True})

        self._emit_event(
            event="tts.health_check_failed",
            stage="tts",
            severity="ERROR",
            correlation_id="",
            job_id="",
            chunk_index=-1,
            extra={"code": "tts_engine_unavailable"},
        )
        return failure(
            code="tts_engine_unavailable",
            message="Kokoro engine failed startup health check",
            details={
                "engine": self.engine_name,
                "reason": "unhealthy",
                "category": "availability",
            },
            retryable=False,
        )
