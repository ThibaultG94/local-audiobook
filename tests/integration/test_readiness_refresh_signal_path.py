from __future__ import annotations

import time
import unittest

from contracts.result import success
from infrastructure.logging.jsonl_logger import JsonlLogger
from ui.presenters.conversion_presenter import ConversionPresenter
from ui.views.conversion_view import ConversionView
from ui.workers.conversion_worker import ConversionWorker


class TestReadinessRefreshSignalPathIntegration(unittest.TestCase):
    def test_recheck_is_non_blocking_and_updates_view_state_via_callback(self) -> None:
        logger = JsonlLogger("runtime/logs/test-readiness-refresh.jsonl")

        def delayed_ready_recheck():
            time.sleep(0.1)
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

        worker = ConversionWorker(recheck_callable=delayed_ready_recheck, logger=logger)
        view = ConversionView(presenter=ConversionPresenter(), worker=worker, logger=logger)

        try:
            initial = success(
                {
                    "status": "not_ready",
                    "engines": [
                        {"engine": "chatterbox_gpu", "ok": False},
                        {"engine": "kokoro_cpu", "ok": True},
                    ],
                    "remediation": ["Install chatterbox model assets"],
                }
            )
            view.render_initial(initial)

            started = time.monotonic()
            future = worker.refresh_readiness()
            elapsed_after_submit = time.monotonic() - started

            self.assertLess(elapsed_after_submit, 0.05)

            future.result(timeout=3)
            self.assertEqual(view.current_state["status"], "ready")
            self.assertTrue(view.current_state["start_enabled"])
        finally:
            worker.shutdown()

