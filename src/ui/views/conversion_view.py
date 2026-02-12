"""Conversion view model controller for readiness and remediation display."""

from __future__ import annotations

from typing import Any

from contracts.result import Result


class ConversionView:
    """Framework-neutral conversion view state holder."""

    def __init__(self, *, presenter: Any, worker: Any, logger: Any) -> None:
        self._presenter = presenter
        self._worker = worker
        self._logger = logger
        self.current_state: dict[str, Any] = {
            "status": "not_ready",
            "start_enabled": False,
            "engine_availability": {"chatterbox_gpu": False, "kokoro_cpu": False},
            "remediation_items": [],
            "title": "Offline readiness",
        }
        self._worker.on_readiness_refreshed(self._on_recheck_result)

    def render_initial(self, readiness_result: Result[dict[str, Any]]) -> Result[dict[str, Any]]:
        mapped = self._presenter.map_readiness(readiness_result)
        if mapped.ok and mapped.data is not None:
            self.current_state = {
                **mapped.data,
                "title": "Offline readiness",
            }
            self._logger.emit(event="readiness.displayed", stage="readiness")
        return mapped

    def recheck(self) -> None:
        self._worker.refresh_readiness()

    def _on_recheck_result(self, readiness_result: Result[dict[str, Any]]) -> None:
        mapped = self._presenter.map_readiness(readiness_result)
        if mapped.ok and mapped.data is not None:
            self.current_state = {
                **mapped.data,
                "title": "Offline readiness",
            }

