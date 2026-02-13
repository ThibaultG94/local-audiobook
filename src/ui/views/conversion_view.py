"""Conversion view state holder for readiness and remediation display."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.contracts.result import Result


@runtime_checkable
class ReadinessPresenter(Protocol):
    """Contract for the readiness presenter dependency."""

    def map_readiness(self, readiness_result: Result[dict[str, Any]]) -> Result[dict[str, Any]]: ...
    def map_conversion_progress(self, payload: dict[str, Any]) -> Result[dict[str, Any]]: ...
    def map_conversion_state(self, payload: dict[str, Any]) -> Result[dict[str, Any]]: ...
    def map_conversion_error(self, payload: dict[str, Any]) -> Result[dict[str, Any]]: ...


@runtime_checkable
class ReadinessWorker(Protocol):
    """Contract for the readiness worker dependency."""

    def on_readiness_refreshed(self, callback: Any) -> None: ...
    def on_conversion_progressed(self, callback: Any) -> None: ...
    def on_conversion_state_changed(self, callback: Any) -> None: ...
    def on_conversion_failed(self, callback: Any) -> None: ...
    def refresh_readiness(self) -> Any: ...


@runtime_checkable
class EventLogger(Protocol):
    """Contract for the structured event logger dependency."""

    def emit(self, *, event: str, stage: str, **kwargs: Any) -> None: ...


class ConversionView:
    """Framework-neutral conversion view state holder.
    
    The `current_state` dictionary contains:
    - status: str - "ready" or "not_ready"
    - start_enabled: bool - Whether conversion can be started
    - engine_availability: dict[str, bool] - Engine availability by engine ID
    - remediation_items: list[str] - Actionable remediation messages
    - configuration_options: dict - Available configuration options:
        - engines: list[dict] - Engine options with id, label, disabled, reason
        - voices: list[dict] - Voice options with id, label, engine, language, disabled, reason
        - languages: list[dict] - Language options with id, label, disabled, reason
        - speech_rate: dict - Speech rate bounds with min, max, step
        - output_formats: list[dict] - Format options with id, label, disabled, reason
    - error: dict | None - Error details if state update failed
    - title: str - View title
    """

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
            "configuration_options": {
                "engines": [],
                "voices": [],
                "languages": [
                    {"id": "FR", "label": "French", "disabled": False, "reason": ""},
                    {"id": "EN", "label": "English", "disabled": False, "reason": ""},
                ],
                "speech_rate": {"min": 0.5, "max": 2.0, "step": 0.05},
                "output_formats": [
                    {"id": "mp3", "label": "MP3", "disabled": False, "reason": ""},
                    {"id": "wav", "label": "WAV", "disabled": False, "reason": ""},
                ],
            },
            "error": None,
            "title": "Offline readiness",
            "conversion": {
                "status": "queued",
                "progress_percent": 0,
                "chunk_index": -1,
                "job_id": "",
                "correlation_id": "",
            },
        }
        self._worker.on_readiness_refreshed(self._on_recheck_result)
        self._worker.on_conversion_progressed(self._on_conversion_progress)
        self._worker.on_conversion_state_changed(self._on_conversion_state)
        self._worker.on_conversion_failed(self._on_conversion_error)

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

    def _on_conversion_progress(self, payload: dict[str, Any]) -> None:
        mapped = self._presenter.map_conversion_progress(payload)
        if not mapped.ok or mapped.data is None:
            self.current_state["error"] = mapped.error.to_dict() if mapped.error else {"code": "unknown", "message": "Conversion progress mapping failed"}
            return

        conversion_state = dict(self.current_state.get("conversion", {}))
        conversion_state.update(mapped.data)
        self.current_state["conversion"] = conversion_state

    def _on_conversion_state(self, payload: dict[str, Any]) -> None:
        mapped = self._presenter.map_conversion_state(payload)
        if not mapped.ok or mapped.data is None:
            self.current_state["error"] = mapped.error.to_dict() if mapped.error else {"code": "unknown", "message": "Conversion state mapping failed"}
            return

        conversion_state = dict(self.current_state.get("conversion", {}))
        conversion_state.update(mapped.data)
        self.current_state["conversion"] = conversion_state

    def _on_conversion_error(self, payload: dict[str, Any]) -> None:
        mapped = self._presenter.map_conversion_error(payload)
        if not mapped.ok or mapped.data is None:
            self.current_state["error"] = mapped.error.to_dict() if mapped.error else {"code": "unknown", "message": "Conversion error mapping failed"}
            return

        self.current_state["error"] = mapped.data
        conversion_state = dict(self.current_state.get("conversion", {}))
        conversion_state["status"] = "failed"
        self.current_state["conversion"] = conversion_state

    def build_configuration_options(
        self,
        *,
        engine_statuses: list[dict[str, Any]],
        voices: list[dict[str, Any]],
    ) -> dict[str, Any]:
        availability = {
            str(item.get("engine", "")): bool(item.get("ok", False))
            for item in engine_statuses
        }

        engine_options = []
        for engine_id, label in (("chatterbox_gpu", "Chatterbox"), ("kokoro_cpu", "Kokoro")):
            enabled = bool(availability.get(engine_id, False))
            engine_options.append(
                {
                    "id": engine_id,
                    "label": label,
                    "disabled": not enabled,
                    "reason": "Engine unavailable locally. Resolve startup readiness remediation before selecting this engine."
                    if not enabled
                    else "",
                }
            )

        voice_options: list[dict[str, Any]] = []
        for voice in voices:
            engine_id = str(voice.get("engine", ""))
            enabled = bool(availability.get(engine_id, False))
            voice_options.append(
                {
                    "id": str(voice.get("id", "")),
                    "label": str(voice.get("name", voice.get("id", ""))),
                    "engine": engine_id,
                    "language": str(voice.get("language", "")).upper(),
                    "disabled": not enabled,
                    "reason": "Selected voice is unavailable because its engine is not ready."
                    if not enabled
                    else "",
                }
            )

        option_state = {
            "engines": engine_options,
            "voices": voice_options,
            "languages": [
                {"id": "FR", "label": "French", "disabled": False, "reason": ""},
                {"id": "EN", "label": "English", "disabled": False, "reason": ""},
            ],
            "speech_rate": {"min": 0.5, "max": 2.0, "step": 0.05},
            "output_formats": [
                {"id": "mp3", "label": "MP3", "disabled": False, "reason": ""},
                {"id": "wav", "label": "WAV", "disabled": False, "reason": ""},
            ],
        }
        self.current_state["configuration_options"] = option_state
        return option_state
