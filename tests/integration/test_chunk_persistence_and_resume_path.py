from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adapters.persistence.sqlite.connection import create_connection
from src.adapters.persistence.sqlite.migration_runner import apply_migrations
from src.adapters.persistence.sqlite.repositories.chunks_repository import ChunksRepository
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
