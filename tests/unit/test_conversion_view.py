from __future__ import annotations

import unittest

from contracts.result import success
from ui.presenters.conversion_presenter import ConversionPresenter
from ui.views.conversion_view import ConversionView


class _FakeWorker:
    def __init__(self) -> None:
        self._callback = None

    def on_readiness_refreshed(self, callback):
        self._callback = callback

    def refresh_readiness(self) -> None:
        result = success(
            {
                "status": "ready",
                "engines": [
                    {"engine": "chatterbox_gpu", "ok": True},
                    {"engine": "kokoro_cpu", "ok": True},
                ],
                "remediation": [],
            }
        )
        self._callback(result)


class _FakeLogger:
    def __init__(self) -> None:
        self.events: list[str] = []

    def emit(self, *, event: str, stage: str, **_: object) -> None:
        self.events.append(f"{stage}:{event}")


class TestConversionView(unittest.TestCase):
    def test_start_disabled_when_not_ready(self) -> None:
        view = ConversionView(
            presenter=ConversionPresenter(),
            worker=_FakeWorker(),
            logger=_FakeLogger(),
        )
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

        mapped = view.render_initial(initial)
        self.assertTrue(mapped.ok)
        self.assertEqual(view.current_state["status"], "not_ready")
        self.assertFalse(view.current_state["start_enabled"])

    def test_start_enabled_after_recheck_when_ready(self) -> None:
        logger = _FakeLogger()
        worker = _FakeWorker()
        view = ConversionView(
            presenter=ConversionPresenter(),
            worker=worker,
            logger=logger,
        )

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

        view.recheck()
        self.assertEqual(view.current_state["status"], "ready")
        self.assertTrue(view.current_state["start_enabled"])
        self.assertIn("readiness:readiness.displayed", logger.events)

