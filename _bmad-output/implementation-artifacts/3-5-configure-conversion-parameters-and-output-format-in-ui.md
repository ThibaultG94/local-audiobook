# Story 3.5: Configure Conversion Parameters and Output Format in UI

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user preparing conversion,
I want to select engine voice language speech rate and output format,
so that generated audio matches my preferences and playback context.

## Acceptance Criteria

1. **Given** available engines and voices are exposed by `tts_provider.py`
   **When** I open conversion controls in `conversion_view.py`
   **Then** I can select engine Chatterbox or Kokoro and a compatible voice
   **And** unavailable options are visibly disabled with explanatory guidance.

2. **Given** MVP language scope and parameter constraints
   **When** I configure synthesis options via `conversion_presenter.py`
   **Then** selectable languages are limited to FR and EN
   **And** speech rate accepts only validated bounds with normalized error feedback on invalid input.

3. **Given** output generation supports MP3 and WAV
   **When** I choose output format before launch
   **Then** selected format is persisted with job configuration
   **And** orchestration receives normalized settings payload for synthesis and post-processing.

4. **Given** parameter and format choices must be auditable
   **When** configuration is saved or rejected
   **Then** JSONL events are emitted by `jsonl_logger.py` with `stage=configuration` and stable `domain.action` events
   **And** payload includes `correlation_id`, `job_id`, `event`, `severity`, and ISO-8601 UTC `timestamp`.

## Tasks / Subtasks

- [x] Add conversion parameter state model and validation contract in presenter layer (AC: 1, 2, 3)
  - [x] Introduce a normalized `conversion_config` payload in `conversion_presenter.py` containing `engine`, `voice_id`, `language`, `speech_rate`, `output_format`.
  - [x] Enforce language whitelist (`FR`, `EN`) and bounded `speech_rate` validation returning normalized errors `{code, message, details, retryable}`.
- [x] Extend conversion view control state and option availability mapping (AC: 1, 2)
  - [x] Add UI-facing option descriptors in `conversion_view.py` for engines, voices, languages, speech-rate range, and output formats.
  - [x] Ensure unavailable engine/voice combinations are disabled with deterministic explanatory text.
- [x] Persist validated settings in conversion job configuration before worker launch (AC: 3)
  - [x] Persist selected `output_format` and synthesis parameters to the job record used by orchestration.
  - [x] Confirm worker launch path receives immutable normalized settings payload.
- [x] Emit structured configuration observability events (AC: 4)
  - [x] Emit `configuration.saved` and `configuration.rejected` via JSONL logger with required schema fields.
  - [x] Include `correlation_id`, `job_id`, `stage=configuration`, `event`, `severity`, and ISO-8601 UTC timestamp.
- [x] Add unit/integration tests covering validation, UI mapping, persistence handoff, and logging schema (AC: 1..4)
  - [x] Extend presenter and view tests for options, disabled states, and language/speech-rate validation boundaries.
  - [x] Add worker/orchestration handoff tests verifying persisted format and config payload consistency.
  - [x] Assert emitted configuration events comply with event schema and `domain.action` naming.

## Dev Notes

### Developer Context Section

- This story is the UI configuration bridge between completed orchestration capabilities in Epic 3 and upcoming worker-execution hardening in Story 3.6.
- Existing readiness rendering logic in [`ConversionView`](src/ui/views/conversion_view.py:32) and mapping in [`ConversionPresenter.map_readiness()`](src/ui/presenters/conversion_presenter.py:22) should be extended, not replaced.
- The TTS contract already exists in [`TtsProvider`](src/domain/ports/tts_provider.py:43); engine and voice selectors must consume canonical provider outputs instead of introducing a new schema.
- Keep the result/error contract stable via [`Result`](src/contracts/result.py) and normalized error objects in [`errors`](src/contracts/errors.py); do not return raw exceptions to UI state.
- UI remains English-only for MVP (labels and remediation text), while accepted synthesis languages remain exactly FR and EN.
- This story must preserve non-blocking behavior: configuration validation/mapping can happen synchronously in presenter/view state, but conversion execution still runs through worker flow in [`ConversionWorker`](src/ui/workers/conversion_worker.py:17).

### Technical Requirements

- Implement a canonical configuration payload passed from presenter/view toward orchestration with fields:
  - `engine`: one of `chatterbox_gpu`, `kokoro_cpu`
  - `voice_id`: provider-returned identifier compatible with selected engine
  - `language`: one of `FR`, `EN`
  - `speech_rate`: validated numeric value in bounded MVP-safe range
  - `output_format`: one of `mp3`, `wav`
