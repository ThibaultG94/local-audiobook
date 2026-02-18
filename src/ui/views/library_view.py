"""Framework-neutral library view for browse/open flows."""

from __future__ import annotations

import threading
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LibraryPresenterPort(Protocol):
    def load_library(self, *, correlation_id: str) -> dict[str, Any]: ...

    def open_item(self, *, correlation_id: str, item_id: str) -> dict[str, Any]: ...

    def select_item(self, *, item_id: str) -> dict[str, Any]: ...

    def convert_selected(self, *, correlation_id: str) -> dict[str, Any]: ...

    def delete_selected(self, *, correlation_id: str) -> dict[str, Any]: ...

    def play(self, *, correlation_id: str) -> dict[str, Any]: ...

    def pause(self, *, correlation_id: str) -> dict[str, Any]: ...

    def seek(self, *, correlation_id: str, position_seconds: float) -> dict[str, Any]: ...

    def refresh_playback_status(self, *, correlation_id: str) -> dict[str, Any]: ...


class LibraryView:
    """Hold deterministic browse state and delegate actions to presenter."""

    def __init__(self, *, presenter: LibraryPresenterPort, auto_refresh_interval_seconds: float = 0.5) -> None:
        self._presenter = presenter
        self._auto_refresh_interval_seconds = max(0.05, float(auto_refresh_interval_seconds))
        self._auto_refresh_stop_event = threading.Event()
        self._auto_refresh_thread: threading.Thread | None = None
        self._auto_refresh_correlation_id = ""
        self.current_state: dict[str, Any] = {
            "status": "idle",
            "items": [],
            "selected_item_id": "",
            "conversion_context": None,
            "playback_context": None,
            "playback_state": "idle",
            "playback_position_seconds": 0.0,
            "playback_duration_seconds": 0.0,
            "playback_progress": 0.0,
            "error": None,
        }

    def load(self, *, correlation_id: str) -> dict[str, Any]:
        state = self._presenter.load_library(correlation_id=correlation_id)
        self.current_state = dict(state)
        return self.current_state

    def open_selected(self, *, correlation_id: str, item_id: str) -> dict[str, Any]:
        state = self._presenter.open_item(correlation_id=correlation_id, item_id=item_id)
        self.current_state = dict(state)
        return self.current_state

    def select_item(self, *, item_id: str) -> dict[str, Any]:
        state = self._presenter.select_item(item_id=item_id)
        self.current_state = dict(state)
        return self.current_state

    def convert_selected(self, *, correlation_id: str) -> dict[str, Any]:
        state = self._presenter.convert_selected(correlation_id=correlation_id)
        self.current_state = dict(state)
        return self.current_state

    def delete_selected(self, *, correlation_id: str) -> dict[str, Any]:
        state = self._presenter.delete_selected(correlation_id=correlation_id)
        self.current_state = dict(state)
        return self.current_state

    def play(self, *, correlation_id: str) -> dict[str, Any]:
        """Start or resume playback of the currently loaded audio."""
        state = self._presenter.play(correlation_id=correlation_id)
        self.current_state = dict(state)
        if str(self.current_state.get("playback_state") or "") == "playing":
            self._start_auto_refresh(correlation_id=correlation_id)
        else:
            self._stop_auto_refresh()
        return self.current_state

    def pause(self, *, correlation_id: str) -> dict[str, Any]:
        """Pause active playback."""
        state = self._presenter.pause(correlation_id=correlation_id)
        self.current_state = dict(state)
        self._stop_auto_refresh()
        return self.current_state

    def seek(self, *, correlation_id: str, position_seconds: float) -> dict[str, Any]:
        """Seek to a specific position in seconds within the loaded audio."""
        state = self._presenter.seek(correlation_id=correlation_id, position_seconds=position_seconds)
        self.current_state = dict(state)
        return self.current_state

    def refresh_playback_status(self, *, correlation_id: str) -> dict[str, Any]:
        """Refresh playback status including position, duration, and progress."""
        state = self._presenter.refresh_playback_status(correlation_id=correlation_id)
        self.current_state = dict(state)
        if str(self.current_state.get("playback_state") or "") != "playing":
            self._stop_auto_refresh()
        return self.current_state

    def shutdown(self) -> None:
        """Stop background playback refresh loop."""
        self._stop_auto_refresh()

    def _start_auto_refresh(self, *, correlation_id: str) -> None:
        self._auto_refresh_correlation_id = str(correlation_id or "")
        if self._auto_refresh_thread is not None and self._auto_refresh_thread.is_alive():
            return
        self._auto_refresh_stop_event.clear()
        self._auto_refresh_thread = threading.Thread(target=self._auto_refresh_loop, daemon=True)
        self._auto_refresh_thread.start()

    def _stop_auto_refresh(self) -> None:
        self._auto_refresh_stop_event.set()
        thread = self._auto_refresh_thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.2)
        self._auto_refresh_thread = None

    def _auto_refresh_loop(self) -> None:
        while not self._auto_refresh_stop_event.wait(self._auto_refresh_interval_seconds):
            state = self._presenter.refresh_playback_status(correlation_id=self._auto_refresh_correlation_id)
            self.current_state = dict(state)
            if str(self.current_state.get("playback_state") or "") != "playing":
                self._auto_refresh_stop_event.set()
                break
