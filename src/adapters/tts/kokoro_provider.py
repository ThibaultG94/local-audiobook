"""Kokoro CPU fallback provider adapter (local stub for startup validation)."""

from __future__ import annotations

import struct
import wave
from io import BytesIO

from contracts.result import Result, success
from domain.ports.tts_provider import TtsSynthesisData, TtsVoice
from adapters.tts.base_tts_provider import BaseTtsProvider


class KokoroProvider(BaseTtsProvider):
    """Local-only Kokoro adapter with CPU fallback."""

    engine_name = "kokoro_cpu"

    def _get_available_voice_ids(self) -> list[str]:
        """Return available voice IDs for Kokoro engine."""
        return ["default"]

    def _get_sample_rate(self) -> int:
        """Kokoro CPU engine sample rate: 22.05kHz (standard for CPU-optimized TTS)."""
        return 22050

    def _synthesize_audio(self, text: str, voice: str) -> bytes:
        """Synthesize audio using Kokoro engine.

        Currently returns a minimal valid WAV file as a stub.
        TODO: Replace with actual Kokoro TTS engine integration.

        Args:
            text: Text to synthesize (already validated)
            voice: Voice ID to use (already validated)

        Returns:
            WAV format audio bytes
        """
        # Generate minimal valid WAV file with silence
        # This is a stub - real implementation will call Kokoro engine
        sample_rate = self._get_sample_rate()
        duration_seconds = max(1, len(text) // 100)  # Rough estimate
        num_samples = sample_rate * duration_seconds
        
        # Create WAV file in memory
        buffer = BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)   # 16-bit
            wav_file.setframerate(sample_rate)
            
            # Generate silence (zeros) as placeholder audio
            # Real implementation will generate actual speech
            silence = struct.pack('<' + 'h' * num_samples, *([0] * num_samples))
            wav_file.writeframes(silence)
        
        return buffer.getvalue()

    def synthesize_chunk(
        self,
        text: str,
        voice: str | None = None,
        *,
        correlation_id: str = "",
        job_id: str = "",
        chunk_index: int = -1,
    ) -> Result[TtsSynthesisData]:
        """Synthesize one text chunk into canonical audio + metadata payload."""
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
        """Return locally available voices in canonical shape."""
        self._emit_event(
            event="tts.list_voices_started",
            stage="tts",
            correlation_id="system",
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
        """Report local engine health and availability."""
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
