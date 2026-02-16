"""Chatterbox GPU provider adapter - stub for future implementation."""

from __future__ import annotations

import struct
import wave
from io import BytesIO

from domain.ports.tts_provider import TtsVoice
from adapters.tts.base_tts_provider import BaseTtsProvider


class ChatterboxProvider(BaseTtsProvider):
    """Local-only Chatterbox adapter with GPU acceleration.
    
    NOTE: This is a stub implementation that generates silence.
    The real Chatterbox TTS engine requires:
    - Python 3.11 (not 3.13)
    - PyTorch with ROCm support (2.8GB download)
    - chatterbox-tts package
    
    See INSTALLATION.md for complete setup instructions.
    """

    engine_name = "chatterbox_gpu"

    def _get_available_voice_ids(self) -> list[str]:
        """Return available voice IDs for Chatterbox engine."""
        return ["default"]

    def _get_sample_rate(self) -> int:
        """Chatterbox GPU engine sample rate: 24kHz."""
        return 24000

    def _synthesize_audio(self, text: str, voice: str) -> bytes:
        """Synthesize audio using Chatterbox engine.

        Currently returns a minimal valid WAV file with silence.
        Real implementation will use Chatterbox TTS once environment is configured.

        Args:
            text: Text to synthesize (already validated)
            voice: Voice ID to use (already validated)

        Returns:
            WAV format audio bytes
        """
        # Generate minimal valid WAV file with silence
        # Real implementation will call Chatterbox engine:
        #
        # from chatterbox.tts_turbo import ChatterboxTurboTTS
        # model = ChatterboxTurboTTS.from_pretrained(device="cuda")
        # wav = model.generate(text, audio_prompt_path=reference_audio)
        # return wav_to_bytes(wav, self._get_sample_rate())
        
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
            silence = struct.pack('<' + 'h' * num_samples, *([0] * num_samples))
            wav_file.writeframes(silence)
        
        return buffer.getvalue()

    def _build_voice_list(self) -> list[TtsVoice]:
        """Build the list of available voices for Chatterbox engine."""
        return [
            {
                "id": "default",
                "name": "Default Chatterbox Voice (stub)",
                "engine": self.engine_name,
                "language": "en",
                "supports_streaming": False,
            }
        ]
