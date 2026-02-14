"""Deterministic WAV rendering adapter."""

from __future__ import annotations

from pathlib import Path
from wave import Error as WaveError
import wave

from src.contracts.result import Result, failure, success


class WavBuilder:
    """Build a valid WAV artifact from assembled PCM frames."""

    def build_from_frames(
        self,
        *,
        target_path: str,
        pcm_frames: bytes,
        sample_rate_hz: int,
        channels: int,
        sample_width_bytes: int,
    ) -> Result[dict[str, object]]:
        output_path = Path(target_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with wave.open(str(output_path), "wb") as out:
                out.setnchannels(channels)
                out.setsampwidth(sample_width_bytes)
                out.setframerate(sample_rate_hz)
                out.writeframes(pcm_frames)
        except (OSError, WaveError) as exc:
            return failure(
                code="audio.wav_build_failed",
                message="WAV rendering failed",
                details={
                    "category": "io",
                    "path": str(output_path),
                    "exception": str(exc),
                },
                retryable=True,
            )

        frame_width = max(channels * sample_width_bytes, 1)
        frame_count = len(pcm_frames) // frame_width
        duration_seconds = frame_count / float(sample_rate_hz) if sample_rate_hz > 0 else 0.0

        return success(
            {
                "path": str(output_path),
                "format": "wav",
                "byte_size": output_path.stat().st_size,
                "duration_seconds": duration_seconds,
                "sample_rate_hz": sample_rate_hz,
                "channels": channels,
                "sample_width_bytes": sample_width_bytes,
            }
        )

