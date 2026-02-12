"""Non-blocking readiness recheck worker with signal-like callbacks."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from contracts.result import Result, failure


Callback = Callable[[Result[dict[str, Any]]], None]


@dataclass(slots=True)
class ConversionWorker:
    """Background worker to refresh readiness without blocking the UI thread.

    Supports an optional ``dispatch_to_main`` callable that wraps listener
    invocations so they execute on the UI thread (e.g. via
    ``QTimer.singleShot(0, fn)``).  When *None*, callbacks are invoked
    directly from the worker thread — suitable for tests but **not** for
    production Qt usage.
    """

    recheck_callable: Callable[[], Result[dict[str, Any]]]
    logger: Any
    dispatch_to_main: Callable[[Callable[[], None]], None] | None = None
    max_workers: int = 1
    _listeners: list[Callback] = field(default_factory=list)
    _executor: ThreadPoolExecutor = field(init=False)
    _is_refreshing: bool = field(init=False, default=False)
    _refresh_lock: threading.Lock = field(init=False, default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="readiness-worker")

    def on_readiness_refreshed(self, callback: Callback) -> None:
        self._listeners.append(callback)

    @property
    def is_refreshing(self) -> bool:
        return self._is_refreshing

    def refresh_readiness(self) -> Future[Result[dict[str, Any]]] | None:
        """Submit a readiness recheck.  Returns *None* if a refresh is already in progress."""
        with self._refresh_lock:
            if self._is_refreshing:
                return None
            self._is_refreshing = True
        self.logger.emit(event="readiness.checked", stage="readiness")
        return self._executor.submit(self._run_refresh)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)

    def _dispatch(self, callback: Callback, result: Result[dict[str, Any]]) -> None:
        """Invoke *callback* on the main thread when a dispatcher is set."""
        if self.dispatch_to_main is not None:
            self.dispatch_to_main(lambda cb=callback, r=result: cb(r))
        else:
            callback(result)

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
        finally:
            with self._refresh_lock:
                self._is_refreshing = False

        for callback in self._listeners:
            self._dispatch(callback, result)
        return result

