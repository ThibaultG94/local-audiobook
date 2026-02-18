from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adapters.audio.mp3_encoder import Mp3Encoder
from src.adapters.audio.wav_builder import WavBuilder
from src.adapters.persistence.sqlite.connection import create_connection
from src.adapters.persistence.sqlite.migration_runner import apply_migrations
from src.adapters.persistence.sqlite.repositories.chunks_repository import ChunksRepository
from src.adapters.persistence.sqlite.repositories.conversion_jobs_repository import ConversionJobsRepository
from src.adapters.persistence.sqlite.repositories.documents_repository import DocumentsRepository
from src.adapters.persistence.sqlite.repositories.library_items_repository import LibraryItemsRepository
from src.adapters.tts.chatterbox_provider import ChatterboxProvider
from src.adapters.tts.kokoro_provider import KokoroProvider
from src.domain.services.audio_postprocess_service import AudioPostprocessService
from src.domain.services.library_service import LibraryService
from src.domain.services.tts_orchestration_service import TtsOrchestrationService
from src.infrastructure.logging.event_schema import REQUIRED_EVENT_FIELDS, is_valid_utc_iso_8601
from src.infrastructure.logging.jsonl_logger import JsonlLogger
from src.ui.workers.conversion_worker import ConversionWorker


class TestPostprocessPipelineIntegration(unittest.TestCase):
    def test_end_to_end_conversion_creates_final_wav_and_emits_postprocess_events(self) -> None:
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
                    "doc-4-1-int",
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
                    "job-4-1-int",
                    "doc-4-1-int",
                    "running",
                    "chatterbox_gpu",
                    "default",
                    "FR",
                    1.0,
                    "wav",
                    "2026-02-13T00:00:00+00:00",
                    "2026-02-13T00:00:00+00:00",
                ),
            )
            connection.commit()

            chunks_repository = ChunksRepository(connection)
            chunks_repository.replace_chunks_for_job(
                job_id="job-4-1-int",
                chunks=[
                    {"chunk_index": 0, "text_content": "Alpha", "status": "pending"},
                    {"chunk_index": 1, "text_content": "Beta", "status": "pending"},
                ],
            )

            logger = JsonlLogger(events_path)
            postprocess_service = AudioPostprocessService(
                wav_builder=WavBuilder(),
                mp3_encoder=Mp3Encoder(),
                logger=logger,
            )
            library_service = LibraryService(
                library_items_repository=LibraryItemsRepository(connection),
                logger=logger,
            )
            orchestrator = TtsOrchestrationService(
                primary_provider=ChatterboxProvider(healthy=True),
                fallback_provider=KokoroProvider(healthy=True),
                audio_postprocess_service=postprocess_service,
                library_service=library_service,
                chunks_repository=chunks_repository,
                conversion_jobs_repository=ConversionJobsRepository(connection),
                documents_repository=DocumentsRepository(connection),
                logger=logger,
            )

            worker = ConversionWorker(
                recheck_callable=lambda: None,
                logger=logger,
                conversion_launcher=orchestrator,
            )

            try:
                result = worker.launch_conversion(
                    document_id="doc-4-1-int",
                    job_id="job-4-1-int",
                    correlation_id="corr-4-1-int",
                    conversion_config={
                        "engine": "chatterbox_gpu",
                        "voice_id": "default",
                        "language": "FR",
                        "speech_rate": 1.0,
                        "output_format": "wav",
                    },
                )
            finally:
                worker.shutdown()

            self.assertTrue(
                result.ok,
                msg=(result.error.to_dict() if getattr(result, "error", None) is not None else result.to_dict()),
            )
            output_artifact = result.data["output_artifact"]
            output_path = Path(output_artifact["path"])
            self.assertTrue(output_path.exists())
            self.assertEqual(output_artifact["format"], "wav")
            self.assertGreater(int(output_artifact["byte_size"]), 44)

            library_row = connection.execute(
                "SELECT job_id, audio_path, format, engine, voice, language FROM library_items WHERE job_id = ?",
                ("job-4-1-int",),
            ).fetchone()
            self.assertIsNotNone(library_row)
            assert library_row is not None
            self.assertEqual(library_row[0], "job-4-1-int")
            self.assertEqual(library_row[2], "wav")
            self.assertEqual(library_row[3], "chatterbox_gpu")
            self.assertEqual(library_row[4], "default")
            self.assertEqual(library_row[5], "FR")

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            postprocess_events = [event for event in events if str(event.get("event", "")).startswith("postprocess.")]
            library_events = [event for event in events if str(event.get("event", "")).startswith("library.")]
            unhandled_events = [
                event for event in events if event.get("event") == "worker_execution.unhandled_exception"
            ]
            self.assertEqual([event["event"] for event in postprocess_events if event["event"] == "postprocess.started"], ["postprocess.started"])
            self.assertEqual([event["event"] for event in postprocess_events if event["event"] == "postprocess.succeeded"], ["postprocess.succeeded"])
            self.assertEqual([event["event"] for event in library_events if event["event"] == "library.item_created"], ["library.item_created"])
            self.assertEqual(unhandled_events, [])

            for event in postprocess_events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))

            for event in library_events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))
                self.assertEqual(event["stage"], "library_persistence")

            connection.close()

    def test_end_to_end_conversion_for_pdf_source_creates_wav_and_completes_without_unhandled_worker_exception(self) -> None:
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
                    "doc-4-1-int-pdf",
                    "/tmp/source.pdf",
                    "source-pdf",
                    "pdf",
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
                    "job-4-1-int-pdf",
                    "doc-4-1-int-pdf",
                    "running",
                    "chatterbox_gpu",
                    "default",
                    "EN",
                    1.0,
                    "wav",
                    "2026-02-13T00:00:00+00:00",
                    "2026-02-13T00:00:00+00:00",
                ),
            )
            connection.commit()

            chunks_repository = ChunksRepository(connection)
            chunks_repository.replace_chunks_for_job(
                job_id="job-4-1-int-pdf",
                chunks=[
                    {"chunk_index": 0, "text_content": "Gamma", "status": "pending"},
                    {"chunk_index": 1, "text_content": "Delta", "status": "pending"},
                ],
            )

            logger = JsonlLogger(events_path)
            postprocess_service = AudioPostprocessService(
                wav_builder=WavBuilder(),
                mp3_encoder=Mp3Encoder(),
                logger=logger,
            )
            library_service = LibraryService(
                library_items_repository=LibraryItemsRepository(connection),
                logger=logger,
            )
            orchestrator = TtsOrchestrationService(
                primary_provider=ChatterboxProvider(healthy=True),
                fallback_provider=KokoroProvider(healthy=True),
                audio_postprocess_service=postprocess_service,
                library_service=library_service,
                chunks_repository=chunks_repository,
                conversion_jobs_repository=ConversionJobsRepository(connection),
                documents_repository=DocumentsRepository(connection),
                logger=logger,
            )

            worker = ConversionWorker(
                recheck_callable=lambda: None,
                logger=logger,
                conversion_launcher=orchestrator,
            )

            try:
                result = worker.launch_conversion(
                    document_id="doc-4-1-int-pdf",
                    job_id="job-4-1-int-pdf",
                    correlation_id="corr-4-1-int-pdf",
                    conversion_config={
                        "engine": "chatterbox_gpu",
                        "voice_id": "default",
                        "language": "EN",
                        "speech_rate": 1.0,
                        "output_format": "wav",
                    },
                )
            finally:
                worker.shutdown()

            self.assertTrue(
                result.ok,
                msg=(result.error.to_dict() if getattr(result, "error", None) is not None else result.to_dict()),
            )
            output_artifact = result.data["output_artifact"]
            output_path = Path(output_artifact["path"])
            self.assertTrue(output_path.exists())
            self.assertEqual(output_artifact["format"], "wav")
            self.assertGreater(int(output_artifact["byte_size"]), 0)

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
            failed_events = [event for event in events if event.get("event") == "worker_execution.failed"]
            unhandled_events = [
                event
                for event in failed_events
                if (event.get("extra") or {}).get("error", {}).get("code") == "worker_execution.unhandled_exception"
            ]

            self.assertEqual(unhandled_events, [])

            connection.close()
