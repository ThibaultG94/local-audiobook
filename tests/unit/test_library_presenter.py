from __future__ import annotations

import unittest

from src.contracts.result import failure, success
from src.ui.presenters.library_presenter import LibraryPresenter


class _FakeLibraryService:
    def __init__(self) -> None:
        self.browse_result = success({"items": [], "count": 0})
        self.reopen_result = success(
            {
                "library_item": {"id": "lib-1", "title": "Title"},
                "playback_context": {"library_item_id": "lib-1", "audio_path": "/tmp/audio.mp3"},
            }
        )

    def browse_library(self, *, correlation_id: str):
        return self.browse_result

    def reopen_library_item(self, *, correlation_id: str, item_id: str):
        return self.reopen_result


class TestLibraryPresenter(unittest.TestCase):
    def test_load_library_maps_success_state(self) -> None:
        service = _FakeLibraryService()
        service.browse_result = success(
            {
                "items": [
                    {
                        "id": "lib-1",
                        "title": "Book 1",
                        "source": "/tmp/book1.epub",
                        "language": "fr",
                        "format": "mp3",
                        "created_date": "2026-02-14T10:00:00+00:00",
                    }
                ],
                "count": 1,
            }
        )
        presenter = LibraryPresenter(library_service=service)

        state = presenter.load_library(correlation_id="corr-presenter-load")

        self.assertEqual(state["status"], "ready")
        self.assertEqual(len(state["items"]), 1)
        self.assertEqual(state["items"][0]["id"], "lib-1")
        self.assertIsNone(state["error"])

    def test_open_item_maps_opened_state(self) -> None:
        service = _FakeLibraryService()
        service.reopen_result = success(
            {
                "library_item": {"id": "lib-open", "title": "Book Open"},
                "playback_context": {
                    "library_item_id": "lib-open",
                    "audio_path": "/tmp/open.mp3",
                    "format": "mp3",
                },
            }
        )
        presenter = LibraryPresenter(library_service=service)

        state = presenter.open_item(correlation_id="corr-presenter-open", item_id="lib-open")

        self.assertEqual(state["status"], "opened")
        self.assertEqual(state["selected_item_id"], "lib-open")
        self.assertEqual(state["playback_context"]["audio_path"], "/tmp/open.mp3")
        self.assertIsNone(state["error"])

    def test_open_item_maps_actionable_error(self) -> None:
        service = _FakeLibraryService()
        service.reopen_result = failure(
            code="library_browse.audio_missing",
            message="Audio artifact file is unavailable on disk.",
            details={
                "audio_path": "runtime/library/audio/missing.mp3",
                "remediation": "Relink the missing artifact path or reconvert the audiobook locally.",
            },
            retryable=False,
        )
        presenter = LibraryPresenter(library_service=service)

        state = presenter.open_item(correlation_id="corr-presenter-open-fail", item_id="lib-missing")

        self.assertEqual(state["status"], "error")
        self.assertEqual(state["selected_item_id"], "lib-missing")
        self.assertIsNotNone(state["error"])
        self.assertEqual(state["error"]["code"], "library_browse.audio_missing")
        self.assertIn("reconvert", state["error"]["remediation"].lower())

