from __future__ import annotations

import unittest

from src.domain.services.library_service import LibraryService


class _InMemoryLibraryItemsRepository:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []

    def create_item(self, record: dict[str, object]) -> dict[str, object]:
        payload = dict(record)
        payload.setdefault("id", "lib-1")
        self.created.append(payload)
        return payload


class _FailingLibraryItemsRepository:
    def create_item(self, record: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("db down")


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

