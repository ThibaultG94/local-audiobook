"""Domain service for persisting final library artifacts and metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from src.contracts.result import Result, failure, success


@runtime_checkable
class LibraryItemsRepositoryPort(Protocol):
    def create_item(self, record: dict[str, object]) -> dict[str, object]:
        ...


@runtime_checkable
class EventLoggerPort(Protocol):
    def emit(
        self,
        *,
        event: str,
        stage: str,
        severity: str = "INFO",
        correlation_id: str = "",
        job_id: str = "",
        chunk_index: int = -1,
        engine: str = "",
        timestamp: str = "",
        extra: dict[str, object] | None = None,
    ) -> None:
        ...


class LibraryService:
    """Persist one library item for a successful final audio artifact."""

    def __init__(
        self,
        *,
        library_items_repository: LibraryItemsRepositoryPort,
        logger: EventLoggerPort | None = None,
    ) -> None:
        self._library_items_repository = library_items_repository
        self._logger = logger

    def persist_final_artifact(
        self,
        *,
        correlation_id: str,
        document: dict[str, object],
        artifact: dict[str, object],
    ) -> Result[dict[str, object]]:
        normalized_or_error = self._normalize_payload(document=document, artifact=artifact)
        if not normalized_or_error.ok:
            self._emit(
                event="library.item_create_failed",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=str(artifact.get("job_id") or ""),
                extra={"error": normalized_or_error.error.to_dict() if normalized_or_error.error else {}},
            )
            return normalized_or_error

        payload = normalized_or_error.data or {}
        try:
            created = self._library_items_repository.create_item(payload)
        except Exception as exc:
            error = failure(
                code="library_persistence.write_failed",
                message="Failed to persist library metadata",
                details={
                    "category": "persistence",
                    "job_id": payload.get("job_id", ""),
                    "exception": str(exc),
                },
                retryable=True,
            )
            self._emit(
                event="library.item_create_failed",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=str(payload.get("job_id") or ""),
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        self._emit(
            event="library.item_created",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=str(created.get("job_id") or ""),
            extra={"library_item_id": created.get("id", "")},
        )
        return success(created)

    def _normalize_payload(
        self,
        *,
        document: dict[str, object],
        artifact: dict[str, object],
    ) -> Result[dict[str, object]]:
        """Normalize and validate library persistence payload.
        
        This method is responsible for generating the created_at timestamp
        to ensure consistency across the service layer. The repository
        receives the timestamp as a string and persists it as-is.
        """
        document_id = str(document.get("id") or "").strip()
        title = str(document.get("title") or "").strip()
        source_path = str(document.get("source_path") or "").strip()
        source_format = str(document.get("source_format") or "").strip().lower()

        job_id = str(artifact.get("job_id") or "").strip()
        audio_path = str(artifact.get("path") or "").strip()
        audio_format = str(artifact.get("format") or "").strip().lower()
        engine = str(artifact.get("engine") or "").strip()
        voice = str(artifact.get("voice") or "").strip()
        language = str(artifact.get("language") or "").strip()
        duration_seconds = float(artifact.get("duration_seconds") or 0.0)
        byte_size = int(artifact.get("byte_size") or 0)

        # Validate audio format is one of the supported formats
        SUPPORTED_AUDIO_FORMATS = {"mp3", "wav"}
        if audio_format and audio_format not in SUPPORTED_AUDIO_FORMATS:
            return failure(
                code="library_persistence.invalid_audio_format",
                message=f"Audio format must be one of {SUPPORTED_AUDIO_FORMATS}",
                details={
                    "category": "input",
                    "audio_format": audio_format,
                    "supported_formats": list(SUPPORTED_AUDIO_FORMATS),
                },
                retryable=False,
            )

        missing: list[str] = []
        for key, value in (
            ("document_id", document_id),
            ("title", title),
            ("source_path", source_path),
            ("job_id", job_id),
            ("audio_path", audio_path),
            ("format", audio_format),
            ("engine", engine),
            ("voice", voice),
            ("language", language),
        ):
            if not value:
                missing.append(key)

        if missing:
            return failure(
                code="library_persistence.invalid_payload",
                message="Library persistence payload is incomplete",
                details={"category": "input", "missing_keys": sorted(missing)},
                retryable=False,
            )

        # Validate path to prevent path traversal attacks
        # We resolve the path to check it's under the expected base, but store the relative path
        try:
            input_path = Path(audio_path)
            resolved_path = input_path.resolve()
            expected_base = Path("runtime/library/audio").resolve()
            
            # Check if resolved path is actually under the expected base directory
            # This prevents path traversal attacks like "../../../etc/passwd"
            if not str(resolved_path).startswith(str(expected_base)):
                return failure(
                    code="library_persistence.invalid_audio_path",
                    message="Audio path must be under runtime/library/audio/",
                    details={
                        "category": "input",
                        "audio_path": audio_path,
                        "resolved_path": str(resolved_path),
                        "expected_base": str(expected_base),
                    },
                    retryable=False,
                )
            
            # Store the relative path for portability
            # If input was already relative and valid, keep it; otherwise use relative from cwd
            if input_path.is_relative_to(Path.cwd()):
                normalized_path = str(input_path.relative_to(Path.cwd())).replace("\\", "/")
            else:
                normalized_path = input_path.as_posix()
                
        except (ValueError, OSError) as exc:
            return failure(
                code="library_persistence.invalid_audio_path",
                message="Audio path resolution failed",
                details={
                    "category": "input",
                    "audio_path": audio_path,
                    "error": str(exc),
                },
                retryable=False,
            )

        return success(
            {
                "document_id": document_id,
                "job_id": job_id,
                "title": title,
                "source_path": source_path,
                "source_format": source_format,
                "audio_path": normalized_path,
                "format": audio_format,
                "engine": engine,
                "voice": voice,
                "language": language,
                "duration_seconds": duration_seconds,
                "byte_size": byte_size,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def _emit(
        self,
        *,
        event: str,
        severity: str,
        correlation_id: str,
        job_id: str,
        extra: dict[str, object] | None = None,
    ) -> None:
        if self._logger is None or not hasattr(self._logger, "emit"):
            return

        self._logger.emit(
            event=event,
            stage="library_persistence",
            severity=severity,
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=-1,
            engine="library_service",
            timestamp=datetime.now(timezone.utc).isoformat(),
            extra=extra or {},
        )

