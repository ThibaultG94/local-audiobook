"""Deterministic MP3 encoding adapter (local pseudo-encoding)."""

from __future__ import annotations

import os
from pathlib import Path

from src.contracts.result import Result, failure, success


class Mp3Encoder:
    """Encode assembled audio into a deterministic MP3 artifact.
    
    NOTE: This is a pseudo-encoder for MVP testing. It generates valid MP3 frame
    headers but does not perform actual audio compression. For production use,
    this should be replaced with a real MP3 encoder (e.g., lame, ffmpeg).
    """

    _FRAME_SIZE_BYTES = 417
    _FRAME_HEADER = bytes([0xFF, 0xFB, 0x90, 0x64])
    # Frame rate calculation: 44.1kHz sample rate / 1152 samples per MP3 frame = ~38.28 frames/sec
    _FRAMES_PER_SECOND = 38.28125

    def encode_from_frames(
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
                code="audio.mp3_directory_creation_failed",
                message="Failed to create output directory",
                details={
                    "category": "io",
                    "path": str(output_path.parent),
                    "exception": str(exc),
                },
                retryable=True,
            )

        # Calculate duration from PCM data
        bytes_per_second = max(sample_rate_hz * channels * sample_width_bytes, 1)
        approx_seconds = len(pcm_frames) / float(bytes_per_second)
        frames_count = max(1, int(approx_seconds * self._FRAMES_PER_SECOND))

        # Generate pseudo-MP3 with valid frame headers
        frame_payload_size = self._FRAME_SIZE_BYTES - len(self._FRAME_HEADER)
        one_frame = self._FRAME_HEADER + (b"\x00" * frame_payload_size)
        mp3_bytes = one_frame * frames_count

        # Check available disk space
        estimated_size = len(mp3_bytes)
        try:
            stat = os.statvfs(output_path.parent)
            available_bytes = stat.f_bavail * stat.f_frsize
            if available_bytes < estimated_size:
                return failure(
                    code="audio.insufficient_disk_space",
                    message="Insufficient disk space for MP3 output",
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
            temp_path.write_bytes(mp3_bytes)
            # Atomic rename to final path
            temp_path.replace(output_path)
        except OSError as exc:
            # Cleanup temporary file on failure
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
            
            return failure(
                code="audio.mp3_encode_failed",
                message="MP3 encoding failed",
                details={
                    "category": "io",
                    "path": str(output_path),
                    "exception": str(exc),
                },
                retryable=True,
            )

        return success(
            {
                "path": str(output_path),
                "format": "mp3",
                "byte_size": output_path.stat().st_size,
                "duration_seconds": approx_seconds,
            }
        )

