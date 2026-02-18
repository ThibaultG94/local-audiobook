"""Startup readiness aggregation from model registry and engine health results."""

from __future__ import annotations

from typing import Any

from contracts.result import Result, failure, success


class StartupReadinessService:
    """Compute deterministic startup readiness for offline conversion."""

    _PRIMARY_ENGINE = "chatterbox_gpu"
    _FALLBACK_ENGINE = "kokoro_cpu"

    @staticmethod
    def _engine_ok(engines: list[dict[str, Any]], expected_name: str) -> bool | None:
        for engine in engines:
            if str(engine.get("engine", "")).strip() == expected_name:
                return bool(engine.get("ok", False))
        return None

    @staticmethod
    def compute(
        *,
        models_result: Result[dict[str, Any]],
        engines: list[dict[str, Any]],
    ) -> Result[dict[str, Any]]:
        if not models_result.ok or models_result.data is None:
            details = models_result.error.to_dict() if models_result.error else {}
            return failure(
                code="startup_model_registry_failed",
                message="Unable to compute startup readiness because model validation failed",
                details=details,
                retryable=False,
            )

        models = models_result.data.get("models", [])
        blocked_models = [
            model
            for model in models
            if model.get("status") in {"missing", "invalid"}
        ]

        failed_engines = [
            engine
            for engine in engines
            if not engine.get("ok", False)
        ]

        primary_ok = StartupReadinessService._engine_ok(engines, StartupReadinessService._PRIMARY_ENGINE)
        fallback_ok = StartupReadinessService._engine_ok(engines, StartupReadinessService._FALLBACK_ENGINE)
        any_engine_ok = any(bool(engine.get("ok", False)) for engine in engines)

        if not any_engine_ok:
            status = "not_ready"
        elif primary_ok is False and fallback_ok is True:
            status = "degraded"
        else:
            status = "ready"

        remediation: list[str] = []
        for model in blocked_models:
            remediation.append(str(model.get("remediation", "Fix model installation")))

        for engine in failed_engines:
            error = engine.get("error") or {}
            details = error.get("details") or {}
            engine_name = details.get("engine", engine.get("engine", "unknown_engine"))
            remediation.append(f"Fix engine availability for {engine_name}")

        return success(
            {
                "status": status,
                "models": models,
                "engines": engines,
                "remediation": remediation,
            }
        )
