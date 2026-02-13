"""TTS orchestration service for provider coordination and fallback logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from contracts.result import Result, failure, success
from domain.services.job_state_validator import validate_job_state_transition

if TYPE_CHECKING:
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
    ) -> None:
        """Initialize orchestration service with optional providers.
        
        Args:
            primary_provider: Primary TTS provider (e.g., Chatterbox GPU)
            fallback_provider: Fallback TTS provider (e.g., Kokoro CPU)
        """
        self._primary_provider = primary_provider
        self._fallback_provider = fallback_provider

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
