from __future__ import annotations

import unittest

from src.ui.views.library_view import LibraryView


class _FakeLibraryPresenter:
    def load_library(self, *, correlation_id: str):
        return {
            "status": "ready",
            "items": [{"id": "lib-1", "title": "Book"}],
            "selected_item_id": "",
            "playback_context": None,
            "playback_state": "idle",
            "playback_position_seconds": 0.0,
            "playback_duration_seconds": 0.0,
            "playback_progress": 0.0,
            "error": None,
        }

    def open_item(self, *, correlation_id: str, item_id: str):
        return {
            "status": "opened",
            "items": [{"id": item_id, "title": "Book"}],
            "selected_item_id": item_id,
            "playback_context": {"library_item_id": item_id, "audio_path": "runtime/library/audio/.gitkeep"},
            "playback_state": "stopped",
            "playback_position_seconds": 0.0,
            "playback_duration_seconds": 0.0,
            "playback_progress": 0.0,
            "error": None,
        }

    def play(self, *, correlation_id: str):
        return {
            "status": "opened",
            "items": [{"id": "lib-1", "title": "Book"}],
            "selected_item_id": "lib-1",
            "playback_context": {"library_item_id": "lib-1", "audio_path": "runtime/library/audio/.gitkeep"},
            "playback_state": "playing",
            "playback_position_seconds": 0.0,
            "playback_duration_seconds": 120.0,
            "playback_progress": 0.0,
            "error": None,
        }

    def pause(self, *, correlation_id: str):
        return {
            "status": "opened",
            "items": [{"id": "lib-1", "title": "Book"}],
            "selected_item_id": "lib-1",
            "playback_context": {"library_item_id": "lib-1", "audio_path": "runtime/library/audio/.gitkeep"},
            "playback_state": "paused",
            "playback_position_seconds": 5.0,
            "playback_duration_seconds": 120.0,
            "playback_progress": 5.0 / 120.0,
            "error": None,
        }

    def seek(self, *, correlation_id: str, position_seconds: float):
        return {
            "status": "opened",
            "items": [{"id": "lib-1", "title": "Book"}],
            "selected_item_id": "lib-1",
            "playback_context": {"library_item_id": "lib-1", "audio_path": "runtime/library/audio/.gitkeep"},
            "playback_state": "paused",
            "playback_position_seconds": float(position_seconds),
            "playback_duration_seconds": 120.0,
            "playback_progress": float(position_seconds) / 120.0,
            "error": None,
        }

    def refresh_playback_status(self, *, correlation_id: str):
        return {
            "status": "opened",
            "items": [{"id": "lib-1", "title": "Book"}],
            "selected_item_id": "lib-1",
            "playback_context": {"library_item_id": "lib-1", "audio_path": "runtime/library/audio/.gitkeep"},
            "playback_state": "paused",
            "playback_position_seconds": 10.0,
            "playback_duration_seconds": 120.0,
            "playback_progress": 10.0 / 120.0,
            "error": None,
        }


class TestLibraryView(unittest.TestCase):
    def test_load_updates_deterministic_state(self) -> None:
        view = LibraryView(presenter=_FakeLibraryPresenter())

        state = view.load(correlation_id="corr-view-load")

        self.assertEqual(state["status"], "ready")
        self.assertEqual(state["playback_state"], "idle")
        self.assertEqual(state["playback_progress"], 0.0)
        self.assertEqual(len(state["items"]), 1)

    def test_open_selected_propagates_playback_state_without_adapter_leak(self) -> None:
        view = LibraryView(presenter=_FakeLibraryPresenter())

        state = view.open_selected(correlation_id="corr-view-open", item_id="lib-1")

        self.assertEqual(state["status"], "opened")
        self.assertEqual(state["selected_item_id"], "lib-1")
        self.assertEqual(state["playback_state"], "stopped")
        self.assertNotIn("qt_object", state)

    def test_play_pause_seek_refresh_routes_through_presenter(self) -> None:
        view = LibraryView(presenter=_FakeLibraryPresenter())

        play_state = view.play(correlation_id="corr-view-play")
        self.assertEqual(play_state["playback_state"], "playing")

        pause_state = view.pause(correlation_id="corr-view-pause")
        self.assertEqual(pause_state["playback_state"], "paused")
        self.assertGreater(pause_state["playback_progress"], 0.0)

        seek_state = view.seek(correlation_id="corr-view-seek", position_seconds=10.0)
        self.assertEqual(seek_state["playback_position_seconds"], 10.0)

        status_state = view.refresh_playback_status(correlation_id="corr-view-status")
        self.assertEqual(status_state["playback_duration_seconds"], 120.0)
