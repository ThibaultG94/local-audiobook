"""Deterministic WAV rendering adapter."""

from __future__ import annotations

import os
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
        
        # Thread-safe directory creation with proper error handling
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return failure(
                code="audio.wav_directory_creation_failed",
                message="Failed to create output directory",
                details={
                    "category": "io",
                    "path": str(output_path.parent),
                    "exception": str(exc),
                },
                retryable=True,
            )

        # Check available disk space (estimate: WAV header ~44 bytes + PCM data)
        estimated_size = len(pcm_frames) + 44
        try:
            stat = os.statvfs(output_path.parent)
            available_bytes = stat.f_bavail * stat.f_frsize
            if available_bytes < estimated_size:
                return failure(
                    code="audio.insufficient_disk_space",
                    message="Insufficient disk space for WAV output",
                    details={
                        "category": "resource",
                        "required_bytes": estimated_size,
                        "available_bytes": available_bytes,
                    },
                    retryable=False,
                )
        except (OSError, AttributeError):
            # statvfs not available on all platforms, continue without check
            pass

        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        try:
            with wave.open(str(temp_path), "wb") as out:
                out.setnchannels(channels)
                out.setsampwidth(sample_width_bytes)
                out.setframerate(sample_rate_hz)
                out.writeframes(pcm_frames)
            
            # Atomic rename to final path
            temp_path.replace(output_path)
        except (OSError, WaveError) as exc:
            # Cleanup temporary file on failure
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
            
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

