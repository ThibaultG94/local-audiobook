# Story 3.6: Execute Conversion in Dedicated Worker with Non-Blocking UI Signals

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user running long conversion tasks,
I want conversion to run in a dedicated worker thread with live progress feedback,
so that the interface stays responsive while processing continues.

## Acceptance Criteria

1. **Given** conversion starts from the UI  
   **When** execution is launched through `conversion_worker.py`  
   **Then** processing runs in a dedicated QThread separate from the UI thread  
   **And** no blocking operation is performed on the main event loop.

2. **Given** orchestration emits chunk progress and state updates  
   **When** worker signals are propagated to `conversion_presenter.py` and `conversion_view.py`  
   **Then** progress percentage and status are updated incrementally  
   **And** users can observe running paused failed completed states in near real time.

3. **Given** runtime errors occur in worker execution  
   **When** exceptions or normalized failures are received from `tts_orchestration_service.py`  
   **Then** errors are relayed through Qt signals with normalized payload structure  
   **And** UI messaging remains actionable and English-only for MVP.

4. **Given** observability requirements for async execution  
   **When** worker starts emits progress fails or completes  
   **Then** JSONL events are written by `jsonl_logger.py` with `stage=worker_execution` and `domain.action` events  
   **And** each event includes `correlation_id`, `job_id`, `chunk_index` when applicable, `event`, `severity`, and ISO-8601 UTC `timestamp`.

## Tasks / Subtasks

- [x] Implement dedicated conversion execution thread aligned with Qt patterns (AC: 1)
  - [x] Ensure conversion launch path uses `QThread`/worker object separation and does not run heavy work on the UI thread.
  - [x] Preserve thread-safe callback dispatch to the UI layer for state updates.
- [x] Add incremental progress/state propagation from worker to presenter/view (AC: 2)
  - [x] Emit deterministic progress events that include chunk-level context when available.
  - [x] Map worker state transitions to UI-facing statuses (`running`, `paused`, `failed`, `completed`) without blocking.
- [x] Normalize worker error propagation and user-facing messaging (AC: 3)
  - [x] Convert runtime exceptions into normalized `{code, message, details, retryable}` payloads.
  - [x] Ensure presenter/view error text remains actionable and English-only.
- [x] Instrument worker execution observability with correlated JSONL events (AC: 4)
  - [x] Emit `worker_execution.started`, `worker_execution.progressed`, `worker_execution.failed`, `worker_execution.completed`.
  - [x] Include required correlation fields and UTC timestamps in every event.
- [x] Add unit/integration tests for non-blocking behavior, signal propagation, and error normalization (AC: 1..4)
  - [x] Validate execution does not block the main thread.
  - [x] Validate progress updates and state transitions are deterministic.
  - [x] Validate normalized failures and event schema compliance.

## Dev Notes

### Developer Context Section

- This story is the execution-path continuation of Story 3.5 and must preserve validated configuration handoff semantics from the worker launch boundary.
- Current code already provides a framework-neutral background worker in `src/ui/workers/conversion_worker.py`; this story hardens it into explicit Qt-aligned execution behavior while preserving testability.
- Keep orchestration ownership intact: fallback policy and chunk ordering stay in `src/domain/services/tts_orchestration_service.py`, not in UI components.
- Preserve normalized result/error contracts from `src/contracts/result.py` and `src/contracts/errors.py` for all worker-to-UI failure paths.

### Technical Requirements

- Worker execution must remain non-blocking for UI, with long-running conversion work isolated from main event processing.
- Worker must propagate progress increments and lifecycle state changes (`queued` → `running` → `paused`/`failed`/`completed`) through deterministic signal/callback channels.
- Runtime exceptions from worker execution must be normalized before reaching presenter/view.
- Conversion launch configuration produced by Story 3.5 (`engine`, `voice_id`, `language`, `speech_rate`, `output_format`) remains immutable once worker execution begins.
- Event logging for worker execution must follow architecture schema fields:
  `correlation_id`, `job_id`, `chunk_index`, `engine`, `stage`, `event`, `severity`, `timestamp`.

### Architecture Compliance

- Respect layer boundaries:
  - UI state/rendering in presenter/view
  - asynchronous execution in worker
  - conversion orchestration logic in domain service
  - persistence/logging in adapters/infrastructure
- Do not move fallback decision logic from `tts_orchestration_service` into worker.
- Keep naming and payload patterns aligned with architecture conventions (`snake_case`, `domain.action`, ISO-8601 UTC timestamps).
- Ensure worker enhancements do not regress previously validated resume and job-lifecycle behavior from Story 3.4.

### Library / Framework Requirements

- Use existing project stack only; no new dependency is required.
- Keep logger usage centralized through existing JSONL infrastructure.
- Maintain compatibility with repository and launcher interfaces already used by `ConversionWorker`.

### File Structure Requirements

- Primary implementation targets:
  - `src/ui/workers/conversion_worker.py`
  - `src/ui/presenters/conversion_presenter.py`
  - `src/ui/views/conversion_view.py`
  - `src/domain/services/tts_orchestration_service.py` (only if event/state propagation contract updates are required)
