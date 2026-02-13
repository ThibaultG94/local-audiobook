"""Centralized event logger port protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EventLoggerPort(Protocol):
    """Protocol for structured event logging across all adapters and services."""

    def emit(
        self,
        *,
        event: str,
        stage: str,
        severity: str = "INFO",
        correlation_id: str = "",
        **kwargs: Any,
    ) -> None:
        """Emit a structured event.

        Args:
            event: Event name in domain.action format
            stage: Pipeline stage (extraction, chunking, synthesis, etc.)
            severity: Event severity (INFO, WARNING, ERROR)
            correlation_id: Request correlation identifier
            **kwargs: Additional event-specific fields
        """
        ...
