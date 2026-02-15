"""Qt playback adapter with deterministic state mapping for local MP3/WAV audio."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

from src.contracts.result import Result, failure, success

_ALLOWED_STATES = {"idle", "loading", "playing", "paused", "stopped", "error"}
_MS_PER_SECOND = 1000


class QtBackendPort(Protocol):
    def load(self, file_path: str) -> None: ...

    def play(self) -> None: ...

    def pause(self) -> None: ...

    def stop(self) -> None: ...

    def seek(self, position_seconds: float) -> None: ...

    def get_state(self) -> str: ...

    def get_position_milliseconds(self) -> int: ...

    def get_duration_milliseconds(self) -> int: ...


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


class _PyQtMediaBackend:
    """Thin backend wrapper around PyQt5 multimedia APIs."""

    def __init__(self) -> None:
        from PyQt5.QtCore import QUrl
        from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer

        self._QUrl = QUrl
        self._QMediaContent = QMediaContent
        self._QMediaPlayer = QMediaPlayer
        self._player = QMediaPlayer()

    def load(self, file_path: str) -> None:
        url = self._QUrl.fromLocalFile(str(Path(file_path).resolve()))
        self._player.setMedia(self._QMediaContent(url))

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    def seek(self, position_seconds: float) -> None:
        # QMediaPlayer.setPosition expects milliseconds, not seconds
        self._player.setPosition(int(float(position_seconds) * _MS_PER_SECOND))

    def get_state(self) -> str:
        state = int(self._player.state())
        # QMediaPlayer: 0=StoppedState, 1=PlayingState, 2=PausedState
        if state == 1:
            return "playing"
        if state == 2:
            return "paused"
        return "stopped"

    def get_position_milliseconds(self) -> int:
        return int(self._player.position())

    def get_duration_milliseconds(self) -> int:
        return int(self._player.duration())


class QtAudioPlayer:
    """Repository-free local playback adapter for MP3/WAV control operations."""

    def __init__(
        self,
        backend_factory: Callable[[], QtBackendPort] | None = None,
        logger: EventLoggerPort | None = None,
    ) -> None:
        if backend_factory is None:
            backend_factory = _PyQtMediaBackend
        self._logger = logger
        try:
            self._backend = backend_factory()
        except Exception as exc:
            self._backend = None
            self._backend_boot_error = str(exc)
        else:
            self._backend_boot_error = ""
        self._state = "idle"

    def load(self, *, file_path: str) -> Result[dict[str, object]]:
        backend = self._ensure_backend()
        if backend is None:
            return self._backend_unavailable_error("load")

        try:
            self._state = "loading"
            backend.load(str(file_path))
        except Exception as exc:
            self._state = "error"
            self._emit(
                event="player.error",
                severity="ERROR",
                extra={"action": "load", "file_path": str(file_path), "exception": str(exc)},
            )
            return failure(
                code="qt_player.load_failed",
                message="Qt backend failed to load local audio file.",
                details={
                    "category": "playback",
                    "file_path": str(file_path),
                    "exception": str(exc),
                    "remediation": "Verify local media backend availability and retry.",
                },
                retryable=True,
            )

        self._state = "stopped"
        self._emit(event="player.loaded", severity="INFO", extra={"file_path": str(file_path)})
        return success({"state": self._state, "file_path": str(file_path)})

    def play(self) -> Result[dict[str, object]]:
        backend = self._ensure_backend()
        if backend is None:
            return self._backend_unavailable_error("play")

        try:
            backend.play()
        except Exception as exc:
            self._state = "error"
            return self._runtime_error("play", exc)

        self._state = "playing"
        self._emit(event="player.play_started", severity="INFO", extra={})
        return success({"state": self._state})

    def pause(self) -> Result[dict[str, object]]:
        backend = self._ensure_backend()
        if backend is None:
            return self._backend_unavailable_error("pause")

        try:
            backend.pause()
        except Exception as exc:
            self._state = "error"
            return self._runtime_error("pause", exc)

        self._state = "paused"
        self._emit(event="player.paused", severity="INFO", extra={})
        return success({"state": self._state})

    def stop(self) -> Result[dict[str, object]]:
        backend = self._ensure_backend()
        if backend is None:
            return self._backend_unavailable_error("stop")

        try:
            backend.stop()
        except Exception as exc:
            self._state = "error"
            return self._runtime_error("stop", exc)

        self._state = "stopped"
        self._emit(event="player.stopped", severity="INFO", extra={})
        return success({"state": self._state})

    def seek(self, *, position_seconds: float) -> Result[dict[str, object]]:
        backend = self._ensure_backend()
        if backend is None:
            return self._backend_unavailable_error("seek")
        
        # Validate numeric position
        try:
            normalized_position = float(position_seconds)
        except (TypeError, ValueError):
            return failure(
                code="qt_player.seek_invalid_position",
                message="Seek position must be a numeric value.",
                details={
                    "category": "input",
                    "position_seconds": position_seconds,
                    "remediation": "Provide a numeric position in seconds.",
                },
                retryable=False,
            )
        
        if not math.isfinite(normalized_position):
            return failure(
                code="qt_player.seek_invalid_position",
                message="Seek position must be a finite numeric value.",
                details={
                    "category": "input",
                    "position_seconds": position_seconds,
                    "remediation": "Provide a finite position (not NaN or Infinity).",
                },
                retryable=False,
            )
        
        if normalized_position < 0:
            return failure(
                code="qt_player.seek_invalid_position",
                message="Seek position must be non-negative.",
                details={
                    "category": "input",
                    "position_seconds": normalized_position,
                    "remediation": "Provide a position >= 0.",
                },
                retryable=False,
            )

        try:
            backend.seek(normalized_position)
        except Exception as exc:
            self._state = "error"
            return self._runtime_error("seek", exc)

        self._emit(event="player.seeked", severity="INFO", extra={"position_seconds": normalized_position})
        return success({"state": self._state, "position_seconds": normalized_position})

    def get_status(self) -> Result[dict[str, object]]:
        backend = self._ensure_backend()
        if backend is None:
            return self._backend_unavailable_error("status")

        try:
            raw_state = str(backend.get_state() or self._state).strip().lower()
        except Exception as exc:
            self._state = "error"
            return self._runtime_error("status", exc)

        normalized_state = raw_state if raw_state in _ALLOWED_STATES else "error"
        self._state = normalized_state
        position_seconds = 0.0
        duration_seconds = 0.0
        if hasattr(backend, "get_position_milliseconds"):
            try:
                position_seconds = max(0.0, float(backend.get_position_milliseconds()) / _MS_PER_SECOND)
            except Exception:
                position_seconds = 0.0
        if hasattr(backend, "get_duration_milliseconds"):
            try:
                duration_seconds = max(0.0, float(backend.get_duration_milliseconds()) / _MS_PER_SECOND)
            except Exception:
                duration_seconds = 0.0

        return success(
            {
                "state": self._state,
                "position_seconds": position_seconds,
                "duration_seconds": duration_seconds,
            }
        )

    def _ensure_backend(self) -> QtBackendPort | None:
        return self._backend

    def _backend_unavailable_error(self, action: str) -> Result[dict[str, object]]:
        self._state = "error"
        self._emit(
            event="player.error",
            severity="ERROR",
            extra={"action": action, "boot_error": self._backend_boot_error, "reason": "backend_unavailable"},
        )
        return failure(
            code=f"qt_player.{action}_backend_unavailable",
            message="Qt multimedia backend is unavailable for local playback.",
            details={
                "category": "configuration",
                "action": action,
                "boot_error": self._backend_boot_error,
                "remediation": "Install/verify local Qt multimedia runtime and retry.",
            },
            retryable=False,
        )

    def _runtime_error(self, action: str, exc: Exception) -> Result[dict[str, object]]:
        self._emit(
            event="player.error",
            severity="ERROR",
            extra={"action": action, "exception": str(exc)},
        )
        return failure(
            code=f"qt_player.{action}_failed",
            message=f"Qt backend failed while trying to {action} playback.",
            details={
                "category": "playback",
                "action": action,
                "exception": str(exc),
                "remediation": "Retry playback. If failure persists, verify local media backend health.",
            },
            retryable=True,
        )

    def _emit(self, *, event: str, severity: str, extra: dict[str, object]) -> None:
        if self._logger is None or not hasattr(self._logger, "emit"):
            return
        self._logger.emit(
            event=event,
            stage="player",
            severity=severity,
            correlation_id="",
            job_id="",
            chunk_index=-1,
            engine="qt_audio_player",
            timestamp=datetime.now(timezone.utc).isoformat(),
            extra=extra,
        )
