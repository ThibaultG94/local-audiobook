"""Kokoro CPU fallback provider adapter using pyttsx3 for testing."""

from __future__ import annotations

import wave
from io import BytesIO
from typing import Any

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

from domain.ports.tts_provider import TtsVoice
from adapters.tts.base_tts_provider import BaseTtsProvider


class KokoroProvider(BaseTtsProvider):
    """Local-only Kokoro adapter with CPU fallback using pyttsx3.
    
    NOTE: This is a temporary implementation using pyttsx3 for testing.
    The real Kokoro TTS engine requires Python 3.11 and additional setup.
    See INSTALLATION.md for instructions on installing the real Kokoro engine.
    """

    engine_name = "kokoro_cpu"

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the Kokoro provider with pyttsx3 engine."""
        super().__init__(**kwargs)
        self._engine: Any = None
        if PYTTSX3_AVAILABLE:
            try:
                self._engine = pyttsx3.init()
                # Configure for better quality
                self._engine.setProperty('rate', 150)  # Speed
                self._engine.setProperty('volume', 0.9)  # Volume
            except Exception:
                self._engine = None

    def _get_available_voice_ids(self) -> list[str]:
        """Return available voice IDs for Kokoro engine."""
        if not PYTTSX3_AVAILABLE or self._engine is None:
            return ["default"]
        
        try:
            voices = self._engine.getProperty('voices')
            return [f"voice_{i}" for i in range(len(voices))] if voices else ["default"]
        except Exception:
            return ["default"]

    def _get_sample_rate(self) -> int:
        """Kokoro CPU engine sample rate: 22.05kHz (standard for CPU-optimized TTS)."""
        return 22050

    def _synthesize_audio(self, text: str, voice: str) -> bytes:
        """Synthesize audio using pyttsx3 engine.

        NOTE: This is a temporary implementation for testing.
        Real Kokoro TTS will be integrated once Python 3.11 environment is set up.

        Args:
            text: Text to synthesize (already validated)
            voice: Voice ID to use (already validated)

        Returns:
            WAV format audio bytes
        """
        if not PYTTSX3_AVAILABLE or self._engine is None:
            # Fallback to silence if pyttsx3 not available
            return self._generate_silence(len(text))
        
        try:
            # Select voice if not default
            if voice != "default" and voice.startswith("voice_"):
                try:
                    voice_index = int(voice.split("_")[1])
                    voices = self._engine.getProperty('voices')
                    if voices and 0 <= voice_index < len(voices):
                        self._engine.setProperty('voice', voices[voice_index].id)
                except (ValueError, IndexError, AttributeError):
                    pass  # Use default voice
            
            # Generate audio to temporary file
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            try:
                self._engine.save_to_file(text, tmp_path)
                self._engine.runAndWait()
                
                # Read the generated WAV file
                with open(tmp_path, 'rb') as f:
                    audio_bytes = f.read()
                
                return audio_bytes
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception:
            # Fallback to silence on any error
            return self._generate_silence(len(text))

    def _generate_silence(self, text_length: int) -> bytes:
        """Generate silent WAV file as fallback.
        
        Args:
            text_length: Length of text to estimate duration
            
        Returns:
            WAV format audio bytes with silence
        """
        import struct
        
        sample_rate = self._get_sample_rate()
        duration_seconds = max(1, text_length // 100)  # Rough estimate
        num_samples = sample_rate * duration_seconds
        
        # Create WAV file in memory
        buffer = BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)   # 16-bit
            wav_file.setframerate(sample_rate)
            
            # Generate silence (zeros)
            silence = struct.pack('<' + 'h' * num_samples, *([0] * num_samples))
            wav_file.writeframes(silence)
        
        return buffer.getvalue()

    def _build_voice_list(self) -> list[TtsVoice]:
        """Build the list of available voices for Kokoro engine."""
        if not PYTTSX3_AVAILABLE or self._engine is None:
            return [
                {
                    "id": "default",
                    "name": "Default Voice (pyttsx3 unavailable)",
                    "engine": self.engine_name,
                    "language": "en",
                    "supports_streaming": False,
                }
            ]
        
        try:
            voices = self._engine.getProperty('voices')
            if not voices:
                return [
                    {
                        "id": "default",
                        "name": "Default Voice",
                        "engine": self.engine_name,
                        "language": "en",
                        "supports_streaming": False,
                    }
                ]
            
            voice_list: list[TtsVoice] = []
            for i, voice in enumerate(voices):
                voice_list.append({
                    "id": f"voice_{i}",
                    "name": voice.name if hasattr(voice, 'name') else f"Voice {i}",
                    "engine": self.engine_name,
                    "language": voice.languages[0] if hasattr(voice, 'languages') and voice.languages else "en",
                    "supports_streaming": False,
                })
            
            return voice_list
        except Exception:
            return [
                {
                    "id": "default",
                    "name": "Default Voice",
                    "engine": self.engine_name,
                    "language": "en",
                    "supports_streaming": False,
                }
            ]
