"""Qt playback adapter with deterministic state mapping for local MP3/WAV audio."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

from src.contracts.result import Result, failure, success

_ALLOWED_STATES = {"idle", "loading", "playing", "paused", "stopped", "error"}


@runtime_checkable
class QtBackendPort(Protocol):
    def load(self, file_path: str) -> None: ...

    def play(self) -> None: ...

    def pause(self) -> None: ...

    def stop(self) -> None: ...

    def seek(self, position_seconds: float) -> None: ...

    def get_state(self) -> str: ...


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
        self._player.setPosition(int(float(position_seconds) * 1000))

    def get_state(self) -> str:
        state = int(self._player.state())
        # QMediaPlayer: 0=StoppedState, 1=PlayingState, 2=PausedState
        if state == 1:
            return "playing"
        if state == 2:
            return "paused"
        return "stopped"


class QtAudioPlayer:
    """Repository-free local playback adapter for MP3/WAV control operations."""

    def __init__(self, backend_factory: Callable[[], QtBackendPort] | None = None) -> None:
        if backend_factory is None:
            backend_factory = _PyQtMediaBackend
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
        return success({"state": self._state})

    def seek(self, *, position_seconds: float) -> Result[dict[str, object]]:
        backend = self._ensure_backend()
        if backend is None:
            return self._backend_unavailable_error("seek")
        if float(position_seconds) < 0:
            return failure(
                code="qt_player.seek_invalid_position",
                message="Seek position must be non-negative.",
                details={
                    "category": "input",
                    "position_seconds": float(position_seconds),
                    "remediation": "Provide a position >= 0.",
                },
                retryable=False,
            )

        try:
            backend.seek(float(position_seconds))
        except Exception as exc:
            self._state = "error"
            return self._runtime_error("seek", exc)

        return success({"state": self._state, "position_seconds": float(position_seconds)})

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
        return success({"state": self._state})

    def _ensure_backend(self) -> QtBackendPort | None:
        return self._backend

    def _backend_unavailable_error(self, action: str) -> Result[dict[str, object]]:
        self._state = "error"
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

