"""Framework-neutral library view for browse/open flows."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LibraryPresenterPort(Protocol):
    def load_library(self, *, correlation_id: str) -> dict[str, Any]: ...

    def open_item(self, *, correlation_id: str, item_id: str) -> dict[str, Any]: ...

    def play(self, *, correlation_id: str) -> dict[str, Any]: ...

    def pause(self, *, correlation_id: str) -> dict[str, Any]: ...

    def seek(self, *, correlation_id: str, position_seconds: float) -> dict[str, Any]: ...

    def refresh_playback_status(self, *, correlation_id: str) -> dict[str, Any]: ...


class LibraryView:
    """Hold deterministic browse state and delegate actions to presenter."""

    def __init__(self, *, presenter: LibraryPresenterPort) -> None:
        self._presenter = presenter
        self.current_state: dict[str, Any] = {
            "status": "idle",
            "items": [],
            "selected_item_id": "",
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

    def play(self, *, correlation_id: str) -> dict[str, Any]:
        state = self._presenter.play(correlation_id=correlation_id)
        self.current_state = dict(state)
        return self.current_state

    def pause(self, *, correlation_id: str) -> dict[str, Any]:
        state = self._presenter.pause(correlation_id=correlation_id)
        self.current_state = dict(state)
        return self.current_state

    def seek(self, *, correlation_id: str, position_seconds: float) -> dict[str, Any]:
        state = self._presenter.seek(correlation_id=correlation_id, position_seconds=position_seconds)
        self.current_state = dict(state)
        return self.current_state

    def refresh_playback_status(self, *, correlation_id: str) -> dict[str, Any]:
        state = self._presenter.refresh_playback_status(correlation_id=correlation_id)
        self.current_state = dict(state)
        return self.current_state
