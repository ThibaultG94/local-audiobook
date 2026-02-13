"""Shared no-op logger implementation for optional logger injection."""

from __future__ import annotations

from typing import Any


class NoopLogger:
    """No-operation logger that silently discards all events.
    
    Used as a default when no logger is injected, avoiding None checks
    throughout the codebase.
    """

    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: Any) -> None:
        """Discard event without side effects."""
        return None
