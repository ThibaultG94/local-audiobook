from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.adapters.persistence.sqlite.connection import create_connection
from src.adapters.persistence.sqlite.migration_runner import apply_migrations
from src.adapters.persistence.sqlite.repositories.library_items_repository import LibraryItemsRepository


class TestLibraryItemsRepository(unittest.TestCase):
    def test_create_item_persists_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "runtime" / "local_audiobook.db"
            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            repository = LibraryItemsRepository(connection)
            connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc-lib-1",
                    "/tmp/source.epub",
                    "Mon livre",
                    "epub",
                    "2026-02-14T00:00:00+00:00",
                    "2026-02-14T00:00:00+00:00",
                ),
            )
            connection.commit()
            payload = {
                "job_id": "job-lib-1",
                "document_id": "doc-lib-1",
                "title": "Mon livre",
                "source_path": "/tmp/source.epub",
                "audio_path": "runtime/library/audio/job-lib-1.mp3",
                "format": "mp3",
                "source_format": "epub",
                "engine": "chatterbox_gpu",
                "voice": "default",
                "language": "fr",
                "duration_seconds": 12.5,
                "byte_size": 2048,
                "created_at": "2026-02-14T00:00:00+00:00",
            }

            created = repository.create_item(payload)

            self.assertEqual(created["job_id"], "job-lib-1")
            self.assertEqual(created["title"], "Mon livre")
            self.assertEqual(created["source_path"], "/tmp/source.epub")
            self.assertEqual(created["audio_path"], "runtime/library/audio/job-lib-1.mp3")
            self.assertEqual(created["format"], "mp3")
            self.assertEqual(created["engine"], "chatterbox_gpu")
            self.assertEqual(created["voice"], "default")
            self.assertEqual(created["language"], "fr")
            self.assertEqual(created["duration_seconds"], 12.5)
            self.assertEqual(created["byte_size"], 2048)
            self.assertEqual(created["created_at"], "2026-02-14T00:00:00+00:00")

            row = connection.execute(
                "SELECT job_id, source_path, format, byte_size FROM library_items WHERE id = ?",
                (created["id"],),
            ).fetchone()
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row[0], "job-lib-1")
            self.assertEqual(row[1], "/tmp/source.epub")
            self.assertEqual(row[2], "mp3")
            self.assertEqual(row[3], 2048)

            connection.close()

    def test_create_item_rolls_back_transaction_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "runtime" / "local_audiobook.db"
            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            repository = LibraryItemsRepository(connection)
            connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc-lib-rollback",
                    "/tmp/source.pdf",
                    "Livre rollback",
                    "pdf",
                    "2026-02-14T00:00:00+00:00",
                    "2026-02-14T00:00:00+00:00",
                ),
            )
            connection.commit()
            payload = {
                "job_id": "job-lib-rollback",
                "document_id": "doc-lib-rollback",
                "title": "Livre rollback",
                "source_path": "/tmp/source.pdf",
                "audio_path": "runtime/library/audio/job-lib-rollback.wav",
                "format": "wav",
                "source_format": "pdf",
                "engine": "kokoro_cpu",
                "voice": "v1",
                "language": "fr",
                "duration_seconds": 1.0,
                "byte_size": 256,
                "created_at": "2026-02-14T00:00:00+00:00",
            }

            connection.execute("DROP TABLE library_items")
            connection.commit()

            with self.assertRaises(sqlite3.Error):
                repository.create_item(payload)

            exists = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'library_items'"
            ).fetchone()
            self.assertIsNone(exists)
            connection.close()
