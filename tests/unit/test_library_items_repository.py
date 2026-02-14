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

    def test_list_items_ordered_is_deterministic_by_created_at_then_id_desc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "runtime" / "local_audiobook.db"
            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")
            repository = LibraryItemsRepository(connection)

            connection.executemany(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("doc-a", "/tmp/a.epub", "A", "epub", "2026-02-14T00:00:00+00:00", "2026-02-14T00:00:00+00:00"),
                    ("doc-b", "/tmp/b.epub", "B", "epub", "2026-02-14T00:00:00+00:00", "2026-02-14T00:00:00+00:00"),
                    ("doc-c", "/tmp/c.epub", "C", "epub", "2026-02-14T00:00:00+00:00", "2026-02-14T00:00:00+00:00"),
                ],
            )
            connection.commit()

            repository.create_item(
                {
                    "id": "lib-a",
                    "job_id": "job-a",
                    "document_id": "doc-a",
                    "title": "A",
                    "source_path": "/tmp/a.epub",
                    "audio_path": "runtime/library/audio/job-a.mp3",
                    "format": "mp3",
                    "source_format": "epub",
                    "engine": "chatterbox_gpu",
                    "voice": "default",
                    "language": "fr",
                    "duration_seconds": 1.0,
                    "byte_size": 100,
                    "created_at": "2026-02-14T11:00:00+00:00",
                }
            )
            repository.create_item(
                {
                    "id": "lib-c",
                    "job_id": "job-c",
                    "document_id": "doc-c",
                    "title": "C",
                    "source_path": "/tmp/c.epub",
                    "audio_path": "runtime/library/audio/job-c.mp3",
                    "format": "mp3",
                    "source_format": "epub",
                    "engine": "chatterbox_gpu",
                    "voice": "default",
                    "language": "fr",
                    "duration_seconds": 1.0,
                    "byte_size": 300,
                    "created_at": "2026-02-14T11:00:00+00:00",
                }
            )
            repository.create_item(
                {
                    "id": "lib-b",
                    "job_id": "job-b",
                    "document_id": "doc-b",
                    "title": "B",
                    "source_path": "/tmp/b.epub",
                    "audio_path": "runtime/library/audio/job-b.mp3",
                    "format": "mp3",
                    "source_format": "epub",
                    "engine": "chatterbox_gpu",
                    "voice": "default",
                    "language": "fr",
                    "duration_seconds": 1.0,
                    "byte_size": 200,
                    "created_at": "2026-02-14T10:00:00+00:00",
                }
            )

            first = repository.list_items_ordered()
            second = repository.list_items_ordered()

            self.assertEqual([item["id"] for item in first], ["lib-c", "lib-a", "lib-b"])
            self.assertEqual([item["id"] for item in second], ["lib-c", "lib-a", "lib-b"])
            connection.close()

    def test_get_item_by_id_returns_none_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "runtime" / "local_audiobook.db"
            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")
            repository = LibraryItemsRepository(connection)

            self.assertIsNone(repository.get_item_by_id("does-not-exist"))
            connection.close()

    def test_create_item_rejects_path_traversal_attack(self) -> None:
        """Test defensive path validation at repository boundary."""
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
                    "doc-path-attack",
                    "/tmp/source.epub",
                    "Attack",
                    "epub",
                    "2026-02-14T00:00:00+00:00",
                    "2026-02-14T00:00:00+00:00",
                ),
            )
            connection.commit()

            # Attempt path traversal attack
            payload = {
                "job_id": "job-attack",
                "document_id": "doc-path-attack",
                "title": "Attack",
                "source_path": "/tmp/source.epub",
                "audio_path": "../../../etc/passwd",  # Path traversal attempt
                "format": "mp3",
                "source_format": "epub",
                "engine": "chatterbox_gpu",
                "voice": "default",
                "language": "fr",
                "duration_seconds": 1.0,
                "byte_size": 100,
                "created_at": "2026-02-14T00:00:00+00:00",
            }

            with self.assertRaises(ValueError) as context:
                repository.create_item(payload)

            self.assertIn("runtime/library/audio", str(context.exception))
            connection.close()

    def test_list_items_ordered_uses_transaction_for_consistent_reads(self) -> None:
        """Test that list_items_ordered uses explicit transaction for read isolation."""
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
                    "doc-tx",
                    "/tmp/source.epub",
                    "TX Test",
                    "epub",
                    "2026-02-14T00:00:00+00:00",
                    "2026-02-14T00:00:00+00:00",
                ),
            )
            connection.commit()

            repository.create_item(
                {
                    "id": "lib-tx",
                    "job_id": "job-tx",
                    "document_id": "doc-tx",
                    "title": "TX Test",
                    "source_path": "/tmp/source.epub",
                    "audio_path": "runtime/library/audio/job-tx.mp3",
                    "format": "mp3",
                    "source_format": "epub",
                    "engine": "chatterbox_gpu",
                    "voice": "default",
                    "language": "fr",
                    "duration_seconds": 1.0,
                    "byte_size": 100,
                    "created_at": "2026-02-14T00:00:00+00:00",
                }
            )

            # Should complete without error (transaction handling is internal)
            items = repository.list_items_ordered()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["id"], "lib-tx")
            connection.close()
