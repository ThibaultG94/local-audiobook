"""Post-processing service for deterministic final audio assembly."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
import wave

from src.contracts.result import Result, failure, success


@runtime_checkable
class EventLoggerPort(Protocol):
    def emit(
        self,
        *,
        event: str,
        stage: str,
        severity: str = "INFO",
        correlation_id: str = "",
        job_id: str = "",
        chunk_index: int = -1,
        engine: str = "",
        timestamp: str = "",
        extra: dict[str, object] | None = None,
    ) -> None:
        ...


@runtime_checkable
class WavBuilderPort(Protocol):
    def build_from_frames(
        self,
        *,
        target_path: str,
        pcm_frames: bytes,
        sample_rate_hz: int,
        channels: int,
        sample_width_bytes: int,
    ) -> Result[dict[str, object]]:
        ...


@runtime_checkable
class Mp3EncoderPort(Protocol):
    def encode_from_frames(
        self,
        *,
        target_path: str,
        pcm_frames: bytes,
        sample_rate_hz: int,
        channels: int,
        sample_width_bytes: int,
    ) -> Result[dict[str, object]]:
        ...


class AudioPostprocessService:
    """Assemble synthesized chunks and render final output artifact."""

    def __init__(
        self,
        *,
        wav_builder: WavBuilderPort,
        mp3_encoder: Mp3EncoderPort,
        logger: EventLoggerPort | None = None,
    ) -> None:
        self._wav_builder = wav_builder
        self._mp3_encoder = mp3_encoder
        self._logger = logger

    def assemble_and_render(
        self,
        *,
        job_id: str,
        correlation_id: str,
        output_format: str,
        chunk_artifacts: list[dict[str, object]],
        target_path: str,
    ) -> Result[dict[str, object]]:
        # Validate output format early to avoid wasting CPU on assembly
        normalized_format = output_format.lower().strip()
        if normalized_format not in ("wav", "mp3"):
            return failure(
                code="audio_postprocess.unsupported_output_format",
                message="Output format is not supported",
                details={"category": "input", "output_format": output_format, "supported": ["wav", "mp3"]},
                retryable=False,
            )

        self._emit_event(
            event="postprocess.started",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            extra={
                "output_format": normalized_format,
                "chunk_count": len(chunk_artifacts),
                "target_path": target_path,
            },
        )

        ordering_error = self._validate_ordered_artifacts(chunk_artifacts)
        if ordering_error is not None:
            self._emit_event(
                event="postprocess.failed",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                extra=ordering_error.error.to_dict() if ordering_error.error else {},
            )
            return ordering_error

        pcm_frames = bytearray()
        sample_rate_hz = 0
        channels = 0
        sample_width = 0

        for expected_index, artifact in enumerate(sorted(chunk_artifacts, key=lambda item: int(item["chunk_index"]))):
            synthesis_payload = self._extract_synthesis_payload(artifact)
            if not synthesis_payload.ok:
                self._emit_event(
                    event="postprocess.failed",
                    severity="ERROR",
                    correlation_id=correlation_id,
                    job_id=job_id,
                    chunk_index=expected_index,
                    extra=synthesis_payload.error.to_dict() if synthesis_payload.error else {},
                )
                return synthesis_payload

            data = synthesis_payload.data or {}
            audio_bytes = data["audio_bytes"]

            read_result = self._read_pcm_frames(audio_bytes=audio_bytes)
            if not read_result.ok:
                self._emit_event(
                    event="postprocess.failed",
                    severity="ERROR",
                    correlation_id=correlation_id,
                    job_id=job_id,
                    chunk_index=expected_index,
                    extra=read_result.error.to_dict() if read_result.error else {},
                )
                return read_result

            read_data = read_result.data or {}
            chunk_rate = int(read_data["sample_rate_hz"])
            chunk_channels = int(read_data["channels"])
            chunk_sample_width = int(read_data["sample_width_bytes"])
            chunk_pcm = read_data["pcm_frames"]

            # Validate minimum audio content to avoid silent/empty chunks
            if len(chunk_pcm) == 0:
                empty_chunk = failure(
                    code="audio_postprocess.empty_chunk_audio",
                    message="Chunk contains no audio frames",
                    details={
                        "category": "input",
                        "chunk_index": expected_index,
                    },
                    retryable=False,
                )
                self._emit_event(
                    event="postprocess.failed",
                    severity="ERROR",
                    correlation_id=correlation_id,
                    job_id=job_id,
                    chunk_index=expected_index,
                    extra=empty_chunk.error.to_dict() if empty_chunk.error else {},
                )
                return empty_chunk

            if expected_index == 0:
                sample_rate_hz = chunk_rate
                channels = chunk_channels
                sample_width = chunk_sample_width
            elif (chunk_rate, chunk_channels, chunk_sample_width) != (sample_rate_hz, channels, sample_width):
                mismatch = failure(
                    code="audio_postprocess.incompatible_chunk_audio",
                    message="Chunk audio parameters are not continuous across boundaries",
                    details={
                        "category": "input",
                        "chunk_index": expected_index,
                        "expected": {
                            "sample_rate_hz": sample_rate_hz,
                            "channels": channels,
                            "sample_width_bytes": sample_width,
                        },
                        "actual": {
                            "sample_rate_hz": chunk_rate,
                            "channels": chunk_channels,
                            "sample_width_bytes": chunk_sample_width,
                        },
                    },
                    retryable=False,
                )
                self._emit_event(
                    event="postprocess.failed",
                    severity="ERROR",
                    correlation_id=correlation_id,
                    job_id=job_id,
                    chunk_index=expected_index,
                    extra=mismatch.error.to_dict() if mismatch.error else {},
                )
                return mismatch

            pcm_frames.extend(chunk_pcm)

        # Memory safety check: prevent unbounded memory accumulation
        MAX_PCM_BYTES = 500 * 1024 * 1024  # 500 MB limit
        if len(pcm_frames) > MAX_PCM_BYTES:
            memory_error = failure(
                code="audio_postprocess.memory_limit_exceeded",
                message="Assembled audio exceeds maximum memory limit",
                details={
                    "category": "resource",
                    "assembled_bytes": len(pcm_frames),
                    "limit_bytes": MAX_PCM_BYTES,
                },
                retryable=False,
            )
            self._emit_event(
                event="postprocess.failed",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                extra=memory_error.error.to_dict() if memory_error.error else {},
            )
            return memory_error

        if normalized_format == "wav":
            render_result = self._wav_builder.build_from_frames(
                target_path=target_path,
                pcm_frames=bytes(pcm_frames),
                sample_rate_hz=sample_rate_hz,
                channels=channels,
                sample_width_bytes=sample_width,
            )
        elif normalized_format == "mp3":
            render_result = self._mp3_encoder.encode_from_frames(
                target_path=target_path,
                pcm_frames=bytes(pcm_frames),
                sample_rate_hz=sample_rate_hz,
                channels=channels,
                sample_width_bytes=sample_width,
            )

        if not render_result.ok:
            self._emit_event(
                event="postprocess.failed",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                extra=render_result.error.to_dict() if render_result.error else {},
            )
            return render_result

        output_artifact = render_result.data or {}
        payload = {
            "job_id": job_id,
            "output_artifact": {
                "path": str(output_artifact.get("path") or Path(target_path)),
                "format": str(output_artifact.get("format") or normalized_format),
                "byte_size": int(output_artifact.get("byte_size") or 0),
                "duration_seconds": float(output_artifact.get("duration_seconds") or 0.0),
            },
            "chunk_count": len(chunk_artifacts),
        }

        self._emit_event(
            event="postprocess.succeeded",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            extra={
                "output_format": payload["output_artifact"]["format"],
                "output_path": payload["output_artifact"]["path"],
                "chunk_count": payload["chunk_count"],
                "byte_size": payload["output_artifact"]["byte_size"],
                "duration_seconds": payload["output_artifact"]["duration_seconds"],
                "sample_rate_hz": sample_rate_hz,
                "channels": channels,
            },
        )
        return success(payload)

    def _validate_ordered_artifacts(self, chunk_artifacts: list[dict[str, object]]) -> Result[None] | None:
        if not chunk_artifacts:
            return failure(
                code="audio_postprocess.no_chunk_artifacts",
                message="No synthesized chunk artifacts available for post-processing",
                details={"category": "input"},
                retryable=False,
            )

        indices = [int(item.get("chunk_index", -1)) for item in chunk_artifacts]
        unique = sorted(set(indices))
        expected = list(range(len(unique)))

        if len(unique) != len(indices):
            return failure(
                code="audio_postprocess.duplicate_chunk_index",
                message="Duplicate chunk_index detected in synthesized artifacts",
                details={"category": "input", "indices": sorted(indices)},
                retryable=False,
            )

        if unique != expected:
            return failure(
                code="audio_postprocess.non_contiguous_chunk_order",
                message="Chunk artifacts must be contiguous from index 0",
                details={"category": "input", "expected": expected, "actual": unique},
                retryable=False,
            )

        return None

    def _extract_synthesis_payload(self, artifact: dict[str, object]) -> Result[dict[str, object]]:
        synthesis = artifact.get("synthesis")
        if not isinstance(synthesis, dict):
            return failure(
                code="audio_postprocess.missing_synthesis_payload",
                message="Chunk artifact is missing synthesis payload",
                details={"category": "input", "chunk_index": artifact.get("chunk_index", -1)},
                retryable=False,
            )

        if not bool(synthesis.get("ok", False)):
            return failure(
                code="audio_postprocess.synthesis_not_successful",
                message="Chunk synthesis payload is not successful",
                details={
                    "category": "input",
                    "chunk_index": artifact.get("chunk_index", -1),
                    "synthesis_error": synthesis.get("error"),
                },
                retryable=False,
            )

        data = synthesis.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("audio_bytes"), (bytes, bytearray)):
            return failure(
                code="audio_postprocess.missing_audio_bytes",
                message="Chunk synthesis payload does not contain audio bytes",
                details={"category": "input", "chunk_index": artifact.get("chunk_index", -1)},
                retryable=False,
            )

        return success({"audio_bytes": bytes(data["audio_bytes"])})

    def _read_pcm_frames(self, *, audio_bytes: bytes) -> Result[dict[str, object]]:
        try:
            with wave.open(BytesIO(audio_bytes), "rb") as source:
                return success(
                    {
                        "sample_rate_hz": source.getframerate(),
                        "channels": source.getnchannels(),
                        "sample_width_bytes": source.getsampwidth(),
                        "pcm_frames": source.readframes(source.getnframes()),
                    }
                )
        except (wave.Error, EOFError, OSError) as exc:
            return failure(
                code="audio_postprocess.invalid_chunk_audio",
                message="Chunk audio payload is not a valid WAV stream",
                details={"category": "input", "exception": str(exc)},
                retryable=False,
            )

    def _emit_event(
        self,
        *,
        event: str,
        severity: str,
        correlation_id: str,
        job_id: str,
        chunk_index: int = -1,
        extra: dict[str, object] | None = None,
    ) -> None:
        if self._logger is None or not hasattr(self._logger, "emit"):
            return

        self._logger.emit(
            event=event,
            stage="postprocess",
            severity=severity,
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=chunk_index,
            engine="postprocess",
            timestamp=datetime.now(timezone.utc).isoformat(),
            extra=extra or {},
        )

