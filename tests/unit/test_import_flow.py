from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from contracts.result import Result
from domain.services.import_service import ImportService
from ui.views.import_view import ImportView


class _InMemoryDocumentsRepository:
    def __init__(self) -> None:
        self.created: list[dict[str, str]] = []

    def create_document(self, record: dict[str, str]) -> dict[str, str]:
        self.created.append(record)
        return record


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
            }
        )


class TestImportFlowUnit(unittest.TestCase):
    def test_view_rejects_unsupported_extension_with_normalized_error(self) -> None:
        service = ImportService(documents_repository=_InMemoryDocumentsRepository(), logger=_CapturingLogger())
        view = ImportView(import_service=service)

        result = view.submit_file("/tmp/input.docx")

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "import.unsupported_extension")
        self.assertEqual(result.error.details["extension"], ".docx")

    def test_view_accepts_uppercase_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "book.EPUB"
            file_path.write_text("content", encoding="utf-8")

            repository = _InMemoryDocumentsRepository()
            logger = _CapturingLogger()
            service = ImportService(documents_repository=repository, logger=logger)
            view = ImportView(import_service=service)

            result = view.submit_file(str(file_path))

            self.assertTrue(result.ok)
            self.assertEqual(repository.created[0]["source_format"], "epub")

    def test_service_returns_error_when_file_missing(self) -> None:
        service = ImportService(documents_repository=_InMemoryDocumentsRepository(), logger=_CapturingLogger())

        result = service.import_document("/tmp/does-not-exist.md")

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "import.file_missing")

    def test_service_returns_error_when_file_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory_path = Path(tmp) / "folder_as_file.md"
            directory_path.mkdir()

            service = ImportService(documents_repository=_InMemoryDocumentsRepository(), logger=_CapturingLogger())
            result = service.import_document(str(directory_path))

            self.assertFalse(result.ok)
            self.assertIsNotNone(result.error)
            self.assertEqual(result.error.code, "import.file_unreadable")

    def test_service_returns_error_when_file_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty_file = Path(tmp) / "empty.md"
            empty_file.write_text("", encoding="utf-8")

            service = ImportService(documents_repository=_InMemoryDocumentsRepository(), logger=_CapturingLogger())
            result = service.import_document(str(empty_file))

            self.assertFalse(result.ok)
            self.assertIsNotNone(result.error)
            self.assertEqual(result.error.code, "import.file_empty")

    def test_service_success_returns_normalized_result_and_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "book.MD"
            file_path.write_text("hello", encoding="utf-8")

            repository = _InMemoryDocumentsRepository()
            logger = _CapturingLogger()
            service = ImportService(documents_repository=repository, logger=logger)
            result: Result[dict[str, str]] = service.import_document(str(file_path), correlation_id="corr-123")

            self.assertTrue(result.ok)
            self.assertIsNone(result.error)
            self.assertIsNotNone(result.data)
            self.assertEqual(len(repository.created), 1)
            self.assertEqual(repository.created[0]["source_path"], str(file_path.resolve()))
            self.assertEqual(repository.created[0]["title"], "book")
            self.assertEqual(repository.created[0]["source_format"], "md")
            self.assertTrue(any(item["event"] == "import.accepted" for item in logger.events))

    def test_service_auto_generates_correlation_id_when_none_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "test.txt"
            file_path.write_text("content", encoding="utf-8")

            logger = _CapturingLogger()
            service = ImportService(documents_repository=_InMemoryDocumentsRepository(), logger=logger)
            result = service.import_document(str(file_path), correlation_id=None)

            self.assertTrue(result.ok)
            self.assertEqual(len(logger.events), 1)
            self.assertNotEqual(logger.events[0]["correlation_id"], "")
            self.assertEqual(len(logger.events[0]["correlation_id"]), 36)  # UUID format

    def test_service_rejects_special_files(self) -> None:
        service = ImportService(documents_repository=_InMemoryDocumentsRepository(), logger=_CapturingLogger())
        result = service.import_document("/dev/null")

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "import.file_unreadable")
        self.assertIn("special", result.error.details.get("file_type", ""))

