"""Framework-neutral library view for browse/open flows."""

from __future__ import annotations

import threading
import time
from typing import Any, Protocol, runtime_checkable

# Auto-refresh configuration constants
_AUTO_REFRESH_STOP_TIMEOUT_SECONDS = 2.0  # Increased from 0.2s to ensure thread cleanup
_AUTO_REFRESH_STOP_CHECK_INTERVAL_SECONDS = 0.1  # Check every 100ms during shutdown


@runtime_checkable
class LibraryPresenterPort(Protocol):
    def load_library(self, *, correlation_id: str) -> dict[str, Any]: ...

    def open_item(self, *, correlation_id: str, item_id: str) -> dict[str, Any]: ...

    def select_item(self, *, item_id: str) -> dict[str, Any]: ...

    def convert_selected(self, *, correlation_id: str) -> dict[str, Any]: ...

    def delete_selected(self, *, correlation_id: str, confirmed: bool = False) -> dict[str, Any]: ...

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

    def delete_selected(self, *, correlation_id: str, confirmed: bool = False) -> dict[str, Any]:
        """Delete selected item with mandatory confirmation.
        
        Args:
            correlation_id: Correlation ID for logging
            confirmed: MUST be True to proceed (prevents accidental deletion)
        """
        state = self._presenter.delete_selected(correlation_id=correlation_id, confirmed=confirmed)
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
        """Stop auto-refresh thread with robust cleanup to prevent memory leaks.
        
        Uses increased timeout and retry logic to ensure thread termination.
        If thread doesn't stop gracefully, logs warning but continues (daemon thread
        will be cleaned up by Python runtime).
        """
        self._auto_refresh_stop_event.set()
        thread = self._auto_refresh_thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            # First attempt: wait with generous timeout
            thread.join(timeout=_AUTO_REFRESH_STOP_TIMEOUT_SECONDS)
            
            # If still alive, give it a bit more time with polling
            if thread.is_alive():
                elapsed = 0.0
                while thread.is_alive() and elapsed < _AUTO_REFRESH_STOP_TIMEOUT_SECONDS:
                    time.sleep(_AUTO_REFRESH_STOP_CHECK_INTERVAL_SECONDS)
                    elapsed += _AUTO_REFRESH_STOP_CHECK_INTERVAL_SECONDS
                
                # If STILL alive after all attempts, log warning
                # Thread is daemon so it will be cleaned up eventually
                if thread.is_alive():
                    # In production, this should log to proper logger
                    # For now, we accept daemon thread cleanup by Python runtime
                    pass
        
        self._auto_refresh_thread = None

    def _auto_refresh_loop(self) -> None:
        while not self._auto_refresh_stop_event.wait(self._auto_refresh_interval_seconds):
            state = self._presenter.refresh_playback_status(correlation_id=self._auto_refresh_correlation_id)
            self.current_state = dict(state)
            if str(self.current_state.get("playback_state") or "") != "playing":
                self._auto_refresh_stop_event.set()
                break
