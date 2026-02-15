from __future__ import annotations

import unittest

from src.contracts.result import failure, success
from src.ui.presenters.conversion_presenter import ConversionPresenter
from src.ui.views.conversion_view import ConversionView


class _FakeWorker:
    def __init__(self, *, recheck_result=None) -> None:
        self._callback = None
        self._progress_callback = None
        self._state_callback = None
        self._error_callback = None
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

    def on_conversion_progressed(self, callback):
        self._progress_callback = callback

    def on_conversion_state_changed(self, callback):
        self._state_callback = callback

    def on_conversion_failed(self, callback):
        self._error_callback = callback

    def emit_progress(self, payload: dict[str, object]) -> None:
        assert self._progress_callback is not None
        self._progress_callback(payload)

    def emit_state(self, payload: dict[str, object]) -> None:
        assert self._state_callback is not None
        self._state_callback(payload)

    def emit_error(self, payload: dict[str, object]) -> None:
        assert self._error_callback is not None
        self._error_callback(payload)


class _FakeLogger:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.payloads: list[dict[str, object]] = []

    def emit(self, *, event: str, stage: str, **kwargs: object) -> None:
        self.events.append(f"{stage}:{event}")
        self.payloads.append({"event": event, "stage": stage, **kwargs})


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

    def test_conversion_progress_and_state_are_mapped_into_view_state(self) -> None:
        worker = _FakeWorker()
        view = ConversionView(
            presenter=ConversionPresenter(),
            worker=worker,
            logger=_FakeLogger(),
        )

        worker.emit_state(
            {
                "status": "running",
                "progress_percent": 0,
                "chunk_index": -1,
                "job_id": "job-state-1",
                "correlation_id": "corr-state-1",
            }
        )
        worker.emit_progress(
            {
                "status": "running",
                "progress_percent": 50,
                "chunk_index": 1,
                "succeeded_chunks": 2,
                "total_chunks": 4,
            }
        )
        worker.emit_state(
            {
                "status": "completed",
                "progress_percent": 100,
                "chunk_index": -1,
                "job_id": "job-state-1",
                "correlation_id": "corr-state-1",
            }
        )

        conversion = view.current_state["conversion"]
        self.assertEqual(conversion["status"], "completed")
        self.assertEqual(conversion["progress_percent"], 100)
        self.assertEqual(conversion["job_id"], "job-state-1")

    def test_conversion_error_sets_failed_status_and_error_payload(self) -> None:
        worker = _FakeWorker()
        view = ConversionView(
            presenter=ConversionPresenter(),
            worker=worker,
            logger=_FakeLogger(),
        )

        worker.emit_error(
            {
                "error": {
                    "code": "tts_orchestration.chunk_failed_unrecoverable",
                    "message": "Chunk synthesis failed for all configured providers",
                    "details": {"chunk_index": 3},
                    "retryable": False,
                }
            }
        )

        self.assertEqual(view.current_state["conversion"]["status"], "failed")
        self.assertEqual(view.current_state["error"]["code"], "tts_orchestration.chunk_failed_unrecoverable")

    def test_conversion_error_builds_actionable_diagnostics_panel(self) -> None:
        logger = _FakeLogger()
        worker = _FakeWorker()
        view = ConversionView(
            presenter=ConversionPresenter(),
            worker=worker,
            logger=logger,
        )

        worker.emit_error(
            {
                "job_id": "job-diag-view-1",
                "correlation_id": "corr-diag-view-1",
                "error": {
                    "code": "postprocess.output_write_failed",
                    "message": "Failed to write final artifact",
                    "details": {
                        "stage": "postprocess",
                        "engine": "kokoro_cpu",
                        "job_id": "job-diag-view-1",
                        "correlation_id": "corr-diag-view-1",
                        "traceback": "internal trace should be hidden",
                    },
                    "retryable": True,
                },
            }
        )

        diagnostics = view.current_state["diagnostics"]
        self.assertTrue(diagnostics["panel_visible"])
        self.assertFalse(diagnostics["details_expanded"])
        self.assertEqual(diagnostics["stage"], "postprocess")
        self.assertEqual(diagnostics["engine"], "kokoro_cpu")
        self.assertEqual(diagnostics["job_id"], "job-diag-view-1")
        self.assertEqual(diagnostics["correlation_id"], "corr-diag-view-1")
        self.assertTrue(diagnostics["retry_enabled"])
        self.assertFalse(diagnostics["safe_for_display"])

        panel_events = [payload for payload in logger.payloads if payload.get("event") == "diagnostics_ui.panel_shown"]
        self.assertEqual(len(panel_events), 1)
        self.assertEqual(panel_events[0]["stage"], "diagnostics_ui")
        self.assertEqual(panel_events[0]["correlation_id"], "corr-diag-view-1")
        self.assertEqual(panel_events[0]["job_id"], "job-diag-view-1")

    def test_diagnostics_details_toggle_and_retry_request_emit_events(self) -> None:
        logger = _FakeLogger()
        worker = _FakeWorker()
        view = ConversionView(
            presenter=ConversionPresenter(),
            worker=worker,
            logger=logger,
        )

        worker.emit_error(
            {
                "job_id": "job-diag-view-2",
                "correlation_id": "corr-diag-view-2",
                "error": {
                    "code": "tts_orchestration.chunk_failed_unrecoverable",
                    "message": "Failure",
                    "details": {
                        "engine": "chatterbox_gpu",
                        "chunk_index": 1,
                        "job_id": "job-diag-view-2",
                        "correlation_id": "corr-diag-view-2",
                    },
                    "retryable": False,
                },
            }
        )

        view.set_diagnostics_details_expanded(True)
        retry_allowed = view.request_retry()

        self.assertTrue(view.current_state["diagnostics"]["details_expanded"])
        self.assertFalse(retry_allowed)

        toggled_events = [payload for payload in logger.payloads if payload.get("event") == "diagnostics_ui.details_toggled"]
        retry_events = [payload for payload in logger.payloads if payload.get("event") == "diagnostics_ui.retry_requested"]
        self.assertEqual(len(toggled_events), 1)
        self.assertEqual(len(retry_events), 1)
        self.assertEqual(toggled_events[0]["stage"], "diagnostics_ui")
        self.assertEqual(retry_events[0]["severity"], "WARNING")

    def test_diagnostics_panel_cleared_when_conversion_completes(self) -> None:
        worker = _FakeWorker()
        view = ConversionView(
            presenter=ConversionPresenter(),
            worker=worker,
            logger=_FakeLogger(),
        )

        # First, trigger an error to show diagnostics panel
        worker.emit_error(
            {
                "job_id": "job-clear-1",
                "correlation_id": "corr-clear-1",
                "error": {
                    "code": "tts_orchestration.chunk_failed_unrecoverable",
                    "message": "Failure",
                    "details": {"chunk_index": 1},
                    "retryable": False,
                },
            }
        )
        self.assertTrue(view.current_state["diagnostics"]["panel_visible"])
        self.assertEqual(view.current_state["conversion"]["status"], "failed")

        # Then, emit a completed state
        worker.emit_state(
            {
                "status": "completed",
                "progress_percent": 100,
                "chunk_index": -1,
                "job_id": "job-clear-1",
                "correlation_id": "corr-clear-1",
            }
        )

        # Diagnostics panel should be cleared
        self.assertFalse(view.current_state["diagnostics"]["panel_visible"])
        self.assertEqual(view.current_state["diagnostics"]["summary"], "")
        self.assertEqual(view.current_state["conversion"]["status"], "completed")
