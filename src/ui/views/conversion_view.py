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
            "diagnostics": {
                "panel_visible": False,
                "details_expanded": False,
                "summary": "",
                "remediation": [],
                "details": {},
                "retry_enabled": False,
                "retry_prerequisites": [],
                "non_retryable_alternatives": [],
                "support_details": {
                    "code": "",
                    "message": "",
                    "details": {},
                    "retryable": False,
                },
                "stage": "",
                "engine": "",
                "correlation_id": "",
                "job_id": "",
                "safe_for_display": True,
            },
        }
        self._worker.on_readiness_refreshed(self._on_recheck_result)
        self._worker.on_conversion_progressed(self._on_conversion_progress)
        self._worker.on_conversion_state_changed(self._on_conversion_state)
        self._worker.on_conversion_failed(self._on_conversion_error)

    def render_initial(self, readiness_result: Result[dict[str, Any]]) -> Result[dict[str, Any]]:
        mapped = self._presenter.map_readiness(readiness_result)
        if mapped.ok and mapped.data is not None:
            self.current_state.update(mapped.data)
            self.current_state["error"] = None
            self.current_state["title"] = "Offline readiness"
            self._logger.emit(event="readiness.displayed", stage="readiness")
        else:
            self.current_state["error"] = mapped.error.to_dict() if mapped.error else {"code": "unknown", "message": "Readiness mapping failed"}
        return mapped

    def recheck(self) -> None:
        self._worker.refresh_readiness()

    def _on_recheck_result(self, readiness_result: Result[dict[str, Any]]) -> None:
        mapped = self._presenter.map_readiness(readiness_result)
        if mapped.ok and mapped.data is not None:
            self.current_state.update(mapped.data)
            self.current_state["error"] = None
            self.current_state["title"] = "Offline readiness"
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
        # Propagate correlation context from payload if not in mapped data
        if "correlation_id" not in conversion_state and "correlation_id" in payload:
            conversion_state["correlation_id"] = str(payload["correlation_id"])
        if "job_id" not in conversion_state and "job_id" in payload:
            conversion_state["job_id"] = str(payload["job_id"])
        self.current_state["conversion"] = conversion_state

    def _on_conversion_state(self, payload: dict[str, Any]) -> None:
        mapped = self._presenter.map_conversion_state(payload)
        if not mapped.ok or mapped.data is None:
            self.current_state["error"] = mapped.error.to_dict() if mapped.error else {"code": "unknown", "message": "Conversion state mapping failed"}
            return

        conversion_state = dict(self.current_state.get("conversion", {}))
        conversion_state.update(mapped.data)
        self.current_state["conversion"] = conversion_state
        
        # Clear diagnostics panel when conversion completes successfully
        if conversion_state.get("status") == "completed":
            self.current_state["diagnostics"] = {
                "panel_visible": False,
                "details_expanded": False,
                "summary": "",
                "remediation": [],
                "details": {},
                "retry_enabled": False,
                "retry_prerequisites": [],
                "non_retryable_alternatives": [],
                "support_details": {
                    "code": "",
                    "message": "",
                    "details": {},
                    "retryable": False,
                },
                "stage": "",
                "engine": "",
                "correlation_id": "",
                "job_id": "",
                "safe_for_display": True,
            }

    def _on_conversion_error(self, payload: dict[str, Any]) -> None:
        mapped = self._presenter.map_conversion_error(payload)
        if not mapped.ok or mapped.data is None:
            self.current_state["error"] = mapped.error.to_dict() if mapped.error else {"code": "unknown", "message": "Conversion error mapping failed"}
            return

        self.current_state["error"] = mapped.data
        conversion_state = dict(self.current_state.get("conversion", {}))
        conversion_state["status"] = "failed"
        self.current_state["conversion"] = conversion_state
        self.current_state["diagnostics"] = {
            "panel_visible": True,
            "details_expanded": False,
            "summary": str(mapped.data.get("summary", "Conversion failed.")),
            "remediation": [str(item) for item in mapped.data.get("remediation", [])],
            "details": dict(mapped.data.get("details", {})),
            "retry_enabled": bool(mapped.data.get("retry_enabled", mapped.data.get("retryable", False))),
            "retry_prerequisites": [
                str(item)
                for item in mapped.data.get("support_workflow", {}).get("retry_prerequisites", [])
            ],
            "non_retryable_alternatives": [
                str(item)
                for item in mapped.data.get("support_workflow", {}).get("non_retryable_alternatives", [])
            ],
            "support_details": {
                "code": str(mapped.data.get("code", "conversion.failed")),
                "message": str(mapped.data.get("message", "Conversion failed.")),
                "details": dict(mapped.data.get("details", {})),
                "retryable": bool(mapped.data.get("retryable", False)),
            },
            "stage": str(mapped.data.get("stage", "")),
            "engine": str(mapped.data.get("engine", "")),
            "correlation_id": str(mapped.data.get("correlation_id", payload.get("correlation_id", ""))),
            "job_id": str(mapped.data.get("job_id", payload.get("job_id", ""))),
            "safe_for_display": not bool(mapped.data.get("hidden_internal_details", False)),
        }
        self._emit_diagnostics_event(
            event="diagnostics_ui.panel_shown",
            severity="ERROR",
            extra={
                "retryable": bool(mapped.data.get("retryable", False)),
                "error_code": str(mapped.data.get("code", "conversion.failed")),
                "details_expandable": bool(mapped.data.get("details_expandable", True)),
            },
        )

    def set_diagnostics_details_expanded(self, expanded: bool) -> None:
        diagnostics = dict(self.current_state.get("diagnostics", {}))
        diagnostics["details_expanded"] = bool(expanded)
        self.current_state["diagnostics"] = diagnostics
        self._emit_diagnostics_event(
            event="diagnostics_ui.details_toggled",
            severity="INFO",
            extra={"expanded": bool(expanded)},
        )

    def request_retry(self) -> bool:
        diagnostics = dict(self.current_state.get("diagnostics", {}))
        can_retry = bool(diagnostics.get("retry_enabled", False))
        self._emit_diagnostics_event(
            event="diagnostics_ui.retry_requested",
            severity="INFO" if can_retry else "WARNING",
            extra={"retry_enabled": can_retry},
        )
        if can_retry:
            self._emit_support_event(
                event="support_workflow.retry_initiated",
                severity="INFO",
                extra={
                    "retry_enabled": True,
                    "prerequisites": [str(item) for item in diagnostics.get("retry_prerequisites", [])],
                },
            )
        return can_retry

    def open_support_details(self) -> dict[str, Any]:
        diagnostics = dict(self.current_state.get("diagnostics", {}))
        support_details = dict(diagnostics.get("support_details", {}))
        self._emit_support_event(
            event="support_workflow.viewed",
            severity="INFO",
            extra={
                "code": str(support_details.get("code", "conversion.failed")),
                "retryable": bool(support_details.get("retryable", False)),
            },
        )
        return support_details

    def copy_support_details(self) -> dict[str, Any]:
        diagnostics = dict(self.current_state.get("diagnostics", {}))
        support_details = dict(diagnostics.get("support_details", {}))
        self._emit_support_event(
            event="support_workflow.copied",
            severity="INFO",
            extra={
                "code": str(support_details.get("code", "conversion.failed")),
                "retryable": bool(support_details.get("retryable", False)),
            },
        )
        return support_details

    def _emit_diagnostics_event(self, *, event: str, severity: str, extra: dict[str, Any]) -> None:
        diagnostics = dict(self.current_state.get("diagnostics", {}))
        conversion = dict(self.current_state.get("conversion", {}))
        correlation_id = str(diagnostics.get("correlation_id") or conversion.get("correlation_id") or "unknown_correlation")
        job_id = str(diagnostics.get("job_id") or conversion.get("job_id") or "")
        engine = str(diagnostics.get("engine") or "unknown_engine")
        try:
            self._logger.emit(
                event=event,
                stage="diagnostics_ui",
                severity=severity,
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=int(self.current_state.get("error", {}).get("chunk_index", -1) or -1),
                engine=engine,
                extra=extra,
            )
        except Exception as e:
            # Fallback: log to stderr when structured logging fails
            import sys
            print(f"[DIAGNOSTICS_EVENT_FAILED] {event}: {e}", file=sys.stderr)
            return

    def _emit_support_event(self, *, event: str, severity: str, extra: dict[str, Any]) -> None:
        diagnostics = dict(self.current_state.get("diagnostics", {}))
        conversion = dict(self.current_state.get("conversion", {}))
        correlation_id = str(diagnostics.get("correlation_id") or conversion.get("correlation_id") or "unknown_correlation")
        job_id = str(diagnostics.get("job_id") or conversion.get("job_id") or "")
        engine = str(diagnostics.get("engine") or "unknown_engine")
        try:
            self._logger.emit(
                event=event,
                stage="support_workflow",
                severity=severity,
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=int(self.current_state.get("error", {}).get("chunk_index", -1) or -1),
                engine=engine,
                extra=extra,
            )
        except Exception as e:
            import sys

            print(f"[SUPPORT_WORKFLOW_EVENT_FAILED] {event}: {e}", file=sys.stderr)
            return

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
