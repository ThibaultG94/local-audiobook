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
            "error": None,
        }

    def open_item(self, *, correlation_id: str, item_id: str):
        return {
            "status": "opened",
            "items": [{"id": item_id, "title": "Book"}],
            "selected_item_id": item_id,
            "playback_context": {"library_item_id": item_id, "audio_path": "runtime/library/audio/.gitkeep"},
            "playback_state": "stopped",
            "error": None,
        }


class TestLibraryView(unittest.TestCase):
    def test_load_updates_deterministic_state(self) -> None:
        view = LibraryView(presenter=_FakeLibraryPresenter())

        state = view.load(correlation_id="corr-view-load")

        self.assertEqual(state["status"], "ready")
        self.assertEqual(state["playback_state"], "idle")
        self.assertEqual(len(state["items"]), 1)

    def test_open_selected_propagates_playback_state_without_adapter_leak(self) -> None:
        view = LibraryView(presenter=_FakeLibraryPresenter())

        state = view.open_selected(correlation_id="corr-view-open", item_id="lib-1")

        self.assertEqual(state["status"], "opened")
        self.assertEqual(state["selected_item_id"], "lib-1")
        self.assertEqual(state["playback_state"], "stopped")
        self.assertNotIn("qt_object", state)

