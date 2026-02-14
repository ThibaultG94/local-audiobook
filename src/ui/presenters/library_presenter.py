"""Library presenter for browse and reopen interactions."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.contracts.result import Result


@runtime_checkable
class LibraryServicePort(Protocol):
    def browse_library(self, *, correlation_id: str) -> Result[dict[str, object]]: ...

    def reopen_library_item(self, *, correlation_id: str, item_id: str) -> Result[dict[str, object]]: ...


class LibraryPresenter:
    """Map library service results into stable UI state payloads."""

    def __init__(self, *, library_service: LibraryServicePort) -> None:
        self._library_service = library_service
        self.state: dict[str, Any] = {
            "status": "idle",
            "items": [],
            "selected_item_id": "",
            "playback_context": None,
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
                "error": self._map_error(result.error.to_dict() if result.error else {}),
            }
            return self.state

        payload = result.data
        self.state = {
            **self.state,
            "status": "opened",
            "selected_item_id": str(item_id or ""),
            "playback_context": payload.get("playback_context"),
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

