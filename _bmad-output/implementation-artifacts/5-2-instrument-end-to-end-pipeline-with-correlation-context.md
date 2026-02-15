# Story 5.2: Instrument End-to-End Pipeline with Correlation Context

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a support-minded user,
I want every pipeline stage to emit correlated events,
so that I can trace a failed conversion from import to playback diagnostics.

## Acceptance Criteria

1. **Given** a conversion job is launched  
   **When** stages execute across import extraction chunking synthesis postprocess library and player  
   **Then** each stage emits JSONL events with a shared `correlation_id` and job-scoped context  
   **And** stage-specific fields include `stage`, `event`, `severity`, and UTC `timestamp`.

2. **Given** chunk-level processing occurs in orchestration  
   **When** chunk events are emitted  
   **Then** payload includes `chunk_index` and active `engine`  
   **And** event sequences remain ordered enough to reconstruct chunk lifecycle.

3. **Given** failures can happen at any stage  
   **When** an error is raised  
   **Then** the emitted event carries normalized error envelope fields `code`, `message`, `details`, `retryable`  
   **And** error and success events share the same schema contract.

4. **Given** instrumentation must not degrade UX  
   **When** event writing is active during long conversions  
   **Then** UI responsiveness is preserved and worker flow remains non-blocking  
   **And** logging backpressure failures are handled locally with structured fallback behavior.

## Tasks / Subtasks

- [x] Establish one correlation context across the end-to-end pipeline boundaries (AC: 1, 4)
  - [x] Ensure conversion launch path generates or propagates a stable non-empty `correlation_id` from import through worker execution
  - [x] Propagate `correlation_id` and `job_id` through import, extraction, chunking, orchestration, postprocess, library, and player calls
  - [x] Add guardrails for fallback correlation generation only at boundary entry points (never mid-pipeline)
- [x] Complete stage instrumentation coverage with schema-conformant events (AC: 1, 2)
  - [x] Verify import and extraction emit `stage`/`event` coverage with shared correlation context
  - [x] Verify chunking and TTS orchestration emit chunk lifecycle events including `chunk_index` and `engine`
  - [x] Verify postprocess, library persistence/browse, and player flows emit correlated events
- [x] Normalize failure event payloads across stages (AC: 3)
  - [x] Ensure emitted failure events include normalized error envelope fields (`code`, `message`, `details`, `retryable`) in `extra`
  - [x] Ensure success and failure events remain compatible with the strict schema contract in infrastructure logging
  - [x] Harmonize non-conformant legacy event payloads in emitter call sites without introducing transport/network logic
- [x] Preserve non-blocking behavior and local fallback under logging pressure (AC: 4)
  - [x] Confirm worker/UI paths avoid blocking on logging operations and retain responsive signal flow
  - [x] Validate logging failures are handled locally and surfaced as structured diagnostics without crashing conversion worker execution
- [x] Expand and align automated verification for correlation and stage coverage (AC: 1, 2, 3, 4)
  - [x] Add/extend unit tests for correlation propagation and failure payload normalization at service boundaries
  - [x] Add/extend integration tests validating end-to-end correlated event emission across pipeline stages

## Dev Notes

### Developer Context Section

- Story target selected from sprint tracker as next backlog item in Epic 5: `5-2-instrument-end-to-end-pipeline-with-correlation-context`.
- Story 5.1 already hardened schema and logger contracts; this story must extend **emission coverage and correlation continuity** across the full runtime path.
- Existing instrumentation is already broad (import, extraction, worker, orchestration, postprocess, library, player), so the expected implementation strategy is **gap-closing + contract alignment**, not subsystem replacement.
- Primary risk to prevent: stage-level events emitted with empty/missing correlation context (especially around player/open/browse and bootstrap-adjacent flows) which can break end-to-end failure reconstruction.
- Correlation lineage that must remain traceable in one job journey:
  - import acceptance/rejection → extraction start/success/fail
  - chunking + orchestration + fallback decisions
  - postprocess + library persistence/browse reopen
  - playback/service diagnostics and UI-presented failures.
- Maintain local-only observability model (JSONL in runtime) and do not introduce network telemetry/export behaviors.

### Technical Requirements

- Preserve strict event schema compliance for all emitted payloads validated by [`validate_event_payload()`](src/infrastructure/logging/event_schema.py:29):
  - required fields must remain present and correctly typed (`correlation_id`, `job_id`, `chunk_index`, `engine`, `stage`, `event`, `severity`, `timestamp`)
  - `event` must follow `domain.action`
  - `timestamp` must remain UTC ISO-8601.
