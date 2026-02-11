"""Canonical domain port for TTS providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from contracts.result import Result


class TtsProvider(ABC):
    """Port for local TTS engines used by the application."""

    engine_name: str

    @abstractmethod
    def synthesize_chunk(self, text: str, voice: str | None = None) -> Result[bytes]:
        """Synthesize one text chunk into audio bytes."""

    @abstractmethod
    def list_voices(self) -> Result[list[str]]:
        """Return the list of locally available voices."""

    @abstractmethod
    def health_check(self) -> Result[dict[str, object]]:
        """Report local engine health and availability."""

