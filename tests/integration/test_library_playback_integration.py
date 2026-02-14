from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adapters.persistence.sqlite.connection import create_connection
from src.adapters.persistence.sqlite.migration_runner import apply_migrations
from src.adapters.persistence.sqlite.repositories.library_items_repository import LibraryItemsRepository
from src.contracts.result import Result, success
from src.domain.services.library_service import LibraryService
from src.domain.services.player_service import PlayerService
from src.infrastructure.logging.event_schema import REQUIRED_EVENT_FIELDS, is_valid_utc_iso_8601
from src.infrastructure.logging.jsonl_logger import JsonlLogger


class _FakeAdapter:
    def __init__(self) -> None:
        self.state = "idle"
        self.position_seconds = 0.0
        self.duration_seconds = 60.0

    def load(self, *, file_path: str) -> Result[dict[str, object]]:
        self.state = "stopped"
        return success({"state": self.state})

    def play(self) -> Result[dict[str, object]]:
        self.state = "playing"
        return success({"state": self.state})

    def pause(self) -> Result[dict[str, object]]:
        self.state = "paused"
        return success({"state": self.state})

    def stop(self) -> Result[dict[str, object]]:
        self.state = "stopped"
        return success({"state": self.state})

    def seek(self, *, position_seconds: float) -> Result[dict[str, object]]:
        self.position_seconds = float(position_seconds)
        return success({"state": self.state, "position_seconds": self.position_seconds})

    def get_status(self) -> Result[dict[str, object]]:
        return success(
            {
                "state": self.state,
                "position_seconds": self.position_seconds,
                "duration_seconds": self.duration_seconds,
            }
        )


class TestLibraryPlaybackIntegration(unittest.TestCase):
    def test_reopen_then_initialize_playback_emits_player_events_and_progress_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runtime_audio = Path("runtime") / "library" / "audio"
            runtime_audio.mkdir(parents=True, exist_ok=True)
            audio_file = runtime_audio / "integration-player-test.mp3"
            audio_file.write_bytes(b"ID3")

            db_path = tmp_path / "runtime" / "local_audiobook.db"
            events_path = tmp_path / "runtime" / "logs" / "events.jsonl"

            connection = create_connection(db_path)
            apply_migrations(connection, "migrations")

            repository = LibraryItemsRepository(connection)
            logger = JsonlLogger(events_path)
            library_service = LibraryService(library_items_repository=repository, logger=logger)
            player_service = PlayerService(playback_adapter=_FakeAdapter(), logger=logger)

            connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc-player-int-1",
                    "/tmp/source.epub",
                    "Playback Integration",
                    "epub",
                    "2026-02-14T00:00:00+00:00",
                    "2026-02-14T00:00:00+00:00",
                ),
            )
            connection.commit()

            try:
                repository.create_item(
                    {
                        "id": "lib-player-int-1",
                        "job_id": "job-player-int-1",
                        "document_id": "doc-player-int-1",
                        "title": "Playback Integration",
                        "source_path": "/tmp/source.epub",
                        "audio_path": str(audio_file),
                        "format": "mp3",
                        "source_format": "epub",
                        "engine": "chatterbox_gpu",
                        "voice": "default",
                        "language": "fr",
                        "duration_seconds": 1.2,
                        "byte_size": 128,
                        "created_at": "2026-02-14T01:00:00+00:00",
                    }
                )

                reopen_result = library_service.reopen_library_item(
                    correlation_id="corr-player-reopen-int",
                    item_id="lib-player-int-1",
                )
                self.assertTrue(reopen_result.ok)

                init_result = player_service.initialize_playback(
                    correlation_id="corr-player-init-int",
                    playback_context=dict((reopen_result.data or {}).get("playback_context") or {}),
                )
                self.assertTrue(init_result.ok)

                self.assertTrue(player_service.play(correlation_id="corr-player-play-int").ok)
                self.assertTrue(player_service.pause(correlation_id="corr-player-pause-int").ok)
                self.assertTrue(player_service.play(correlation_id="corr-player-resume-int").ok)
                self.assertTrue(player_service.seek(correlation_id="corr-player-seek-int", position_seconds=15.0).ok)
                status_result = player_service.get_status(correlation_id="corr-player-status-int")
                self.assertTrue(status_result.ok)
                self.assertEqual((status_result.data or {}).get("state"), "playing")
                self.assertEqual((status_result.data or {}).get("position_seconds"), 15.0)
                self.assertEqual((status_result.data or {}).get("duration_seconds"), 60.0)
                self.assertAlmostEqual(float((status_result.data or {}).get("progress", 0.0)), 0.25)
                self.assertTrue(player_service.stop(correlation_id="corr-player-stop-int").ok)

                events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
                player_events = [event for event in events if event.get("stage") == "player"]

                self.assertGreaterEqual(len(player_events), 4)
                event_names = [event.get("event") for event in player_events]
                self.assertIn("player.load_requested", event_names)
                self.assertIn("player.play_started", event_names)
                self.assertIn("player.paused", event_names)
                self.assertIn("player.seeked", event_names)
                self.assertIn("player.stopped", event_names)

                for event in player_events:
                    self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                    self.assertTrue(is_valid_utc_iso_8601(str(event["timestamp"])))
                    self.assertEqual(event["stage"], "player")
            finally:
                if audio_file.exists():
                    audio_file.unlink()

            connection.close()
