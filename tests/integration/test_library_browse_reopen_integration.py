from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adapters.persistence.sqlite.connection import create_connection
from src.adapters.persistence.sqlite.migration_runner import apply_migrations
from src.adapters.persistence.sqlite.repositories.library_items_repository import LibraryItemsRepository
from src.domain.services.library_service import LibraryService
from src.infrastructure.logging.event_schema import REQUIRED_EVENT_FIELDS, is_valid_utc_iso_8601
from src.infrastructure.logging.jsonl_logger import JsonlLogger


class TestLibraryBrowseReopenIntegration(unittest.TestCase):
    def test_browse_and_reopen_emit_library_browse_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            repository = LibraryItemsRepository(connection)
            logger = JsonlLogger(events_path)
            service = LibraryService(library_items_repository=repository, logger=logger)

            connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc-lib-int-1",
                    "/tmp/source.epub",
                    "Integration Livre",
                    "epub",
                    "2026-02-14T00:00:00+00:00",
                    "2026-02-14T00:00:00+00:00",
                ),
            )
            connection.commit()

            repository.create_item(
                {
                    "id": "lib-int-1",
                    "job_id": "job-lib-int-1",
                    "document_id": "doc-lib-int-1",
                    "title": "Integration Livre",
                    "source_path": "/tmp/source.epub",
                    "audio_path": "runtime/library/audio/.gitkeep",
                    "format": "mp3",
                    "source_format": "epub",
                    "engine": "chatterbox_gpu",
                    "voice": "default",
                    "language": "fr",
                    "duration_seconds": 2.5,
                    "byte_size": 100,
                    "created_at": "2026-02-14T01:00:00+00:00",
                }
            )

            browse_result = service.browse_library(correlation_id="corr-lib-browse-int")
            self.assertTrue(browse_result.ok)

            reopen_result = service.reopen_library_item(correlation_id="corr-lib-open-int", item_id="lib-int-1")
            self.assertTrue(reopen_result.ok)

            fail_result = service.reopen_library_item(correlation_id="corr-lib-open-fail-int", item_id="missing-item")
            self.assertFalse(fail_result.ok)

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            browse_events = [event for event in events if event.get("stage") == "library_browse"]

            self.assertGreaterEqual(len(browse_events), 3)
            self.assertIn("library.list_loaded", [event["event"] for event in browse_events])
            self.assertIn("library.item_opened", [event["event"] for event in browse_events])
            self.assertIn("library.item_open_failed", [event["event"] for event in browse_events])

            for event in browse_events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))

            connection.close()

