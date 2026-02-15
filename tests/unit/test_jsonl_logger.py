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

    def test_emit_preserves_existing_content_in_append_mode(self) -> None:
        """Verify append-only behavior: new writes preserve existing file content."""
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "events.jsonl"
            
            # Write initial content
            logger1 = JsonlLogger(events_file)
            logger1.emit(
                event="initial.event",
                stage="test",
                correlation_id="corr-1",
                job_id="job-1",
                chunk_index=0,
                engine="test",
            )
            
            # Verify initial content
            lines_after_first = events_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines_after_first), 1)
            
            # Create new logger instance and append more content
            logger2 = JsonlLogger(events_file)
            logger2.emit(
                event="second.event",
                stage="test",
                correlation_id="corr-2",
                job_id="job-2",
                chunk_index=1,
                engine="test",
            )
            logger2.emit(
                event="third.event",
                stage="test",
                correlation_id="corr-3",
                job_id="job-3",
                chunk_index=2,
                engine="test",
            )
            
            # Verify all content is preserved
            lines_final = events_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines_final), 3)
            
            events = [json.loads(line) for line in lines_final]
            self.assertEqual(events[0]["event"], "initial.event")
            self.assertEqual(events[1]["event"], "second.event")
            self.assertEqual(events[2]["event"], "third.event")

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

