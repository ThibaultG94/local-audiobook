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

            artifact_path = Path("runtime/library/audio/lib-int-1-delete-test.mp3")
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_bytes(b"int")

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
                    "audio_path": str(artifact_path),
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

            selection_result = service.prepare_item_for_conversion(
                correlation_id="corr-lib-select-int",
                item_id="lib-int-1",
            )
            self.assertTrue(selection_result.ok)

            browse_result = service.browse_library(correlation_id="corr-lib-browse-int")
            self.assertTrue(browse_result.ok)
            assert browse_result.data is not None
            self.assertEqual(browse_result.data["items"][0]["conversion_status"], "ready")

            reopen_result = service.reopen_library_item(correlation_id="corr-lib-open-int", item_id="lib-int-1")
            self.assertTrue(reopen_result.ok)

            fail_result = service.reopen_library_item(correlation_id="corr-lib-open-fail-int", item_id="missing-item")
            self.assertFalse(fail_result.ok)

            delete_result = service.delete_library_item(correlation_id="corr-lib-delete-int", item_id="lib-int-1")
            self.assertTrue(delete_result.ok)

            browse_after_delete = service.browse_library(correlation_id="corr-lib-browse-after-delete-int")
            self.assertTrue(browse_after_delete.ok)
            assert browse_after_delete.data is not None
            self.assertEqual(browse_after_delete.data["count"], 0)

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            browse_events = [event for event in events if event.get("stage") == "library_browse"]
            management_events = [event for event in events if event.get("stage") == "library_management"]

            self.assertGreaterEqual(len(browse_events), 3)
            self.assertIn("library.list_loaded", [event["event"] for event in browse_events])
            self.assertIn("library.item_opened", [event["event"] for event in browse_events])
            self.assertIn("library.item_open_failed", [event["event"] for event in browse_events])

            self.assertGreaterEqual(len(management_events), 2)
            self.assertIn("library.item_prepared_for_convert", [event["event"] for event in management_events])
            self.assertIn("library.item_deleted", [event["event"] for event in management_events])

            combined_events = browse_events + management_events

            for event in combined_events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))

            connection.close()
