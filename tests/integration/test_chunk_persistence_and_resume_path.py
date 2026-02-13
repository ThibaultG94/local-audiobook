from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adapters.persistence.sqlite.connection import create_connection
from src.adapters.persistence.sqlite.migration_runner import apply_migrations
from src.adapters.persistence.sqlite.repositories.chunks_repository import ChunksRepository
from src.adapters.tts.chatterbox_provider import ChatterboxProvider
from src.adapters.tts.kokoro_provider import KokoroProvider
from src.domain.services.chunking_service import ChunkingService
from src.domain.services.tts_orchestration_service import TtsOrchestrationService
from src.infrastructure.logging.event_schema import REQUIRED_EVENT_FIELDS, is_valid_utc_iso_8601
from src.infrastructure.logging.jsonl_logger import JsonlLogger


class TestChunkPersistenceAndResumePath(unittest.TestCase):
    def test_orchestration_persists_deterministic_chunk_index_and_hash_for_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc-3-2-1",
                    "/tmp/source.txt",
                    "source",
                    "txt",
                    "2026-02-13T00:00:00+00:00",
                    "2026-02-13T00:00:00+00:00",
                ),
            )
            # Foreign key dependency for chunks(job_id -> conversion_jobs.id)
            connection.execute(
                """
                INSERT INTO conversion_jobs(
                    id, document_id, state, engine, voice, language,
                    speech_rate, output_format, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "job-3-2-1",
                    "doc-3-2-1",
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

            logger = JsonlLogger(events_path)
            repository = ChunksRepository(connection)
            orchestrator = TtsOrchestrationService(
                chunking_service=ChunkingService(),
                chunks_repository=repository,
                logger=logger,
            )

            text = "Phrase alpha. Phrase beta. Phrase gamma."
            first = orchestrator.chunk_text_for_job(
                text=text,
                job_id="job-3-2-1",
                correlation_id="corr-3-2-1",
                max_chars=20,
            )
            second = orchestrator.chunk_text_for_job(
                text=text,
                job_id="job-3-2-1",
                correlation_id="corr-3-2-1",
                max_chars=20,
            )

            self.assertTrue(first.ok)
            self.assertTrue(second.ok)
            first_signature = [
                (chunk["chunk_index"], chunk["text"], chunk["content_hash"])
                for chunk in first.data["chunks"]
            ]
            second_signature = [
                (chunk["chunk_index"], chunk["text"], chunk["content_hash"])
                for chunk in second.data["chunks"]
            ]
            self.assertEqual(first_signature, second_signature)
            self.assertEqual(first.data["chunk_count"], 3)

            rows = connection.execute(
                "SELECT chunk_index, text_content, content_hash, job_id FROM chunks WHERE job_id = ? ORDER BY chunk_index ASC",
                ("job-3-2-1",),
            ).fetchall()
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0][0], 0)
            self.assertEqual(rows[1][0], 1)
            self.assertEqual(rows[2][0], 2)
            self.assertTrue(all(row[2] for row in rows))
            self.assertTrue(all(row[3] == "job-3-2-1" for row in rows))

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            chunking_events = [event for event in events if event.get("stage") == "chunking"]
            self.assertGreaterEqual(len(chunking_events), 4)
            event_names = [event["event"] for event in chunking_events]
            self.assertIn("chunking.started", event_names)
            self.assertIn("chunking.completed", event_names)
            for event in chunking_events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))

            connection.close()

    def test_replace_chunks_validates_sequential_chunk_index(self) -> None:
        """Repository should reject non-sequential chunk indices."""
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
                    "doc-validation",
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
                    "job-validation",
                    "doc-validation",
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

            repository = ChunksRepository(connection)

            # Invalid: chunk_index jumps from 0 to 5
            invalid_chunks = [
                {"chunk_index": 0, "text_content": "First"},
                {"chunk_index": 5, "text_content": "Invalid jump"},
            ]

            with self.assertRaises(ValueError) as context:
                repository.replace_chunks_for_job(job_id="job-validation", chunks=invalid_chunks)

            self.assertIn("sequential", str(context.exception).lower())
            self.assertIn("0", str(context.exception))

            connection.close()

    def test_replace_chunks_is_atomic_on_transaction(self) -> None:
        """Replace operation should be atomic within transaction context."""
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
                    "doc-atomic",
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
                    "job-atomic",
                    "doc-atomic",
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

            repository = ChunksRepository(connection)

            # First insert
            first_chunks = [
                {"chunk_index": 0, "text_content": "Original chunk 0"},
                {"chunk_index": 1, "text_content": "Original chunk 1"},
            ]
            repository.replace_chunks_for_job(job_id="job-atomic", chunks=first_chunks)

            # Verify first insert
            rows = connection.execute(
                "SELECT COUNT(*) FROM chunks WHERE job_id = ?", ("job-atomic",)
            ).fetchone()
            self.assertEqual(rows[0], 2)

            # Second replace should delete old and insert new atomically
            second_chunks = [
                {"chunk_index": 0, "text_content": "Replaced chunk 0"},
                {"chunk_index": 1, "text_content": "Replaced chunk 1"},
                {"chunk_index": 2, "text_content": "New chunk 2"},
            ]
            repository.replace_chunks_for_job(job_id="job-atomic", chunks=second_chunks)

            # Verify replacement was atomic (old deleted, new inserted)
            rows = connection.execute(
                "SELECT COUNT(*) FROM chunks WHERE job_id = ?", ("job-atomic",)
            ).fetchone()
            self.assertEqual(rows[0], 3)

            # Verify content was replaced
            text_rows = connection.execute(
                "SELECT text_content FROM chunks WHERE job_id = ? ORDER BY chunk_index",
                ("job-atomic",),
            ).fetchall()
            self.assertEqual(text_rows[0][0], "Replaced chunk 0")
            self.assertEqual(text_rows[1][0], "Replaced chunk 1")
            self.assertEqual(text_rows[2][0], "New chunk 2")

            connection.close()

    def test_synthesize_persisted_chunks_respects_persisted_order_and_emits_tts_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc-3-3-order",
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
                    "job-3-3-order",
                    "doc-3-3-order",
                    "running",
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

            repository = ChunksRepository(connection)
            repository.replace_chunks_for_job(
                job_id="job-3-3-order",
                chunks=[
                    {"chunk_index": 0, "text_content": "Alpha", "status": "pending"},
                    {"chunk_index": 1, "text_content": "Beta", "status": "pending"},
                    {"chunk_index": 2, "text_content": "Gamma", "status": "pending"},
                ],
            )

            logger = JsonlLogger(events_path)
            orchestrator = TtsOrchestrationService(
                primary_provider=ChatterboxProvider(healthy=True),
                fallback_provider=KokoroProvider(healthy=True),
                chunks_repository=repository,
                logger=logger,
            )

            result = orchestrator.synthesize_persisted_chunks_for_job(
                job_id="job-3-3-order",
                correlation_id="corr-3-3-order",
            )

            self.assertTrue(result.ok)
            self.assertEqual([row["chunk_index"] for row in result.data["chunk_results"]], [0, 1, 2])

            status_rows = connection.execute(
                "SELECT chunk_index, status FROM chunks WHERE job_id = ? ORDER BY chunk_index ASC",
                ("job-3-3-order",),
            ).fetchall()
            self.assertEqual([row[0] for row in status_rows], [0, 1, 2])
            self.assertTrue(all(str(row[1]).startswith("synthesized_") for row in status_rows))

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            tts_events = [event for event in events if event.get("event", "").startswith("tts.")]
            self.assertGreaterEqual(len([event for event in tts_events if event.get("event") == "tts.chunk_started"]), 3)
            self.assertGreaterEqual(len([event for event in tts_events if event.get("event") == "tts.chunk_succeeded"]), 3)
            for event in tts_events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))
                self.assertIn(".", event["event"])

            connection.close()

    def test_synthesize_persisted_chunks_halts_on_dual_provider_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc-3-3-fail",
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
                    "job-3-3-fail",
                    "doc-3-3-fail",
                    "running",
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

            repository = ChunksRepository(connection)
            repository.replace_chunks_for_job(
                job_id="job-3-3-fail",
                chunks=[
                    {"chunk_index": 0, "text_content": "One", "status": "pending"},
                    {"chunk_index": 1, "text_content": "Two", "status": "pending"},
                ],
            )

            logger = JsonlLogger(events_path)
            orchestrator = TtsOrchestrationService(
                primary_provider=ChatterboxProvider(model_available=False),
                fallback_provider=KokoroProvider(model_available=False),
                chunks_repository=repository,
                logger=logger,
            )

            result = orchestrator.synthesize_persisted_chunks_for_job(
                job_id="job-3-3-fail",
                correlation_id="corr-3-3-fail",
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "tts_orchestration.chunk_failed_unrecoverable")
            self.assertFalse(result.error.retryable)
            self.assertEqual(result.error.details["chunk_index"], 0)

            statuses = connection.execute(
                "SELECT chunk_index, status FROM chunks WHERE job_id = ? ORDER BY chunk_index ASC",
                ("job-3-3-fail",),
            ).fetchall()
            self.assertEqual(statuses[0][1], "failed")
            self.assertEqual(statuses[1][1], "pending")

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            started = [event for event in events if event.get("event") == "tts.chunk_started"]
            failed = [event for event in events if event.get("event") == "tts.chunk_failed"]
            self.assertEqual([event["chunk_index"] for event in started], [0])
            self.assertEqual(len(failed), 1)

            connection.close()
