"""Deterministic MP3 encoding adapter (local pseudo-encoding)."""

from __future__ import annotations

from pathlib import Path

from src.contracts.result import Result, failure, success


class Mp3Encoder:
    """Encode assembled audio into a deterministic MP3 artifact."""

    _FRAME_SIZE_BYTES = 417
    _FRAME_HEADER = bytes([0xFF, 0xFB, 0x90, 0x64])

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
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Pseudo-encoding: deterministic CBR frame stream.
        # This keeps the adapter boundary explicit and replaceable by real codec wiring later.
        bytes_per_second = max(sample_rate_hz * channels * sample_width_bytes, 1)
        approx_seconds = len(pcm_frames) / float(bytes_per_second)
        frames_count = max(1, int(approx_seconds * 38.28125))  # ~44.1kHz / 1152 samples

        frame_payload_size = self._FRAME_SIZE_BYTES - len(self._FRAME_HEADER)
        one_frame = self._FRAME_HEADER + (b"\x00" * frame_payload_size)
        mp3_bytes = one_frame * frames_count

        try:
            output_path.write_bytes(mp3_bytes)
        except OSError as exc:
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