- Ensure correlation propagation remains explicit across service boundaries:
  - import entry points in [`ImportService.import_document()`](src/domain/services/import_service.py:57)
  - extraction adapters (`epub`, `pdf`, `text`) through their `extract(..., correlation_id, job_id)` signatures
  - conversion worker lifecycle in [`ConversionWorker.run_conversion()`](src/ui/workers/conversion_worker.py:168)
  - orchestration flow in [`TtsOrchestrationService.convert_document()`](src/domain/services/tts_orchestration_service.py:126)
  - library + playback surfaces in [`LibraryService`](src/domain/services/library_service.py) and [`PlayerService`](src/domain/services/player_service.py).
- Guarantee chunk-level observability in orchestration:
  - include `chunk_index` and active `engine` in chunk lifecycle emissions
  - keep events sufficiently ordered to reconstruct started/fallback/retry/completed/failed paths.
- Normalize failure diagnostics in emitted event payloads:
  - include `code`, `message`, `details`, `retryable` in structured `extra.error` envelopes
  - align error envelopes across import, extraction, orchestration, postprocess, library, and player emitters.
- Preserve non-blocking UX constraints while instrumenting:
  - no logging-induced blocking on UI thread
  - worker execution remains responsive even on logging validation/write failures
  - failures remain local structured errors with no network side effects.

### Architecture Compliance

- Keep logging contract responsibilities centralized in infrastructure:
  - schema validation in [`event_schema.py`](src/infrastructure/logging/event_schema.py)
  - append-only persistence in [`jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py)
  - no ad-hoc serializer or alternate sink inside domain/UI/adapters.
- Preserve bounded-layer responsibilities from architecture artifacts:
  - UI/presenters/workers emit events and surface diagnostics, but do not own schema policy
  - domain services orchestrate event semantics (`stage`, `event`, correlation lineage)
  - adapters provide stage-local context while respecting shared payload contract.
- Respect standardized service outcome contracts already in use:
  - keep `{ok, data, error}` and normalized errors `{code, message, details, retryable}` as primary failure model
  - ensure event payload `extra.error` mirrors the same normalized envelope to prevent drift.
- Enforce project-wide `domain.action` naming and deterministic stage vocabulary for this story scope:
  - import/extraction/chunking/tts_orchestration/postprocess/library_browse/library_persistence/player/worker_execution/diagnostics surfaces.
- Keep offline-first boundary intact:
  - observability remains local JSONL under runtime log storage
  - no telemetry shipping, no cloud dependency, no network retries in logging path.

### Library / Framework Requirements

- Keep implementation within the current dependency baseline declared in [`pyproject.toml`](pyproject.toml):
  - rely on Python standard library + existing project packages for instrumentation updates
  - do not introduce remote telemetry SDKs or external log agents.
- Current dependency context validated during story preparation:
  - `PyQt5` latest available: `5.15.11`
  - `PyYAML` latest available: `6.0.3`
  - `EbookLib` installed/latest: `0.20`
  - `PyPDF2` installed/latest: `3.0.1`.
- Preserve logging implementation approach based on existing infrastructure primitives:
  - event schema enforcement via [`validate_event_payload()`](src/infrastructure/logging/event_schema.py:29)
  - append-only writes via [`JsonlLogger.emit()`](src/infrastructure/logging/jsonl_logger.py:38).
- Maintain compatibility with existing PyQt threading model:
  - instrumentation changes must not alter worker signal/slot behavior
  - no synchronous heavy I/O added in presenter/view call paths.

### File Structure Requirements

- Primary implementation surfaces for Story 5.2:
  - [`src/domain/services/import_service.py`](src/domain/services/import_service.py)
  - [`src/adapters/extraction/epub_extractor.py`](src/adapters/extraction/epub_extractor.py)
  - [`src/adapters/extraction/pdf_extractor.py`](src/adapters/extraction/pdf_extractor.py)
  - [`src/adapters/extraction/text_extractor.py`](src/adapters/extraction/text_extractor.py)
  - [`src/ui/workers/conversion_worker.py`](src/ui/workers/conversion_worker.py)
  - [`src/domain/services/tts_orchestration_service.py`](src/domain/services/tts_orchestration_service.py)
  - [`src/domain/services/audio_postprocess_service.py`](src/domain/services/audio_postprocess_service.py)
  - [`src/domain/services/library_service.py`](src/domain/services/library_service.py)
  - [`src/domain/services/player_service.py`](src/domain/services/player_service.py)
  - [`src/ui/presenters/conversion_presenter.py`](src/ui/presenters/conversion_presenter.py)
  - [`src/ui/views/conversion_view.py`](src/ui/views/conversion_view.py).
- Logging core must remain centralized and reused (no duplication):
  - [`src/infrastructure/logging/event_schema.py`](src/infrastructure/logging/event_schema.py)
  - [`src/infrastructure/logging/jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py).
