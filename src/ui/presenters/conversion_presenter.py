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

    _SUPPORTED_ENGINES = {"chatterbox_gpu", "kokoro_cpu"}
    _SUPPORTED_LANGUAGES = {"FR", "EN"}
    _SUPPORTED_OUTPUT_FORMATS = {"mp3", "wav"}
    _MIN_SPEECH_RATE = 0.5
    _MAX_SPEECH_RATE = 2.0
    _UNSAFE_DETAIL_KEYS = {
        "trace",
        "traceback",
        "stack",
        "stacktrace",
        "exception",
        "internal_error",
        "debug",
    }

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
        source_status = str(readiness.get("status", "")).strip()
        ui_status = source_status if source_status in {"ready", "degraded"} else "not_ready"

        engines = readiness.get("engines", [])
        engine_summary = {
            "chatterbox_gpu": self._engine_available(engines, "chatterbox_gpu"),
            "kokoro_cpu": self._engine_available(engines, "kokoro_cpu"),
        }

        remediation = [str(item) for item in readiness.get("remediation", [])]
        start_enabled = ui_status in {"ready", "degraded"}

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

        # Build retry-aware remediation message (AC2: retry recommendation reflects actual retryable value)
        if retry_enabled:
            retry_guidance = "Retry the import operation."
        else:
            retry_guidance = "Correct the source file locally, then re-import."

        # All remediation messages are strictly local-only (AC4)
        if code == "extraction.no_text_content":
            message = f"Unable to extract readable text from {source_format}. Verify file contents, then {retry_guidance.lower()}"
        elif code in {"extraction.malformed_package", "extraction.malformed_pdf"}:
            message = f"{source_format} structure appears invalid. Repair or replace the local file, then {retry_guidance.lower()}"
        elif code == "extraction.encoding_invalid":
            message = f"{source_format} contains unreadable encoding. Save the file as UTF-8 locally and {retry_guidance.lower()}"
        elif code in {"extraction.unreadable_archive", "extraction.unreadable_source"}:
            message = f"{source_format} file could not be read. Check local file permissions and integrity, then {retry_guidance.lower()}"
        elif code == "extraction.extractor_unavailable":
            message = f"No local extractor is available for {source_format}. Verify local application setup and {retry_guidance.lower()}"
        elif code == "extraction.unsupported_source_format":
            message = f"{source_format} is not supported for local extraction. Choose EPUB, PDF, TXT, or MD."
        else:
            message = f"{source_format} extraction failed. Review the local file and {retry_guidance.lower()}"

        self._logger.emit(
            event="diagnostics.presented",
            stage="diagnostics_ui",
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

    def build_conversion_config(
        self,
        *,
        engine: str,
        voice_id: str,
        language: str,
        speech_rate: float | int | str,
        output_format: str,
        voice_catalog: list[dict[str, Any]],
        correlation_id: str = "",
        job_id: str = "",
    ) -> Result[dict[str, Any]]:
        normalized_engine = str(engine).strip()
        normalized_voice_id = str(voice_id).strip()
        normalized_language = str(language).strip().upper()
        normalized_output_format = str(output_format).strip().lower()

        # Validate voice_catalog is not empty
        if not voice_catalog:
            return self._reject_configuration(
                code="configuration.voice_catalog_empty",
                message="Voice catalog is empty; cannot validate voice compatibility",
                details={"field": "voice_catalog"},
                correlation_id=correlation_id,
                job_id=job_id,
            )

        if normalized_engine not in self._SUPPORTED_ENGINES:
            return self._reject_configuration(
                code="configuration.engine_unsupported",
                message="Selected engine is not supported",
                details={
                    "field": "engine",
                    "engine": normalized_engine,
                    "supported": sorted(self._SUPPORTED_ENGINES),
                },
                correlation_id=correlation_id,
                job_id=job_id,
            )

        # Validate that selected engine has at least one voice in catalog
        engine_has_voices = any(
            str(item.get("engine", "")).strip() == normalized_engine
            for item in voice_catalog
        )
        if not engine_has_voices:
            return self._reject_configuration(
                code="configuration.engine_has_no_voices",
                message="Selected engine has no available voices in catalog",
                details={
                    "field": "engine",
                    "engine": normalized_engine,
                },
                correlation_id=correlation_id,
                job_id=job_id,
            )

        if normalized_language not in self._SUPPORTED_LANGUAGES:
            return self._reject_configuration(
                code="configuration.language_not_supported",
                message="Language must be one of FR or EN",
                details={
                    "field": "language",
                    "language": normalized_language,
                    "supported": sorted(self._SUPPORTED_LANGUAGES),
                },
                correlation_id=correlation_id,
                job_id=job_id,
            )

        try:
            normalized_speech_rate = float(speech_rate)
        except (TypeError, ValueError):
            return self._reject_configuration(
                code="configuration.speech_rate_invalid",
                message="Speech rate must be numeric",
                details={
                    "field": "speech_rate",
                    "speech_rate": speech_rate,
                },
                correlation_id=correlation_id,
                job_id=job_id,
            )

        if not (self._MIN_SPEECH_RATE <= normalized_speech_rate <= self._MAX_SPEECH_RATE):
            return self._reject_configuration(
                code="configuration.speech_rate_out_of_bounds",
                message="Speech rate is outside allowed bounds",
                details={
                    "field": "speech_rate",
                    "speech_rate": normalized_speech_rate,
                    "min": self._MIN_SPEECH_RATE,
                    "max": self._MAX_SPEECH_RATE,
                },
                correlation_id=correlation_id,
                job_id=job_id,
            )

        if normalized_output_format not in self._SUPPORTED_OUTPUT_FORMATS:
            return self._reject_configuration(
                code="configuration.output_format_unsupported",
                message="Output format must be mp3 or wav",
                details={
                    "field": "output_format",
                    "output_format": normalized_output_format,
                    "supported": sorted(self._SUPPORTED_OUTPUT_FORMATS),
                },
                correlation_id=correlation_id,
                job_id=job_id,
            )

        compatible_voice_exists = any(
            str(item.get("id", "")).strip() == normalized_voice_id
            and str(item.get("engine", "")).strip() == normalized_engine
            for item in voice_catalog
        )
        if not compatible_voice_exists:
            return self._reject_configuration(
                code="configuration.voice_not_compatible",
                message="Voice is not compatible with selected engine",
                details={
                    "field": "voice_id",
                    "voice_id": normalized_voice_id,
                    "engine": normalized_engine,
                },
                correlation_id=correlation_id,
                job_id=job_id,
            )

        payload = {
            "engine": normalized_engine,
            "voice_id": normalized_voice_id,
            "language": normalized_language,
            "speech_rate": normalized_speech_rate,
            "output_format": normalized_output_format,
        }
        self._logger.emit(
            event="configuration.saved",
            stage="configuration",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            extra={"config": payload},
        )
        return success(payload)

    def _reject_configuration(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, Any],
        correlation_id: str,
        job_id: str,
    ) -> Result[dict[str, Any]]:
        self._logger.emit(
            event="configuration.rejected",
            stage="configuration",
            severity="ERROR",
            correlation_id=correlation_id,
            job_id=job_id,
            extra={"error": {"code": code, "details": details}},
        )
        return failure(code=code, message=message, details=details, retryable=False)

    def map_conversion_progress(self, payload: dict[str, Any]) -> Result[dict[str, Any]]:
        try:
            progress_percent = int(payload.get("progress_percent", 0) or 0)
            chunk_index = int(payload.get("chunk_index", -1) or -1)
            status = str(payload.get("status", "running") or "running")
        except (TypeError, ValueError):
            return failure(
                code="conversion.progress_invalid_payload",
                message="Conversion progress payload is invalid",
                details={"payload": payload},
                retryable=False,
            )

        normalized_progress = max(0, min(progress_percent, 100))
        return success(
            {
                "status": status,
                "progress_percent": normalized_progress,
                "chunk_index": chunk_index,
                "succeeded_chunks": int(payload.get("succeeded_chunks", 0) or 0),
                "total_chunks": int(payload.get("total_chunks", 0) or 0),
            }
        )

    def map_conversion_state(self, payload: dict[str, Any]) -> Result[dict[str, Any]]:
        allowed = {"queued", "running", "paused", "failed", "completed"}
        status = str(payload.get("status", "running") or "running")
        if status not in allowed:
            return failure(
                code="conversion.state_invalid",
                message="Conversion state is invalid",
                details={"status": status, "allowed": sorted(allowed)},
                retryable=False,
            )

        return success(
            {
                "status": status,
                "progress_percent": int(payload.get("progress_percent", 0) or 0),
                "chunk_index": int(payload.get("chunk_index", -1) or -1),
                "job_id": str(payload.get("job_id", "")),
                "correlation_id": str(payload.get("correlation_id", "")),
            }
        )

    def map_conversion_error(self, payload: dict[str, Any]) -> Result[dict[str, Any]]:
        error = payload.get("error", {})
        if not isinstance(error, dict):
            return failure(
                code="conversion.error_invalid_payload",
                message="Conversion error payload is invalid",
                details={"payload": payload},
                retryable=False,
            )

        code = str(error.get("code", "conversion.failed"))
        message = str(error.get("message", "Conversion failed."))
        details = error.get("details", {})
        retryable = bool(error.get("retryable", False))
        normalized_details = details if isinstance(details, dict) else {"details": details}

        stage = self._infer_stage(code=code, details=normalized_details)
        engine = self._infer_engine(details=normalized_details)
        correlation_id = str(
            payload.get("correlation_id")
            or normalized_details.get("correlation_id")
            or ""
        )
        job_id = str(payload.get("job_id") or normalized_details.get("job_id") or "")
        chunk_index = int(normalized_details.get("chunk_index", -1) or -1)

        safe_details, hidden_keys = self._sanitize_details_for_user(normalized_details)
        summary, remediation = self._build_diagnostics_text(
            code=code,
            stage=stage,
            message=message,
            retryable=retryable,
        )
        support_workflow = self._build_support_workflow(
            code=code,
            message=message,
            stage=stage,
            details=safe_details,
            retryable=retryable,
        )

        return success(
            {
                "code": code,
                "message": message,
                "summary": summary,
                "details": safe_details,
                "retryable": retryable,
                "retry_enabled": retryable,
                "remediation": remediation,
                "support_workflow": support_workflow,
                "stage": stage,
                "engine": engine,
                "correlation_id": correlation_id,
                "job_id": job_id,
                "chunk_index": chunk_index,
                "details_expandable": True,
                "hidden_internal_details": bool(hidden_keys),
                "hidden_internal_keys": hidden_keys,
            }
        )

    def _infer_stage(self, *, code: str, details: dict[str, Any]) -> str:
        raw_stage = str(details.get("stage", "")).strip().lower()
        if raw_stage:
            return raw_stage

        if code.startswith("extraction."):
            return "extraction"
        if code.startswith("chunking."):
            return "chunking"
        if code.startswith("tts") or code.startswith("voice"):
            return "tts"
        if code.startswith("postprocess.") or code.startswith("audio_postprocess"):
            return "postprocess"
        if code.startswith("persistence.") or code.startswith("sqlite."):
            return "persistence"
        return "conversion"

    def _infer_engine(self, *, details: dict[str, Any]) -> str:
        for key in ("engine", "provider", "fallback_engine"):
            value = str(details.get(key, "")).strip()
            if value:
                return value
        attempted = details.get("attempted_engines")
        if isinstance(attempted, list) and attempted:
            candidate = str(attempted[0]).strip()
            if candidate:
                return candidate
        return "unknown_engine"

    def _sanitize_details_for_user(self, details: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        safe: dict[str, Any] = {}
        hidden_keys: list[str] = []
        allow_internal = bool(details.get("safe_for_user_display", False))

        for key, value in details.items():
            lowered = key.lower()
            if not allow_internal and lowered in self._UNSAFE_DETAIL_KEYS:
                hidden_keys.append(key)
                continue
            # Recursively sanitize nested dictionaries
            if isinstance(value, dict):
                sanitized_nested, nested_hidden = self._sanitize_details_for_user(value)
                safe[key] = sanitized_nested
                hidden_keys.extend([f"{key}.{nested_key}" for nested_key in nested_hidden])
            else:
                safe[key] = value

        return safe, sorted(hidden_keys)

    def _build_diagnostics_text(self, *, code: str, stage: str, message: str, retryable: bool) -> tuple[str, list[str]]:
        summary_by_stage = {
            "extraction": "Extraction failed before conversion could start.",
            "chunking": "Text segmentation failed during chunk preparation.",
            "tts": "Speech synthesis failed during TTS generation.",
            "postprocess": "Audio post-processing failed while assembling output.",
            "persistence": "Saving conversion artifacts failed.",
            "conversion": "Conversion failed.",
        }
        _ = message  # Incoming backend message is intentionally not shown to keep deterministic user text.
        summary = f"{summary_by_stage.get(stage, 'Conversion failed.')} Reference code: {code}."

        if retryable:
            remediation = [
                "Retry the conversion with the same settings.",
                "If the failure repeats, verify input file integrity and local model availability.",
            ]
        else:
            remediation = [
                "Re-import the source document and validate its content.",
                "Confirm engine/model setup and selected voice compatibility.",
                "Adjust conversion settings, then launch a new conversion job.",
            ]

        # Deterministic code-specific lead guidance.
        if code.startswith("extraction."):
            remediation.insert(0, "Check source file readability, format support, and local permissions.")
        elif code.startswith("tts"):
            remediation.insert(0, "Verify TTS engine readiness and voice availability before retrying.")

        return summary, remediation

    def _build_support_workflow(
        self,
        *,
        code: str,
        message: str,
        stage: str,
        details: dict[str, Any],
        retryable: bool,
    ) -> dict[str, Any]:
        """Build support workflow payload with category-specific guidance.
        
        Args:
            code: Error code from normalized error envelope
            message: Error message from normalized error envelope
            stage: Inferred pipeline stage (extraction, chunking, tts, postprocess, persistence)
            details: Sanitized error details (already filtered for unsafe keys)
            retryable: Whether the error is retryable
            
        Returns:
            Support workflow dict with category, guidance, prerequisites, and alternatives.
        """
        category = self._support_category_for(stage=stage)
        guidance_by_category = {
            "extraction": [
                "Verify the local source file exists, is readable, and uses a supported format.",
                "Re-import the document from local storage after correcting file issues.",
            ],
            "chunking": [
                "Check local chunking settings and confirm extracted text is present.",
                "Retry conversion after adjusting chunk size or segmentation parameters.",
            ],
            "engine_tts": [
                "Run local readiness checks and confirm the selected engine and voice are available.",
                "Retry conversion only after local model/voice availability is restored.",
            ],
            "export_postprocess": [
                "Verify local output path permissions and ensure no target file is locked.",
                "Retry conversion after confirming sufficient local disk space.",
            ],
            "persistence": [
                "Check local database and runtime directory write permissions.",
                "Retry conversion after resolving local storage integrity issues.",
            ],
        }

        retry_prerequisites_by_category = {
            "extraction": [
                "Source file can be opened locally without permission errors.",
                "Source format is supported (EPUB, PDF, TXT, or MD).",
            ],
            "chunking": [
                "Extracted text is available in the current local job context.",
                "Chunking settings were reviewed and corrected if needed.",
            ],
            "engine_tts": [
                "Selected local TTS engine is ready.",
                "Selected voice is available for the active engine.",
            ],
            "export_postprocess": [
                "Output directory is writable on local filesystem.",
                "No process is locking the expected output file.",
            ],
            "persistence": [
                "Local runtime storage is writable.",
                "Database path is available and not corrupted.",
            ],
        }

        # Non-retryable alternatives ordered by priority:
        # 1. Re-import (fixes source-level issues)
        # 2. Model repair (fixes engine-level issues)
        # 3. Settings correction (fixes configuration issues)
        alternatives = [
            "Re-import the source document from local storage.",
            "Repair or replace local model files, then rerun readiness checks.",
            "Correct conversion settings and start a new conversion job.",
        ]

        return {
            "category": category,
            "code": code,
            "message": message,
            "details": details,
            "retryable": retryable,
            # Fallback to engine_tts guidance if category not found (defensive default)
            "guidance": guidance_by_category.get(category, guidance_by_category["engine_tts"]),
            # Empty list if category not found or not retryable (no prerequisites needed)
            "retry_prerequisites": retry_prerequisites_by_category.get(category, []) if retryable else [],
            "non_retryable_alternatives": alternatives if not retryable else [],
        }

    @staticmethod
    def _support_category_for(*, stage: str) -> str:
        mapping = {
            "extraction": "extraction",
            "chunking": "chunking",
            "tts": "engine_tts",
            "postprocess": "export_postprocess",
            "persistence": "persistence",
        }
        return mapping.get(stage, "engine_tts")

    @staticmethod
    def _engine_available(engines: list[dict[str, Any]], expected_name: str) -> bool:
        for engine in engines:
            if str(engine.get("engine", "")) == expected_name:
                return bool(engine.get("ok", False))
        return False
