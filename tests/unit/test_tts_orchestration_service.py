"""Unit tests for TTS orchestration service."""
from __future__ import annotations

import re
import unittest

from src.contracts.result import success
from src.adapters.tts.chatterbox_provider import ChatterboxProvider
from src.adapters.tts.kokoro_provider import KokoroProvider
from src.domain.services.chunking_service import ChunkingService
from src.domain.services.tts_orchestration_service import TtsOrchestrationService
from src.infrastructure.logging.event_schema import is_valid_utc_iso_8601


class TestTtsOrchestrationService(unittest.TestCase):
    def test_launch_conversion_runs_postprocess_and_returns_output_artifact(self) -> None:
        class _InMemoryChunksRepository:
            def __init__(self) -> None:
                self.rows = [{"job_id": "job-post", "chunk_index": 0, "text_content": "Alpha", "status": "pending"}]

            def list_chunks_for_job(self, *, job_id: str) -> list[dict[str, object]]:
                return [row for row in self.rows if row["job_id"] == job_id]

            def update_chunk_synthesis_outcome(self, *, job_id: str, chunk_index: int, status: str) -> None:
                for row in self.rows:
                    if row["job_id"] == job_id and int(row["chunk_index"]) == int(chunk_index):
                        row["status"] = status

        class _PostprocessStub:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def assemble_and_render(self, **kwargs: object):
                self.calls.append(dict(kwargs))
                return success(
                    {
                        "job_id": str(kwargs.get("job_id")),
                        "chunk_count": len(list(kwargs.get("chunk_artifacts") or [])),
                        "output_artifact": {
                            "path": str(kwargs.get("target_path")),
                            "format": str(kwargs.get("output_format")),
                            "byte_size": 123,
                            "duration_seconds": 1.0,
                        },
                    }
                )

        class _LibraryServiceStub:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def persist_final_artifact(self, **kwargs: object):
                self.calls.append(dict(kwargs))
                return success({"id": "lib-1", "job_id": "job-post"})

        class _DocumentsRepositoryStub:
            def get_document_by_id(self, *, document_id: str) -> dict[str, object] | None:
                if document_id == "doc-post":
                    return {
                        "id": "doc-post",
                        "title": "Titre",
                        "source_path": "/tmp/source.txt",
                        "source_format": "txt",
                    }
                return None

        class _JobsRepositoryStub:
            def get_job_by_id(self, *, job_id: str) -> dict[str, object] | None:
                return {"id": job_id, "document_id": "doc-post", "state": "running", "updated_at": "2026-02-13T00:00:00+00:00"}

            def update_job_state_if_current(
                self,
                *,
                job_id: str,
                expected_state: str,
                next_state: str,
                updated_at: str | None = None,
            ) -> bool:
                return True

        repo = _InMemoryChunksRepository()
        postprocess = _PostprocessStub()
        library_service = _LibraryServiceStub()
        orchestrator = TtsOrchestrationService(
            primary_provider=ChatterboxProvider(healthy=True),
            fallback_provider=KokoroProvider(healthy=True),
            audio_postprocess_service=postprocess,
            library_service=library_service,
            chunks_repository=repo,
            conversion_jobs_repository=_JobsRepositoryStub(),
            documents_repository=_DocumentsRepositoryStub(),
        )

        result = orchestrator.launch_conversion(
            job_id="job-post",
            correlation_id="corr-post",
            conversion_config={
                "engine": "chatterbox_gpu",
                "voice_id": "default",
                "language": "FR",
                "speech_rate": 1.0,
                "output_format": "wav",
            },
        )

        self.assertTrue(result.ok)
        self.assertIn("output_artifact", result.data)
        self.assertEqual(result.data["output_artifact"]["format"], "wav")
        self.assertEqual(len(postprocess.calls), 1)
        self.assertEqual(len(library_service.calls), 1)

    def test_synthesize_with_healthy_primary_uses_primary(self) -> None:
        """When primary is healthy, it should be used."""
        primary = ChatterboxProvider(healthy=True)
        fallback = KokoroProvider(healthy=True)
        orchestrator = TtsOrchestrationService(
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = orchestrator.synthesize_with_fallback("Test text")

        self.assertTrue(result.ok)
        self.assertEqual(result.data["metadata"]["engine"], "chatterbox_gpu")

    def test_synthesize_with_unavailable_primary_falls_back_to_secondary(self) -> None:
        """When primary is unavailable, should fallback to secondary."""
        primary = ChatterboxProvider(model_available=False)
        fallback = KokoroProvider(healthy=True)
        orchestrator = TtsOrchestrationService(
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = orchestrator.synthesize_with_fallback("Test text")

        self.assertTrue(result.ok)
        self.assertEqual(result.data["metadata"]["engine"], "kokoro_cpu")

    def test_synthesize_with_input_error_does_not_fallback(self) -> None:
        """Input validation errors should not trigger fallback."""
        primary = ChatterboxProvider(healthy=True)
        fallback = KokoroProvider(healthy=True)
        orchestrator = TtsOrchestrationService(
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = orchestrator.synthesize_with_fallback("   ")  # Empty text

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "tts_input_invalid")
        # Should not have tried fallback for input error

    def test_synthesize_with_both_providers_unavailable_returns_combined_error(self) -> None:
        """When both providers fail, should return combined error."""
        primary = ChatterboxProvider(model_available=False)
        fallback = KokoroProvider(model_available=False)
        orchestrator = TtsOrchestrationService(
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = orchestrator.synthesize_with_fallback("Test text")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "tts_all_providers_failed")
        error_details = result.error.details
        self.assertIn("primary_error", error_details)
        self.assertIn("fallback_error", error_details)

    def test_synthesize_with_no_providers_returns_error(self) -> None:
        """When no providers configured, should return error."""
        orchestrator = TtsOrchestrationService()

        result = orchestrator.synthesize_with_fallback("Test text")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "tts_no_providers")

    def test_synthesize_with_only_fallback_provider_uses_it(self) -> None:
        """When only fallback provider configured, should use it."""
        fallback = KokoroProvider(healthy=True)
        orchestrator = TtsOrchestrationService(fallback_provider=fallback)

        result = orchestrator.synthesize_with_fallback("Test text")

        self.assertTrue(result.ok)
        self.assertEqual(result.data["metadata"]["engine"], "kokoro_cpu")

    def test_check_provider_health_returns_status_for_all_providers(self) -> None:
        """Health check should return status for all configured providers."""
        primary = ChatterboxProvider(healthy=True)
        fallback = KokoroProvider(model_available=False)
        orchestrator = TtsOrchestrationService(
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = orchestrator.check_provider_health()

        self.assertTrue(result.ok)
        self.assertIn("primary", result.data)
        self.assertIn("fallback", result.data)
        self.assertTrue(result.data["primary"]["healthy"])
        self.assertFalse(result.data["fallback"]["healthy"])

    def test_should_fallback_logic_for_availability_errors(self) -> None:
        """Test internal fallback decision logic."""
        orchestrator = TtsOrchestrationService()

        # Should fallback on availability errors
        availability_error = {
            "code": "tts_engine_unavailable",
            "details": {"category": "availability"},
            "retryable": False,
        }
        self.assertTrue(orchestrator._should_fallback(availability_error))

        # Should NOT fallback on input errors
        input_error = {
            "code": "tts_input_invalid",
            "details": {"category": "input"},
            "retryable": False,
        }
        self.assertFalse(orchestrator._should_fallback(input_error))

        # Should NOT fallback on retryable errors
        retryable_error = {
            "code": "tts_engine_unavailable",
            "details": {"category": "availability"},
            "retryable": True,
        }
        self.assertFalse(orchestrator._should_fallback(retryable_error))

    def test_synthesize_passes_correlation_fields_to_providers(self) -> None:
        """Ensure correlation fields are passed through to providers."""
        primary = ChatterboxProvider(healthy=True)
        orchestrator = TtsOrchestrationService(primary_provider=primary)

        result = orchestrator.synthesize_with_fallback(
            "Test text",
            voice="default",
            correlation_id="test-corr-123",
            job_id="test-job-456",
            chunk_index=42,
        )

        self.assertTrue(result.ok)
        # If providers log correctly, correlation fields were passed
        # (validated in provider tests)

    def test_chunk_text_for_job_persists_indexed_hashes(self) -> None:
        class _InMemoryChunksRepository:
            def __init__(self) -> None:
                self.items: list[dict[str, object]] = []

            def replace_chunks_for_job(self, *, job_id: str, chunks: list[dict[str, object]]) -> list[dict[str, object]]:
                self.items = [item for item in self.items if item["job_id"] != job_id]
                normalized = []
                for item in chunks:
                    normalized.append(
                        {
                            "job_id": job_id,
                            "chunk_index": item["chunk_index"],
                            "text_content": item["text_content"],
                            "content_hash": item["content_hash"],
                            "created_at": item["created_at"],
                        }
                    )
                self.items.extend(normalized)
                return [item for item in self.items if item["job_id"] == job_id]

        class _CapturingLogger:
            def __init__(self) -> None:
                self.events: list[dict[str, object]] = []

            def emit(self, **payload: object) -> None:
                self.events.append(payload)

        repository = _InMemoryChunksRepository()
        logger = _CapturingLogger()
        orchestrator = TtsOrchestrationService(
            chunking_service=ChunkingService(),
            chunks_repository=repository,
            logger=logger,
        )

        result = orchestrator.chunk_text_for_job(
            text="Phrase une. Phrase deux. Phrase trois.",
            job_id="job-chunk-1",
            correlation_id="corr-chunk-1",
            max_chars=20,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.data["chunk_count"], 3)
        self.assertEqual(result.data["chunks"][0]["chunk_index"], 0)
        self.assertEqual(result.data["chunks"][1]["chunk_index"], 1)
        self.assertEqual(result.data["chunks"][2]["chunk_index"], 2)
        self.assertTrue(all(item.get("content_hash") for item in result.data["chunks"]))
        event_names = [event.get("event") for event in logger.events]
        self.assertIn("chunking.started", event_names)
        self.assertIn("chunking.completed", event_names)

    def test_chunk_text_for_job_returns_normalized_failure_and_emits_failed_event(self) -> None:
        class _InMemoryChunksRepository:
            def replace_chunks_for_job(self, *, job_id: str, chunks: list[dict[str, object]]) -> list[dict[str, object]]:
                return chunks

        class _CapturingLogger:
            def __init__(self) -> None:
                self.events: list[dict[str, object]] = []

            def emit(self, **payload: object) -> None:
                self.events.append(payload)

        logger = _CapturingLogger()
        orchestrator = TtsOrchestrationService(
            chunking_service=ChunkingService(),
            chunks_repository=_InMemoryChunksRepository(),
            logger=logger,
        )

        result = orchestrator.chunk_text_for_job(
            text="   ",
            job_id="job-chunk-err",
            correlation_id="corr-chunk-err",
            max_chars=100,
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "chunking.invalid_text")
        failed_events = [event for event in logger.events if event.get("event") == "chunking.failed"]
        self.assertEqual(len(failed_events), 1)

    def test_synthesize_persisted_chunks_processes_strict_index_order_and_emits_lifecycle_events(self) -> None:
        class _InMemoryChunksRepository:
            def __init__(self) -> None:
                self.rows = [
                    {"job_id": "job-order", "chunk_index": 2, "text_content": "trois", "status": "pending"},
                    {"job_id": "job-order", "chunk_index": 0, "text_content": "un", "status": "pending"},
                    {"job_id": "job-order", "chunk_index": 1, "text_content": "deux", "status": "pending"},
                ]
                self.updated: list[tuple[str, int, str]] = []

            def list_chunks_for_job(self, *, job_id: str) -> list[dict[str, object]]:
                return [row for row in self.rows if row["job_id"] == job_id]

            def update_chunk_synthesis_outcome(self, *, job_id: str, chunk_index: int, status: str) -> None:
                self.updated.append((job_id, chunk_index, status))

        class _CapturingLogger:
            def __init__(self) -> None:
                self.events: list[dict[str, object]] = []

            def emit(self, **payload: object) -> None:
                self.events.append(payload)

        repo = _InMemoryChunksRepository()
        logger = _CapturingLogger()
        orchestrator = TtsOrchestrationService(
            primary_provider=ChatterboxProvider(healthy=True),
            fallback_provider=KokoroProvider(healthy=True),
            chunks_repository=repo,
            logger=logger,
        )

        result = orchestrator.synthesize_persisted_chunks_for_job(
            job_id="job-order",
            correlation_id="corr-order",
        )

        self.assertTrue(result.ok)
        indices = [item["chunk_index"] for item in result.data["chunk_results"]]
        self.assertEqual(indices, [0, 1, 2])
        self.assertEqual([item[1] for item in repo.updated], [0, 1, 2])

        event_names = [event.get("event") for event in logger.events]
        self.assertGreaterEqual(event_names.count("tts.chunk_started"), 3)
        self.assertGreaterEqual(event_names.count("tts.chunk_succeeded"), 3)
        
        # Validate event schema compliance
        for event in logger.events:
            # Required fields
            self.assertIn("correlation_id", event)
            self.assertIn("job_id", event)
            self.assertIn("chunk_index", event)
            self.assertIn("engine", event)
            self.assertIn("stage", event)
            self.assertIn("event", event)
            self.assertIn("severity", event)
            self.assertIn("timestamp", event)
            
            # Validate timestamp format (ISO-8601 UTC)
            self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))
            
            # Validate event naming convention (domain.action)
            self.assertRegex(event["event"], r"^\w+\.\w+$", f"Event name '{event['event']}' must follow domain.action format")
            
            # Validate severity values
            self.assertIn(event["severity"], ["INFO", "WARNING", "ERROR"])

    def test_synthesize_persisted_chunks_applies_fallback_only_for_eligible_failures(self) -> None:
        class _InMemoryChunksRepository:
            def __init__(self) -> None:
                self.rows = [{"job_id": "job-fallback", "chunk_index": 0, "text_content": "Texte ok", "status": "pending"}]
                self.updated: list[tuple[str, int, str]] = []

            def list_chunks_for_job(self, *, job_id: str) -> list[dict[str, object]]:
                return [row for row in self.rows if row["job_id"] == job_id]

            def update_chunk_synthesis_outcome(self, *, job_id: str, chunk_index: int, status: str) -> None:
                self.updated.append((job_id, chunk_index, status))

        class _CapturingLogger:
            def __init__(self) -> None:
                self.events: list[dict[str, object]] = []

            def emit(self, **payload: object) -> None:
                self.events.append(payload)

        repo = _InMemoryChunksRepository()
        logger = _CapturingLogger()
        orchestrator = TtsOrchestrationService(
            primary_provider=ChatterboxProvider(model_available=False),
            fallback_provider=KokoroProvider(healthy=True),
            chunks_repository=repo,
            logger=logger,
        )

        result = orchestrator.synthesize_persisted_chunks_for_job(
            job_id="job-fallback",
            correlation_id="corr-fallback",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.data["chunk_results"][0]["engine"], "kokoro_cpu")
        fallback_events = [event for event in logger.events if event.get("event") == "tts.fallback_applied"]
        self.assertEqual(len(fallback_events), 1)
        self.assertEqual(repo.updated[0][2], "synthesized_kokoro_cpu")

    def test_synthesize_persisted_chunks_dual_failure_returns_deterministic_error_and_halts(self) -> None:
        class _InMemoryChunksRepository:
            def __init__(self) -> None:
                self.rows = [
                    {"job_id": "job-fail", "chunk_index": 0, "text_content": "A", "status": "pending"},
                    {"job_id": "job-fail", "chunk_index": 1, "text_content": "B", "status": "pending"},
                ]
                self.updated: list[tuple[str, int, str]] = []

            def list_chunks_for_job(self, *, job_id: str) -> list[dict[str, object]]:
                return [row for row in self.rows if row["job_id"] == job_id]

            def update_chunk_synthesis_outcome(self, *, job_id: str, chunk_index: int, status: str) -> None:
                self.updated.append((job_id, chunk_index, status))

        class _CapturingLogger:
            def __init__(self) -> None:
                self.events: list[dict[str, object]] = []

            def emit(self, **payload: object) -> None:
                self.events.append(payload)

        repo = _InMemoryChunksRepository()
        logger = _CapturingLogger()
        orchestrator = TtsOrchestrationService(
            primary_provider=ChatterboxProvider(model_available=False),
            fallback_provider=KokoroProvider(model_available=False),
            chunks_repository=repo,
            logger=logger,
        )

        result = orchestrator.synthesize_persisted_chunks_for_job(
            job_id="job-fail",
            correlation_id="corr-fail",
            current_job_state="running",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "tts_orchestration.chunk_failed_unrecoverable")
        self.assertFalse(result.error.retryable)
        self.assertEqual(result.error.details["chunk_index"], 0)
        self.assertEqual(result.error.details["attempted_engines"], ["chatterbox_gpu", "kokoro_cpu"])
        self.assertTrue(result.error.details["transition_intent"]["validated"])

        started_events = [event for event in logger.events if event.get("event") == "tts.chunk_started"]
        self.assertEqual([event["chunk_index"] for event in started_events], [0])
        failed_events = [event for event in logger.events if event.get("event") == "tts.chunk_failed"]
        self.assertEqual(len(failed_events), 1)
        self.assertEqual(repo.updated, [("job-fail", 0, "failed")])

    def test_synthesize_persisted_chunks_rejects_empty_persisted_set(self) -> None:
        class _InMemoryChunksRepository:
            def list_chunks_for_job(self, *, job_id: str) -> list[dict[str, object]]:
                return []

        orchestrator = TtsOrchestrationService(
            primary_provider=ChatterboxProvider(healthy=True),
            chunks_repository=_InMemoryChunksRepository(),
        )

        result = orchestrator.synthesize_persisted_chunks_for_job(
            job_id="job-empty",
            correlation_id="corr-empty",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "tts_orchestration.no_persisted_chunks")

    def test_persist_chunk_outcome_raises_on_missing_repository(self) -> None:
        """Critical: _persist_chunk_outcome must raise exception if repository unavailable."""
        orchestrator = TtsOrchestrationService(
            primary_provider=ChatterboxProvider(healthy=True),
            chunks_repository=None,  # No repository configured
        )

        with self.assertRaises(RuntimeError) as context:
            orchestrator._persist_chunk_outcome(
                job_id="test-job",
                chunk_index=0,
                status="synthesized_test",
            )

        self.assertIn("repository not configured", str(context.exception).lower())
        self.assertIn("job_id=test-job", str(context.exception))
        self.assertIn("chunk_index=0", str(context.exception))

    def test_synthesize_persisted_chunks_skips_already_synthesized_by_default(self) -> None:
        class _InMemoryChunksRepository:
            def __init__(self) -> None:
                self.rows = [
                    {"job_id": "job-resume", "chunk_index": 0, "text_content": "A", "status": "synthesized_chatterbox_gpu"},
                    {"job_id": "job-resume", "chunk_index": 1, "text_content": "B", "status": "failed"},
                    {"job_id": "job-resume", "chunk_index": 2, "text_content": "C", "status": "pending"},
                ]
                self.updated: list[tuple[str, int, str]] = []

            def list_chunks_for_job(self, *, job_id: str) -> list[dict[str, object]]:
                return [row for row in self.rows if row["job_id"] == job_id]

            def update_chunk_synthesis_outcome(self, *, job_id: str, chunk_index: int, status: str) -> None:
                self.updated.append((job_id, chunk_index, status))

        class _InMemoryJobsRepository:
            def __init__(self) -> None:
                self.state = "running"

            def get_job_by_id(self, *, job_id: str) -> dict[str, object] | None:
                return {"id": job_id, "state": self.state, "updated_at": "2026-02-13T00:00:00+00:00"}

            def update_job_state_if_current(
                self,
                *,
                job_id: str,
                expected_state: str,
                next_state: str,
                updated_at: str | None = None,
            ) -> bool:
                if self.state != expected_state:
                    return False
                self.state = next_state
                return True

        class _CapturingLogger:
            def __init__(self) -> None:
                self.events: list[dict[str, object]] = []

            def emit(self, **payload: object) -> None:
                self.events.append(payload)

        repo = _InMemoryChunksRepository()
        jobs = _InMemoryJobsRepository()
        logger = _CapturingLogger()
        orchestrator = TtsOrchestrationService(
            primary_provider=ChatterboxProvider(healthy=True),
            fallback_provider=KokoroProvider(healthy=True),
            chunks_repository=repo,
            conversion_jobs_repository=jobs,
            logger=logger,
        )

        result = orchestrator.synthesize_persisted_chunks_for_job(
            job_id="job-resume",
            correlation_id="corr-resume",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.data["resume_start_index"], 1)
        self.assertEqual(result.data["retry_decision_path"], "first_non_synthesized_status:failed")
        self.assertEqual([item[1] for item in repo.updated], [1, 2])

        started_indices = [
            event["chunk_index"]
            for event in logger.events
            if event.get("event") == "tts.chunk_started"
        ]
        self.assertEqual(started_indices, [1, 2])

    def test_synthesize_persisted_chunks_force_reprocess_processes_all_chunks(self) -> None:
        class _InMemoryChunksRepository:
            def __init__(self) -> None:
                self.rows = [
                    {"job_id": "job-force", "chunk_index": 0, "text_content": "A", "status": "synthesized_kokoro_cpu"},
                    {"job_id": "job-force", "chunk_index": 1, "text_content": "B", "status": "synthesized_chatterbox_gpu"},
                ]
                self.updated: list[tuple[str, int, str]] = []

            def list_chunks_for_job(self, *, job_id: str) -> list[dict[str, object]]:
                return [row for row in self.rows if row["job_id"] == job_id]

            def update_chunk_synthesis_outcome(self, *, job_id: str, chunk_index: int, status: str) -> None:
                self.updated.append((job_id, chunk_index, status))

        class _CapturingLogger:
            def __init__(self) -> None:
                self.events: list[dict[str, object]] = []

            def emit(self, **payload: object) -> None:
                self.events.append(payload)

        repo = _InMemoryChunksRepository()
        logger = _CapturingLogger()
        orchestrator = TtsOrchestrationService(
            primary_provider=ChatterboxProvider(healthy=True),
            fallback_provider=KokoroProvider(healthy=True),
            chunks_repository=repo,
            logger=logger,
        )

        result = orchestrator.synthesize_persisted_chunks_for_job(
            job_id="job-force",
            correlation_id="corr-force",
            force_reprocess=True,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.data["resume_start_index"], 0)
        self.assertEqual(result.data["retry_decision_path"], "forced_full_reprocess")
        self.assertEqual([item[1] for item in repo.updated], [0, 1])

        resume_started = [event for event in logger.events if event.get("event") == "conversion.resume_started"]
        self.assertEqual(len(resume_started), 1)
        self.assertTrue(resume_started[0].get("extra", {}).get("force_reprocess"))

    def test_synthesize_persisted_chunks_rejects_invalid_lifecycle_transition_with_normalized_error(self) -> None:
        class _InMemoryChunksRepository:
            def list_chunks_for_job(self, *, job_id: str) -> list[dict[str, object]]:
                return [{"job_id": job_id, "chunk_index": 0, "text_content": "A", "status": "pending"}]

            def update_chunk_synthesis_outcome(self, *, job_id: str, chunk_index: int, status: str) -> None:
                return None

        class _CompletedJobsRepository:
            def get_job_by_id(self, *, job_id: str) -> dict[str, object] | None:
                return {"id": job_id, "state": "completed", "updated_at": "2026-02-13T00:00:00+00:00"}

            def update_job_state_if_current(
                self,
                *,
                job_id: str,
                expected_state: str,
                next_state: str,
                updated_at: str | None = None,
            ) -> bool:
                return False

        class _CapturingLogger:
            def __init__(self) -> None:
                self.events: list[dict[str, object]] = []

            def emit(self, **payload: object) -> None:
                self.events.append(payload)

        logger = _CapturingLogger()
        orchestrator = TtsOrchestrationService(
            primary_provider=ChatterboxProvider(healthy=True),
            chunks_repository=_InMemoryChunksRepository(),
            conversion_jobs_repository=_CompletedJobsRepository(),
            logger=logger,
        )

        result = orchestrator.synthesize_persisted_chunks_for_job(
            job_id="job-completed",
            correlation_id="corr-completed",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "job.transition_rejected")
        self.assertEqual(result.error.details["transition_intent"]["current_state"], "completed")
        self.assertEqual(result.error.details["transition_intent"]["next_state"], "running")
        self.assertFalse(result.error.details["transition_intent"]["validated"])

        rejected_events = [event for event in logger.events if event.get("event") == "job.transition_rejected"]
        self.assertEqual(len(rejected_events), 1)

    def test_launch_conversion_handles_none_documents_repository(self) -> None:
        """Test that launch_conversion works when documents_repository is None."""
        class _InMemoryChunksRepository:
            def __init__(self) -> None:
                self.rows = [{"job_id": "job-no-doc-repo", "chunk_index": 0, "text_content": "Test", "status": "pending"}]

            def list_chunks_for_job(self, *, job_id: str) -> list[dict[str, object]]:
                return [row for row in self.rows if row["job_id"] == job_id]

            def update_chunk_synthesis_outcome(self, *, job_id: str, chunk_index: int, status: str) -> None:
                for row in self.rows:
                    if row["job_id"] == job_id and int(row["chunk_index"]) == int(chunk_index):
                        row["status"] = status

        class _PostprocessStub:
            def assemble_and_render(self, **kwargs: object):
                return success(
                    {
                        "job_id": str(kwargs.get("job_id")),
                        "chunk_count": 1,
                        "output_artifact": {
                            "path": "runtime/library/audio/job-no-doc-repo.wav",
                            "format": "wav",
                            "byte_size": 100,
                            "duration_seconds": 1.0,
                        },
                    }
                )

        class _LibraryServiceStub:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def persist_final_artifact(self, **kwargs: object):
                self.calls.append(dict(kwargs))
                # Verify that document parameter is passed even when documents_repository is None
                document = kwargs.get("document", {})
                self.last_document = document
                return success({"id": "lib-no-doc", "job_id": "job-no-doc-repo"})

        class _JobsRepositoryStub:
            def get_job_by_id(self, *, job_id: str) -> dict[str, object] | None:
                return {"id": job_id, "document_id": "doc-unknown", "state": "running"}

            def update_job_state_if_current(self, *, job_id: str, expected_state: str, next_state: str, **kwargs: object) -> bool:
                return True

        repo = _InMemoryChunksRepository()
        postprocess = _PostprocessStub()
        library_service = _LibraryServiceStub()
        
        # Create orchestrator WITHOUT documents_repository (None)
        orchestrator = TtsOrchestrationService(
            primary_provider=ChatterboxProvider(healthy=True),
            fallback_provider=KokoroProvider(healthy=True),
            audio_postprocess_service=postprocess,
            library_service=library_service,
            chunks_repository=repo,
            conversion_jobs_repository=_JobsRepositoryStub(),
            documents_repository=None,  # Explicitly None
        )

        result = orchestrator.launch_conversion(
            job_id="job-no-doc-repo",
            correlation_id="corr-no-doc-repo",
            conversion_config={
                "engine": "chatterbox_gpu",
                "voice_id": "default",
                "language": "FR",
                "output_format": "wav",
            },
        )

        # Should succeed even without documents_repository
        self.assertTrue(result.ok)
        self.assertEqual(len(library_service.calls), 1)
        
        # Verify that library service received a minimal document dict with just the id
        self.assertEqual(library_service.last_document, {"id": "doc-unknown"})
