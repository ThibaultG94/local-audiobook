"""Kokoro CPU fallback provider adapter (local stub for startup validation)."""

from __future__ import annotations

import struct
import wave
from io import BytesIO

from domain.ports.tts_provider import TtsVoice
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

    def _build_voice_list(self) -> list[TtsVoice]:
        """Build the list of available voices for Kokoro engine."""
        return [
            {
                "id": "default",
                "name": "Default Kokoro Voice",
                "engine": self.engine_name,
                "language": "en",
                "supports_streaming": False,
            }
        ]