- Validation failures must return normalized envelopes through [`failure()`](src/contracts/result.py:34) with error shape `{code, message, details, retryable}` and actionable local remediation.
- Persist selected parameters with conversion job configuration before conversion launch, so downstream orchestration can reproduce runs deterministically.
- Ensure rejected configurations do not trigger worker execution and always surface deterministic UI state.
- Emit observability events at configuration stage for both accepted and rejected paths with schema-required fields and UTC ISO-8601 timestamps.

### Architecture Compliance

- Keep orchestration policy boundaries intact: parameter selection/validation belongs to presenter/view flow, while synthesis/fallback policy remains in [`tts_orchestration_service.py`](src/domain/services/tts_orchestration_service.py:1).
- Respect UI separation patterns already present:
  - view state holder in [`ConversionView`](src/ui/views/conversion_view.py:32),
  - mapping/normalization in [`ConversionPresenter`](src/ui/presenters/conversion_presenter.py:16),
  - asynchronous execution path in [`ConversionWorker`](src/ui/workers/conversion_worker.py:17).
- Maintain canonical contract usage from [`TtsProvider`](src/domain/ports/tts_provider.py:43) for engine and voice discovery; do not invent provider-specific UI contracts.
- Preserve normalized service contracts (`{ok,data,error}` and structured error payload) across all configuration entry points.
- Keep event naming in `domain.action` format and stage tagging aligned with architecture observability rules.

### Library / Framework Requirements

- Use existing project stack only (Python + current UI/domain modules); no new third-party dependency is needed for this story.
- Reuse provider contract and existing adapters surfaced through [`TtsProvider`](src/domain/ports/tts_provider.py:43) and container wiring in [`dependency_container.py`](src/app/dependency_container.py:1).
- Keep structured logging through current logger infrastructure (JSONL) and avoid ad-hoc file writes for diagnostics.
- Keep compatibility with current contract helpers in [`result.py`](src/contracts/result.py:1) and [`errors.py`](src/contracts/errors.py:1) for deterministic UI feedback.

### File Structure Requirements

- Primary implementation targets:
  - [`conversion_presenter.py`](src/ui/presenters/conversion_presenter.py)
  - [`conversion_view.py`](src/ui/views/conversion_view.py)
  - [`conversion_worker.py`](src/ui/workers/conversion_worker.py) (handoff boundary checks only)
  - supporting orchestration input contract in [`tts_orchestration_service.py`](src/domain/services/tts_orchestration_service.py:1) if settings payload shape must be consumed.
- Test targets:
  - [`test_conversion_presenter.py`](tests/unit/test_conversion_presenter.py)
  - [`test_conversion_view.py`](tests/unit/test_conversion_view.py)
  - [`test_conversion_worker.py`](tests/unit/test_conversion_worker.py)
  - integration scenario updates under [`tests/integration`](tests/integration) for configuration persistence/handoff.
- Keep UI configuration logic out of repositories and provider adapters.
- Preserve established project layout and naming conventions (`snake_case` modules, normalized payload keys).

### Testing Requirements

- Unit tests in [`test_conversion_presenter.py`](tests/unit/test_conversion_presenter.py):
  - valid configuration mapping for engine/voice/language/speech-rate/output-format,
  - rejection for unsupported language values,
  - rejection for out-of-range speech-rate values,
  - normalized error envelope assertions.
- Unit tests in [`test_conversion_view.py`](tests/unit/test_conversion_view.py):
  - option availability state for engine/voice compatibility,
  - disabled controls and explanatory guidance for unavailable choices,
  - deterministic state updates when config accepted/rejected.
- Unit tests in [`test_conversion_worker.py`](tests/unit/test_conversion_worker.py):
  - handoff receives validated immutable configuration payload,
  - rejected configuration does not start worker path.
- Integration coverage under [`tests/integration`](tests/integration):
  - selected configuration persisted into job record before conversion launch,
  - orchestration receives expected normalized payload,
  - `configuration.saved` and `configuration.rejected` events emitted with required fields.

### Previous Story Intelligence

- Story 3.4 completed job lifecycle persistence and deterministic resume in [`3-4-persist-job-lifecycle-and-resume-conversion-from-last-failed-chunk.md`](_bmad-output/implementation-artifacts/3-4-persist-job-lifecycle-and-resume-conversion-from-last-failed-chunk.md).
- Reuse established patterns from Epic 3:
  - strict normalized result/error contracts,
  - deterministic orchestration inputs,
  - structured event emission with stable schema fields.
- Avoid regressions by ensuring new UI configuration payload plugs into existing orchestration flow rather than creating a parallel launch path.

### Git Intelligence Summary

- Recent commits show active stabilization of orchestration and resume behavior:
  - `b6b1f55` code-review fixes for story 3.4,
  - `83a58aa` persistent job lifecycle transitions and deterministic resume,
  - `eb6a36b` story 3.4 context creation,
  - `92fc18b` story 3.3 hardening,
  - `a2708c8` deterministic persisted-chunk orchestration.
