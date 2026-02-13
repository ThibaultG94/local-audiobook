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
        if self._primary_provider is None and self._fallback_provider is None:
            return failure(
                code="tts_no_providers",
                message="No TTS providers configured",
                details={"category": "configuration"},
                retryable=False,
            )

        # Try primary provider first
        if self._primary_provider is not None:
            result = self._primary_provider.synthesize_chunk(
                text,
                voice,
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
            )
            
            if result.ok:
                return result
            
            # Check if we should fallback based on error category
            if result.error and self._should_fallback(result.error.to_dict()):
                # Try fallback provider
                if self._fallback_provider is not None:
                    fallback_result = self._fallback_provider.synthesize_chunk(
                        text,
                        voice,
                        correlation_id=correlation_id,
                        job_id=job_id,
                        chunk_index=chunk_index,
                    )
                    
                    if fallback_result.ok:
                        return fallback_result
                    
                    # Both providers failed
                    return failure(
                        code="tts_all_providers_failed",
                        message="Both primary and fallback providers failed",
                        details={
                            "primary_error": result.error.to_dict(),
                            "fallback_error": fallback_result.error.to_dict(),
                            "category": "availability",
                        },
                        retryable=False,
                    )
            
            # Non-fallback error, return primary error
            return result
        
        # No primary provider, try fallback directly
        if self._fallback_provider is not None:
            return self._fallback_provider.synthesize_chunk(
                text,
                voice,
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
            )
        
        # Should never reach here due to initial check
        return failure(
            code="tts_no_providers",
            message="No TTS providers available",
            details={"category": "configuration"},
            retryable=False,
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
        extra: dict[str, object] | None = None,
    ) -> None:
        if self._logger is None or not hasattr(self._logger, "emit"):
            return

        self._logger.emit(
            event=event,
            stage="chunking",
            severity=severity,
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=-1,
            engine="orchestrator",
            timestamp=datetime.now(timezone.utc).isoformat(),
            extra=extra or {},
        )