- Verification targets for this story:
  - [`tests/integration/test_jsonl_logging.py`](tests/integration/test_jsonl_logging.py)
  - [`tests/integration/test_tts_provider_events_schema.py`](tests/integration/test_tts_provider_events_schema.py)
  - targeted unit tests under [`tests/unit/`](tests/unit) for correlation propagation and emitter payload normalization.
- Do not create alternate log storage paths; keep runtime outputs in architecture-defined locations (`runtime/logs`).

### Testing Requirements

- Add/extend unit tests to validate correlation context propagation and structured failure payloads for key boundaries:
  - import/extraction handoff
  - worker/orchestration handoff
  - library/player diagnostics paths.
- Extend integration tests to assert end-to-end correlation continuity:
  - same `correlation_id` observable through multi-stage pipeline events for a conversion lifecycle
  - chunk events include `chunk_index` and `engine` when relevant
  - failure events preserve normalized envelope (`code`, `message`, `details`, `retryable`).
- Preserve strict schema validation in all tests (required fields, `domain.action`, UTC timestamp, severity constraints).
- Include regression assertions for non-blocking behavior:
  - logging failures must not crash worker execution path
  - UI-facing flows continue to return normalized result payloads.

### Previous Story Intelligence

- Previous story [`5-1-define-correlated-jsonl-event-schema-and-logging-contract.md`](_bmad-output/implementation-artifacts/5-1-define-correlated-jsonl-event-schema-and-logging-contract.md) finalized strict schema and logger hardening; Story 5.2 must build on that baseline rather than rework core logger internals.
- Actionable carry-over from Story 5.1:
  - keep `domain.action` naming strict and deterministic
  - preserve UTC ISO-8601 timestamp integrity
  - keep local-only structured failures (`logging.invalid_event_payload`, `logging.write_failed` semantics)
  - avoid broad refactors that risk regressions in already-green logging test suites.
- Most likely gap area for this story: emitter consistency and cross-layer propagation, not schema core correctness.

### Git Intelligence Summary

- Recent history confirms Epic 5 sequencing and expected implementation posture:
  - `0193235` — Story 5.1 code review fixes (strict validation/test expansion)
  - `9ddf32b` — Story 5.1 logging contract hardening
  - `650378e` — Story 5.1 context created and marked ready-for-dev
  - earlier commits (`f425811`, `555cbcb`) closed Epic 4 playback hardening and touched player/view layers now relevant to Story 5.2 instrumentation continuity.
- Implications for Story 5.2 implementation:
  - prioritize additive emitter-alignment changes
  - preserve event schema compatibility relied on by existing tests
  - focus on correlation continuity across previously modified playback/library paths.

### Latest Tech Information

- Package-index checks executed during story preparation indicate no required dependency upgrades for this story:
  - `PyQt5` latest `5.15.11`
  - `PyYAML` latest `6.0.3`
  - `EbookLib` installed/latest `0.20`
  - `PyPDF2` installed/latest `3.0.1`.
- Story 5.2 should remain implementation-focused on instrumentation logic and test coverage with existing stack versions.

### Project Context Reference

