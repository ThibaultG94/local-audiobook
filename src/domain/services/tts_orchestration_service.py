"""TTS orchestration service for provider coordination and fallback logic."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from contracts.result import Result, failure, success
from domain.services.job_state_validator import validate_job_state_transition

if TYPE_CHECKING:
    from domain.services.chunking_service import ChunkingService
    from domain.ports.tts_provider import TtsProvider, TtsSynthesisData


class TtsOrchestrationService:
    """Orchestration service managing TTS provider selection and fallback behavior.
    
    This service owns all fallback policy decisions and coordinates between
    multiple TTS providers based on their health and error responses.
    """

    def __init__(
        self,
        primary_provider: TtsProvider | None = None,
        fallback_provider: TtsProvider | None = None,
        chunking_service: ChunkingService | None = None,
        chunks_repository: object | None = None,
        logger: object | None = None,
    ) -> None:
        """Initialize orchestration service with optional providers.
        
        Args:
            primary_provider: Primary TTS provider (e.g., Chatterbox GPU)
            fallback_provider: Fallback TTS provider (e.g., Kokoro CPU)
        """
        self._primary_provider = primary_provider
        self._fallback_provider = fallback_provider
        self._chunking_service = chunking_service
        self._chunks_repository = chunks_repository
        self._logger = logger

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
    ) -> Result[dict[str, object]]:
        """Synthesize persisted chunks in deterministic chunk_index order.

        This orchestration entrypoint owns fallback policy decisions and emits
        per-chunk structured lifecycle events for diagnosis.
        """
        if self._chunks_repository is None or not hasattr(self._chunks_repository, "list_chunks_for_job"):
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

        ordered_chunks = sorted(persisted_chunks, key=lambda chunk: int(chunk["chunk_index"]))
        chunk_results: list[dict[str, object]] = []

        for chunk in ordered_chunks:
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
                continue

            failure_details = {
                "job_id": job_id,
                "chunk_index": chunk_index,
                "attempted_engines": attempt_trace.get("attempted_engines", []),
                "primary_error": attempt_trace.get("primary_error", {}),
                "fallback_error": attempt_trace.get("fallback_error", {}),
                "category": "availability",
                "transition_intent": self._build_transition_intent(
                    current_state=current_job_state,
                    next_state="failed",
                ),
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
                extra={"code": "tts_orchestration.chunk_failed_unrecoverable"},
            )

            return failure(
                code="tts_orchestration.chunk_failed_unrecoverable",
                message="Chunk synthesis failed for all configured providers",
                details=failure_details,
                retryable=False,
            )

        return success(
            {
                "job_id": job_id,
                "chunk_results": chunk_results,
                "succeeded_chunks": len(chunk_results),
                "transition_intent": self._build_transition_intent(
                    current_state=current_job_state,
                    next_state="completed",
                ),
            }
        )

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

        if self._chunks_repository is None or not hasattr(self._chunks_repository, "replace_chunks_for_job"):
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

    def _persist_chunk_outcome(self, *, job_id: str, chunk_index: int, status: str) -> None:
        """Persist chunk-level synthesis outcome when repository supports it."""
        if self._chunks_repository is None or not hasattr(self._chunks_repository, "update_chunk_synthesis_outcome"):
            return

        self._chunks_repository.update_chunk_synthesis_outcome(
            job_id=job_id,
            chunk_index=chunk_index,
            status=status,
        )

    def _build_transition_intent(self, *, current_state: str, next_state: str) -> dict[str, object]:
        """Validate transition intent through service-level state rules."""
        transition = self.validate_transition(current_state, next_state)
        if transition.ok:
            return {
                "current_state": current_state,
                "next_state": next_state,
                "validated": True,
                "error": None,
            }
        return {
            "current_state": current_state,
            "next_state": next_state,
            "validated": False,
            "error": transition.error.to_dict() if transition.error else {},
        }