- Implication for Story 3.5: integrate configuration in a minimally invasive way that preserves proven orchestration and test patterns.

### Project Structure Notes

- No `project-context.md` file discovered by configured pattern; context derived from planning artifacts, architecture, prior stories, and current codebase.
- Keep implementation within current module boundaries and avoid introducing new top-level folders for this story.

### References

- Story source: [`epics.md`](_bmad-output/planning-artifacts/epics.md)
- Product constraints: [`prd.md`](_bmad-output/planning-artifacts/prd.md)
- Architecture constraints: [`architecture.md`](_bmad-output/planning-artifacts/architecture.md)
- Sprint tracking: [`sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml)
- Previous story intelligence: [`3-4-persist-job-lifecycle-and-resume-conversion-from-last-failed-chunk.md`](_bmad-output/implementation-artifacts/3-4-persist-job-lifecycle-and-resume-conversion-from-last-failed-chunk.md)
- Current UI surfaces: [`conversion_view.py`](src/ui/views/conversion_view.py), [`conversion_presenter.py`](src/ui/presenters/conversion_presenter.py), [`conversion_worker.py`](src/ui/workers/conversion_worker.py)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `cat ./_bmad/core/tasks/workflow.xml`
- `cat ./_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`
- `cat ./_bmad/bmm/workflows/4-implementation/create-story/instructions.xml`
- `cat ./_bmad-output/implementation-artifacts/sprint-status.yaml`
- `git log --oneline -n 5`
- `PYTHONPATH=src python -m unittest tests.unit.test_conversion_presenter tests.unit.test_conversion_view tests.unit.test_conversion_worker tests.unit.test_conversion_jobs_repository tests.integration.test_conversion_configuration_integration`
- `PYTHONPATH=src python -m unittest discover -s tests`

### Completion Notes List

- Story selected from first backlog entry in sprint status: `3-5-configure-conversion-parameters-and-output-format-in-ui`.
- Comprehensive developer context prepared from epics, architecture, PRD, prior story intelligence, and current source analysis.
- Story status is set to `ready-for-dev` and includes implementation guardrails for configuration validation, persistence handoff, and observability.
- Sprint status should be updated so development_status for this story becomes `ready-for-dev`.
- Implemented normalized configuration payload construction and strict validation in presenter (`engine`, `voice_id`, `language`, `speech_rate`, `output_format`) with deterministic normalized failures.
- Implemented configuration-stage observability events `configuration.saved` and `configuration.rejected` with required schema fields.
- Extended conversion view state with deterministic UI option descriptors and disabled-reason mapping for unavailable engine/voice combinations.
- Added conversion launch path in worker that persists validated settings into `conversion_jobs`, emits configuration launch event, and forwards immutable payload to launcher.
- Extended conversion jobs repository for full configuration readback and explicit job creation API.
- Added/updated unit and integration coverage for validation boundaries, option mapping, persistence/handoff immutability, and configuration event schema compliance.
- Full regression suite executed successfully: `Ran 135 tests ... OK`.
- **Code review fixes applied (2026-02-13):**
  - Fixed import paths in `conversion_view.py` and `conversion_worker.py` to use `src.contracts.result`
  - Added validation for empty `voice_catalog` with error code `configuration.voice_catalog_empty`
  - Added validation that selected engine has voices in catalog with error code `configuration.engine_has_no_voices`
  - Added 6 new unit tests covering edge cases: unsupported engine, unsupported output format, negative speech rate, empty voice catalog, engine with no voices, incompatible voice ID
  - Added comprehensive docstring to `ConversionView` explaining `current_state` schema
  - Full regression suite now passes with 141 tests (6 new tests added)

### File List

- _bmad-output/implementation-artifacts/3-5-configure-conversion-parameters-and-output-format-in-ui.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/ui/presenters/conversion_presenter.py
- src/ui/views/conversion_view.py
- src/ui/workers/conversion_worker.py
- src/adapters/persistence/sqlite/repositories/conversion_jobs_repository.py
- tests/unit/test_conversion_presenter.py
- tests/unit/test_conversion_view.py
- tests/unit/test_conversion_worker.py
- tests/integration/test_conversion_configuration_integration.py

## Change Log

- 2026-02-13: Story 3.5 context created with full implementation guidance and status `ready-for-dev`.
- 2026-02-13: Implemented Story 3.5 configuration payload validation, view option mapping, worker persistence/handoff, and observability with full unit/integration coverage.
- 2026-02-13: Code review completed - fixed 7 HIGH and 3 MEDIUM issues: import paths, validation gaps, missing tests, and documentation. Test suite expanded from 135 to 141 tests.

## Story Completion Status

- Status set to: `done`
- Completion note: Implementation complete with code review fixes applied; all tasks/subtasks checked, configuration ACs validated, and full regression suite passed (141 tests).
