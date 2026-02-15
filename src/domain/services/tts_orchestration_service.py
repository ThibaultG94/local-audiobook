"""TTS orchestration service for provider coordination and fallback logic."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable

from src.contracts.result import Result, failure, success
from src.domain.services.job_state_validator import validate_job_state_transition

if TYPE_CHECKING:
    from src.domain.services.audio_postprocess_service import AudioPostprocessService
    from src.domain.services.library_service import LibraryService
    from domain.services.chunking_service import ChunkingService
    from domain.ports.tts_provider import TtsProvider, TtsSynthesisData


@runtime_checkable
class ChunksRepositoryPort(Protocol):
    """Protocol for chunks repository operations."""

    def list_chunks_for_job(self, *, job_id: str) -> list[dict[str, object]]:
        """List all chunks for a job in chunk_index order."""
        ...

    def replace_chunks_for_job(self, *, job_id: str, chunks: list[dict[str, object]]) -> list[dict[str, object]]:
        """Replace all chunks for a job with new chunk set."""
        ...

    def update_chunk_synthesis_outcome(self, *, job_id: str, chunk_index: int, status: str) -> None:
        """Update synthesis outcome status for a specific chunk."""
        ...


@runtime_checkable
class EventLoggerPort(Protocol):
    """Protocol for event logging operations."""

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
        """Emit a structured event."""
        ...


@runtime_checkable
class ConversionJobsRepositoryPort(Protocol):
    """Protocol for conversion job state persistence operations."""

    def get_job_by_id(self, *, job_id: str) -> dict[str, object] | None:
        """Fetch a conversion job by id."""
        ...

    def update_job_state_if_current(
        self,
        *,
        job_id: str,
        expected_state: str,
        next_state: str,
        updated_at: str | None = None,
    ) -> bool:
        """Atomically update job state if current state matches expected state."""
        ...


@runtime_checkable
class DocumentsRepositoryPort(Protocol):
    """Protocol for document persistence reads used by orchestration."""

    def get_document_by_id(self, *, document_id: str) -> dict[str, object] | None:
        """Fetch a document by id."""
        ...


class TtsOrchestrationService:
    """Orchestration service managing TTS provider selection and fallback behavior.
    
    This service owns all fallback policy decisions and coordinates between
    multiple TTS providers based on their health and error responses.
    """

    def __init__(
        self,
        primary_provider: TtsProvider | None = None,
        fallback_provider: TtsProvider | None = None,
        audio_postprocess_service: AudioPostprocessService | None = None,
        library_service: LibraryService | None = None,
        chunking_service: ChunkingService | None = None,
        chunks_repository: ChunksRepositoryPort | None = None,
        conversion_jobs_repository: ConversionJobsRepositoryPort | None = None,
        documents_repository: DocumentsRepositoryPort | None = None,
        logger: EventLoggerPort | None = None,
    ) -> None:
        """Initialize orchestration service with optional providers.
        
        Args:
            primary_provider: Primary TTS provider (e.g., Chatterbox GPU)
            fallback_provider: Fallback TTS provider (e.g., Kokoro CPU)
            audio_postprocess_service: Service for final audio assembly and rendering
            chunking_service: Service for text chunking operations
            chunks_repository: Repository for chunk persistence
            conversion_jobs_repository: Repository for conversion job lifecycle persistence
            logger: Event logger for structured logging
        """
        self._primary_provider = primary_provider
        self._fallback_provider = fallback_provider
        self._audio_postprocess_service = audio_postprocess_service
        self._library_service = library_service
        self._chunking_service = chunking_service
        self._chunks_repository = chunks_repository
        self._conversion_jobs_repository = conversion_jobs_repository
        self._documents_repository = documents_repository
        self._logger = logger

    def launch_conversion(
        self,
        *,
        job_id: str,
        correlation_id: str,
        conversion_config: dict[str, Any],
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> Result[dict[str, object]]:
        """Launch full conversion flow: synthesis then post-processing."""
        synthesis_result = self.synthesize_persisted_chunks_for_job(
            job_id=job_id,
            correlation_id=correlation_id,
            voice=str(conversion_config.get("voice_id") or "default"),
            current_job_state="running",
            force_reprocess=bool(conversion_config.get("force_reprocess", False)),
            progress_callback=progress_callback,
        )
        if not synthesis_result.ok:
            return synthesis_result

        if self._audio_postprocess_service is None:
            return synthesis_result

        output_format = str(conversion_config.get("output_format") or "wav").lower()
        target_path = str(Path("runtime") / "library" / "audio" / f"{job_id}.{output_format}")

        postprocess_result = self._audio_postprocess_service.assemble_and_render(
            job_id=job_id,
            correlation_id=correlation_id,
            output_format=output_format,
            chunk_artifacts=list((synthesis_result.data or {}).get("chunk_results") or []),
            target_path=target_path,
        )
        if not postprocess_result.ok:
            return postprocess_result

        # Attempt library persistence but don't fail conversion if it fails
        # The audio file has been successfully generated and is on disk
        library_metadata: dict[str, object] = {}
        if self._library_service is not None:
            output_artifact = (postprocess_result.data or {}).get("output_artifact", {})
            job_record = (
                self._conversion_jobs_repository.get_job_by_id(job_id=job_id)
                if self._conversion_jobs_repository is not None
                else None
            )
            document_id = str((job_record or {}).get("document_id") or "")
            document_record = (
                self._documents_repository.get_document_by_id(document_id=document_id)
                if self._documents_repository is not None and document_id
                else None
            )

            library_result = self._library_service.persist_final_artifact(
                correlation_id=correlation_id,
                document=document_record or {"id": document_id},
                artifact={
                    "job_id": job_id,
                    "path": str(output_artifact.get("path") or target_path),
                    "format": str(output_artifact.get("format") or output_format),
                    "duration_seconds": float(output_artifact.get("duration_seconds") or 0.0),
                    "byte_size": int(output_artifact.get("byte_size") or 0),
                    "engine": str(conversion_config.get("engine") or ""),
                    "voice": str(conversion_config.get("voice_id") or ""),
                    "language": str(conversion_config.get("language") or ""),
                },
            )
            if library_result.ok:
                library_metadata = {"library_item_id": (library_result.data or {}).get("id", "")}
            else:
                # Log the error but don't fail the conversion
                # The audio file is still available on disk at the known path
                library_metadata = {
                    "library_persistence_failed": True,
                    "library_error": library_result.error.to_dict() if library_result.error else {},
                }

        merged_payload = dict(synthesis_result.data or {})
        merged_payload.update(
            {
                "output_artifact": (postprocess_result.data or {}).get("output_artifact", {}),
                "postprocess": {
                    "chunk_count": int((postprocess_result.data or {}).get("chunk_count", 0) or 0),
                },
                "library_metadata": library_metadata,
            }
        )
        return success(merged_payload)

    @staticmethod
    def validate_transition(current_state: str, next_state: str) -> Result[None]:
        """Validate job state transition (legacy method from Story 1.1)."""
        return validate_job_state_transition(current_state, next_state)

    def synthesize_with_fallback(
        self,
        text: str,
        voice: str | None = None,
        *,
        correlation_id: str = "",
        job_id: str = "",
        chunk_index: int = -1,
    ) -> Result[TtsSynthesisData]:
        """Synthesize text with automatic fallback on provider failure.
        
        Attempts synthesis with primary provider first. On failure with
        retryable=False and category=availability, falls back to secondary provider.
        
        Args:
            text: Text to synthesize
            voice: Voice ID (provider-specific)
            correlation_id: Request correlation ID
            job_id: Job identifier
            chunk_index: Chunk index within job
            
        Returns:
            Success with audio data, or failure if all providers fail
        """
        result, _ = self._synthesize_with_policy(
            text,
            voice,
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=chunk_index,
        )
        return result

    def synthesize_persisted_chunks_for_job(
        self,
        *,
        job_id: str,
        correlation_id: str,
        voice: str | None = None,
        current_job_state: str = "running",
        force_reprocess: bool = False,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> Result[dict[str, object]]:
        """Synthesize persisted chunks in deterministic chunk_index order.

        This orchestration entrypoint owns fallback policy decisions and emits
        per-chunk structured lifecycle events for diagnosis.
        
        Args:
            job_id: Job identifier
            correlation_id: Request correlation ID
            voice: Voice ID (provider-specific)
            current_job_state: Current job state (default: "running")
            force_reprocess: If True, reprocess all chunks regardless of status (default: False)
            
        Returns:
            Success with chunk results and resume metadata, or failure with error details
        """
        if self._chunks_repository is None:
            return failure(
                code="tts_orchestration.repository_unavailable",
                message="Chunks repository is not configured",
                details={"category": "configuration"},
                retryable=False,
            )

        persisted_chunks = self._chunks_repository.list_chunks_for_job(job_id=job_id)
        if not persisted_chunks:
            return failure(
                code="tts_orchestration.no_persisted_chunks",
                message="No persisted chunks available for job orchestration",
                details={"job_id": job_id, "category": "input"},
                retryable=False,
            )

        job_state = self._resolve_current_job_state(job_id=job_id, fallback_state=current_job_state)

        running_transition = self._apply_job_transition(
            job_id=job_id,
            correlation_id=correlation_id,
            current_state=job_state,
            next_state="running",
            chunk_index=-1,
            reason="conversion_orchestration_start",
        )
        if not running_transition.ok:
            return failure(
                code="job.transition_rejected",
                message="Cannot start chunk orchestration because job transition to running was rejected",
                details={
                    "job_id": job_id,
                    "transition_intent": {
                        "current_state": job_state,
                        "next_state": "running",
                        "validated": False,
                        "error": running_transition.error.to_dict() if running_transition.error else {},
                    },
                    "category": "state",
                },
                retryable=False,
            )

        # Sort chunks by index to ensure deterministic processing order.
        # Convert to int to handle both string and numeric chunk_index values from repository.
        ordered_chunks = sorted(persisted_chunks, key=lambda chunk: int(chunk["chunk_index"]))
        resume_start_index, retry_decision_path = self._select_resume_start_index(
            ordered_chunks=ordered_chunks,
            force_reprocess=force_reprocess,
        )

        self._emit_tts_event(
            event="conversion.resume_started",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=resume_start_index,
            engine="orchestrator",
            extra={
                "resume_start_index": resume_start_index,
                "retry_decision_path": retry_decision_path,
                "force_reprocess": force_reprocess,
                "total_chunks": len(ordered_chunks),
            },
        )

        chunks_to_process = [
            chunk
            for chunk in ordered_chunks
            if int(chunk["chunk_index"]) >= resume_start_index
            and (force_reprocess or not self._is_synthesized_status(str(chunk.get("status") or "")))
        ]

        chunk_results: list[dict[str, object]] = []
        total_chunks = len(chunks_to_process)

        for chunk in chunks_to_process:
            chunk_index = int(chunk["chunk_index"])
            text_content = str(chunk["text_content"])
            started_engine = self._primary_provider.engine_name if self._primary_provider is not None else "orchestrator"

            self._emit_tts_event(
                event="tts.chunk_started",
                severity="INFO",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
                engine=started_engine,
                extra={},
            )

            synthesis_result, attempt_trace = self._synthesize_with_policy(
                text_content,
                voice,
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
            )

            if attempt_trace.get("fallback_applied"):
                self._emit_tts_event(
                    event="tts.fallback_applied",
                    severity="WARNING",
                    correlation_id=correlation_id,
                    job_id=job_id,
                    chunk_index=chunk_index,
                    engine=str(attempt_trace.get("selected_engine") or attempt_trace.get("fallback_engine") or "orchestrator"),
                    extra={
                        "from_engine": attempt_trace.get("primary_engine", ""),
                        "to_engine": attempt_trace.get("fallback_engine", ""),
                        "trigger": "availability_non_retryable",
                    },
                )

            if synthesis_result.ok:
                selected_engine = str((synthesis_result.data or {}).get("metadata", {}).get("engine", ""))
                self._persist_chunk_outcome(
                    job_id=job_id,
                    chunk_index=chunk_index,
                    status=f"synthesized_{selected_engine or 'unknown'}",
                )
                self._emit_tts_event(
                    event="tts.chunk_succeeded",
                    severity="INFO",
                    correlation_id=correlation_id,
                    job_id=job_id,
                    chunk_index=chunk_index,
                    engine=selected_engine or "orchestrator",
                    extra={"attempted_engines": attempt_trace.get("attempted_engines", [])},
                )
                chunk_results.append(
                    {
                        "chunk_index": chunk_index,
                        "synthesis": synthesis_result.to_dict(),
                        "engine": selected_engine,
                    }
                )
                if progress_callback is not None:
                    progress_callback(
                        {
                            "chunk_index": chunk_index,
                            "succeeded_chunks": len(chunk_results),
                            "total_chunks": total_chunks,
                            "progress_percent": int((len(chunk_results) / total_chunks) * 100) if total_chunks > 0 else 0,
                            "status": "running",
                        }
                    )
                continue

            failure_details = {
                "job_id": job_id,
                "chunk_index": chunk_index,
                "resume_start_index": resume_start_index,
                "retry_decision_path": retry_decision_path,
                "attempted_engines": attempt_trace.get("attempted_engines", []),
                "primary_error": attempt_trace.get("primary_error", {}),
                "fallback_error": attempt_trace.get("fallback_error", {}),
                "category": "availability",
            }

            self._persist_chunk_outcome(
                job_id=job_id,
                chunk_index=chunk_index,
                status="failed",
            )
            self._emit_tts_event(
                event="tts.chunk_failed",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
                engine=str(attempt_trace.get("selected_engine") or started_engine),
                extra={
                    "error": {
                        "code": "tts_orchestration.chunk_failed_unrecoverable",
                        "message": "Chunk synthesis failed for all configured providers",
                        "details": {
                            "primary_error": attempt_trace.get("primary_error", {}),
                            "fallback_error": attempt_trace.get("fallback_error", {}),
                            "attempted_engines": attempt_trace.get("attempted_engines", []),
                        },
                        "retryable": False,
                    }
                },
            )

            failed_transition = self._apply_job_transition(
                job_id=job_id,
                correlation_id=correlation_id,
                current_state="running",
                next_state="failed",
                chunk_index=chunk_index,
                reason="chunk_failed_unrecoverable",
            )
            failure_details["transition_intent"] = {
                "current_state": "running",
                "next_state": "failed",
                "validated": failed_transition.ok,
                "error": failed_transition.error.to_dict() if failed_transition.error else None,
            }

            return failure(
                code="tts_orchestration.chunk_failed_unrecoverable",
                message="Chunk synthesis failed for all configured providers",
                details=failure_details,
                retryable=False,
            )

        completed_transition = self._apply_job_transition(
            job_id=job_id,
            correlation_id=correlation_id,
            current_state="running",
            next_state="completed",
            chunk_index=-1,
            reason="conversion_orchestration_completed",
        )

        if not completed_transition.ok:
            return failure(
                code="job.transition_rejected",
                message="Chunk orchestration completed but job transition to completed was rejected",
                details={
                    "job_id": job_id,
                    "resume_start_index": resume_start_index,
                    "retry_decision_path": retry_decision_path,
                    "transition_intent": {
                        "current_state": "running",
                        "next_state": "completed",
                        "validated": False,
                        "error": completed_transition.error.to_dict() if completed_transition.error else {},
                    },
                    "category": "state",
                },
                retryable=False,
            )

        return success(
            {
                "job_id": job_id,
                "chunk_results": chunk_results,
                "succeeded_chunks": len(chunk_results),
                "resume_start_index": resume_start_index,
                "retry_decision_path": retry_decision_path,
                "transition_intent": {
                    "current_state": "running",
                    "next_state": "completed",
                    "validated": True,
                    "error": None,
                },
            }
        )

    @staticmethod
    def _is_synthesized_status(status: str) -> bool:
        return status.startswith("synthesized_")

    def _select_resume_start_index(
        self,
        *,
        ordered_chunks: list[dict[str, object]],
        force_reprocess: bool,
    ) -> tuple[int, str]:
        if not ordered_chunks:
            return 0, "no_chunks"

        if force_reprocess:
            first_chunk_index = int(ordered_chunks[0]["chunk_index"])
            return first_chunk_index, "forced_full_reprocess"

        for chunk in ordered_chunks:
            status = str(chunk.get("status") or "")
            if not self._is_synthesized_status(status):
                return int(chunk["chunk_index"]), f"first_non_synthesized_status:{status or 'unknown'}"

        last_chunk_index = int(ordered_chunks[-1]["chunk_index"])
        return last_chunk_index + 1, "all_chunks_already_synthesized"

    def _resolve_current_job_state(self, *, job_id: str, fallback_state: str) -> str:
        if self._conversion_jobs_repository is None:
            return fallback_state

        job_row = self._conversion_jobs_repository.get_job_by_id(job_id=job_id)
        if job_row is None:
            return fallback_state

        return str(job_row.get("state") or fallback_state)

    def _apply_job_transition(
        self,
        *,
        job_id: str,
        correlation_id: str,
        current_state: str,
        next_state: str,
        chunk_index: int,
        reason: str,
    ) -> Result[dict[str, object]]:
        """Validate and apply a job lifecycle transition with observability events."""
        self._emit_tts_event(
            event="job.transition_requested",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=chunk_index,
            engine="orchestrator",
            extra={
                "transition_intent": {
                    "current_state": current_state,
                    "next_state": next_state,
                },
                "reason": reason,
            },
        )

        if current_state == next_state:
            self._emit_tts_event(
                event="job.transition_applied",
                severity="INFO",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
                engine="orchestrator",
                extra={
                    "transition_intent": {
                        "current_state": current_state,
                        "next_state": next_state,
                        "validated": True,
                    },
                    "reason": reason,
                    "no_op": True,
                },
            )
            return success({"current_state": current_state, "next_state": next_state, "no_op": True})

        transition = validate_job_state_transition(current_state, next_state)
        if not transition.ok:
            normalized = transition.error.to_dict() if transition.error else {}
            self._emit_tts_event(
                event="job.transition_rejected",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
                engine="orchestrator",
                extra={
                    "transition_intent": {
                        "current_state": current_state,
                        "next_state": next_state,
                        "validated": False,
                    },
                    "reason": reason,
                    "error": normalized,
                },
            )
            return failure(
                code=normalized.get("code", "invalid_job_transition"),
                message=normalized.get("message", "Job state transition is not allowed"),
                details={
                    "transition_intent": {
                        "current_state": current_state,
                        "next_state": next_state,
                        "validated": False,
                    },
                    "reason": reason,
                    "error": normalized,
                },
                retryable=bool(normalized.get("retryable", False)),
            )

        persistence_applied = False
        if self._conversion_jobs_repository is not None:
            persisted = self._conversion_jobs_repository.update_job_state_if_current(
                job_id=job_id,
                expected_state=current_state,
                next_state=next_state,
            )
            if not persisted:
                current_record = self._conversion_jobs_repository.get_job_by_id(job_id=job_id)
                observed_state = str((current_record or {}).get("state") or "")
                self._emit_tts_event(
                    event="job.transition_rejected",
                    severity="ERROR",
                    correlation_id=correlation_id,
                    job_id=job_id,
                    chunk_index=chunk_index,
                    engine="orchestrator",
                    extra={
                        "transition_intent": {
                            "current_state": current_state,
                            "next_state": next_state,
                            "validated": False,
                        },
                        "reason": reason,
                        "error": {
                            "code": "job_state_transition_conflict",
                            "message": "Job state changed concurrently before transition could be persisted",
                            "details": {
                                "expected_state": current_state,
                                "observed_state": observed_state,
                                "job_id": job_id,
                            },
                            "retryable": True,
                        },
                    },
                )
                return failure(
                    code="job_state_transition_conflict",
                    message="Job state changed concurrently before transition could be persisted",
                    details={
                        "expected_state": current_state,
                        "observed_state": observed_state,
                        "job_id": job_id,
                    },
                    retryable=True,
                )
            persistence_applied = True

        self._emit_tts_event(
            event="job.transition_applied",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=chunk_index,
            engine="orchestrator",
            extra={
                "transition_intent": {
                    "current_state": current_state,
                    "next_state": next_state,
                    "validated": True,
                },
                "reason": reason,
                "persistence_applied": persistence_applied,
            },
        )
        return success({"current_state": current_state, "next_state": next_state, "no_op": False})

    def _synthesize_with_policy(
        self,
        text: str,
        voice: str | None,
        *,
        correlation_id: str,
        job_id: str,
        chunk_index: int,
    ) -> tuple[Result[TtsSynthesisData], dict[str, object]]:
        """Apply deterministic provider policy and return synthesis + attempt trace."""
        trace: dict[str, object] = {
            "attempted_engines": [],
            "fallback_applied": False,
            "primary_engine": self._primary_provider.engine_name if self._primary_provider is not None else "",
            "fallback_engine": self._fallback_provider.engine_name if self._fallback_provider is not None else "",
            "selected_engine": "",
            "primary_error": {},
            "fallback_error": {},
        }

        if self._primary_provider is None and self._fallback_provider is None:
            return (
                failure(
                    code="tts_no_providers",
                    message="No TTS providers configured",
                    details={"category": "configuration"},
                    retryable=False,
                ),
                trace,
            )

        # Try primary provider first
        if self._primary_provider is not None:
            trace["attempted_engines"] = [self._primary_provider.engine_name]
            result = self._primary_provider.synthesize_chunk(
                text,
                voice,
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
            )

            if result.ok:
                trace["selected_engine"] = self._primary_provider.engine_name
                return result, trace

            # Check if we should fallback based on error category
            if result.error and self._should_fallback(result.error.to_dict()):
                # Try fallback provider
                if self._fallback_provider is not None:
                    trace["attempted_engines"] = [
                        self._primary_provider.engine_name,
                        self._fallback_provider.engine_name,
                    ]
                    trace["fallback_applied"] = True
                    trace["primary_error"] = result.error.to_dict()
                    fallback_result = self._fallback_provider.synthesize_chunk(
                        text,
                        voice,
                        correlation_id=correlation_id,
                        job_id=job_id,
                        chunk_index=chunk_index,
                    )

                    if fallback_result.ok:
                        trace["selected_engine"] = self._fallback_provider.engine_name
                        return fallback_result, trace

                    # Both providers failed
                    trace["selected_engine"] = self._fallback_provider.engine_name
                    trace["fallback_error"] = fallback_result.error.to_dict() if fallback_result.error else {}
                    return (
                        failure(
                            code="tts_all_providers_failed",
                            message="Both primary and fallback providers failed",
                            details={
                                "primary_error": result.error.to_dict(),
                                "fallback_error": fallback_result.error.to_dict() if fallback_result.error else {},
                                "category": "availability",
                            },
                            retryable=False,
                        ),
                        trace,
                    )

            # Non-fallback error, return primary error
            trace["primary_error"] = result.error.to_dict() if result.error else {}
            trace["selected_engine"] = self._primary_provider.engine_name
            return result, trace

        # No primary provider, try fallback directly
        if self._fallback_provider is not None:
            trace["attempted_engines"] = [self._fallback_provider.engine_name]
            fallback_only_result = self._fallback_provider.synthesize_chunk(
                text,
                voice,
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
            )
            trace["selected_engine"] = self._fallback_provider.engine_name
            trace["fallback_error"] = fallback_only_result.error.to_dict() if fallback_only_result.error else {}
            return fallback_only_result, trace

        # Should never reach here due to initial check
        return (
            failure(
                code="tts_no_providers",
                message="No TTS providers available",
                details={"category": "configuration"},
                retryable=False,
            ),
            trace,
        )

    def _should_fallback(self, error_dict: dict) -> bool:
        """Determine if error warrants fallback to secondary provider.
        
        Fallback criteria:
        - Error category is "availability" (engine unavailable)
        - Error is not retryable (permanent failure)
        
        Args:
            error_dict: Error dictionary from provider
            
        Returns:
            True if should attempt fallback, False otherwise
        """
        details = error_dict.get("details", {})
        category = details.get("category", "")
        retryable = error_dict.get("retryable", False)
        
        # Fallback on availability issues that are not retryable
        return category == "availability" and not retryable

    def check_provider_health(self) -> Result[dict[str, object]]:
        """Check health of all configured providers.
        
        Returns:
            Success with health status of all providers, or failure if none configured
        """
        if self._primary_provider is None and self._fallback_provider is None:
            return failure(
                code="tts_no_providers",
                message="No TTS providers configured",
                details={"category": "configuration"},
                retryable=False,
            )
        
        health_status = {}
        
        if self._primary_provider is not None:
            primary_health = self._primary_provider.health_check()
            health_status["primary"] = {
                "engine": self._primary_provider.engine_name,
                "healthy": primary_health.ok,
                "details": primary_health.data if primary_health.ok else primary_health.error.to_dict(),
            }
        
        if self._fallback_provider is not None:
            fallback_health = self._fallback_provider.health_check()
            health_status["fallback"] = {
                "engine": self._fallback_provider.engine_name,
                "healthy": fallback_health.ok,
                "details": fallback_health.data if fallback_health.ok else fallback_health.error.to_dict(),
            }
        
        return success(health_status)

    def chunk_text_for_job(
        self,
        *,
        text: str,
        job_id: str,
        correlation_id: str,
        max_chars: int,
        language_hint: str | None = None,
    ) -> Result[dict[str, object]]:
        """Chunk extracted text and persist deterministic chunk metadata for a job."""
        if self._chunking_service is None:
            return failure(
                code="chunking.service_unavailable",
                message="Chunking service is not configured",
                details={"category": "configuration"},
                retryable=False,
            )

        if self._chunks_repository is None:
            return failure(
                code="chunking.repository_unavailable",
                message="Chunks repository is not configured",
                details={"category": "configuration"},
                retryable=False,
            )

        self._emit_chunking_event(
            event="chunking.started",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            extra={"max_chars": max_chars},
        )

        chunking_result = self._chunking_service.chunk_text(
            text=text,
            max_chars=max_chars,
            language_hint=language_hint,
        )
        if not chunking_result.ok:
            self._emit_chunking_event(
                event="chunking.failed",
                severity="ERROR",
                correlation_id=correlation_id,
                job_id=job_id,
                extra={"error": chunking_result.error.to_dict() if chunking_result.error else {}},
            )
            return chunking_result

        created_at = datetime.now(timezone.utc).isoformat()
        chunks_payload: list[dict[str, object]] = []
        for index, chunk_text in enumerate(chunking_result.data or []):
            chunks_payload.append(
                {
                    "chunk_index": index,
                    "text_content": chunk_text,
                    "content_hash": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
                    "status": "pending",
                    "created_at": created_at,
                }
            )

        persisted_chunks = self._chunks_repository.replace_chunks_for_job(
            job_id=job_id,
            chunks=chunks_payload,
        )

        self._emit_chunking_event(
            event="chunking.completed",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            extra={"chunk_count": len(persisted_chunks)},
        )

        return success(
            {
                "job_id": job_id,
                "chunk_count": len(persisted_chunks),
                "chunks": [
                    {
                        "chunk_index": chunk["chunk_index"],
                        "text": chunk["text_content"],
                        "content_hash": chunk.get("content_hash", ""),
                        "created_at": chunk.get("created_at", created_at),
                    }
                    for chunk in persisted_chunks
                ],
            }
        )

    def _emit_chunking_event(
        self,
        *,
        event: str,
        severity: str,
        correlation_id: str,
        job_id: str,
        chunk_index: int = -1,
        extra: dict[str, object] | None = None,
    ) -> None:
        """Emit chunking lifecycle event with proper chunk_index tracking.
        
        Args:
            event: Event name (chunking.started, chunking.completed, chunking.failed)
            severity: Event severity level
            correlation_id: Request correlation ID
            job_id: Job identifier
            chunk_index: Chunk index for per-chunk events, -1 for job-level events
            extra: Additional event payload fields
        """
        if self._logger is None or not hasattr(self._logger, "emit"):
            return

        try:
            self._logger.emit(
                event=event,
                stage="chunking",
                severity=severity,
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
                engine="orchestrator",
                timestamp=datetime.now(timezone.utc).isoformat(),
                extra=extra or {},
            )
        except Exception:
            return

    def _emit_tts_event(
        self,
        *,
        event: str,
        severity: str,
        correlation_id: str,
        job_id: str,
        chunk_index: int,
        engine: str,
        extra: dict[str, object] | None = None,
    ) -> None:
        """Emit per-chunk TTS orchestration lifecycle event."""
        if self._logger is None or not hasattr(self._logger, "emit"):
            return

        try:
            self._logger.emit(
                event=event,
                stage="tts_orchestration",
                severity=severity,
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
                engine=engine,
                timestamp=datetime.now(timezone.utc).isoformat(),
                extra=extra or {},
            )
        except Exception:
            return

    def _persist_chunk_outcome(self, *, job_id: str, chunk_index: int, status: str) -> None:
        """Persist chunk-level synthesis outcome.
        
        Critical: This method must succeed or raise an exception. Silent failures
        would compromise resume capability and state consistency.
        
        Raises:
            RuntimeError: If chunks repository is not configured or persistence fails
        """
        if self._chunks_repository is None:
            raise RuntimeError(
                f"Cannot persist chunk outcome: chunks repository not configured (job_id={job_id}, chunk_index={chunk_index})"
            )

        self._chunks_repository.update_chunk_synthesis_outcome(
            job_id=job_id,
            chunk_index=chunk_index,
            status=status,
        )
