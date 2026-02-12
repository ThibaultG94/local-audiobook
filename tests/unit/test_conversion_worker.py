from __future__ import annotations

import threading
import time
import unittest

from contracts.result import success
from ui.workers.conversion_worker import ConversionWorker


class _FakeLogger:
    def __init__(self) -> None:
        self.events: list[str] = []

    def emit(self, *, event: str, stage: str, **_: object) -> None:
        self.events.append(f"{stage}:{event}")


class TestConversionWorker(unittest.TestCase):
    def test_recheck_failure_is_normalized(self) -> None:
        logger = _FakeLogger()

        def failing_recheck():
            raise RuntimeError("boom")

        worker = ConversionWorker(recheck_callable=failing_recheck, logger=logger)
        try:
            future = worker.refresh_readiness()
            result = future.result(timeout=2)
            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "readiness_recheck_failed")
            self.assertIn("exception", result.error.details)
            self.assertIn("readiness:readiness.checked", logger.events)
        finally:
            worker.shutdown()

    def test_refresh_runs_off_main_thread(self) -> None:
        logger = _FakeLogger()
        main_thread_name = threading.current_thread().name
        thread_names: list[str] = []

        def delayed_recheck():
            thread_names.append(threading.current_thread().name)
            time.sleep(0.05)
            return success(
                {
                    "status": "ready",
                    "engines": [
                        {"engine": "chatterbox_gpu", "ok": True},
                        {"engine": "kokoro_cpu", "ok": True},
                    ],
                    "remediation": [],
                }
            )

        worker = ConversionWorker(recheck_callable=delayed_recheck, logger=logger)
        try:
            future = worker.refresh_readiness()
            future.result(timeout=2)
            self.assertTrue(thread_names)
            self.assertNotEqual(thread_names[0], main_thread_name)
        finally:
            worker.shutdown()

