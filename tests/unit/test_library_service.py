from __future__ import annotations

import unittest

from src.domain.services.library_service import LibraryService


class _InMemoryLibraryItemsRepository:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.items: list[dict[str, object]] = []

    def create_item(self, record: dict[str, object]) -> dict[str, object]:
        payload = dict(record)
        payload.setdefault("id", "lib-1")
        self.created.append(payload)
        self.items.append(payload)
        return payload

    def list_items_ordered(self) -> list[dict[str, object]]:
        return list(self.items)

    def get_item_by_id(self, item_id: str) -> dict[str, object] | None:
        for item in self.items:
            if str(item.get("id") or "") == str(item_id):
                return dict(item)
        return None


class _FailingLibraryItemsRepository:
    def create_item(self, record: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("db down")

    def list_items_ordered(self) -> list[dict[str, object]]:
        raise RuntimeError("db down")

    def get_item_by_id(self, item_id: str) -> dict[str, object] | None:
        return None


class _CapturingLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def emit(self, **payload: object) -> None:
        self.events.append(dict(payload))


class TestLibraryService(unittest.TestCase):
    def test_persist_final_artifact_success_returns_normalized_payload_and_event(self) -> None:
        repository = _InMemoryLibraryItemsRepository()
        logger = _CapturingLogger()
        service = LibraryService(library_items_repository=repository, logger=logger)

        result = service.persist_final_artifact(
            correlation_id="corr-lib-1",
            document={
                "id": "doc-lib-1",
                "title": "Titre",
                "source_path": "/tmp/source.epub",
                "source_format": "epub",
            },
            artifact={
                "job_id": "job-lib-1",
                "path": "runtime/library/audio/job-lib-1.mp3",
                "format": "mp3",
                "duration_seconds": 10.0,
                "byte_size": 1234,
                "engine": "chatterbox_gpu",
                "voice": "default",
                "language": "fr",
            },
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.data["job_id"], "job-lib-1")
        self.assertEqual(result.data["audio_path"], "runtime/library/audio/job-lib-1.mp3")
        self.assertEqual(len(repository.created), 1)

        created_events = [event for event in logger.events if event.get("event") == "library.item_created"]
        self.assertEqual(len(created_events), 1)
        self.assertEqual(created_events[0].get("stage"), "library_persistence")

    def test_browse_library_returns_deterministic_items_and_event(self) -> None:
        repository = _InMemoryLibraryItemsRepository()
        repository.items = [
            {
                "id": "lib-2",
                "title": "Titre 2",
                "source_path": "/tmp/b.epub",
                "language": "fr",
                "format": "mp3",
                "created_at": "2026-02-14T10:00:00+00:00",
                "audio_path": "runtime/library/audio/.gitkeep",
                "job_id": "job-2",
                "source_format": "epub",
            }
        ]
        logger = _CapturingLogger()
        service = LibraryService(library_items_repository=repository, logger=logger)

        result = service.browse_library(correlation_id="corr-browse-1")

        self.assertTrue(result.ok)
        assert result.data is not None
        self.assertEqual(result.data["count"], 1)
        self.assertEqual(result.data["items"][0]["id"], "lib-2")
        self.assertEqual(result.data["items"][0]["created_date"], "2026-02-14T10:00:00+00:00")
        loaded_events = [event for event in logger.events if event.get("event") == "library.list_loaded"]
        self.assertEqual(len(loaded_events), 1)
        self.assertEqual(loaded_events[0].get("stage"), "library_browse")

    def test_reopen_library_item_success_prepares_playback_context(self) -> None:
        repository = _InMemoryLibraryItemsRepository()
        repository.items = [
            {
                "id": "lib-ok",
                "title": "Titre OK",
                "source_path": "/tmp/source.epub",
                "language": "fr",
                "format": "mp3",
                "created_at": "2026-02-14T10:00:00+00:00",
                "audio_path": "runtime/library/audio/.gitkeep",
                "job_id": "job-ok",
                "source_format": "epub",
            }
        ]
        logger = _CapturingLogger()
        service = LibraryService(library_items_repository=repository, logger=logger)

        result = service.reopen_library_item(correlation_id="corr-open-ok", item_id="lib-ok")

        self.assertTrue(result.ok)
        assert result.data is not None
        self.assertEqual(result.data["library_item"]["id"], "lib-ok")
        self.assertIn("runtime/library/audio/.gitkeep", result.data["playback_context"]["audio_path"])
        opened_events = [event for event in logger.events if event.get("event") == "library.item_opened"]
        self.assertEqual(len(opened_events), 1)
        self.assertEqual(opened_events[0].get("stage"), "library_browse")

    def test_reopen_library_item_missing_record_returns_normalized_error(self) -> None:
        repository = _InMemoryLibraryItemsRepository()
        logger = _CapturingLogger()
        service = LibraryService(library_items_repository=repository, logger=logger)

        result = service.reopen_library_item(correlation_id="corr-open-missing", item_id="missing-id")

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "library_browse.item_not_found")
        self.assertIn("remediation", result.error.details)

    def test_reopen_library_item_missing_artifact_returns_actionable_error(self) -> None:
        repository = _InMemoryLibraryItemsRepository()
        repository.items = [
            {
                "id": "lib-missing-audio",
                "title": "Titre Missing",
                "source_path": "/tmp/source.epub",
                "language": "fr",
                "format": "mp3",
                "created_at": "2026-02-14T10:00:00+00:00",
                "audio_path": "runtime/library/audio/file-does-not-exist.mp3",
                "job_id": "job-missing",
                "source_format": "epub",
            }
        ]
        logger = _CapturingLogger()
        service = LibraryService(library_items_repository=repository, logger=logger)

        result = service.reopen_library_item(correlation_id="corr-open-missing-audio", item_id="lib-missing-audio")

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "library_browse.audio_missing")
        self.assertIn("reconvert", str(result.error.details.get("remediation", "")).lower())

    def test_reopen_library_item_empty_item_id_returns_normalized_error(self) -> None:
        """Test AC2: Verify empty item_id is rejected with actionable error."""
        repository = _InMemoryLibraryItemsRepository()
        logger = _CapturingLogger()
        service = LibraryService(library_items_repository=repository, logger=logger)

        result = service.reopen_library_item(correlation_id="corr-open-empty", item_id="")

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "library_browse.invalid_item_id")
        self.assertIn("select", str(result.error.message).lower())
        self.assertFalse(result.error.retryable)

    def test_reopen_library_item_none_item_id_returns_normalized_error(self) -> None:
        """Test AC2: Verify None item_id is rejected with actionable error."""
        repository = _InMemoryLibraryItemsRepository()
        logger = _CapturingLogger()
        service = LibraryService(library_items_repository=repository, logger=logger)

        result = service.reopen_library_item(correlation_id="corr-open-none", item_id=None)

        self.assertFalse(result.ok)
        assert result.error is not None
        self.assertEqual(result.error.code, "library_browse.invalid_item_id")

    def test_reopen_library_item_does_not_trigger_extraction_or_synthesis(self) -> None:
        """Test AC2: Verify reopen prepares playback context without re-running extraction or synthesis.
        
        This test ensures that reopen_library_item only accesses the repository
        and does not call any extraction, chunking, or TTS services.
        """
        repository = _InMemoryLibraryItemsRepository()
        repository.items = [
            {
                "id": "lib-no-reconvert",
                "title": "No Reconvert",
                "source_path": "/tmp/source.epub",
                "language": "fr",
                "format": "mp3",
                "created_at": "2026-02-14T10:00:00+00:00",
                "audio_path": "runtime/library/audio/.gitkeep",
                "job_id": "job-no-reconvert",
                "source_format": "epub",
            }
        ]
        logger = _CapturingLogger()
        service = LibraryService(library_items_repository=repository, logger=logger)

        # Track repository access count
        initial_access_count = len(repository.items)
        
        result = service.reopen_library_item(correlation_id="corr-no-reconvert", item_id="lib-no-reconvert")

        # Verify success
        self.assertTrue(result.ok)
        
        # Verify only repository was accessed (no new items created)
        self.assertEqual(len(repository.items), initial_access_count)
        self.assertEqual(len(repository.created), 0)
        
        # Verify no extraction/synthesis events in logs
        event_names = [event.get("event") for event in logger.events]
        self.assertNotIn("extraction.started", event_names)
        self.assertNotIn("chunking.started", event_names)
        self.assertNotIn("tts.chunk_started", event_names)
        self.assertNotIn("synthesis.started", event_names)
        
        # Verify only library_browse events
        for event in logger.events:
            self.assertEqual(event.get("stage"), "library_browse")

    def test_persist_final_artifact_rejects_missing_required_fields(self) -> None:
        repository = _InMemoryLibraryItemsRepository()
        logger = _CapturingLogger()
        service = LibraryService(library_items_repository=repository, logger=logger)

        result = service.persist_final_artifact(
            correlation_id="corr-lib-err",
            document={
                "id": "doc-lib-err",
                "title": "",
                "source_path": "/tmp/source.epub",
                "source_format": "epub",
            },
            artifact={
                "job_id": "job-lib-err",
                "path": "runtime/library/audio/job-lib-err.mp3",
                "format": "mp3",
                "duration_seconds": 3.0,
                "byte_size": 222,
                "engine": "chatterbox_gpu",
                "voice": "default",
                "language": "fr",
            },
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "library_persistence.invalid_payload")

    def test_persist_final_artifact_maps_repository_failure_and_emits_failed_event(self) -> None:
        logger = _CapturingLogger()
        service = LibraryService(library_items_repository=_FailingLibraryItemsRepository(), logger=logger)

        result = service.persist_final_artifact(
            correlation_id="corr-lib-fail",
            document={
                "id": "doc-lib-fail",
                "title": "Titre",
                "source_path": "/tmp/source.pdf",
                "source_format": "pdf",
            },
            artifact={
                "job_id": "job-lib-fail",
                "path": "runtime/library/audio/job-lib-fail.wav",
                "format": "wav",
                "duration_seconds": 2.0,
                "byte_size": 111,
                "engine": "kokoro_cpu",
                "voice": "v1",
                "language": "fr",
            },
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "library_persistence.write_failed")

        failed_events = [event for event in logger.events if event.get("event") == "library.item_create_failed"]
        self.assertEqual(len(failed_events), 1)
        self.assertEqual(failed_events[0].get("stage"), "library_persistence")
