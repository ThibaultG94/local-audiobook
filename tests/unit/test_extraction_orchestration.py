from __future__ import annotations

import unittest

from contracts.result import failure, success
from domain.services.import_service import ImportService
from ui.presenters.conversion_presenter import ConversionPresenter


class _CapturingLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, str]] = []

    def emit(self, *, event: str, stage: str, severity: str = "INFO", correlation_id: str = "", **kwargs: object) -> None:
        self.events.append(
            {
                "event": event,
                "stage": stage,
                "severity": severity,
                "correlation_id": correlation_id,
                "engine": str(kwargs.get("engine", "")),
            }
        )


class _FakeDocumentsRepository:
    def create_document(self, record: dict[str, str]) -> dict[str, str]:
        return record


class _FakeEpubExtractor:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[dict[str, str]] = []

    def extract(self, source_path: str, *, correlation_id: str, job_id: str):
        self.calls.append({"source_path": source_path, "correlation_id": correlation_id, "job_id": job_id})
        if self.should_fail:
            return failure(
                code="extraction.malformed_package",
                message="Malformed EPUB package metadata",
                details={"source_path": source_path},
                retryable=False,
            )
        return success({"source_path": source_path, "source_format": "epub", "text": "Hello world", "sections": 1})


class _FakePdfExtractor:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[dict[str, str]] = []

    def extract(self, source_path: str, *, correlation_id: str, job_id: str):
        self.calls.append({"source_path": source_path, "correlation_id": correlation_id, "job_id": job_id})
        if self.should_fail:
            return failure(
                code="extraction.malformed_pdf",
                message="PDF extraction failed due to malformed or unsupported content",
                details={"source_path": source_path, "source_format": "pdf"},
                retryable=False,
            )
        return success(
            {
                "source_path": source_path,
                "source_format": "pdf",
                "text": "PDF text",
                "sections": 2,
                "pages": 2,
                "non_text_pages": 0,
            }
        )


class TestExtractionOrchestration(unittest.TestCase):
    def test_service_routes_epub_document_to_epub_extractor(self) -> None:
        logger = _CapturingLogger()
        extractor = _FakeEpubExtractor(should_fail=False)
        service = ImportService(documents_repository=_FakeDocumentsRepository(), logger=logger, epub_extractor=extractor)

        result = service.extract_document(
            document={"id": "doc-1", "source_path": "/tmp/book.epub", "source_format": "epub"},
            correlation_id="corr-extract-ok",
            job_id="job-1",
        )

        self.assertTrue(result.ok)
        self.assertEqual(len(extractor.calls), 1)
        self.assertEqual(extractor.calls[0]["source_path"], "/tmp/book.epub")

    def test_service_maps_unsupported_formats_to_normalized_error(self) -> None:
        logger = _CapturingLogger()
        extractor = _FakeEpubExtractor(should_fail=False)
        service = ImportService(documents_repository=_FakeDocumentsRepository(), logger=logger, epub_extractor=extractor)

        result = service.extract_document(
            document={"id": "doc-2", "source_path": "/tmp/book.docx", "source_format": "docx"},
            correlation_id="corr-extract-pdf",
            job_id="job-2",
        )

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "extraction.unsupported_source_format")

    def test_service_routes_pdf_document_to_pdf_extractor(self) -> None:
        logger = _CapturingLogger()
        epub_extractor = _FakeEpubExtractor(should_fail=False)
        pdf_extractor = _FakePdfExtractor(should_fail=False)
        service = ImportService(
            documents_repository=_FakeDocumentsRepository(),
            logger=logger,
            epub_extractor=epub_extractor,
            pdf_extractor=pdf_extractor,
        )

        result = service.extract_document(
            document={"id": "doc-3", "source_path": "/tmp/book.pdf", "source_format": "pdf"},
            correlation_id="corr-extract-pdf-ok",
            job_id="job-3",
        )

        self.assertTrue(result.ok)
        self.assertEqual(len(pdf_extractor.calls), 1)
        self.assertEqual(pdf_extractor.calls[0]["source_path"], "/tmp/book.pdf")

    def test_presenter_surfaces_actionable_english_feedback_for_pdf_failure(self) -> None:
        presenter = ConversionPresenter()
        extraction_result = failure(
            code="extraction.malformed_pdf",
            message="PDF extraction failed due to malformed or unsupported content",
            details={"source_path": "/tmp/broken.pdf", "source_format": "pdf"},
            retryable=False,
        )

        presented = presenter.map_extraction(extraction_result)

        self.assertTrue(presented.ok)
        self.assertIsNotNone(presented.data)
        self.assertEqual(presented.data["status"], "failed")
        self.assertEqual(
            presented.data["message"],
            "PDF structure appears invalid. Please provide a well-formed file.",
        )
        self.assertEqual(presented.data["severity"], "ERROR")

    def test_presenter_surfaces_actionable_english_feedback_for_failure(self) -> None:
        presenter = ConversionPresenter()
        extraction_result = failure(
            code="extraction.no_text_content",
            message="No readable text content found in EPUB",
            details={"source_path": "/tmp/empty.epub", "source_format": "epub"},
            retryable=False,
        )

        presented = presenter.map_extraction(extraction_result)

        self.assertTrue(presented.ok)
        self.assertIsNotNone(presented.data)
        self.assertEqual(presented.data["status"], "failed")
        self.assertEqual(presented.data["message"], "Unable to extract readable text from EPUB. Please verify the file contents.")
        self.assertEqual(presented.data["severity"], "ERROR")
