"""Conversion view state holder for readiness and remediation display."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from contracts.result import Result


@runtime_checkable
class ReadinessPresenter(Protocol):
    """Contract for the readiness presenter dependency."""

    def map_readiness(self, readiness_result: Result[dict[str, Any]]) -> Result[dict[str, Any]]: ...


@runtime_checkable
class ReadinessWorker(Protocol):
    """Contract for the readiness worker dependency."""

    def on_readiness_refreshed(self, callback: Any) -> None: ...
    def refresh_readiness(self) -> Any: ...


@runtime_checkable
class EventLogger(Protocol):
    """Contract for the structured event logger dependency."""

    def emit(self, *, event: str, stage: str, **kwargs: Any) -> None: ...


class ConversionView:
    """Framework-neutral conversion view state holder."""

    def __init__(
        self,
        *,
        presenter: ReadinessPresenter,
        worker: ReadinessWorker,
        logger: EventLogger,
    ) -> None:
        self._presenter = presenter
        self._worker = worker
        self._logger = logger
        self.current_state: dict[str, Any] = {
            "status": "not_ready",
            "start_enabled": False,
            "engine_availability": {"chatterbox_gpu": False, "kokoro_cpu": False},
            "remediation_items": [],
            "error": None,
            "title": "Offline readiness",
        }
        self._worker.on_readiness_refreshed(self._on_recheck_result)

    def render_initial(self, readiness_result: Result[dict[str, Any]]) -> Result[dict[str, Any]]:
        mapped = self._presenter.map_readiness(readiness_result)
        if mapped.ok and mapped.data is not None:
            self.current_state = {
                **mapped.data,
                "error": None,
                "title": "Offline readiness",
            }
            self._logger.emit(event="readiness.displayed", stage="readiness")
        else:
            self.current_state["error"] = mapped.error.to_dict() if mapped.error else {"code": "unknown", "message": "Readiness mapping failed"}
        return mapped

    def recheck(self) -> None:
        self._worker.refresh_readiness()

    def _on_recheck_result(self, readiness_result: Result[dict[str, Any]]) -> None:
        mapped = self._presenter.map_readiness(readiness_result)
        if mapped.ok and mapped.data is not None:
            self.current_state = {
                **mapped.data,
                "error": None,
                "title": "Offline readiness",
            }
            self._logger.emit(event="readiness.displayed", stage="readiness")
        else:
            self.current_state["error"] = mapped.error.to_dict() if mapped.error else {"code": "unknown", "message": "Readiness recheck mapping failed"}

