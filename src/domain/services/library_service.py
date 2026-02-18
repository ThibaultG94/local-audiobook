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

    def list_items_ordered(self) -> list[dict[str, object]]:
        ...

    def get_item_by_id(self, item_id: str) -> dict[str, object] | None:
        ...

    def delete_item_by_id(self, item_id: str) -> dict[str, object] | None:
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

    def browse_library(self, *, correlation_id: str) -> Result[dict[str, object]]:
        """Load deterministic local library list for UI browse surfaces."""
        try:
            rows = self._library_items_repository.list_items_ordered()
        except Exception as exc:
            error = failure(
                code="library_browse.list_failed",
                message="Unable to load local library list. Retry and, if needed, check local database health.",
                details={
                    "category": "persistence",
                    "exception": str(exc),
                    "exception_type": type(exc).__name__,
                    "remediation": "Retry loading the library. If the issue persists, verify local SQLite integrity.",
                },
                retryable=True,
            )
            self._emit(
                event="library.list_failed",
                stage="library_browse",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id="",
                extra={
                    "error": error.error.to_dict() if error.error else {},
                    "exception_type": type(exc).__name__,
                },
            )
            return error

        items = [self._to_browse_item(item) for item in rows]
        self._emit(
            event="library.list_loaded",
            stage="library_browse",
            severity="INFO",
            correlation_id=correlation_id,
            job_id="",
            extra={"count": len(items)},
        )
        return success({"items": items, "count": len(items)})

    def reopen_library_item(self, *, correlation_id: str, item_id: str) -> Result[dict[str, object]]:
        """Resolve one library item and prepare playback context without reconversion."""
        normalized_item_id = str(item_id or "").strip()
        if not normalized_item_id:
            error = failure(
                code="library_browse.invalid_item_id",
                message="A library item must be selected before opening audio.",
                details={
                    "category": "input",
                    "item_id": normalized_item_id,
                    "remediation": "Select an item from the local library and retry.",
                },
                retryable=False,
            )
            self._emit(
                event="library.item_open_failed",
                stage="library_browse",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id="",
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        record = self._library_items_repository.get_item_by_id(normalized_item_id)
        if record is None:
            error = failure(
                code="library_browse.item_not_found",
                message="Selected audiobook was not found in the local library.",
                details={
                    "category": "not_found",
                    "item_id": normalized_item_id,
                    "remediation": "Refresh the library list. If still missing, reconvert the source document.",
                },
                retryable=False,
            )
            self._emit(
                event="library.item_open_failed",
                stage="library_browse",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id="",
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        path_result = self._validate_reopen_path(
            audio_path=str(record.get("audio_path") or ""),
            correlation_id=correlation_id,
            job_id=str(record.get("job_id") or ""),
        )
        if not path_result.ok:
            self._emit(
                event="library.item_open_failed",
                stage="library_browse",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=str(record.get("job_id") or ""),
                extra={"error": path_result.error.to_dict() if path_result.error else {}},
            )
            return path_result

        resolved_audio_path = str((path_result.data or {}).get("resolved_audio_path") or "")
        library_item = self._to_browse_item(record)
        playback_context = {
            "library_item_id": str(record.get("id") or ""),
            "title": str(record.get("title") or ""),
            "audio_path": resolved_audio_path,
            "format": str(record.get("format") or ""),
            "language": str(record.get("language") or ""),
        }
        payload = {
            "library_item": library_item,
            "playback_context": playback_context,
        }
        self._emit(
            event="library.item_opened",
            stage="library_browse",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=str(record.get("job_id") or ""),
            extra={"library_item_id": str(record.get("id") or "")},
        )
        return success(payload)

    def prepare_item_for_conversion(self, *, correlation_id: str, item_id: str) -> Result[dict[str, object]]:
        """Resolve a selected library item into conversion context payload."""
        normalized_item_id = str(item_id or "").strip()
        if not normalized_item_id:
            error = failure(
                code="library_management.invalid_item_id",
                message="A library item must be selected before conversion.",
                details={
                    "category": "input",
                    "item_id": normalized_item_id,
                    "remediation": "Select an item from the library and retry conversion.",
                },
                retryable=False,
            )
            self._emit(
                event="library.item_prepare_convert_failed",
                stage="library_management",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id="",
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        record = self._library_items_repository.get_item_by_id(normalized_item_id)
        if record is None:
            error = failure(
                code="library_management.item_not_found",
                message="Selected library item was not found for conversion.",
                details={
                    "category": "not_found",
                    "item_id": normalized_item_id,
                    "remediation": "Refresh the library list and select an existing item.",
                },
                retryable=False,
            )
            self._emit(
                event="library.item_prepare_convert_failed",
                stage="library_management",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id="",
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        conversion_context = {
            "library_item_id": str(record.get("id") or ""),
            "document_id": str(record.get("document_id") or ""),
            "source_path": str(record.get("source_path") or ""),
            "source_format": str(record.get("source_format") or ""),
            "title": str(record.get("title") or ""),
            "language": str(record.get("language") or ""),
        }
        payload = {
            "library_item": self._to_browse_item(record),
            "conversion_context": conversion_context,
        }
        self._emit(
            event="library.item_prepared_for_convert",
            stage="library_management",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=str(record.get("job_id") or ""),
            extra={"library_item_id": str(record.get("id") or "")},
        )
        return success(payload)

    def delete_library_item(self, *, correlation_id: str, item_id: str) -> Result[dict[str, object]]:
        """Delete one library item and cleanup local artifact references safely.
        
        CRITICAL: Deletes metadata from DB FIRST (transactional), then cleans up
        artifact file (best-effort). This prevents orphaned metadata pointing to
        non-existent files if artifact cleanup fails.
        """
        normalized_item_id = str(item_id or "").strip()
        if not normalized_item_id:
            error = failure(
                code="library_management.invalid_item_id",
                message="A library item must be selected before deletion.",
                details={
                    "category": "input",
                    "item_id": normalized_item_id,
                    "remediation": "Select an item from the library and retry deletion.",
                },
                retryable=False,
            )
            self._emit(
                event="library.item_delete_failed",
                stage="library_management",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id="",
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        record = self._library_items_repository.get_item_by_id(normalized_item_id)
        if record is None:
            error = failure(
                code="library_management.item_not_found",
                message="Selected library item was not found.",
                details={
                    "category": "not_found",
                    "item_id": normalized_item_id,
                    "remediation": "Refresh the local library and retry deletion.",
                },
                retryable=False,
            )
            self._emit(
                event="library.item_delete_failed",
                stage="library_management",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id="",
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        # Store artifact path and metadata for cleanup and logging BEFORE deletion
        audio_path = str(record.get("audio_path") or "")
        title = str(record.get("title") or "")
        byte_size = int(record.get("byte_size") or 0)
        job_id = str(record.get("job_id") or "")

        # STEP 1: Delete from DB first (transactional, can rollback)
        try:
            deleted = self._library_items_repository.delete_item_by_id(normalized_item_id)
        except Exception as exc:
            error = failure(
                code="library_management.delete_failed",
                message="Unable to remove local library metadata.",
                details={
                    "category": "persistence",
                    "item_id": normalized_item_id,
                    "exception": str(exc),
                    "exception_type": type(exc).__name__,
                    "remediation": "Retry deletion. If this persists, verify local SQLite database integrity.",
                },
                retryable=True,
            )
            self._emit(
                event="library.item_delete_failed",
                stage="library_management",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                extra={
                    "error": error.error.to_dict() if error.error else {},
                    "exception_type": type(exc).__name__,
                },
            )
            return error

        if deleted is None:
            error = failure(
                code="library_management.item_not_found",
                message="Selected library item disappeared before deletion completed.",
                details={
                    "category": "not_found",
                    "item_id": normalized_item_id,
                    "remediation": "Refresh the library list and retry if needed.",
                },
                retryable=False,
            )
            self._emit(
                event="library.item_delete_failed",
                stage="library_management",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        # STEP 2: Cleanup artifact file (best-effort, non-critical if fails)
        # If this fails, metadata is already deleted, so we don't fail the operation
        artifact_cleanup = self._cleanup_artifact_for_delete(
            audio_path=audio_path,
            correlation_id=correlation_id,
            job_id=job_id,
        )
        
        artifact_deleted = bool((artifact_cleanup.data or {}).get("artifact_deleted", False))
        
        # Log successful deletion with full audit trail
        self._emit(
            event="library.item_deleted",
            stage="library_management",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            extra={
                "library_item_id": normalized_item_id,
                "title": title,
                "audio_path": audio_path,
                "byte_size": byte_size,
                "artifact_deleted": artifact_deleted,
            },
        )
        return success(
            {
                "deleted_item_id": normalized_item_id,
                "deleted_item": self._to_browse_item(deleted),
                "artifact_deleted": artifact_deleted,
            }
        )

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
                stage="library_persistence",
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
                    "exception_type": type(exc).__name__,
                },
                retryable=True,
            )
            self._emit(
                event="library.item_create_failed",
                stage="library_persistence",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=str(payload.get("job_id") or ""),
                extra={
                    "error": error.error.to_dict() if error.error else {},
                    "exception_type": type(exc).__name__,
                },
            )
            return error

        self._emit(
            event="library.item_created",
            stage="library_persistence",
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
        stage: str,
        severity: str,
        correlation_id: str,
        job_id: str,
        extra: dict[str, object] | None = None,
    ) -> None:
        if self._logger is None or not hasattr(self._logger, "emit"):
            return

        try:
            self._logger.emit(
                event=event,
                stage=stage,
                severity=severity,
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=-1,
                engine="library_service",
                timestamp=datetime.now(timezone.utc).isoformat(),
                extra=extra or {},
            )
        except Exception:
            return

    @staticmethod
    def _to_browse_item(item: dict[str, object]) -> dict[str, object]:
        """Transform repository record into UI-friendly browse item payload.
        
        Maps internal persistence fields to presentation layer contract:
        - source_path -> source (for UI display)
        - created_at -> created_date (semantic clarity)
        - Preserves audio_path, job_id, source_format for reopen context
        
        Args:
            item: Raw repository record with all persistence fields
            
        Returns:
            Normalized browse item dict for presenter/view consumption
        """
        return {
            "id": str(item.get("id") or ""),
            "title": str(item.get("title") or ""),
            "source": str(item.get("source_path") or ""),
            "language": str(item.get("language") or ""),
            "format": str(item.get("format") or ""),
            "byte_size": int(item.get("byte_size") or 0),
            "created_date": str(item.get("created_at") or ""),
            "conversion_status": "ready",
            "audio_path": str(item.get("audio_path") or ""),
            "job_id": str(item.get("job_id") or ""),
            "source_format": str(item.get("source_format") or ""),
        }

    def _cleanup_artifact_for_delete(
        self,
        *,
        audio_path: str,
        correlation_id: str,
        job_id: str,
    ) -> Result[dict[str, object]]:
        normalized_audio_path = str(audio_path or "").strip()
        if not normalized_audio_path:
            return success({"artifact_deleted": False, "reason": "missing_path"})

        input_path = Path(normalized_audio_path)
        expected_base = Path("runtime/library/audio").resolve(strict=False)
        try:
            resolved_path = input_path.resolve(strict=False)
        except OSError as exc:
            return failure(
                code="library_management.artifact_cleanup_failed",
                message="Audio artifact path is malformed and cannot be cleaned up.",
                details={
                    "category": "artifact",
                    "audio_path": normalized_audio_path,
                    "exception": str(exc),
                    "remediation": "Verify artifact path under runtime/library/audio and retry deletion.",
                },
                retryable=False,
            )

        # Use is_relative_to() for secure path validation (Python 3.9+)
        try:
            if not resolved_path.is_relative_to(expected_base):
                return failure(
                    code="library_management.artifact_cleanup_failed",
                    message="Refusing to delete artifact outside runtime/library/audio bounds.",
                    details={
                        "category": "artifact",
                        "audio_path": normalized_audio_path,
                        "resolved_path": str(resolved_path),
                        "expected_base": str(expected_base),
                        "remediation": "Move the artifact under runtime/library/audio or correct the metadata path before retrying.",
                    },
                    retryable=False,
                )
        except (ValueError, AttributeError):
            # Fallback for edge cases or if is_relative_to fails
            return failure(
                code="library_management.artifact_cleanup_failed",
                message="Unable to validate artifact path safety.",
                details={
                    "category": "artifact",
                    "audio_path": normalized_audio_path,
                    "remediation": "Verify artifact path under runtime/library/audio and retry deletion.",
                },
                retryable=False,
            )

        if not resolved_path.exists():
            return success({"artifact_deleted": False, "reason": "already_missing"})

        try:
            resolved_path.unlink()
        except OSError as exc:
            return failure(
                code="library_management.artifact_cleanup_failed",
                message="Unable to remove local audio artifact during deletion.",
                details={
                    "category": "artifact",
                    "audio_path": normalized_audio_path,
                    "resolved_path": str(resolved_path),
                    "exception": str(exc),
                    "remediation": "Close any process using the file and retry deletion.",
                },
                retryable=True,
            )

        self._emit(
            event="library.item_artifact_deleted",
            stage="library_management",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            extra={"audio_path": str(resolved_path)},
        )
        return success({"artifact_deleted": True, "audio_path": str(resolved_path)})

    def _validate_reopen_path(
        self,
        *,
        audio_path: str,
        correlation_id: str,
        job_id: str,
    ) -> Result[dict[str, object]]:
        normalized_audio_path = str(audio_path or "").strip()
        if not normalized_audio_path:
            error = failure(
                code="library_browse.audio_missing",
                message="Audio artifact is missing for this library item.",
                details={
                    "category": "artifact",
                    "audio_path": normalized_audio_path,
                    "remediation": "Relink the audio file or reconvert the source document locally.",
                },
                retryable=False,
            )
            self._emit(
                event="library.path_validation_failed",
                stage="library_browse",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        input_path = Path(normalized_audio_path)
        expected_base = Path("runtime/library/audio").resolve(strict=False)
        try:
            resolved_path = input_path.resolve(strict=False)
        except OSError as exc:
            error = failure(
                code="library_browse.invalid_audio_path",
                message="Audio path is malformed and cannot be resolved.",
                details={
                    "category": "input",
                    "audio_path": normalized_audio_path,
                    "exception": str(exc),
                    "remediation": "Relink the audiobook file or reconvert locally.",
                },
                retryable=False,
            )
            self._emit(
                event="library.path_validation_failed",
                stage="library_browse",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        # Use is_relative_to() for secure path validation (Python 3.9+)
        try:
            if not resolved_path.is_relative_to(expected_base):
                error = failure(
                    code="library_browse.invalid_audio_path",
                    message="Audio path is outside local runtime bounds.",
                    details={
                        "category": "input",
                        "audio_path": normalized_audio_path,
                        "resolved_path": str(resolved_path),
                        "expected_base": str(expected_base),
                        "remediation": "Relink the item to a file under runtime/library/audio or reconvert locally.",
                    },
                    retryable=False,
                )
                self._emit(
                    event="library.path_validation_failed",
                    stage="library_browse",
                    severity="ERROR",
                    correlation_id=correlation_id,
                    job_id=job_id,
                    extra={"error": error.error.to_dict() if error.error else {}},
                )
                return error
        except (ValueError, AttributeError):
            # Fallback for edge cases
            error = failure(
                code="library_browse.invalid_audio_path",
                message="Unable to validate audio path safety.",
                details={
                    "category": "input",
                    "audio_path": normalized_audio_path,
                    "remediation": "Relink the audiobook file or reconvert locally.",
                },
                retryable=False,
            )
            self._emit(
                event="library.path_validation_failed",
                stage="library_browse",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        if not resolved_path.exists():
            error = failure(
                code="library_browse.audio_missing",
                message="Audio artifact file is unavailable on disk.",
                details={
                    "category": "artifact",
                    "audio_path": normalized_audio_path,
                    "resolved_path": str(resolved_path),
                    "remediation": "Relink the missing artifact path or reconvert the audiobook locally.",
                },
                retryable=False,
            )
            self._emit(
                event="library.path_validation_failed",
                stage="library_browse",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                extra={"error": error.error.to_dict() if error.error else {}},
            )
            return error

        return success({"resolved_audio_path": str(resolved_path)})
