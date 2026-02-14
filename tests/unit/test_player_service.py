from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.contracts.result import failure, success
from src.domain.services.player_service import PlayerService


class _FakePlaybackAdapter:
    def __init__(self) -> None:
        self.load_result = success({"state": "stopped"})
        self.play_result = success({"state": "playing"})
        self.pause_result = success({"state": "paused"})
        self.stop_result = success({"state": "stopped"})
        self.seek_result = success({"state": "paused"})
        self.status_result = success({"state": "stopped", "position_seconds": 0.0, "duration_seconds": 0.0})

    def load(self, *, file_path: str):
        return self.load_result

    def play(self):
        return self.play_result

    def pause(self):
        return self.pause_result

    def stop(self):
        return self.stop_result

    def seek(self, *, position_seconds: float):
        return self.seek_result

    def get_status(self):
        return self.status_result


class _CapturingLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def emit(self, **payload: object) -> None:
        self.events.append(dict(payload))


class TestPlayerService(unittest.TestCase):
    def test_initialize_playback_success_for_mp3(self) -> None:
        adapter = _FakePlaybackAdapter()
        logger = _CapturingLogger()
        service = PlayerService(playback_adapter=adapter, logger=logger)
        audio_base = Path("runtime/library/audio")
        audio_base.mkdir(parents=True, exist_ok=True)
        audio_file = audio_base / "test-player-ok.mp3"
        audio_file.write_bytes(b"ID3")
        try:
            result = service.initialize_playback(
                correlation_id="corr-player-ok",
                playback_context={
                    "library_item_id": "lib-1",
                    "audio_path": str(audio_file),
                    "format": "mp3",
                },
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.data["state"], "stopped")
            self.assertEqual(result.data["playback"]["format"], "mp3")

            events = [event.get("event") for event in logger.events]
            self.assertIn("player.load_requested", events)
        finally:
            if audio_file.exists():
                audio_file.unlink()

    def test_initialize_playback_rejects_missing_audio_path(self) -> None:
        adapter = _FakePlaybackAdapter()
        service = PlayerService(playback_adapter=adapter)

        result = service.initialize_playback(
            correlation_id="corr-player-missing",
            playback_context={"library_item_id": "lib-1", "audio_path": "", "format": "mp3"},
        )

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "player.audio_missing")
        self.assertIn("relink", str(result.error.details.get("remediation", "")).lower())

    def test_initialize_playback_rejects_unsupported_format(self) -> None:
        adapter = _FakePlaybackAdapter()
        service = PlayerService(playback_adapter=adapter)
        audio_base = Path("runtime/library/audio")
        audio_base.mkdir(parents=True, exist_ok=True)
        audio_file = audio_base / "test-player-format.ogg"
        audio_file.write_bytes(b"ogg")
        try:
            result = service.initialize_playback(
                correlation_id="corr-player-format",
                playback_context={"library_item_id": "lib-1", "audio_path": str(audio_file), "format": "ogg"},
            )

            self.assertFalse(result.ok)
            assert result.error is not None
            self.assertEqual(result.error.code, "player.format_unsupported")
            self.assertIn("mp3", str(result.error.details.get("supported_formats", [])))
        finally:
            if audio_file.exists():
                audio_file.unlink()

    def test_invalid_pause_transition_from_idle(self) -> None:
        adapter = _FakePlaybackAdapter()
        service = PlayerService(playback_adapter=adapter)

        result = service.pause(correlation_id="corr-player-pause-invalid")

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "player.pause_invalid_state")

    def test_seek_requires_compatible_state(self) -> None:
        adapter = _FakePlaybackAdapter()
        service = PlayerService(playback_adapter=adapter)

        result = service.seek(correlation_id="corr-player-seek-invalid", position_seconds=12.5)

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "player.seek_invalid_state")

    def test_seek_rejects_invalid_numeric_payload(self) -> None:
        adapter = _FakePlaybackAdapter()
        service = PlayerService(playback_adapter=adapter)
        audio_base = Path("runtime/library/audio")
        audio_base.mkdir(parents=True, exist_ok=True)
        audio_file = audio_base / "test-player-seek-invalid-payload.mp3"
        audio_file.write_bytes(b"ID3")
        try:
            init_result = service.initialize_playback(
                correlation_id="corr-player-seek-invalid-init",
                playback_context={"library_item_id": "lib-seek-invalid", "audio_path": str(audio_file), "format": "mp3"},
            )
            self.assertTrue(init_result.ok)

            result = service.seek(correlation_id="corr-player-seek-invalid", position_seconds="abc")  # type: ignore[arg-type]

            self.assertFalse(result.ok)
            assert result.error is not None
            self.assertEqual(result.error.code, "player.seek_invalid_payload")
        finally:
            if audio_file.exists():
                audio_file.unlink()

    def test_seek_rejects_out_of_range_position(self) -> None:
        adapter = _FakePlaybackAdapter()
        adapter.status_result = success({"state": "paused", "position_seconds": 3.0, "duration_seconds": 8.0})
        service = PlayerService(playback_adapter=adapter)
        audio_base = Path("runtime/library/audio")
        audio_base.mkdir(parents=True, exist_ok=True)
        audio_file = audio_base / "test-player-seek-range.mp3"
        audio_file.write_bytes(b"ID3")
        try:
            init_result = service.initialize_playback(
                correlation_id="corr-player-seek-range-init",
                playback_context={"library_item_id": "lib-seek-range", "audio_path": str(audio_file), "format": "mp3"},
            )
            self.assertTrue(init_result.ok)

            result = service.seek(correlation_id="corr-player-seek-range", position_seconds=12.0)

            self.assertFalse(result.ok)
            assert result.error is not None
            self.assertEqual(result.error.code, "player.seek_out_of_range")
        finally:
            if audio_file.exists():
                audio_file.unlink()

    def test_play_pause_stop_and_status_flow(self) -> None:
        adapter = _FakePlaybackAdapter()
        service = PlayerService(playback_adapter=adapter)
        audio_base = Path("runtime/library/audio")
        audio_base.mkdir(parents=True, exist_ok=True)
        audio_file = audio_base / "test-player-seq.wav"
        audio_file.write_bytes(b"RIFF")
        try:
            init_result = service.initialize_playback(
                correlation_id="corr-player-seq-init",
                playback_context={"library_item_id": "lib-2", "audio_path": str(audio_file), "format": "wav"},
            )
            self.assertTrue(init_result.ok)

            play_result = service.play(correlation_id="corr-player-seq-play")
            self.assertTrue(play_result.ok)
            self.assertEqual(play_result.data["state"], "playing")

            pause_result = service.pause(correlation_id="corr-player-seq-pause")
            self.assertTrue(pause_result.ok)
            self.assertEqual(pause_result.data["state"], "paused")

            adapter.status_result = success({"state": "paused"})
            status_result = service.get_status(correlation_id="corr-player-seq-status")
            self.assertTrue(status_result.ok)
            self.assertEqual(status_result.data["state"], "paused")

            adapter.status_result = success({"state": "paused", "position_seconds": 10.0, "duration_seconds": 50.0})
            progress_status = service.get_status(correlation_id="corr-player-seq-progress")
            self.assertTrue(progress_status.ok)
            self.assertEqual(progress_status.data["position_seconds"], 10.0)
            self.assertEqual(progress_status.data["duration_seconds"], 50.0)
            self.assertAlmostEqual(progress_status.data["progress"], 0.2)

            stop_result = service.stop(correlation_id="corr-player-seq-stop")
            self.assertTrue(stop_result.ok)
            self.assertEqual(stop_result.data["state"], "stopped")
        finally:
            if audio_file.exists():
                audio_file.unlink()

    def test_adapter_failure_is_normalized(self) -> None:
        adapter = _FakePlaybackAdapter()
        adapter.play_result = failure(
            code="qt_player.play_failed",
            message="backend play failed",
            details={"category": "playback"},
            retryable=True,
        )
        service = PlayerService(playback_adapter=adapter)
        audio_base = Path("runtime/library/audio")
        audio_base.mkdir(parents=True, exist_ok=True)
        audio_file = audio_base / "test-player-adapter.wav"
        audio_file.write_bytes(b"RIFF")
        try:
            init_result = service.initialize_playback(
                correlation_id="corr-player-adapter-init",
                playback_context={"library_item_id": "lib-3", "audio_path": str(audio_file), "format": "wav"},
            )
            self.assertTrue(init_result.ok)
        finally:
            if audio_file.exists():
                audio_file.unlink()

        result = service.play(correlation_id="corr-player-adapter-play")
        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "player.play_failed")

    def test_rejects_path_traversal_attack(self) -> None:
        adapter = _FakePlaybackAdapter()
        service = PlayerService(playback_adapter=adapter)

        result = service.initialize_playback(
            correlation_id="corr-player-traversal",
            playback_context={
                "library_item_id": "lib-attack",
                "audio_path": "runtime/library/audio/../../../etc/passwd",
                "format": "mp3",
            },
        )

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "player.invalid_audio_path")

    def test_rejects_absolute_path_outside_bounds(self) -> None:
        adapter = _FakePlaybackAdapter()
        service = PlayerService(playback_adapter=adapter)

        result = service.initialize_playback(
            correlation_id="corr-player-absolute",
            playback_context={"library_item_id": "lib-abs", "audio_path": "/tmp/audio.mp3", "format": "mp3"},
        )

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "player.invalid_audio_path")
        self.assertIn("outside", str(result.error.message).lower())

    def test_seek_emits_logging_events(self) -> None:
        adapter = _FakePlaybackAdapter()
        logger = _CapturingLogger()
        service = PlayerService(playback_adapter=adapter, logger=logger)
        audio_base = Path("runtime/library/audio")
        audio_base.mkdir(parents=True, exist_ok=True)
        audio_file = audio_base / "test-player-seek-log.mp3"
        audio_file.write_bytes(b"ID3")
        try:
            init_result = service.initialize_playback(
                correlation_id="corr-player-seek-log",
                playback_context={"library_item_id": "lib-seek", "audio_path": str(audio_file), "format": "mp3"},
            )
            self.assertTrue(init_result.ok)

            seek_result = service.seek(correlation_id="corr-player-seek-log", position_seconds=10.5)
            self.assertTrue(seek_result.ok)

            events = [event.get("event") for event in logger.events]
            self.assertIn("player.seeked", events)
        finally:
            if audio_file.exists():
                audio_file.unlink()
