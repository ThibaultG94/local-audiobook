from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.adapters.extraction.text_extractor import TextExtractor


class _CapturingLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: object) -> None:
        payload = {
            "event": event,
            "stage": stage,
            "severity": severity,
            "correlation_id": correlation_id,
        }
        payload.update(kwargs)
        self.events.append(payload)


class TestTextExtractor(unittest.TestCase):
    def test_extract_txt_normalizes_line_breaks_and_whitespace(self) -> None:
        logger = _CapturingLogger()
        extractor = TextExtractor(logger=logger)

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"  Hello   world\r\n\r\nLine\t two  \n")
            tmp_path = tmp.name

        try:
            result = extractor.extract(tmp_path, correlation_id="corr-text-1", job_id="job-text-1")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.data)
        data = result.data or {}
        self.assertEqual(data["source_format"], "txt")
        self.assertEqual(data["text"], "Hello world\nLine two")
        self.assertEqual(data["sections"], 2)
        self.assertEqual(data["text_length"], len("Hello world\nLine two"))

    def test_extract_md_cleans_markdown_markers_for_reading(self) -> None:
        extractor = TextExtractor()

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
            tmp.write(
                (
                    b"# Chapter 1\n\n"
                    b"- First point\n"
                    b"- Second point\n\n"
                    b"Read [the guide](https://example.com).\n\n"
                    b"```\nprint('debug')\n```\n"
                )
            )
            tmp_path = tmp.name

        try:
            result = extractor.extract(tmp_path, correlation_id="corr-text-2", job_id="job-text-2")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.data)
        text = (result.data or {}).get("text", "")
        self.assertIn("Chapter 1", text)
        self.assertIn("First point", text)
        self.assertIn("Read the guide.", text)
        self.assertNotIn("```", text)
        self.assertNotIn("[", text)

    def test_extract_unreadable_bytes_returns_normalized_error(self) -> None:
        extractor = TextExtractor()

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"\xff\xfe\xfd\xff\xfe\xfd")
            tmp_path = tmp.name

        try:
            result = extractor.extract(tmp_path, correlation_id="corr-text-3", job_id="job-text-3")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "extraction.encoding_invalid")
        self.assertIn("source_path", result.error.details)
        self.assertEqual(result.error.details.get("source_format"), "txt")

    def test_extract_emits_text_engine_extraction_events_with_diagnostics(self) -> None:
        logger = _CapturingLogger()
        extractor = TextExtractor(logger=logger)

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
            tmp.write(b"# Title\n\nSimple content")
            tmp_path = tmp.name

        try:
            result = extractor.extract(tmp_path, correlation_id="corr-text-4", job_id="job-text-4")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self.assertTrue(result.ok)
        extraction_events = [event for event in logger.events if event.get("stage") == "extraction" and event.get("engine") == "text"]
        self.assertGreaterEqual(len(extraction_events), 2)
        self.assertEqual(extraction_events[0]["event"], "extraction.started")
        self.assertEqual(extraction_events[-1]["event"], "extraction.succeeded")
        self.assertIn("text_length", extraction_events[-1].get("extra", {}))

    def test_extract_rejects_file_too_large(self) -> None:
        extractor = TextExtractor()

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"x" * (501 * 1024 * 1024))
            tmp_path = tmp.name

        try:
            result = extractor.extract(tmp_path, correlation_id="corr-text-5", job_id="job-text-5")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "extraction.file_too_large")
        self.assertFalse(result.error.retryable)

    def test_extract_rejects_file_with_only_whitespace(self) -> None:
        extractor = TextExtractor()

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"   \n\n\t\t  \r\n   ")
            tmp_path = tmp.name

        try:
            result = extractor.extract(tmp_path, correlation_id="corr-text-6", job_id="job-text-6")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "extraction.no_text_content")
        self.assertFalse(result.error.retryable)

    def test_extract_rejects_empty_source_path(self) -> None:
        extractor = TextExtractor()
        result = extractor.extract("", correlation_id="corr-text-7", job_id="job-text-7")

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "extraction.invalid_source_path")
        self.assertFalse(result.error.retryable)
