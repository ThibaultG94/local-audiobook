from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapters.persistence.sqlite.connection import create_connection
from adapters.persistence.sqlite.migration_runner import apply_migrations
from adapters.persistence.sqlite.repositories.documents_repository import DocumentsRepository
from domain.services.import_service import ImportService
from infrastructure.logging.event_schema import REQUIRED_EVENT_FIELDS, is_valid_utc_iso_8601
from infrastructure.logging.jsonl_logger import JsonlLogger


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
                "SELECT source_path, title, created_at, updated_at FROM documents WHERE id = ?",
                (data["id"],),
            ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], str(source_file))
            self.assertEqual(rows[0][1], "chapter")
            self.assertTrue(is_valid_utc_iso_8601(rows[0][2]))
            self.assertTrue(is_valid_utc_iso_8601(rows[0][3]))

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

