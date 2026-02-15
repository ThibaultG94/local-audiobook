from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adapters.persistence.sqlite.connection import create_connection
from src.adapters.persistence.sqlite.migration_runner import apply_migrations
from src.adapters.persistence.sqlite.repositories.conversion_jobs_repository import ConversionJobsRepository
from src.infrastructure.logging.event_schema import REQUIRED_EVENT_FIELDS, is_valid_utc_iso_8601
from src.infrastructure.logging.jsonl_logger import JsonlLogger
from src.contracts.result import failure, success
from src.ui.presenters.conversion_presenter import ConversionPresenter
from src.ui.views.conversion_view import ConversionView
from src.ui.workers.conversion_worker import ConversionWorker


class _LauncherProbe:
    def __init__(self) -> None:
        self.config = None

    def launch_conversion(self, *, job_id: str, correlation_id: str, conversion_config):
        self.config = conversion_config
        return success({"job_id": job_id, "correlation_id": correlation_id})


class _NoopWorker:
    def on_readiness_refreshed(self, callback):
        self._readiness = callback

    def on_conversion_progressed(self, callback):
        self._progress = callback

    def on_conversion_state_changed(self, callback):
        self._state = callback

    def on_conversion_failed(self, callback):
        self._error = callback

    def refresh_readiness(self):
        return None


