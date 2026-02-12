"""Conversion readiness presenter for deterministic UI state mapping."""

from __future__ import annotations

from typing import Any

from contracts.result import Result, failure, success


class ConversionPresenter:
    """Map startup readiness payloads into a stable UI-facing view model."""

    def map_readiness(self, readiness_result: Result[dict[str, Any]]) -> Result[dict[str, Any]]:
        if not readiness_result.ok or readiness_result.data is None:
            details = readiness_result.error.to_dict() if readiness_result.error else {}
            return failure(
                code="readiness_presenter_mapping_failed",
                message="Unable to render readiness state",
                details=details,
                retryable=False,
            )

        readiness = readiness_result.data
        source_status = readiness.get("status")
        ui_status = "ready" if source_status == "ready" else "not_ready"

        engines = readiness.get("engines", [])
        engine_summary = {
            "chatterbox_gpu": self._engine_available(engines, "chatterbox_gpu"),
            "kokoro_cpu": self._engine_available(engines, "kokoro_cpu"),
        }

        remediation = [str(item) for item in readiness.get("remediation", [])]
        start_enabled = ui_status == "ready"

        return success(
            {
                "status": ui_status,
                "start_enabled": start_enabled,
                "engine_availability": engine_summary,
                "remediation_items": remediation,
            }
        )

    @staticmethod
    def _engine_available(engines: list[dict[str, Any]], expected_name: str) -> bool:
        for engine in engines:
            if str(engine.get("engine", "")) == expected_name:
                return bool(engine.get("ok", False))
        return False

