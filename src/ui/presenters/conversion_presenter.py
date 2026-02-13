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
        details = error.to_dict() if error else {}

        source_format = str(details.get("details", {}).get("source_format", "document")).upper()

        if code == "extraction.no_text_content":
            message = f"Unable to extract readable text from {source_format}. Please verify the file contents."
        elif code in {"extraction.malformed_package", "extraction.malformed_pdf"}:
            message = f"{source_format} structure appears invalid. Please provide a well-formed file."
        elif code == "extraction.encoding_invalid" and source_format in {"TXT", "MD"}:
            message = (
                f"{source_format} contains unreadable or invalid encoding data. "
                "Please save the file as UTF-8 and try again."
            )
        elif code in {"extraction.unreadable_archive", "extraction.unreadable_source"}:
            message = f"{source_format} file could not be read. Please check file permissions or integrity."
        else:
            message = f"{source_format} extraction failed. Please try again or select a different file."

        return success(
            {
                "status": "failed",
                "severity": "ERROR",
                "message": message,
                "details": details,
            }
        )

    @staticmethod
    def _engine_available(engines: list[dict[str, Any]], expected_name: str) -> bool:
        for engine in engines:
            if str(engine.get("engine", "")) == expected_name:
                return bool(engine.get("ok", False))
        return False
