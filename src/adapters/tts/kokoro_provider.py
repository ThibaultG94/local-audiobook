"""Kokoro TTS provider using kokoro-onnx (CPU, ONNX Runtime)."""

from __future__ import annotations

import io
import wave
from typing import Any

try:
    from kokoro_onnx import Kokoro
    import numpy as np
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False

from domain.ports.tts_provider import TtsVoice
from adapters.tts.base_tts_provider import BaseTtsProvider

# Kokoro voice catalog
KOKORO_VOICES = {
    "af_heart": {"name": "Heart (American Female)", "lang": "en"},
    "af_sky": {"name": "Sky (American Female)", "lang": "en"},
    "am_adam": {"name": "Adam (American Male)", "lang": "en"},
    "am_michael": {"name": "Michael (American Male)", "lang": "en"},
    "bf_emma": {"name": "Emma (British Female)", "lang": "en"},
    "bm_george": {"name": "George (British Male)", "lang": "en"},
    "ff_siwis": {"name": "Siwis (French Female)", "lang": "fr"},
}

# Language code mapping
LANG_MAP = {"en": "en-us", "fr": "fr-fr"}


class KokoroProvider(BaseTtsProvider):
    """Local Kokoro TTS adapter using kokoro-onnx (CPU inference)."""

    engine_name = "kokoro_cpu"

    def __init__(
        self,
        model_path: str = "runtime/models/kokoro/kokoro-v1.0.onnx",
        voices_path: str = "runtime/models/kokoro/voices-v1.0.bin",
        speed: float = 1.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._speed = speed
        self._kokoro: Kokoro | None = None
        if KOKORO_AVAILABLE:
            try:
                self._kokoro = Kokoro(model_path, voices_path)
            except Exception:
                self._kokoro = None

    def _get_available_voice_ids(self) -> list[str]:
        return list(KOKORO_VOICES.keys()) if self._kokoro else ["default"]

    def _get_sample_rate(self) -> int:
        return 24000

    def _synthesize_audio(self, text: str, voice: str) -> bytes:
        if not self._kokoro:
            return self._generate_silence(len(text))

        voice_id = voice if voice in KOKORO_VOICES else "af_heart"
        lang_code = LANG_MAP.get(KOKORO_VOICES.get(voice_id, {}).get("lang", "en"), "en-us")

        samples, sr = self._kokoro.create(text, voice=voice_id, speed=self._speed, lang=lang_code)

        # Convert float32 numpy array to 16-bit PCM WAV
        pcm = (samples * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()

    def _generate_silence(self, text_length: int) -> bytes:
        import struct
        sr = self._get_sample_rate()
        n = sr * max(1, text_length // 100)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(struct.pack("<" + "h" * n, *([0] * n)))
        return buf.getvalue()

    def _build_voice_list(self) -> list[TtsVoice]:
        if not self._kokoro:
            return [{"id": "default", "name": "Default (Kokoro unavailable)", "engine": self.engine_name, "language": "en", "supports_streaming": False}]
        return [
            {"id": vid, "name": info["name"], "engine": self.engine_name, "language": info["lang"], "supports_streaming": False}
            for vid, info in KOKORO_VOICES.items()
        ]
