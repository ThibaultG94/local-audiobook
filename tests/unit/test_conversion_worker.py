from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from contracts.result import success
from src.adapters.persistence.sqlite.connection import create_connection
from src.adapters.persistence.sqlite.migration_runner import apply_migrations
from src.adapters.persistence.sqlite.repositories.conversion_jobs_repository import ConversionJobsRepository
from ui.workers.conversion_worker import ConversionWorker


class _FakeLogger:
    def __init__(self) -> None:
        self.events: list[str] = []

    def emit(self, *, event: str, stage: str, **_: object) -> None:
        self.events.append(f"{stage}:{event}")


class _FakeLauncher:
    def __init__(self) -> None:
        self.received_config = None
        self.progress_events: list[dict[str, object]] = []

    def launch_conversion(self, *, job_id: str, correlation_id: str, conversion_config, progress_callback=None):
        self.received_config = conversion_config
        if progress_callback is not None:
            progress_callback({"chunk_index": 0, "succeeded_chunks": 1, "total_chunks": 2, "progress_percent": 50})
            progress_callback({"chunk_index": 1, "succeeded_chunks": 2, "total_chunks": 2, "progress_percent": 100})
        return success({"job_id": job_id, "correlation_id": correlation_id})


class _FailingLauncher:
    def launch_conversion(self, *, job_id: str, correlation_id: str, conversion_config, progress_callback=None):
        raise RuntimeError("launcher exploded")


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

    def test_launch_conversion_persists_settings_and_handoff_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")
            connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc-worker-1",
                    "/tmp/source.txt",
                    "source",
                    "txt",
                    "2026-02-13T00:00:00+00:00",
                    "2026-02-13T00:00:00+00:00",
                ),
            )
            connection.commit()

            logger = _FakeLogger()
            launcher = _FakeLauncher()
            repository = ConversionJobsRepository(connection)

            worker = ConversionWorker(
                recheck_callable=lambda: success({"status": "ready", "engines": [], "remediation": []}),
                logger=logger,
                conversion_jobs_repository=repository,
                conversion_launcher=launcher,
            )
            try:
                result = worker.launch_conversion(
                    document_id="doc-worker-1",
                    job_id="job-worker-1",
                    correlation_id="corr-worker-1",
                    conversion_config={
                        "engine": "chatterbox_gpu",
                        "voice_id": "default",
                        "language": "FR",
                        "speech_rate": 1.1,
                        "output_format": "wav",
                    },
                )

                self.assertTrue(result.ok)
                job = repository.get_job_by_id(job_id="job-worker-1")
                self.assertIsNotNone(job)
                assert job is not None
                self.assertEqual(job["output_format"], "wav")
                self.assertEqual(job["engine"], "chatterbox_gpu")
                self.assertEqual(job["voice"], "default")
                self.assertEqual(job["language"], "FR")

                self.assertIsNotNone(launcher.received_config)
                with self.assertRaises(TypeError):
                    launcher.received_config["output_format"] = "mp3"
            finally:
                worker.shutdown()
                connection.close()

    def test_launch_conversion_rejects_missing_configuration_key(self) -> None:
        worker = ConversionWorker(
            recheck_callable=lambda: success({"status": "ready", "engines": [], "remediation": []}),
            logger=_FakeLogger(),
        )
        try:
            result = worker.launch_conversion(
                document_id="doc-missing",
                job_id="job-missing",
                correlation_id="corr-missing",
                conversion_config={
                    "engine": "chatterbox_gpu",
                    "voice_id": "default",
                    "language": "FR",
                    "speech_rate": 1.0,
                },
            )
            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "configuration.invalid_payload")
            self.assertIn("output_format", result.error.details["missing_keys"])
        finally:
            worker.shutdown()

    def test_execute_conversion_async_emits_running_progress_and_completed_states(self) -> None:
        logger = _FakeLogger()
        launcher = _FakeLauncher()
        worker = ConversionWorker(
            recheck_callable=lambda: success({"status": "ready", "engines": [], "remediation": []}),
            logger=logger,
            conversion_launcher=launcher,
        )
        states: list[dict[str, object]] = []
        progresses: list[dict[str, object]] = []
        errors: list[dict[str, object]] = []

        worker.on_conversion_state_changed(lambda payload: states.append(payload))
        worker.on_conversion_progressed(lambda payload: progresses.append(payload))
        worker.on_conversion_failed(lambda payload: errors.append(payload))
        try:
            future = worker.execute_conversion_async(
                document_id="doc-1",
                job_id="job-async-1",
                correlation_id="corr-async-1",
                conversion_config={
                    "engine": "chatterbox_gpu",
                    "voice_id": "default",
                    "language": "FR",
                    "speech_rate": 1.0,
                    "output_format": "wav",
                },
            )
            result = future.result(timeout=2)
            self.assertTrue(result.ok)

            self.assertEqual(states[0]["status"], "running")
            self.assertEqual(states[-1]["status"], "completed")
            self.assertEqual(states[-1]["progress_percent"], 100)

            self.assertEqual([item["progress_percent"] for item in progresses], [50, 100])
            self.assertEqual(errors, [])

            self.assertIn("worker_execution:worker_execution.started", logger.events)
            self.assertIn("worker_execution:worker_execution.progressed", logger.events)
            self.assertIn("worker_execution:worker_execution.completed", logger.events)
            self.assertEqual(worker.active_conversion_count, 0)
        finally:
            worker.shutdown()

    def test_execute_conversion_async_normalizes_unhandled_launcher_exception(self) -> None:
        logger = _FakeLogger()
        worker = ConversionWorker(
            recheck_callable=lambda: success({"status": "ready", "engines": [], "remediation": []}),
            logger=logger,
            conversion_launcher=_FailingLauncher(),
        )
        errors: list[dict[str, object]] = []
        worker.on_conversion_failed(lambda payload: errors.append(payload))
        try:
            future = worker.execute_conversion_async(
                document_id="doc-2",
                job_id="job-async-2",
                correlation_id="corr-async-2",
                conversion_config={
                    "engine": "kokoro_cpu",
                    "voice_id": "default",
                    "language": "EN",
                    "speech_rate": 1.0,
                    "output_format": "mp3",
                },
            )
            result = future.result(timeout=2)
            self.assertFalse(result.ok)
            assert result.error is not None
            self.assertEqual(result.error.code, "worker_execution.unhandled_exception")
            self.assertTrue(errors)
            self.assertEqual(errors[0]["error"]["code"], "worker_execution.unhandled_exception")
            self.assertIn("worker_execution:worker_execution.failed", logger.events)
        finally:
            worker.shutdown()
