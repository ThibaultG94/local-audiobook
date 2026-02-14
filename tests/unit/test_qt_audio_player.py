from __future__ import annotations

import unittest

from src.adapters.playback.qt_audio_player import QtAudioPlayer


class _FakeBackend:
    def __init__(self) -> None:
        self.state = "stopped"
        self.fail_action: str | None = None
        self.position_milliseconds = 0
        self.duration_milliseconds = 0

    def load(self, file_path: str) -> None:
        if self.fail_action == "load":
            raise RuntimeError("load boom")
        self.state = "stopped"

    def play(self) -> None:
        if self.fail_action == "play":
            raise RuntimeError("play boom")
        self.state = "playing"

    def pause(self) -> None:
        if self.fail_action == "pause":
            raise RuntimeError("pause boom")
        self.state = "paused"

    def stop(self) -> None:
        if self.fail_action == "stop":
            raise RuntimeError("stop boom")
        self.state = "stopped"

    def seek(self, position_seconds: float) -> None:
        if self.fail_action == "seek":
            raise RuntimeError("seek boom")
        self.position_milliseconds = int(float(position_seconds) * 1000)

    def get_state(self) -> str:
        if self.fail_action == "status":
            raise RuntimeError("status boom")
        return self.state

    def get_position_milliseconds(self) -> int:
        return self.position_milliseconds

    def get_duration_milliseconds(self) -> int:
        return self.duration_milliseconds


class TestQtAudioPlayer(unittest.TestCase):
    def test_maps_backend_states_to_deterministic_states(self) -> None:
        backend = _FakeBackend()
        backend.duration_milliseconds = 25000
        adapter = QtAudioPlayer(backend_factory=lambda: backend)

        self.assertTrue(adapter.load(file_path="runtime/library/audio/.gitkeep").ok)

        play_result = adapter.play()
        self.assertTrue(play_result.ok)
        self.assertEqual(play_result.data["state"], "playing")

        pause_result = adapter.pause()
        self.assertTrue(pause_result.ok)
        self.assertEqual(pause_result.data["state"], "paused")

        stop_result = adapter.stop()
        self.assertTrue(stop_result.ok)
        self.assertEqual(stop_result.data["state"], "stopped")

        status_result = adapter.get_status()
        self.assertTrue(status_result.ok)
        self.assertEqual(status_result.data["state"], "stopped")
        self.assertEqual(status_result.data["position_seconds"], 0.0)
        self.assertEqual(status_result.data["duration_seconds"], 25.0)

    def test_seek_validates_non_negative(self) -> None:
        adapter = QtAudioPlayer(backend_factory=_FakeBackend)

        result = adapter.seek(position_seconds=-1)

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "qt_player.seek_invalid_position")

    def test_backend_runtime_failures_are_normalized(self) -> None:
        backend = _FakeBackend()
        backend.fail_action = "play"
        adapter = QtAudioPlayer(backend_factory=lambda: backend)

        result = adapter.play()

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "qt_player.play_failed")

    def test_backend_unavailable_is_normalized(self) -> None:
        def _raising_factory() -> _FakeBackend:
            raise RuntimeError("no qt backend")

        adapter = QtAudioPlayer(backend_factory=_raising_factory)

        result = adapter.load(file_path="runtime/library/audio/.gitkeep")

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "qt_player.load_backend_unavailable")