class TestConversionConfigurationIntegration(unittest.TestCase):
    def test_configuration_saved_and_rejected_events_follow_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"
            logger = JsonlLogger(events_path)
            presenter = ConversionPresenter(logger=logger)

            accepted = presenter.build_conversion_config(
                engine="chatterbox_gpu",
                voice_id="default",
                language="FR",
                speech_rate=1.0,
                output_format="wav",
                voice_catalog=[{"id": "default", "engine": "chatterbox_gpu", "language": "en"}],
                correlation_id="corr-cfg-int-ok",
                job_id="job-cfg-int-ok",
            )
            self.assertTrue(accepted.ok)

            rejected = presenter.build_conversion_config(
                engine="chatterbox_gpu",
                voice_id="default",
                language="DE",
                speech_rate=1.0,
                output_format="wav",
                voice_catalog=[{"id": "default", "engine": "chatterbox_gpu", "language": "en"}],
                correlation_id="corr-cfg-int-ko",
                job_id="job-cfg-int-ko",
            )
            self.assertFalse(rejected.ok)

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            target_events = [event for event in events if event.get("stage") == "configuration"]
            self.assertEqual({event["event"] for event in target_events}, {"configuration.saved", "configuration.rejected"})

            for event in target_events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))
                self.assertIn(event["severity"], {"INFO", "ERROR"})

    def test_worker_persists_output_format_and_handoff_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")
            connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc-cfg-int-1",
                    "/tmp/source.txt",
                    "source",
                    "txt",
                    "2026-02-13T00:00:00+00:00",
                    "2026-02-13T00:00:00+00:00",
                ),
            )
            connection.commit()

            try:
                logger = JsonlLogger(events_path)
                repository = ConversionJobsRepository(connection)
                launcher = _LauncherProbe()
                worker = ConversionWorker(
                    recheck_callable=lambda: {"ok": True},
                    logger=logger,
                    conversion_jobs_repository=repository,
                    conversion_launcher=launcher,
                )

                result = worker.launch_conversion(
                    document_id="doc-cfg-int-1",
                    job_id="job-cfg-int-1",
                    correlation_id="corr-cfg-int-1",
                    conversion_config={
                        "engine": "kokoro_cpu",
                        "voice_id": "default",
                        "language": "EN",
                        "speech_rate": 0.9,
                        "output_format": "mp3",
                    },
                )
                self.assertTrue(result.ok)

                row = connection.execute(
                    "SELECT engine, voice, language, speech_rate, output_format FROM conversion_jobs WHERE id = ?",
                    ("job-cfg-int-1",),
                ).fetchone()
                self.assertIsNotNone(row)
                assert row is not None
                self.assertEqual(row[0], "kokoro_cpu")
                self.assertEqual(row[1], "default")
                self.assertEqual(row[2], "EN")
                self.assertEqual(row[4], "mp3")

                self.assertIsNotNone(launcher.config)
                with self.assertRaises(TypeError):
                    launcher.config["output_format"] = "wav"

                events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
                prepared = [event for event in events if event.get("event") == "conversion.launch_prepared"]
                self.assertEqual(len(prepared), 1)
                self.assertEqual(prepared[0]["stage"], "configuration")
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(prepared[0].keys()))
                self.assertTrue(is_valid_utc_iso_8601(prepared[0]["timestamp"]))
            finally:
                worker.shutdown()
                connection.close()

    def test_support_workflow_events_follow_schema_on_view_copy_and_retry_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"
            logger = JsonlLogger(events_path)
            presenter = ConversionPresenter(logger=logger)
            view = ConversionView(
                presenter=presenter,
                worker=_NoopWorker(),
                logger=logger,
            )

            view._on_conversion_error(
                {
                    "job_id": "job-diag-int-1",
                    "correlation_id": "corr-diag-int-1",
                    "error": {
                        "code": "tts_orchestration.chunk_failed_unrecoverable",
                        "message": "Chunk synthesis failed",
                        "details": {
                            "stage": "tts",
                            "engine": "chatterbox_gpu",
                            "chunk_index": 4,
                            "job_id": "job-diag-int-1",
                            "correlation_id": "corr-diag-int-1",
                        },
                        "retryable": False,
                    },
                }
            )
            view.open_support_details()
            view.copy_support_details()
            view.request_retry()

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            support_events = [event for event in events if event.get("stage") == "support_workflow"]
            self.assertEqual(
                {event["event"] for event in support_events},
                {
                    "support_workflow.viewed",
                    "support_workflow.copied",
                },
            )

            for event in support_events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertEqual(event["correlation_id"], "corr-diag-int-1")
                self.assertEqual(event["job_id"], "job-diag-int-1")
                self.assertEqual(event["stage"], "support_workflow")
                self.assertEqual(event["severity"], "INFO")
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))

    def test_support_workflow_retry_initiated_event_follows_schema_when_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"
            logger = JsonlLogger(events_path)
            presenter = ConversionPresenter(logger=logger)
            view = ConversionView(
                presenter=presenter,
                worker=_NoopWorker(),
                logger=logger,
            )

            view._on_conversion_error(
                {
                    "job_id": "job-diag-int-2",
                    "correlation_id": "corr-diag-int-2",
                    "error": {
                        "code": "extraction.no_text_content",
                        "message": "No text",
                        "details": {
                            "stage": "extraction",
                            "engine": "bootstrap",
                            "chunk_index": -1,
                            "job_id": "job-diag-int-2",
                            "correlation_id": "corr-diag-int-2",
                        },
                        "retryable": True,
                    },
                }
            )
            retry_allowed = view.request_retry()
            self.assertTrue(retry_allowed)

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            retry_events = [event for event in events if event.get("event") == "support_workflow.retry_initiated"]
            self.assertEqual(len(retry_events), 1)

            event = retry_events[0]
            self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
            self.assertEqual(event["stage"], "support_workflow")
            self.assertEqual(event["correlation_id"], "corr-diag-int-2")
            self.assertEqual(event["job_id"], "job-diag-int-2")
            self.assertEqual(event["severity"], "INFO")
            self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))

    def test_extraction_diagnostics_events_follow_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"
            logger = JsonlLogger(events_path)
            presenter = ConversionPresenter(logger=logger)

            # Simulate extraction failure
            extraction_failure = failure(
                code="extraction.no_text_content",
                message="No readable text found",
                details={
                    "source_format": "pdf",
                    "source_path": "/tmp/test.pdf",
                    "correlation_id": "corr-extract-int-1",
                    "job_id": "job-extract-int-1",
                },
                retryable=True,
            )

            result = presenter.map_extraction(extraction_failure)
            self.assertTrue(result.ok)
            assert result.data is not None
            self.assertEqual(result.data["status"], "failed")
            self.assertTrue(result.data["retry_enabled"])

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            diagnostics_events = [event for event in events if event.get("event") == "diagnostics.presented"]
            self.assertEqual(len(diagnostics_events), 1)

            event = diagnostics_events[0]
            self.assertEqual(event["stage"], "diagnostics_ui")
            self.assertEqual(event["correlation_id"], "corr-extract-int-1")
            self.assertEqual(event["job_id"], "job-extract-int-1")
            self.assertEqual(event["chunk_index"], -1)
            self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
            self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))
