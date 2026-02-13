from __future__ import annotations

import unittest

from contracts.result import failure, success
from ui.presenters.conversion_presenter import ConversionPresenter
from ui.views.conversion_view import ConversionView


class _FakeWorker:
    def __init__(self, *, recheck_result=None) -> None:
        self._callback = None
        self._recheck_result = recheck_result

    def on_readiness_refreshed(self, callback):
        self._callback = callback

    def refresh_readiness(self) -> None:
        if self._recheck_result is not None:
            self._callback(self._recheck_result)
        else:
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
        # readiness.displayed emitted on initial render AND on recheck
        displayed_events = [e for e in logger.events if e == "readiness:readiness.displayed"]
        self.assertEqual(len(displayed_events), 2)

    def test_recheck_failure_propagates_error_to_view_state(self) -> None:
        """H4: Verify that a failed recheck populates the error field in view state."""
        logger = _FakeLogger()
        recheck_failure = failure(
            code="readiness_recheck_failed",
            message="Readiness recheck failed",
            details={"exception": "boom"},
            retryable=True,
        )
        worker = _FakeWorker(recheck_result=recheck_failure)
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
        # State should remain not_ready (not silently swallowed)
        self.assertEqual(view.current_state["status"], "not_ready")
        self.assertFalse(view.current_state["start_enabled"])
        # Error should be populated
        self.assertIsNotNone(view.current_state["error"])
        self.assertEqual(view.current_state["error"]["code"], "readiness_presenter_mapping_failed")

    def test_build_configuration_options_disables_unavailable_engine_and_voice(self) -> None:
        view = ConversionView(
            presenter=ConversionPresenter(),
            worker=_FakeWorker(),
            logger=_FakeLogger(),
        )

        options = view.build_configuration_options(
            engine_statuses=[
                {"engine": "chatterbox_gpu", "ok": False},
                {"engine": "kokoro_cpu", "ok": True},
            ],
            voices=[
                {"id": "default", "name": "Default Chatterbox Voice", "engine": "chatterbox_gpu", "language": "en"},
                {"id": "default", "name": "Default Kokoro Voice", "engine": "kokoro_cpu", "language": "en"},
            ],
        )

        chatterbox = next(item for item in options["engines"] if item["id"] == "chatterbox_gpu")
        kokoro = next(item for item in options["engines"] if item["id"] == "kokoro_cpu")
        self.assertTrue(chatterbox["disabled"])
        self.assertIn("unavailable", chatterbox["reason"].lower())
        self.assertFalse(kokoro["disabled"])

        chatterbox_voice = next(item for item in options["voices"] if item["engine"] == "chatterbox_gpu")
        kokoro_voice = next(item for item in options["voices"] if item["engine"] == "kokoro_cpu")
        self.assertTrue(chatterbox_voice["disabled"])
        self.assertFalse(kokoro_voice["disabled"])
