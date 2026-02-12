from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.extraction.pdf_extractor import PdfExtractor


class _FakePage:
    def __init__(self, text: str | None) -> None:
        self._text = text

    def extract_text(self) -> str | None:
        return self._text


class _FakePdfReader:
    def __init__(self, _source_path: str) -> None:
        self.pages = [
            _FakePage("  Page 1   text\n\nLine two  "),
            _FakePage(None),
            _FakePage("Page 3\ttext"),
        ]


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


class TestPdfExtractor(unittest.TestCase):
    def test_extract_keeps_deterministic_page_order_and_tracks_non_text_pages(self) -> None:
        import adapters.extraction.pdf_extractor as pdf_module

        logger = _CapturingLogger()
        extractor = PdfExtractor(logger=logger)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"fake pdf")
            tmp_path = tmp.name

        try:
            original_reader = pdf_module.PdfReader
            pdf_module.PdfReader = _FakePdfReader  # type: ignore[assignment]

            result = extractor.extract(tmp_path, correlation_id="corr-pdf-1", job_id="job-pdf-1")
        finally:
            pdf_module.PdfReader = original_reader  # type: ignore[assignment]
            Path(tmp_path).unlink(missing_ok=True)

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.data)
        data = result.data or {}
        self.assertEqual(data["text"], "Page 1 text\nLine two\nPage 3 text")
        self.assertEqual(data["source_format"], "pdf")
        self.assertEqual(data["pages"], 3)
        self.assertEqual(data["non_text_pages"], 1)
        self.assertEqual(
            data["page_diagnostics"],
            [
                {"page_index": 0, "has_text": True, "chars": 20, "words": 5},
                {"page_index": 1, "has_text": False, "chars": 0, "words": 0},
                {"page_index": 2, "has_text": True, "chars": 11, "words": 3},
            ],
        )

        extraction_events = [event for event in logger.events if event.get("stage") == "extraction" and event.get("engine") == "pdf"]
        self.assertGreaterEqual(len(extraction_events), 2)

    def test_extract_returns_normalized_error_when_no_readable_text_exists(self) -> None:
        import adapters.extraction.pdf_extractor as pdf_module

        class _AllEmptyReader:
            def __init__(self, _source_path: str) -> None:
                self.pages = [_FakePage("   "), _FakePage(None)]

        extractor = PdfExtractor()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"fake pdf")
            tmp_path = tmp.name

        try:
            original_reader = pdf_module.PdfReader
            pdf_module.PdfReader = _AllEmptyReader  # type: ignore[assignment]

            result = extractor.extract(tmp_path, correlation_id="corr-pdf-2", job_id="job-pdf-2")
        finally:
            pdf_module.PdfReader = original_reader  # type: ignore[assignment]
            Path(tmp_path).unlink(missing_ok=True)

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "extraction.no_text_content")
        self.assertIn("source_path", result.error.details)
        self.assertEqual(result.error.details.get("pages"), 2)
        self.assertEqual(result.error.details.get("non_text_pages"), 2)

    def test_extract_returns_error_for_file_too_large(self) -> None:
        import adapters.extraction.pdf_extractor as pdf_module

        extractor = PdfExtractor()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            # Create a file larger than MAX_FILE_SIZE_BYTES
            tmp.write(b"x" * (501 * 1024 * 1024))  # 501MB
            tmp_path = tmp.name

        try:
            result = extractor.extract(tmp_path, correlation_id="corr-pdf-large", job_id="job-pdf-large")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "extraction.file_too_large")
        self.assertFalse(result.error.retryable)

    def test_extract_returns_error_for_missing_file(self) -> None:
        extractor = PdfExtractor()
        result = extractor.extract("/nonexistent/file.pdf", correlation_id="corr-pdf-missing", job_id="job-pdf-missing")

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "extraction.unreadable_source")
        self.assertTrue(result.error.retryable)

    def test_extract_returns_error_for_malformed_pdf(self) -> None:
        import adapters.extraction.pdf_extractor as pdf_module
        from PyPDF2.errors import PdfReadError

        class _MalformedPdfReader:
            def __init__(self, _source_path: str) -> None:
                raise PdfReadError("Invalid PDF structure")

        extractor = PdfExtractor()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"not a real pdf")
            tmp_path = tmp.name

        try:
            original_reader = pdf_module.PdfReader
            pdf_module.PdfReader = _MalformedPdfReader  # type: ignore[assignment]

            result = extractor.extract(tmp_path, correlation_id="corr-pdf-malformed", job_id="job-pdf-malformed")
        finally:
            pdf_module.PdfReader = original_reader  # type: ignore[assignment]
            Path(tmp_path).unlink(missing_ok=True)

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "extraction.malformed_pdf")
        self.assertFalse(result.error.retryable)

    def test_extract_handles_unicode_content(self) -> None:
        import adapters.extraction.pdf_extractor as pdf_module

        class _UnicodePdfReader:
            def __init__(self, _source_path: str) -> None:
                self.pages = [
                    _FakePage("Français: café, naïve, œuvre"),
                    _FakePage("中文: 你好世界"),
                    _FakePage("Emoji: 🔥 💻 ✅"),
                ]

        logger = _CapturingLogger()
        extractor = PdfExtractor(logger=logger)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"fake pdf")
            tmp_path = tmp.name

        try:
            original_reader = pdf_module.PdfReader
            pdf_module.PdfReader = _UnicodePdfReader  # type: ignore[assignment]

            result = extractor.extract(tmp_path, correlation_id="corr-pdf-unicode", job_id="job-pdf-unicode")
        finally:
            pdf_module.PdfReader = original_reader  # type: ignore[assignment]
            Path(tmp_path).unlink(missing_ok=True)

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.data)
        data = result.data or {}
        self.assertIn("café", data["text"])
        self.assertIn("你好世界", data["text"])
        self.assertIn("🔥", data["text"])

