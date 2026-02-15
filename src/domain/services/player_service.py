"""Domain service that orchestrates local audio playback through an adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from src.contracts.result import Result, failure, success

_ALLOWED_EXTENSIONS = {".mp3", ".wav"}
_ALLOWED_STATES = {"idle", "loading", "playing", "paused", "stopped", "error"}
_TRANSITIONS: dict[str, set[str]] = {
    "idle": {"loading", "error"},
    "loading": {"playing", "stopped", "error"},
    "playing": {"paused", "stopped", "error"},
    "paused": {"playing", "stopped", "error"},
    "stopped": {"loading", "playing", "error"},
    "error": {"loading", "stopped"},
}


@runtime_checkable
class PlaybackAdapterPort(Protocol):
    def load(self, *, file_path: str) -> Result[dict[str, object]]: ...

    def play(self) -> Result[dict[str, object]]: ...

    def pause(self) -> Result[dict[str, object]]: ...

    def stop(self) -> Result[dict[str, object]]: ...

    def seek(self, *, position_seconds: float) -> Result[dict[str, object]]: ...

    def get_status(self) -> Result[dict[str, object]]: ...


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
    ) -> None: ...


class PlayerService:
    """Service boundary for local playback initialization and controls."""

    def __init__(self, *, playback_adapter: PlaybackAdapterPort, logger: EventLoggerPort | None = None) -> None:
        self._playback_adapter = playback_adapter
        self._logger = logger
        self._state = "idle"

    def initialize_playback(
        self,
        *,
        correlation_id: str,
        playback_context: dict[str, object],
    ) -> Result[dict[str, object]]:
        self._emit(
            event="player.load_requested",
            severity="INFO",
            correlation_id=correlation_id,
            extra={"library_item_id": str(playback_context.get("library_item_id") or "")},
        )

        path_result = self._validate_playback_path(playback_context)
        if not path_result.ok:
            self._state = "error"
            self._emit(
                event="player.load_failed",
                severity="ERROR",
                correlation_id=correlation_id,
                extra={"error": path_result.error.to_dict() if path_result.error else {}},
            )
            return path_result

        resolved_audio_path = str((path_result.data or {}).get("resolved_audio_path") or "")
        self._state = "loading"
        adapter_result = self._playback_adapter.load(file_path=resolved_audio_path)
        if not adapter_result.ok:
            self._state = "error"
            error = failure(
                code="player.load_failed",
                message="Unable to load local audio file for playback.",
                details={
                    "category": "playback",
                    "audio_path": resolved_audio_path,
                    "adapter_error": adapter_result.error.to_dict() if adapter_result.error else {},
                    "remediation": "Check local file permissions, relink the item, or reconvert the audiobook.",
                },
                retryable=True,
            )
            self._emit(
                event="player.load_failed",
                severity="ERROR",
                correlation_id=correlation_id,
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        target_state = str((adapter_result.data or {}).get("state") or "stopped")
        transition = self._transition_to(target_state)
        if not transition.ok:
            self._emit(
                event="player.error",
                severity="ERROR",
                correlation_id=correlation_id,
                extra={"error": transition.error.to_dict() if transition.error else {}},
            )
            return transition

        return success(
            {
                "state": self._state,
                "playback": {
                    "audio_path": resolved_audio_path,
                    "library_item_id": str(playback_context.get("library_item_id") or ""),
                    "format": str(playback_context.get("format") or "").lower(),
                },
            }
        )

    def play(self, *, correlation_id: str) -> Result[dict[str, object]]:
        if self._state not in {"paused", "stopped"}:
            return self._invalid_transition_error(
                correlation_id=correlation_id,
                action="play",
                remediation="Load audio first, then play from paused or stopped state.",
            )

        result = self._playback_adapter.play()
        if not result.ok:
            return self._adapter_failure(correlation_id=correlation_id, action="play", result=result)

        transition = self._transition_to("playing")
        if not transition.ok:
            return transition

        self._emit(event="player.play_started", severity="INFO", correlation_id=correlation_id, extra={})
        return success({"state": self._state})

    def pause(self, *, correlation_id: str) -> Result[dict[str, object]]:
        if self._state != "playing":
            return self._invalid_transition_error(
                correlation_id=correlation_id,
                action="pause",
                remediation="Playback can be paused only while audio is currently playing.",
            )

        result = self._playback_adapter.pause()
        if not result.ok:
            return self._adapter_failure(correlation_id=correlation_id, action="pause", result=result)

        transition = self._transition_to("paused")
        if not transition.ok:
            return transition

        self._emit(event="player.paused", severity="INFO", correlation_id=correlation_id, extra={})
        return success({"state": self._state})

    def stop(self, *, correlation_id: str) -> Result[dict[str, object]]:
        if self._state not in {"playing", "paused", "loading", "stopped", "error"}:
            return self._invalid_transition_error(
                correlation_id=correlation_id,
                action="stop",
                remediation="Load audio before trying to stop playback.",
            )

        result = self._playback_adapter.stop()
        if not result.ok:
            return self._adapter_failure(correlation_id=correlation_id, action="stop", result=result)

        transition = self._transition_to("stopped")
        if not transition.ok:
            return transition

        self._emit(event="player.stopped", severity="INFO", correlation_id=correlation_id, extra={})
        return success({"state": self._state})

    def seek(self, *, correlation_id: str, position_seconds: float) -> Result[dict[str, object]]:
        if self._state not in {"playing", "paused", "stopped"}:
            return self._invalid_transition_error(
                correlation_id=correlation_id,
                action="seek",
                remediation="Load audio before seeking and use play/pause/stopped states only.",
            )

        try:
            normalized_position = float(position_seconds)
        except (TypeError, ValueError):
            error = failure(
                code="player.seek_invalid_payload",
                message="Seek position must be a numeric value in seconds.",
                details={
                    "category": "input",
                    "position_seconds": position_seconds,
                    "remediation": "Provide a numeric seek position (for example: 42.5).",
                },
                retryable=False,
            )
            self._emit(
                event="player.error",
                severity="ERROR",
                correlation_id=correlation_id,
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        if not math.isfinite(normalized_position):
            error = failure(
                code="player.seek_invalid_payload",
                message="Seek position must be a finite numeric value.",
                details={
                    "category": "input",
                    "position_seconds": position_seconds,
                    "remediation": "Provide a finite seek position in seconds.",
                },
                retryable=False,
            )
            self._emit(
                event="player.error",
                severity="ERROR",
                correlation_id=correlation_id,
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        if normalized_position < 0:
            error = failure(
                code="player.seek_invalid_position",
                message="Seek position must be a non-negative value.",
                details={
                    "category": "input",
                    "position_seconds": normalized_position,
                    "remediation": "Provide a position greater than or equal to 0.",
                },
                retryable=False,
            )
            self._emit(
                event="player.error",
                severity="ERROR",
                correlation_id=correlation_id,
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        status_result = self._playback_adapter.get_status()
        if status_result.ok:
            duration_seconds = self._coerce_non_negative_float((status_result.data or {}).get("duration_seconds"))
            if duration_seconds > 0 and normalized_position > duration_seconds:
                error = failure(
                    code="player.seek_out_of_range",
                    message="Seek position exceeds current audio duration.",
                    details={
                        "category": "input",
                        "position_seconds": normalized_position,
                        "duration_seconds": duration_seconds,
                        "remediation": "Seek to a value between 0 and the total duration.",
                    },
                    retryable=False,
                )
                self._emit(
                    event="player.error",
                    severity="ERROR",
                    correlation_id=correlation_id,
                    extra={"error": error.error.to_dict() if error.error else {}},
                )
                return error

        result = self._playback_adapter.seek(position_seconds=normalized_position)
        if not result.ok:
            return self._adapter_failure(correlation_id=correlation_id, action="seek", result=result)

        self._emit(event="player.seeked", severity="INFO", correlation_id=correlation_id, extra={"position_seconds": normalized_position})
        return success({"state": self._state, "position_seconds": normalized_position})

    def get_status(self, *, correlation_id: str) -> Result[dict[str, object]]:
        result = self._playback_adapter.get_status()
        if not result.ok:
            return self._adapter_failure(correlation_id=correlation_id, action="status", result=result)

        adapter_state = str((result.data or {}).get("state") or self._state)
        transition = self._transition_to(adapter_state)
        if not transition.ok:
            return transition

        payload = dict(result.data or {})
        payload["state"] = self._state
        duration_seconds = self._coerce_non_negative_float(payload.get("duration_seconds"))
        position_seconds = self._coerce_non_negative_float(payload.get("position_seconds"))
        if duration_seconds > 0:
            position_seconds = min(position_seconds, duration_seconds)
            progress = min(1.0, max(0.0, position_seconds / duration_seconds))
        else:
            progress = 0.0

        payload["position_seconds"] = position_seconds
        payload["duration_seconds"] = duration_seconds
        payload["progress"] = progress
        return success(payload)

    @staticmethod
    def _coerce_non_negative_float(value: object) -> float:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(numeric_value):
            return 0.0
        return max(0.0, numeric_value)

    def _validate_playback_path(self, playback_context: dict[str, object]) -> Result[dict[str, object]]:
        raw_audio_path = str(playback_context.get("audio_path") or "").strip()
        if not raw_audio_path:
            return failure(
                code="player.audio_missing",
                message="Audio artifact is missing for this item.",
                details={
                    "category": "artifact",
                    "audio_path": raw_audio_path,
                    "remediation": "Relink the audio file or reconvert the source document locally.",
                },
                retryable=False,
            )

        path = Path(raw_audio_path)
        try:
            resolved_path = path.resolve()
        except OSError as exc:
            return failure(
                code="player.invalid_audio_path",
                message="Audio path is malformed and cannot be resolved.",
                details={
                    "category": "input",
                    "audio_path": raw_audio_path,
                    "exception": str(exc),
                    "remediation": "Relink the audiobook file or reconvert locally.",
                },
                retryable=False,
            )

        expected_base = Path("runtime/library/audio").resolve()
        try:
            resolved_path.relative_to(expected_base)
        except ValueError:
            return failure(
                code="player.invalid_audio_path",
                message="Audio path is outside local runtime bounds.",
                details={
                    "category": "input",
                    "audio_path": raw_audio_path,
                    "resolved_path": str(resolved_path),
                    "expected_base": str(expected_base),
                    "remediation": "Relink the item to a file under runtime/library/audio or reconvert locally.",
                },
                retryable=False,
            )

        if not resolved_path.exists() or not resolved_path.is_file():
            return failure(
                code="player.audio_missing",
                message="Audio artifact file is unavailable on disk.",
                details={
                    "category": "artifact",
                    "audio_path": raw_audio_path,
                    "resolved_path": str(resolved_path),
                    "remediation": "Relink the missing artifact path or reconvert the audiobook locally.",
                },
                retryable=False,
            )

        try:
            with resolved_path.open("rb") as stream:
                stream.read(1)
        except OSError:
            return failure(
                code="player.audio_unreadable",
                message="Audio artifact file cannot be read.",
                details={
                    "category": "artifact",
                    "audio_path": raw_audio_path,
                    "resolved_path": str(resolved_path),
                    "remediation": "Check permissions for the local file and retry.",
                },
                retryable=False,
            )

        extension = resolved_path.suffix.lower()
        format_hint = str(playback_context.get("format") or "").strip().lower()
        if extension not in _ALLOWED_EXTENSIONS or (format_hint and format_hint not in {"mp3", "wav", ""}):
            return failure(
                code="player.format_unsupported",
                message="Only local MP3 and WAV playback is supported.",
                details={
                    "category": "format",
                    "audio_path": raw_audio_path,
                    "extension": extension,
                    "format": format_hint,
                    "supported_formats": ["mp3", "wav"],
                    "remediation": "Reconvert the audiobook to MP3 or WAV, then retry playback.",
                },
                retryable=False,
            )

        return success(
            {
                "resolved_audio_path": str(resolved_path),
                "extension": extension,
            }
        )

    def _transition_to(self, target_state: str) -> Result[None]:
        normalized_target = str(target_state or "").strip().lower()
        if normalized_target not in _ALLOWED_STATES:
            return failure(
                code="player.state_unknown",
                message="Playback adapter returned an unknown state.",
                details={
                    "category": "playback",
                    "state": normalized_target,
                    "allowed_states": sorted(_ALLOWED_STATES),
                    "remediation": "Retry playback or relaunch local application.",
                },
                retryable=True,
            )

        allowed_next = _TRANSITIONS.get(self._state, set())
        if normalized_target == self._state:
            return success(None)
        if normalized_target not in allowed_next:
            return failure(
                code="player.state_transition_invalid",
                message="Invalid deterministic playback state transition.",
                details={
                    "category": "state",
                    "current_state": self._state,
                    "requested_state": normalized_target,
                    "allowed_next_states": sorted(allowed_next),
                    "remediation": "Use load/play/pause/stop in a valid order before retrying.",
                },
                retryable=False,
            )

        self._state = normalized_target
        return success(None)

    def _invalid_transition_error(self, *, correlation_id: str, action: str, remediation: str) -> Result[dict[str, object]]:
        error = failure(
            code=f"player.{action}_invalid_state",
            message=f"Cannot {action} from current playback state.",
            details={
                "category": "state",
                "state": self._state,
                "remediation": remediation,
            },
            retryable=False,
        )
        self._emit(
            event="player.error",
            severity="ERROR",
            correlation_id=correlation_id,
            extra={"error": error.error.to_dict() if error.error else {}},
        )
        return error

    def _adapter_failure(self, *, correlation_id: str, action: str, result: Result[dict[str, object]]) -> Result[dict[str, object]]:
        self._state = "error"
        error = failure(
            code=f"player.{action}_failed",
            message=f"Playback adapter failed while trying to {action} local audio.",
            details={
                "category": "playback",
                "state": self._state,
                "adapter_error": result.error.to_dict() if result.error else {},
                "remediation": "Retry locally. If this keeps failing, relink or reconvert the audiobook.",
            },
            retryable=True,
        )
        self._emit(
            event="player.error",
            severity="ERROR",
            correlation_id=correlation_id,
            extra={"error": error.error.to_dict() if error.error else {}},
        )
        return error

    def _emit(
        self,
        *,
        event: str,
        severity: str,
        correlation_id: str,
        extra: dict[str, object],
    ) -> None:
        if self._logger is None or not hasattr(self._logger, "emit"):
            return
        try:
            self._logger.emit(
                event=event,
                stage="player",
                severity=severity,
                correlation_id=correlation_id,
                job_id="",
                chunk_index=-1,
                engine="player_service",
                timestamp=datetime.now(timezone.utc).isoformat(),
                extra=extra,
            )
        except Exception:
            return
