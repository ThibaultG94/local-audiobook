"""Chatterbox GPU provider adapter using ChatterboxTurboTTS (ROCm/CUDA)."""

from __future__ import annotations

import io
import struct
import wave
from typing import Any

try:
    import torchaudio as ta
    from chatterbox.tts_turbo import ChatterboxTurboTTS

    CHATTERBOX_AVAILABLE = True
except ImportError:
    CHATTERBOX_AVAILABLE = False

from src.domain.ports.tts_provider import TtsVoice
from src.adapters.tts.base_tts_provider import BaseTtsProvider


class ChatterboxProvider(BaseTtsProvider):
    """Local Chatterbox TTS adapter with GPU acceleration via ROCm.

    Uses ChatterboxTurboTTS (350M params) for high-quality speech synthesis.
    Falls back to silence generation when the engine is not installed.
    """

    engine_name = "chatterbox_gpu"

    def __init__(
        self,
        device: str = "cuda",
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._device = device
        self._exaggeration = exaggeration
        self._cfg_weight = cfg_weight
        self._model: Any = None

        if CHATTERBOX_AVAILABLE:
            try:
                self._model = ChatterboxTurboTTS.from_pretrained(device=self._device)
            except Exception:
                self._model = None

    def _get_available_voice_ids(self) -> list[str]:
        return ["default"]

    def _get_sample_rate(self) -> int:
        if self._model is not None and hasattr(self._model, "sr"):
            return int(self._model.sr)
        return 24000

    def _synthesize_audio(self, text: str, voice: str) -> bytes:
        """Synthesize audio using Chatterbox Turbo engine."""
        if not self._model:
            return self._generate_silence(len(text))

        wav_tensor = self._model.generate(
            text,
            exaggeration=self._exaggeration,
            cfg_weight=self._cfg_weight,
        )

        sample_rate = self._get_sample_rate()
        buf = io.BytesIO()
        ta.save(buf, wav_tensor, sample_rate, format="wav")
        return buf.getvalue()

    def _generate_silence(self, text_length: int) -> bytes:
        """Generate silent WAV as fallback when engine is unavailable."""
        sr = self._get_sample_rate()
        num_samples = sr * max(1, text_length // 100)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(struct.pack("<" + "h" * num_samples, *([0] * num_samples)))
        return buf.getvalue()

    def _build_voice_list(self) -> list[TtsVoice]:
        if not self._model:
            return [
                {
                    "id": "default",
                    "name": "Default (Chatterbox unavailable)",
                    "engine": self.engine_name,
                    "language": "en",
                    "supports_streaming": False,
                }
            ]
        return [
            {
                "id": "default",
                "name": "Chatterbox Turbo Default",
                "engine": self.engine_name,
                "language": "en",
                "supports_streaming": False,
            }
        ]