- Test targets:
  - `tests/unit/test_conversion_worker.py`
  - `tests/unit/test_conversion_presenter.py`
  - `tests/unit/test_conversion_view.py`
  - relevant integration tests in `tests/integration/` for worker execution path and observability.

### Testing Requirements

- Unit tests should verify:
  - worker execution occurs off main thread,
  - progress/state updates are emitted deterministically,
  - normalized errors are returned on worker exceptions,
  - missing/invalid payload handling still fails fast.
- Integration tests should verify:
  - launch path persists job configuration then starts async execution,
  - UI-facing state can be refreshed from worker signals without blocking,
  - worker execution events follow JSONL schema and `domain.action` naming.

### Previous Story Intelligence

- Story 3.5 introduced strict configuration validation, immutable handoff payloads, and configuration-stage observability.
- Preserve these guarantees when wiring asynchronous execution.
- Do not bypass presenter validation by creating alternate worker entry points.

### Git Intelligence Summary

- Recent commits indicate active stabilization in this sequence:
  - Story 3.5 implementation and review hardening,
  - Story 3.4 resume/lifecycle stabilization.
- Implementation strategy should remain minimally invasive and regression-safe by extending existing worker and tests rather than replacing them.

### Latest Tech Information

- For this story scope, no mandatory dependency-version upgrade is required.
- Focus is execution correctness and UI responsiveness under current stack.
- If Qt threading semantics are adjusted, keep behavior testable in non-Qt unit tests via abstraction-friendly callbacks.

### Project Context Reference

- No `project-context.md` file was found via configured discovery pattern.
- Context for this story is derived from planning artifacts, architecture decisions, sprint status, previous story output, recent commits, and current codebase.

### References

- Story source: [epics.md](_bmad-output/planning-artifacts/epics.md)
- Product constraints: [prd.md](_bmad-output/planning-artifacts/prd.md)
- Architecture constraints: [architecture.md](_bmad-output/planning-artifacts/architecture.md)
- Sprint tracking: [sprint-status.yaml](_bmad-output/implementation-artifacts/sprint-status.yaml)
- Previous story: [3-5-configure-conversion-parameters-and-output-format-in-ui.md](_bmad-output/implementation-artifacts/3-5-configure-conversion-parameters-and-output-format-in-ui.md)
- Worker baseline: [conversion_worker.py](src/ui/workers/conversion_worker.py)
- Presenter baseline: [conversion_presenter.py](src/ui/presenters/conversion_presenter.py)
- View baseline: [conversion_view.py](src/ui/views/conversion_view.py)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log -n 5 --pretty=format:'%h|%s' --name-only`
- `PYTHONPATH=src python -m unittest tests.unit.test_conversion_worker tests.unit.test_conversion_presenter tests.unit.test_conversion_view tests.unit.test_tts_orchestration_service tests.integration.test_conversion_configuration_integration`
- `PYTHONPATH=src python -m unittest discover -s tests`

### Completion Notes List

- Story selected from first backlog entry in sprint status: `3-6-execute-conversion-in-dedicated-worker-with-non-blocking-ui-signals`.
- Comprehensive context assembled from epics, architecture, PRD, previous implementation artifacts, and current source/testing baseline.
- Implemented asynchronous conversion execution path in worker with dedicated background execution, thread-safe dispatch hooks for UI callbacks, and lifecycle signal propagation (`running`/`failed`/`completed`).
- Added deterministic worker progress signaling with chunk-level context and orchestration callback support while preserving orchestration ownership in domain service.
- Added normalized worker failure propagation for launcher exceptions and orchestration failures with `{code, message, details, retryable}` payloads.
- Added worker execution observability events (`worker_execution.started`, `worker_execution.progressed`, `worker_execution.failed`, `worker_execution.completed`) with correlated fields and UTC timestamps.
- Extended presenter/view mapping for conversion progress/state/error and enforced actionable English error payloads at UI mapping boundary.
- Added and updated unit/integration tests for non-blocking execution semantics, signal propagation, error normalization, and JSONL schema compliance; full test suite passed.

### File List

- _bmad-output/implementation-artifacts/3-6-execute-conversion-in-dedicated-worker-with-non-blocking-ui-signals.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/domain/services/tts_orchestration_service.py
- src/ui/presenters/conversion_presenter.py
- src/ui/views/conversion_view.py
- src/ui/workers/conversion_worker.py
- tests/integration/test_conversion_configuration_integration.py
- tests/unit/test_conversion_presenter.py
- tests/unit/test_conversion_view.py
- tests/unit/test_conversion_worker.py

## Change Log

- 2026-02-13: Story 3.6 context created with full implementation guidance and status `ready-for-dev`.
- 2026-02-13: Implemented dedicated async conversion worker execution, worker_execution observability, conversion state/progress/error UI mappings, and related unit/integration coverage; story moved to `review`.
- 2026-02-13: Code review completed - Fixed 10 issues: corrected import paths in `tts_orchestration_service.py` and test files, documented `progress_callback` parameter in `ConversionLauncherPort`, improved type validation in `_invoke_launcher`, enhanced `dispatch_to_main` documentation with Qt example. All tests passing (23/23).

## Story Completion Status

- Status set to: `review`
- Completion note: All ACs implemented and validated with full automated test pass (`148/148`).
