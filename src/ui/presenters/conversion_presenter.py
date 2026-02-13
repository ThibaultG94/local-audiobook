"""Conversion readiness presenter for deterministic UI state mapping."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.contracts.result import Result, failure, success
from src.infrastructure.logging.noop_logger import NoopLogger


@runtime_checkable
class EventLoggerPort(Protocol):
    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: Any) -> None: ...


class ConversionPresenter:
    """Map startup readiness payloads into a stable UI-facing view model."""

    def __init__(self, *, logger: EventLoggerPort | None = None) -> None:
        self._logger = logger or NoopLogger()

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

    def map_extraction(self, extraction_result: Result[dict[str, Any]]) -> Result[dict[str, Any]]:
        if extraction_result.ok and extraction_result.data is not None:
            source_path = str(extraction_result.data.get("source_path", ""))
            sections = int(extraction_result.data.get("sections", extraction_result.data.get("pages", 0)))
            source_format = str(extraction_result.data.get("source_format", "document")).upper()
            return success(
                {
                    "status": "succeeded",
                    "severity": "INFO",
                    "message": f"{source_format} text extracted successfully.",
                    "details": {
                        "source_path": source_path,
                        "sections": sections,
                        "non_text_pages": int(extraction_result.data.get("non_text_pages", 0)),
                    },
                }
            )

        error = extraction_result.error
        code = error.code if error else "extraction.unknown"
        details = error.to_dict() if error else {"code": code, "message": "Unknown extraction error", "details": {}, "retryable": False}

        nested_details = details.get("details", {}) if isinstance(details.get("details", {}), dict) else {}
        source_format_value = str(nested_details.get("source_format", "document"))
        source_format = source_format_value.upper()
        retry_enabled = bool(details.get("retryable", False))
        correlation_id = str(nested_details.get("correlation_id", ""))
        job_id = str(nested_details.get("job_id", ""))

        # All remediation messages are strictly local-only (AC4)
        if code == "extraction.no_text_content":
            message = f"Unable to extract readable text from {source_format}. Verify file contents, then re-import the local file."
        elif code in {"extraction.malformed_package", "extraction.malformed_pdf"}:
            message = f"{source_format} structure appears invalid. Repair or replace the local file, then retry import."
        elif code == "extraction.encoding_invalid":
            message = f"{source_format} contains unreadable encoding. Save the file as UTF-8 locally and try again."
        elif code in {"extraction.unreadable_archive", "extraction.unreadable_source"}:
            message = f"{source_format} file could not be read. Check local file permissions and integrity, then retry."
        elif code == "extraction.extractor_unavailable":
            message = f"No local extractor is available for {source_format}. Verify local application setup and try again."
        elif code == "extraction.unsupported_source_format":
            message = f"{source_format} is not supported for local extraction. Choose EPUB, PDF, TXT, or MD."
        else:
            message = f"{source_format} extraction failed. Review the local file and retry import."

        self._logger.emit(
            event="diagnostics.presented",
            stage="extraction",
            severity="ERROR",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=-1,
            engine=source_format_value or "extraction",
            extra={
                "error_code": code,
                "retryable": retry_enabled,
                "source_path": str(nested_details.get("source_path", "")),
                "source_format": source_format_value,
                "remediation": message,
            },
        )

        return success(
            {
                "status": "failed",
                "severity": "ERROR",
                "message": message,
                "details": details,
                "retry_enabled": retry_enabled,
            }
        )

    @staticmethod
    def _engine_available(engines: list[dict[str, Any]], expected_name: str) -> bool:
        for engine in engines:
            if str(engine.get("engine", "")) == expected_name:
                return bool(engine.get("ok", False))
        return False