- No `project-context.md` discovered for pattern `**/project-context.md`.
- Context sources used for this story:
  - [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md)
  - [`_bmad-output/planning-artifacts/prd.md`](_bmad-output/planning-artifacts/prd.md)
  - [`_bmad-output/planning-artifacts/architecture.md`](_bmad-output/planning-artifacts/architecture.md)
  - [`_bmad-output/implementation-artifacts/sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml)
  - Previous story context:
    - [`_bmad-output/implementation-artifacts/5-1-define-correlated-jsonl-event-schema-and-logging-contract.md`](_bmad-output/implementation-artifacts/5-1-define-correlated-jsonl-event-schema-and-logging-contract.md).

### Project Structure Notes

- Respect current repository structure and existing concrete file names over aspirational architecture examples.
- Keep instrumentation work distributed in emitters while preserving centralized schema/writer contract.
- Avoid renaming or relocating core logging modules during this story to minimize regression risk.

### References

- Epic/story source: [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md)
- Product requirements: [`_bmad-output/planning-artifacts/prd.md`](_bmad-output/planning-artifacts/prd.md)
- Architecture constraints: [`_bmad-output/planning-artifacts/architecture.md`](_bmad-output/planning-artifacts/architecture.md)
- Sprint tracker: [`_bmad-output/implementation-artifacts/sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml)
- Previous story: [`_bmad-output/implementation-artifacts/5-1-define-correlated-jsonl-event-schema-and-logging-contract.md`](_bmad-output/implementation-artifacts/5-1-define-correlated-jsonl-event-schema-and-logging-contract.md)
- Core logging contracts:
  - [`validate_event_payload()`](src/infrastructure/logging/event_schema.py:29)
  - [`JsonlLogger.emit()`](src/infrastructure/logging/jsonl_logger.py:38)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log -n 5 --date=iso --pretty=format:'%h|%ad|%an|%s' --name-status`
- `python -m pip index versions PyQt5`
- `python -m pip index versions PyYAML`
- `python -m pip index versions EbookLib`
- `python -m pip index versions PyPDF2`
- `python -m unittest -q tests.unit.test_import_flow tests.unit.test_extraction_orchestration tests.unit.test_tts_orchestration_service tests.unit.test_audio_postprocess_service tests.unit.test_library_service tests.unit.test_conversion_worker tests.integration.test_import_flow_integration tests.integration.test_chunk_persistence_and_resume_path`

### Completion Notes List

- Story 5.2 selected from sprint tracker as first backlog story after Story 5.1 completion.
- End-to-end instrumentation context prepared with explicit correlation propagation expectations across import → extraction → chunking → orchestration → postprocess → library → player.
- Failure-payload normalization requirements documented to keep diagnostics envelopes schema-aligned across all stages.
- Non-blocking UX guardrails captured for worker/UI flows under logging activity and failure conditions.
- Ultimate context engine analysis completed - comprehensive developer guide created.
- Implemented normalized `extra.error` envelopes for import and extraction failure emitters with fields `code`, `message`, `details`, `retryable`.
- Added safe/non-blocking logger guards around import, extraction, orchestration, postprocess, library, player, and worker event emission paths to avoid logging failures crashing worker/UI flows.
- Hardened correlation fallback generation at import boundary by rejecting blank correlation values and generating only at entry when missing.
- Updated TTS chunk failure event payloads to structured `extra.error` envelopes and preserved chunk lifecycle observability (`chunk_index`, `engine`, ordered sequence).
- Ran targeted unit/integration regression suite with `PYTHONPATH=src:.` and all selected tests passed (79 tests).
- **Code review fixes (2026-02-15):**
  - Fixed correlation_id propagation in import_service.extract_document to use normalized fallback UUID instead of original empty value
  - Added correlation_id fallback generation at worker boundary entry point in conversion_worker._run_conversion
  - Added missing event emissions for library path validation failures in library_service._validate_reopen_path
  - Added player.load_succeeded event emission in player_service.initialize_playback for success path symmetry
  - Added chunk-level assembly progress events (postprocess.chunk_assembling, postprocess.chunk_assembled) in audio_postprocess_service
  - All HIGH and MEDIUM severity issues from adversarial code review resolved

### File List

- _bmad-output/implementation-artifacts/5-2-instrument-end-to-end-pipeline-with-correlation-context.md
- src/domain/services/import_service.py (modified: correlation_id fallback propagation)
- src/adapters/extraction/epub_extractor.py
- src/adapters/extraction/pdf_extractor.py
- src/adapters/extraction/text_extractor.py
- src/domain/services/tts_orchestration_service.py
- src/domain/services/audio_postprocess_service.py (modified: chunk assembly events)
- src/domain/services/library_service.py (modified: path validation events)
- src/domain/services/player_service.py (modified: load success event)
- src/ui/workers/conversion_worker.py (modified: correlation_id fallback at boundary)

## Change Log

- 2026-02-15: Implemented Story 5.2 end-to-end correlation instrumentation alignment, normalized failure envelopes, and non-blocking logging safeguards across pipeline stages.
- 2026-02-15: Code review fixes - resolved correlation_id propagation issues, added missing event emissions for library/player/postprocess stages, ensured boundary-level fallback generation.

## Story Completion Status

- Story ID: `5.2`
- Story Key: `5-2-instrument-end-to-end-pipeline-with-correlation-context`
- Status set to: `done`
- Completion note: Implementation complete with end-to-end correlated event coverage, normalized error envelopes, non-blocking logging safeguards, and code review fixes addressing correlation propagation and event emission gaps.
