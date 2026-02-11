"""Chatterbox GPU provider adapter (local stub for startup validation)."""

from __future__ import annotations

from contracts.result import Result, failure, success
from domain.ports.tts_provider import TtsProvider


class ChatterboxProvider(TtsProvider):
    """Local-only Chatterbox adapter."""

    engine_name = "chatterbox_gpu"

    def __init__(self, healthy: bool = True) -> None:
        self._healthy = healthy

    def synthesize_chunk(self, text: str, voice: str | None = None) -> Result[bytes]:
        return failure(
            code="tts_not_implemented",
            message="Chatterbox synthesis is not implemented in this story",
            details={"engine": self.engine_name},
            retryable=False,
        )

    def list_voices(self) -> Result[list[str]]:
        return success([])

    def health_check(self) -> Result[dict[str, object]]:
        if self._healthy:
            return success({"engine": self.engine_name, "available": True})

        return failure(
            code="tts_engine_unavailable",
            message="Chatterbox engine failed startup health check",
            details={"engine": self.engine_name, "reason": "unhealthy"},
            retryable=False,
        )

