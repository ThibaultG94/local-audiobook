from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adapters.persistence.sqlite.connection import create_connection
from src.adapters.persistence.sqlite.migration_runner import apply_migrations
from src.adapters.persistence.sqlite.repositories.documents_repository import DocumentsRepository
from src.adapters.extraction.epub_extractor import EpubExtractor
from src.adapters.extraction.pdf_extractor import PdfExtractor
from src.adapters.extraction.text_extractor import TextExtractor
from src.domain.services.import_service import ImportService
from src.ui.presenters.conversion_presenter import ConversionPresenter
from src.infrastructure.logging.event_schema import REQUIRED_EVENT_FIELDS, is_valid_utc_iso_8601
from src.infrastructure.logging.jsonl_logger import JsonlLogger


class TestImportFlowIntegration(unittest.TestCase):
    def test_successful_import_persists_document_with_snake_case_and_utc_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"
            source_file = tmp_path / "chapter.md"
            source_file.write_text("Hello import", encoding="utf-8")

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            repository = DocumentsRepository(connection)
            logger = JsonlLogger(events_path)
            service = ImportService(documents_repository=repository, logger=logger)

            result = service.import_document(str(source_file), correlation_id="corr-int-1")

            self.assertTrue(result.ok)
            self.assertIsNotNone(result.data)
            data = result.data or {}
            self.assertIn("source_path", data)
            self.assertIn("source_format", data)
            self.assertIn("created_at", data)
            self.assertIn("updated_at", data)
            self.assertEqual(data["source_format"], "md")
            self.assertTrue(is_valid_utc_iso_8601(data["created_at"]))
            self.assertTrue(is_valid_utc_iso_8601(data["updated_at"]))

            rows = connection.execute(
                "SELECT source_path, title, source_format, created_at, updated_at FROM documents WHERE id = ?",
                (data["id"],),
            ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], str(source_file.resolve()))
            self.assertEqual(rows[0][1], "chapter")
            self.assertEqual(rows[0][2], "md")
            self.assertTrue(is_valid_utc_iso_8601(rows[0][3]))
            self.assertTrue(is_valid_utc_iso_8601(rows[0][4]))

            connection.close()

    def test_epub_extraction_logs_required_fields_and_presenter_message_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            repository = DocumentsRepository(connection)
            logger = JsonlLogger(events_path)
            extractor = EpubExtractor(logger=logger)
            service = ImportService(documents_repository=repository, logger=logger, epub_extractor=extractor)

            document = {
                "id": "doc-epub-1",
                "source_path": str(tmp_path / "missing.epub"),
                "source_format": "epub",
            }
            extraction = service.extract_document(document=document, correlation_id="corr-epub-int", job_id="job-epub-1")

            self.assertFalse(extraction.ok)

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            extraction_events = [event for event in events if event["stage"] == "extraction" and event.get("engine") == "epub"]
            # Should have at least extraction.started and extraction.failed events
            self.assertGreaterEqual(len(extraction_events), 1)
            for event in extraction_events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))

            presenter = ConversionPresenter(logger=logger)
            presented = presenter.map_extraction(extraction)
            self.assertTrue(presented.ok)
            self.assertEqual(presented.data["status"], "failed")
            self.assertIn("EPUB", presented.data["message"])
            self.assertEqual(presented.data["severity"], "ERROR")

            all_events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            diagnostics_events = [event for event in all_events if event.get("event") == "diagnostics.presented"]
            self.assertEqual(len(diagnostics_events), 1)
            diagnostics_event = diagnostics_events[0]
            self.assertEqual(diagnostics_event["stage"], "diagnostics_ui")
            self.assertEqual(diagnostics_event["severity"], "ERROR")
            self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(diagnostics_event.keys()))
            self.assertTrue(is_valid_utc_iso_8601(diagnostics_event["timestamp"]))

            connection.close()

    def test_import_events_emit_required_schema_for_accepted_and_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"
            good_file = tmp_path / "book.txt"
            good_file.write_text("content", encoding="utf-8")

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            repository = DocumentsRepository(connection)
            logger = JsonlLogger(events_path)
            service = ImportService(documents_repository=repository, logger=logger)

            accepted = service.import_document(str(good_file), correlation_id="corr-accept")
            rejected = service.import_document(str(tmp_path / "bad.docx"), correlation_id="corr-reject")
            self.assertTrue(accepted.ok)
            self.assertFalse(rejected.ok)

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            event_names = [event["event"] for event in events]
            self.assertIn("import.accepted", event_names)
            self.assertIn("import.rejected", event_names)

            for event in events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))
                self.assertIn(event["severity"], {"INFO", "ERROR"})
                self.assertEqual(event["stage"], "import")

            connection.close()

    def test_pdf_extraction_logs_required_fields_and_presenter_message_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            repository = DocumentsRepository(connection)
            logger = JsonlLogger(events_path)
            extractor = PdfExtractor(logger=logger)
            service = ImportService(
                documents_repository=repository,
                logger=logger,
                epub_extractor=EpubExtractor(logger=logger),
                pdf_extractor=extractor,
            )

            document = {
                "id": "doc-pdf-1",
                "source_path": str(tmp_path / "missing.pdf"),
                "source_format": "pdf",
            }
            extraction = service.extract_document(document=document, correlation_id="corr-pdf-int", job_id="job-pdf-1")

            self.assertFalse(extraction.ok)

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            extraction_events = [event for event in events if event["stage"] == "extraction" and event.get("engine") == "pdf"]
            self.assertGreaterEqual(len(extraction_events), 1)
            for event in extraction_events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))

            presenter = ConversionPresenter(logger=logger)
            presented = presenter.map_extraction(extraction)
            self.assertTrue(presented.ok)
            self.assertEqual(presented.data["status"], "failed")
            self.assertIn("PDF", presented.data["message"])
            self.assertEqual(presented.data["severity"], "ERROR")

            connection.close()

    def test_text_extraction_logs_required_fields_and_presenter_message_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"
            source_file = tmp_path / "chapter.md"
            source_file.write_text("# Title\n\nHello world", encoding="utf-8")

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            repository = DocumentsRepository(connection)
            logger = JsonlLogger(events_path)
            service = ImportService(
                documents_repository=repository,
                logger=logger,
                text_extractor=TextExtractor(logger=logger),
            )

            document = {
                "id": "doc-text-1",
                "source_path": str(source_file),
                "source_format": "md",
            }
            extraction = service.extract_document(document=document, correlation_id="corr-text-int", job_id="job-text-1")

            self.assertTrue(extraction.ok)

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            extraction_events = [event for event in events if event["stage"] == "extraction" and event.get("engine") == "text"]
            self.assertGreaterEqual(len(extraction_events), 2)
            for event in extraction_events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))

            presenter = ConversionPresenter()
            presented = presenter.map_extraction(extraction)
            self.assertTrue(presented.ok)
            self.assertEqual(presented.data["status"], "succeeded")
            self.assertIn("text extracted successfully", presented.data["message"].lower())
            self.assertEqual(presented.data["severity"], "INFO")

            connection.close()

    def test_pdf_extraction_failure_emits_diagnostics_presented_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            repository = DocumentsRepository(connection)
            logger = JsonlLogger(events_path)
            extractor = PdfExtractor(logger=logger)
            service = ImportService(
                documents_repository=repository,
                logger=logger,
                pdf_extractor=extractor,
            )

            document = {
                "id": "doc-pdf-diag",
                "source_path": str(tmp_path / "missing.pdf"),
                "source_format": "pdf",
            }
            extraction = service.extract_document(document=document, correlation_id="corr-pdf-diag", job_id="job-pdf-diag")

            self.assertFalse(extraction.ok)

            presenter = ConversionPresenter(logger=logger)
            presented = presenter.map_extraction(extraction)
            self.assertTrue(presented.ok)
            self.assertEqual(presented.data["status"], "failed")

            all_events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            diagnostics_events = [event for event in all_events if event.get("event") == "diagnostics.presented"]
            self.assertEqual(len(diagnostics_events), 1)
            diagnostics_event = diagnostics_events[0]
            self.assertEqual(diagnostics_event["stage"], "diagnostics_ui")
            self.assertEqual(diagnostics_event["severity"], "ERROR")
            self.assertEqual(diagnostics_event["correlation_id"], "corr-pdf-diag")
            self.assertEqual(diagnostics_event["job_id"], "job-pdf-diag")
            self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(diagnostics_event.keys()))
            self.assertTrue(is_valid_utc_iso_8601(diagnostics_event["timestamp"]))

            connection.close()

    def test_text_extraction_failure_emits_diagnostics_presented_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            repository = DocumentsRepository(connection)
            logger = JsonlLogger(events_path)
            extractor = TextExtractor(logger=logger)
            service = ImportService(
                documents_repository=repository,
                logger=logger,
                text_extractor=extractor,
            )

            document = {
                "id": "doc-text-diag",
                "source_path": str(tmp_path / "missing.txt"),
                "source_format": "txt",
            }
            extraction = service.extract_document(document=document, correlation_id="corr-text-diag", job_id="job-text-diag")

            self.assertFalse(extraction.ok)

            presenter = ConversionPresenter(logger=logger)
            presented = presenter.map_extraction(extraction)
            self.assertTrue(presented.ok)
            self.assertEqual(presented.data["status"], "failed")

            all_events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            diagnostics_events = [event for event in all_events if event.get("event") == "diagnostics.presented"]
            self.assertEqual(len(diagnostics_events), 1)
            diagnostics_event = diagnostics_events[0]
            self.assertEqual(diagnostics_event["stage"], "diagnostics_ui")
            self.assertEqual(diagnostics_event["severity"], "ERROR")
            self.assertEqual(diagnostics_event["correlation_id"], "corr-text-diag")
            self.assertEqual(diagnostics_event["job_id"], "job-text-diag")
            self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(diagnostics_event.keys()))
            self.assertTrue(is_valid_utc_iso_8601(diagnostics_event["timestamp"]))

            connection.close()
