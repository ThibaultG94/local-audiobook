"""Non-blocking readiness recheck worker with signal-like callbacks."""

from __future__ import annotations

import threading
import traceback
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from inspect import Signature, signature
from types import MappingProxyType
from typing import Any, Callable
from uuid import uuid4

from src.contracts.result import Result, failure, success


Callback = Callable[[Result[dict[str, Any]]], None]
ProgressCallback = Callable[[dict[str, Any]], None]
StateCallback = Callable[[dict[str, Any]], None]


class ConversionJobsRepositoryPort:
    def create_job(
        self,
        *,
        job_id: str,
        document_id: str,
        state: str,
        engine: str,
        voice: str,
        language: str,
        speech_rate: float,
        output_format: str,
        created_at: str,
        updated_at: str,
    ) -> dict[str, Any]: ...


class ConversionLauncherPort:
    def launch_conversion(
        self,
        *,
        job_id: str,
        correlation_id: str,
        conversion_config: dict[str, Any],
        progress_callback: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> Result[dict[str, Any]]: ...


@dataclass(slots=True)
class ConversionWorker:
    """Background worker to refresh readiness without blocking the UI thread.

    Supports an optional ``dispatch_to_main`` callable that wraps listener
    invocations so they execute on the UI thread. This is **critical** for Qt
    production usage to avoid thread-safety violations when updating UI widgets.
    
    **Qt Implementation Example:**
        ```python
        from PyQt5.QtCore import QTimer
        
        def qt_dispatcher(fn: Callable[[], None]) -> None:
            QTimer.singleShot(0, fn)
        
        worker = ConversionWorker(
            recheck_callable=...,
            logger=...,
            dispatch_to_main=qt_dispatcher
        )
        ```
    
    When ``dispatch_to_main`` is *None*, callbacks are invoked directly from
    the worker thread — suitable for tests but **unsafe** for production Qt
    usage (will cause crashes or undefined behavior when touching UI objects).
    """

    recheck_callable: Callable[[], Result[dict[str, Any]]]
    logger: Any
    conversion_jobs_repository: ConversionJobsRepositoryPort | None = None
    conversion_launcher: ConversionLauncherPort | None = None
    dispatch_to_main: Callable[[Callable[[], None]], None] | None = None
    max_workers: int = 1
    _listeners: list[Callback] = field(default_factory=list)
    _conversion_progress_listeners: list[ProgressCallback] = field(default_factory=list)
    _conversion_state_listeners: list[StateCallback] = field(default_factory=list)
    _conversion_error_listeners: list[StateCallback] = field(default_factory=list)
    _active_conversion_threads: set[int] = field(default_factory=set)
    _conversion_lock: threading.Lock = field(init=False, default_factory=threading.Lock)
    _executor: ThreadPoolExecutor = field(init=False)
    _is_refreshing: bool = field(init=False, default=False)
    _refresh_lock: threading.Lock = field(init=False, default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="conversion-worker")

    def on_readiness_refreshed(self, callback: Callback) -> None:
        self._listeners.append(callback)

    def on_conversion_progressed(self, callback: ProgressCallback) -> None:
        self._conversion_progress_listeners.append(callback)

    def on_conversion_state_changed(self, callback: StateCallback) -> None:
        self._conversion_state_listeners.append(callback)

    def on_conversion_failed(self, callback: StateCallback) -> None:
        self._conversion_error_listeners.append(callback)

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

    def _dispatch_payload(self, callback: Callable[[dict[str, Any]], None], payload: dict[str, Any]) -> None:
        if self.dispatch_to_main is not None:
            self.dispatch_to_main(lambda cb=callback, data=payload: cb(data))
        else:
            callback(payload)

    def _dispatch_state(self, payload: dict[str, Any]) -> None:
        for callback in self._conversion_state_listeners:
            self._dispatch_payload(callback, payload)

    def _dispatch_progress(self, payload: dict[str, Any]) -> None:
        for callback in self._conversion_progress_listeners:
            self._dispatch_payload(callback, payload)

    def _dispatch_error(self, payload: dict[str, Any]) -> None:
        for callback in self._conversion_error_listeners:
            self._dispatch_payload(callback, payload)

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

    def launch_conversion(
        self,
        *,
        document_id: str,
        job_id: str,
        correlation_id: str,
        conversion_config: dict[str, Any],
    ) -> Result[dict[str, Any]]:
        prepared = self._prepare_conversion_launch(
            document_id=document_id,
            job_id=job_id,
            correlation_id=correlation_id,
            conversion_config=conversion_config,
        )
        if not prepared.ok:
            return prepared

        immutable_config = MappingProxyType(dict(prepared.data or {}))

        if self.conversion_launcher is None:
            return Result(ok=True, data={"job_id": job_id, "config": dict(immutable_config)}, error=None)

        return self.conversion_launcher.launch_conversion(
            job_id=job_id,
            correlation_id=correlation_id,
            conversion_config=immutable_config,
        )

    def _prepare_conversion_launch(
        self,
        *,
        document_id: str,
        job_id: str,
        correlation_id: str,
        conversion_config: dict[str, Any],
    ) -> Result[dict[str, Any]]:
        required_keys = {"engine", "voice_id", "language", "speech_rate", "output_format"}
        missing = sorted(required_keys - conversion_config.keys())
        if missing:
            return failure(
                code="configuration.invalid_payload",
                message="Conversion configuration payload is incomplete",
                details={"missing_keys": missing},
                retryable=False,
            )

        normalized_config = {
            "engine": str(conversion_config["engine"]),
            "voice_id": str(conversion_config["voice_id"]),
            "language": str(conversion_config["language"]),
            "speech_rate": float(conversion_config["speech_rate"]),
            "output_format": str(conversion_config["output_format"]),
        }
        immutable_config = MappingProxyType(dict(normalized_config))

        timestamp = datetime.now(timezone.utc).isoformat()
        if self.conversion_jobs_repository is not None:
            self.conversion_jobs_repository.create_job(
                job_id=job_id,
                document_id=document_id,
                state="queued",
                engine=normalized_config["engine"],
                voice=normalized_config["voice_id"],
                language=normalized_config["language"],
                speech_rate=normalized_config["speech_rate"],
                output_format=normalized_config["output_format"],
                created_at=timestamp,
                updated_at=timestamp,
            )

        self.logger.emit(
            event="conversion.launch_prepared",
            stage="configuration",
            severity="INFO",
            correlation_id=correlation_id,
            job_id=job_id,
            chunk_index=-1,
            engine=normalized_config["engine"],
            extra={"output_format": normalized_config["output_format"]},
        )
        return success(dict(immutable_config))

    def execute_conversion_async(
        self,
        *,
        document_id: str,
        job_id: str,
        correlation_id: str,
        conversion_config: dict[str, Any],
    ) -> Future[Result[dict[str, Any]]]:
        return self._executor.submit(
            self._run_conversion,
            document_id,
            job_id,
            correlation_id,
            conversion_config,
        )

    def _run_conversion(
        self,
        document_id: str,
        job_id: str,
        correlation_id: str,
        conversion_config: dict[str, Any],
    ) -> Result[dict[str, Any]]:
        # Generate fallback correlation_id at worker boundary entry point if missing
        normalized_correlation_id = str(correlation_id or "").strip() or str(uuid4())
        
        with self._conversion_lock:
            self._active_conversion_threads.add(threading.get_ident())

        self._emit_worker_event(
            event="worker_execution.started",
            severity="INFO",
            correlation_id=normalized_correlation_id,
            job_id=job_id,
            engine=str(conversion_config.get("engine", "")),
            chunk_index=-1,
            extra={"state": "running"},
        )
        self._dispatch_state(
            {
                "job_id": job_id,
                "correlation_id": normalized_correlation_id,
                "status": "running",
                "progress_percent": 0,
                "chunk_index": -1,
            }
        )

        def emit_progress(progress_payload: Mapping[str, Any]) -> None:
            total_chunks = int(progress_payload.get("total_chunks", 0) or 0)
            succeeded_chunks = int(progress_payload.get("succeeded_chunks", 0) or 0)
            percent = int(progress_payload.get("progress_percent", 0) or 0)
            if percent <= 0 and total_chunks > 0:
                percent = int((succeeded_chunks / total_chunks) * 100)
            normalized = {
                "job_id": job_id,
                "correlation_id": normalized_correlation_id,
                "status": "running",
                "progress_percent": max(0, min(percent, 100)),
                "chunk_index": int(progress_payload.get("chunk_index", -1) or -1),
                "succeeded_chunks": succeeded_chunks,
                "total_chunks": total_chunks,
            }
            self._emit_worker_event(
                event="worker_execution.progressed",
                severity="INFO",
                correlation_id=normalized_correlation_id,
                job_id=job_id,
                engine=str(conversion_config.get("engine", "")),
                chunk_index=normalized["chunk_index"],
                extra={
                    "status": normalized["status"],
                    "progress_percent": normalized["progress_percent"],
                    "succeeded_chunks": normalized["succeeded_chunks"],
                    "total_chunks": normalized["total_chunks"],
                },
            )
            self._dispatch_progress(normalized)

        try:
            prepared = self._prepare_conversion_launch(
                document_id=document_id,
                job_id=job_id,
                correlation_id=normalized_correlation_id,
                conversion_config=conversion_config,
            )
            if not prepared.ok:
                failed_payload = prepared.error.to_dict() if prepared.error else {}
                self._emit_worker_event(
                    event="worker_execution.failed",
                    severity="ERROR",
                    correlation_id=normalized_correlation_id,
                    job_id=job_id,
                    engine=str(conversion_config.get("engine", "")),
                    chunk_index=int(failed_payload.get("details", {}).get("chunk_index", -1) or -1),
                    extra={"error": failed_payload, "status": "failed"},
                )
                self._dispatch_state(
                    {
                        "job_id": job_id,
                        "correlation_id": normalized_correlation_id,
                        "status": "failed",
                        "progress_percent": 0,
                        "chunk_index": int(failed_payload.get("details", {}).get("chunk_index", -1) or -1),
                    }
                )
                self._dispatch_error(
                    {
                        "job_id": job_id,
                        "correlation_id": normalized_correlation_id,
                        "error": failed_payload,
                        "status": "failed",
                    }
                )
                return prepared

            orchestration_result = self._invoke_launcher(
                job_id=job_id,
                correlation_id=normalized_correlation_id,
                conversion_config=prepared.data or conversion_config,
                progress_callback=emit_progress,
            )
            if not orchestration_result.ok:
                normalized_failure = orchestration_result.error.to_dict() if orchestration_result.error else {
                    "code": "worker_execution.failed",
                    "message": "Conversion execution failed",
                    "details": {},
                    "retryable": False,
                }
                chunk_index = int(normalized_failure.get("details", {}).get("chunk_index", -1) or -1)
                self._emit_worker_event(
                    event="worker_execution.failed",
                    severity="ERROR",
                    correlation_id=normalized_correlation_id,
                    job_id=job_id,
                    engine=str(conversion_config.get("engine", "")),
                    chunk_index=chunk_index,
                    extra={"error": normalized_failure, "status": "failed"},
                )
                self._dispatch_state(
                    {
                        "job_id": job_id,
                        "correlation_id": normalized_correlation_id,
                        "status": "failed",
                        "progress_percent": int(normalized_failure.get("details", {}).get("progress_percent", 0) or 0),
                        "chunk_index": chunk_index,
                    }
                )
                self._dispatch_error(
                    {
                        "job_id": job_id,
                        "correlation_id": normalized_correlation_id,
                        "error": normalized_failure,
                        "status": "failed",
                    }
                )
                return orchestration_result

            payload = orchestration_result.data or {}
            self._emit_synthetic_progress_if_missing(
                payload=payload,
                correlation_id=normalized_correlation_id,
                job_id=job_id,
                engine=str(conversion_config.get("engine", "")),
                emitter=emit_progress,
            )
            self._emit_worker_event(
                event="worker_execution.completed",
                severity="INFO",
                correlation_id=normalized_correlation_id,
                job_id=job_id,
                engine=str(conversion_config.get("engine", "")),
                chunk_index=-1,
                extra={
                    "status": "completed",
                    "succeeded_chunks": int(payload.get("succeeded_chunks", 0) or 0),
                    "total_chunks": int(payload.get("succeeded_chunks", 0) or 0),
                    "progress_percent": 100,
                },
            )
            self._dispatch_state(
                {
                    "job_id": job_id,
                    "correlation_id": normalized_correlation_id,
                    "status": "completed",
                    "progress_percent": 100,
                    "chunk_index": -1,
                }
            )
            return orchestration_result
        except Exception as exc:  # pragma: no cover - guarded by tests via normalized payload assertions
            normalized = failure(
                code="worker_execution.unhandled_exception",
                message="Conversion worker execution failed unexpectedly",
                details={
                    "exception": str(exc),
                    "exception_type": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                },
                retryable=True,
            )
            error_payload = normalized.error.to_dict() if normalized.error else {}
            self._emit_worker_event(
                event="worker_execution.failed",
                severity="ERROR",
                correlation_id=normalized_correlation_id,
                job_id=job_id,
                engine=str(conversion_config.get("engine", "")),
                chunk_index=-1,
                extra={"error": error_payload, "status": "failed"},
            )
            self._dispatch_state(
                {
                    "job_id": job_id,
                    "correlation_id": normalized_correlation_id,
                    "status": "failed",
                    "progress_percent": 0,
                    "chunk_index": -1,
                }
            )
            self._dispatch_error(
                {
                    "job_id": job_id,
                    "correlation_id": normalized_correlation_id,
                    "error": error_payload,
                    "status": "failed",
                }
            )
            return normalized
        finally:
            with self._conversion_lock:
                self._active_conversion_threads.discard(threading.get_ident())

    @property
    def active_conversion_count(self) -> int:
        with self._conversion_lock:
            return len(self._active_conversion_threads)

    def _invoke_launcher(
        self,
        *,
        job_id: str,
        correlation_id: str,
        conversion_config: dict[str, Any],
        progress_callback: Callable[[Mapping[str, Any]], None],
    ) -> Result[dict[str, Any]]:
        if self.conversion_launcher is None:
            return Result(ok=True, data={"job_id": job_id}, error=None)

        launcher = self.conversion_launcher.launch_conversion
        sig: Signature = signature(launcher)
        kwargs: dict[str, Any] = {
            "job_id": job_id,
            "correlation_id": correlation_id,
            "conversion_config": MappingProxyType(dict(conversion_config)),
        }
        if "progress_callback" in sig.parameters:
            kwargs["progress_callback"] = progress_callback

        result = launcher(**kwargs)
        if not isinstance(result, Result):
            return failure(
                code="worker_execution.invalid_result",
                message="Conversion launcher returned an invalid result payload",
                details={"type": type(result).__name__, "expected": "Result"},
                retryable=False,
            )
        return result

    def _emit_synthetic_progress_if_missing(
        self,
        *,
        payload: Mapping[str, Any],
        correlation_id: str,
        job_id: str,
        engine: str,
        emitter: Callable[[Mapping[str, Any]], None],
    ) -> None:
        chunk_results = payload.get("chunk_results")
        if not isinstance(chunk_results, list) or not chunk_results:
            return

        total_chunks = len(chunk_results)
        for index, chunk in enumerate(chunk_results, start=1):
            chunk_index = -1
            if isinstance(chunk, Mapping):
                chunk_index = int(chunk.get("chunk_index", -1) or -1)
            percent = int((index / total_chunks) * 100)
            emitter(
                {
                    "chunk_index": chunk_index,
                    "succeeded_chunks": index,
                    "total_chunks": total_chunks,
                    "progress_percent": percent,
                }
            )

    def _emit_worker_event(
        self,
        *,
        event: str,
        severity: str,
        correlation_id: str,
        job_id: str,
        engine: str,
        chunk_index: int,
        extra: dict[str, Any],
    ) -> None:
        try:
            self.logger.emit(
                event=event,
                stage="worker_execution",
                severity=severity,
                correlation_id=correlation_id,
                job_id=job_id,
                chunk_index=chunk_index,
                engine=engine,
                timestamp=datetime.now(timezone.utc).isoformat(),
                extra=extra,
            )
        except Exception:
            return
