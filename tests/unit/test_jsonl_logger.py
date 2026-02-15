from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.logging.jsonl_logger import JsonlLogger, JsonlLoggingError


class TestJsonlLogger(unittest.TestCase):
    def test_emit_appends_one_json_object_per_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "events.jsonl"
            logger = JsonlLogger(events_file)

            logger.emit(
                event="bootstrap.started",
                stage="bootstrap",
                correlation_id="corr-a",
                job_id="job-a",
                chunk_index=-1,
                engine="bootstrap",
            )
            logger.emit(
                event="bootstrap.completed",
                stage="bootstrap",
                correlation_id="corr-a",
                job_id="job-a",
                chunk_index=-1,
                engine="bootstrap",
            )

            lines = events_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)

            first = json.loads(lines[0])
            second = json.loads(lines[1])
            self.assertEqual(first["event"], "bootstrap.started")
            self.assertEqual(second["event"], "bootstrap.completed")

    def test_emit_rejects_non_conformant_event_name_with_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "events.jsonl"
            logger = JsonlLogger(events_file)

            with self.assertRaises(JsonlLoggingError) as ctx:
                logger.emit(event="invalid", stage="bootstrap")

            error = ctx.exception
            self.assertEqual(error.code, "logging.invalid_event_payload")
            self.assertFalse(error.retryable)
            self.assertIn("domain.action", error.details["error"])

    def test_emit_surfaces_write_failures_as_structured_local_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "events_as_directory"
            log_dir.mkdir()
            logger = JsonlLogger(log_dir)

            with self.assertRaises(JsonlLoggingError) as ctx:
                logger.emit(event="bootstrap.started", stage="bootstrap")

            error = ctx.exception
            self.assertEqual(error.code, "logging.write_failed")
            self.assertTrue(error.retryable)
            self.assertEqual(error.details["path"], str(log_dir))

