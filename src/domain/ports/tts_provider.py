"""Canonical domain port for TTS providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, TypedDict

from src.contracts.result import Result


class TtsVoice(TypedDict):
    """Normalized voice descriptor returned by providers."""

    id: str
    name: str
    engine: str
    language: str
    supports_streaming: bool


class TtsSynthesisMetadata(TypedDict):
    """Standardized synthesis metadata payload."""

    engine: str
    voice_id: str
    content_type: str
    sample_rate_hz: int


class TtsSynthesisData(TypedDict):
    """Standardized synthesis data payload."""

    audio_bytes: bytes
    metadata: TtsSynthesisMetadata


class ProviderLogger(Protocol):
    """Minimal logger interface used by provider adapters."""

    def emit(self, **payload: Any) -> None: ...


class TtsProvider(ABC):
    """Port for local TTS engines used by the application."""

    engine_name: str

    @abstractmethod
    def synthesize_chunk(
        self,
        text: str,
        voice: str | None = None,
        *,
        correlation_id: str = "",
        job_id: str = "",
        chunk_index: int = -1,
    ) -> Result[TtsSynthesisData]:
        """Synthesize one text chunk into canonical audio + metadata payload."""

    @abstractmethod
    def list_voices(self) -> Result[list[TtsVoice]]:
        """Return locally available voices in canonical shape."""

    @abstractmethod
    def health_check(self) -> Result[dict[str, object]]:
        """Report local engine health and availability."""
