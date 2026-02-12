"""Non-blocking readiness recheck worker with signal-like callbacks."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from contracts.result import Result, failure


Callback = Callable[[Result[dict[str, Any]]], None]


@dataclass(slots=True)
class ConversionWorker:
    """Background worker to refresh readiness without blocking the UI thread."""

    recheck_callable: Callable[[], Result[dict[str, Any]]]
    logger: Any
    max_workers: int = 1
    _listeners: list[Callback] = field(default_factory=list)
    _executor: ThreadPoolExecutor = field(init=False)

    def __post_init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="readiness-worker")

    def on_readiness_refreshed(self, callback: Callback) -> None:
        self._listeners.append(callback)

    def refresh_readiness(self) -> Future[Result[dict[str, Any]]]:
        self.logger.emit(event="readiness.checked", stage="readiness")
        return self._executor.submit(self._run_refresh)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)

    def _run_refresh(self) -> Result[dict[str, Any]]:
        try:
            result = self.recheck_callable()
        except Exception as exc:
            result = failure(
                code="readiness_recheck_failed",
                message="Readiness recheck failed",
                details={"exception": str(exc)},
                retryable=True,
            )

        for callback in self._listeners:
            callback(result)
        return result

