"""Normalized result contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from .errors import AppError

T = TypeVar("T")


@dataclass(slots=True)
class Result(Generic[T]):
    """Result envelope with shape: {ok, data, error}."""

    ok: bool
    data: T | None = None
    error: AppError | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error.to_dict() if self.error else None,
        }


def success(data: T | None = None) -> Result[T]:
    return Result(ok=True, data=data, error=None)


def failure(code: str, message: str, details: dict[str, Any] | None = None, retryable: bool = False) -> Result[Any]:
    return Result(
        ok=False,
        data=None,
        error=AppError(
            code=code,
            message=message,
            details=details or {},
            retryable=retryable,
        ),
    )

