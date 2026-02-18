"""Library presenter for browse and reopen interactions."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.contracts.result import Result


@runtime_checkable
class LibraryServicePort(Protocol):
    def browse_library(self, *, correlation_id: str) -> Result[dict[str, object]]: ...

    def reopen_library_item(self, *, correlation_id: str, item_id: str) -> Result[dict[str, object]]: ...

    def prepare_item_for_conversion(self, *, correlation_id: str, item_id: str) -> Result[dict[str, object]]: ...

    def delete_library_item(self, *, correlation_id: str, item_id: str) -> Result[dict[str, object]]: ...
    
    def check_item_in_use(self, *, item_id: str) -> bool: ...


@runtime_checkable
class PlayerServicePort(Protocol):
    def initialize_playback(
        self,
        *,
        correlation_id: str,
        playback_context: dict[str, object],
    ) -> Result[dict[str, object]]: ...

    def play(self, *, correlation_id: str) -> Result[dict[str, object]]: ...

    def pause(self, *, correlation_id: str) -> Result[dict[str, object]]: ...

    def stop(self, *, correlation_id: str) -> Result[dict[str, object]]: ...

    def seek(self, *, correlation_id: str, position_seconds: float) -> Result[dict[str, object]]: ...

    def get_status(self, *, correlation_id: str) -> Result[dict[str, object]]: ...


class LibraryPresenter:
    """Map library service results into stable UI state payloads."""

    def __init__(self, *, library_service: LibraryServicePort, player_service: PlayerServicePort) -> None:
        self._library_service = library_service
        self._player_service = player_service
        self.state: dict[str, Any] = {
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

    def load_library(self, *, correlation_id: str) -> dict[str, Any]:
        result = self._library_service.browse_library(correlation_id=correlation_id)
        if not result.ok or result.data is None:
            self.state = {
                **self.state,
                "status": "error",
                "items": [],
                "error": self._map_error(result.error.to_dict() if result.error else {}),
            }
            return self.state

        items = list(result.data.get("items", []))
        self.state = {
            **self.state,
            "status": "ready",
            "items": items,
            "conversion_context": None,
            "error": None,
        }
        return self.state

    def open_item(self, *, correlation_id: str, item_id: str) -> dict[str, Any]:
        result = self._library_service.reopen_library_item(correlation_id=correlation_id, item_id=item_id)
        if not result.ok or result.data is None:
            self.state = {
                **self.state,
                "status": "error",
                "selected_item_id": str(item_id or ""),
                "playback_context": None,
                "playback_state": "error",
                "error": self._map_error(result.error.to_dict() if result.error else {}),
            }
            return self.state

        payload = result.data
        playback_context = payload.get("playback_context") if isinstance(payload.get("playback_context"), dict) else {}
        init_result = self._player_service.initialize_playback(
            correlation_id=correlation_id,
            playback_context=dict(playback_context),
        )
        if not init_result.ok:
            self.state = {
                **self.state,
                "status": "error",
                "selected_item_id": str(item_id or ""),
                "playback_context": playback_context,
                "playback_state": "error",
                "error": self._map_error(init_result.error.to_dict() if init_result.error else {}),
            }
            return self.state

        playback_state = str((init_result.data or {}).get("state") or "stopped")
        self.state = {
            **self.state,
            "status": "opened",
            "selected_item_id": str(item_id or ""),
            "conversion_context": None,
            "playback_context": playback_context,
            "playback_state": playback_state,
            "playback_position_seconds": 0.0,
            "playback_duration_seconds": 0.0,
            "playback_progress": 0.0,
            "error": None,
        }
        return self.state

    def select_item(self, *, item_id: str) -> dict[str, Any]:
        normalized_item_id = str(item_id or "")
        self.state = {
            **self.state,
            "selected_item_id": normalized_item_id,
            "error": None,
        }
        return self.state

    def convert_selected(self, *, correlation_id: str) -> dict[str, Any]:
        selected_item_id = str(self.state.get("selected_item_id") or "")
        result = self._library_service.prepare_item_for_conversion(
            correlation_id=correlation_id,
            item_id=selected_item_id,
        )
        if not result.ok or result.data is None:
            self.state = {
                **self.state,
                "status": "error",
                "error": self._map_error(result.error.to_dict() if result.error else {}),
            }
            return self.state

        self.state = {
            **self.state,
            "status": "ready",
            "conversion_context": dict(result.data.get("conversion_context") or {}),
            "error": None,
        }
        return self.state

    def delete_selected(self, *, correlation_id: str, confirmed: bool = False) -> dict[str, Any]:
        """Delete selected library item with mandatory confirmation.
        
        Args:
            correlation_id: Correlation ID for logging
            confirmed: MUST be True to proceed with deletion (prevents accidental deletes)
        
        Returns:
            Updated state dict with deletion result or confirmation request
        """
        selected_item_id = str(self.state.get("selected_item_id") or "")
        
        # CRITICAL: Require explicit confirmation for destructive operation
        if not confirmed:
            self.state = {
                **self.state,
                "status": "confirmation_required",
                "error": {
                    "code": "library_management.confirmation_required",
                    "message": "Deletion requires confirmation to prevent accidental data loss.",
                    "details": {
                        "category": "confirmation",
                        "selected_item_id": selected_item_id,
                        "remediation": "Call delete_selected with confirmed=True to proceed.",
                    },
                    "retryable": False,
                    "remediation": "Confirm deletion to proceed.",
                },
            }
            return self.state
        
        result = self._library_service.delete_library_item(
            correlation_id=correlation_id,
            item_id=selected_item_id,
        )
        if not result.ok:
            self.state = {
                **self.state,
                "status": "error",
                "error": self._map_error(result.error.to_dict() if result.error else {}),
            }
            return self.state

        deleted_item_id = str((result.data or {}).get("deleted_item_id") or selected_item_id)
        remaining_items = [
            item for item in list(self.state.get("items") or []) if str(item.get("id") or "") != deleted_item_id
        ]
        self.state = {
            **self.state,
            "status": "ready",
            "items": remaining_items,
            "selected_item_id": "",
            "playback_context": None,
            "playback_state": "idle",
            "playback_position_seconds": 0.0,
            "playback_duration_seconds": 0.0,
            "playback_progress": 0.0,
            "error": None,
        }
        return self.state

    def play(self, *, correlation_id: str) -> dict[str, Any]:
        """Start or resume playback through player service."""
        result = self._player_service.play(correlation_id=correlation_id)
        return self._update_from_player_result(result)

    def pause(self, *, correlation_id: str) -> dict[str, Any]:
        """Pause active playback through player service."""
        result = self._player_service.pause(correlation_id=correlation_id)
        return self._update_from_player_result(result)

    def seek(self, *, correlation_id: str, position_seconds: float) -> dict[str, Any]:
        """Seek to specific position through player service."""
        result = self._player_service.seek(correlation_id=correlation_id, position_seconds=position_seconds)
        return self._update_from_player_result(result)

    def refresh_playback_status(self, *, correlation_id: str) -> dict[str, Any]:
        """Refresh playback status from player service."""
        result = self._player_service.get_status(correlation_id=correlation_id)
        return self._update_from_player_result(result)

    def _update_from_player_result(self, result: Result[dict[str, object]]) -> dict[str, Any]:
        if not result.ok:
            self.state = {
                **self.state,
                "status": "error",
                "error": self._map_error(result.error.to_dict() if result.error else {}),
            }
            return self.state

        payload = dict(result.data or {})
        self.state = {
            **self.state,
            "status": "opened",
            "playback_state": str(payload.get("state") or self.state.get("playback_state") or "idle"),
            "playback_position_seconds": float(payload.get("position_seconds") or 0.0),
            "playback_duration_seconds": float(payload.get("duration_seconds") or 0.0),
            "playback_progress": float(payload.get("progress") or 0.0),
            "error": None,
        }
        return self.state

    @staticmethod
    def _map_error(error: dict[str, Any]) -> dict[str, Any]:
        details = error.get("details", {}) if isinstance(error.get("details"), dict) else {}
        remediation = str(details.get("remediation") or "Review local metadata and retry.")
        return {
            "code": str(error.get("code") or "library_browse.unknown_error"),
            "message": str(error.get("message") or "Unable to load local library item."),
            "details": details,
            "retryable": bool(error.get("retryable", False)),
            "remediation": remediation,
        }
