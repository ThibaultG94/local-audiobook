from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.adapters.persistence.sqlite.connection import create_connection
from src.adapters.persistence.sqlite.migration_runner import apply_migrations
from src.adapters.persistence.sqlite.repositories.conversion_jobs_repository import ConversionJobsRepository


class TestConversionJobsRepository(unittest.TestCase):
    def test_get_job_by_id_returns_state_and_updated_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc-jobs-1",
                    "/tmp/source.txt",
                    "source",
                    "txt",
                    "2026-02-13T00:00:00+00:00",
                    "2026-02-13T00:00:00+00:00",
                ),
            )
            connection.execute(
                """
                INSERT INTO conversion_jobs(
                    id, document_id, state, engine, voice, language,
                    speech_rate, output_format, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "job-jobs-1",
                    "doc-jobs-1",
                    "queued",
                    "",
                    "",
                    "",
                    1.0,
                    "wav",
                    "2026-02-13T00:00:00+00:00",
                    "2026-02-13T00:00:00+00:00",
                ),
            )
            connection.commit()

            repository = ConversionJobsRepository(connection)
            job = repository.get_job_by_id(job_id="job-jobs-1")

            self.assertIsNotNone(job)
            assert job is not None
            self.assertEqual(job["id"], "job-jobs-1")
            self.assertEqual(job["state"], "queued")
            self.assertEqual(job["updated_at"], "2026-02-13T00:00:00+00:00")

            connection.close()

    def test_update_job_state_if_current_updates_state_and_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc-jobs-2",
                    "/tmp/source.txt",
                    "source",
                    "txt",
                    "2026-02-13T00:00:00+00:00",
                    "2026-02-13T00:00:00+00:00",
                ),
            )
            connection.execute(
                """
                INSERT INTO conversion_jobs(
                    id, document_id, state, engine, voice, language,
                    speech_rate, output_format, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "job-jobs-2",
                    "doc-jobs-2",
                    "queued",
                    "",
                    "",
                    "",
                    1.0,
                    "wav",
                    "2026-02-13T00:00:00+00:00",
                    "2026-02-13T00:00:00+00:00",
                ),
            )
            connection.commit()

            repository = ConversionJobsRepository(connection)
            updated = repository.update_job_state_if_current(
                job_id="job-jobs-2",
                expected_state="queued",
                next_state="running",
                updated_at="2026-02-13T00:01:00+00:00",
            )

            self.assertTrue(updated)

            row = connection.execute(
                "SELECT state, updated_at FROM conversion_jobs WHERE id = ?",
                ("job-jobs-2",),
            ).fetchone()
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row[0], "running")
            self.assertEqual(row[1], "2026-02-13T00:01:00+00:00")

            connection.close()

    def test_update_job_state_if_current_returns_false_for_not_found_or_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc-jobs-3",
                    "/tmp/source.txt",
                    "source",
                    "txt",
                    "2026-02-13T00:00:00+00:00",
                    "2026-02-13T00:00:00+00:00",
                ),
            )
            connection.execute(
                """
                INSERT INTO conversion_jobs(
                    id, document_id, state, engine, voice, language,
                    speech_rate, output_format, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "job-jobs-3",
                    "doc-jobs-3",
                    "paused",
                    "",
                    "",
                    "",
                    1.0,
                    "wav",
                    "2026-02-13T00:00:00+00:00",
                    "2026-02-13T00:00:00+00:00",
                ),
            )
            connection.commit()

            repository = ConversionJobsRepository(connection)

            not_found = repository.update_job_state_if_current(
                job_id="missing-job",
                expected_state="queued",
                next_state="running",
            )
            self.assertFalse(not_found)

            conflict = repository.update_job_state_if_current(
                job_id="job-jobs-3",
                expected_state="queued",
                next_state="running",
            )
            self.assertFalse(conflict)

            row = connection.execute(
                "SELECT state FROM conversion_jobs WHERE id = ?",
                ("job-jobs-3",),
            ).fetchone()
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row[0], "paused")

            connection.close()
