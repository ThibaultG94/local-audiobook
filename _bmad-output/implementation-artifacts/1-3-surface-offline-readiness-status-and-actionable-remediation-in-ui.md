# Story 1.3: Surface Offline Readiness Status and Actionable Remediation in UI

Status: review

## Story

As a desktop user before launching conversion,
I want to see clear offline readiness and remediation guidance in the UI,
so that I can fix missing prerequisites and start conversion confidently.

## Acceptance Criteria

1. **Given** startup readiness output from `model_registry_service.py` and provider health checks from `tts_provider.py`  
   **When** the user opens the conversion entry view in `conversion_view.py`  
   **Then** the UI shows a deterministic readiness state `ready` or `not_ready`  
   **And** the active engine availability for Chatterbox GPU and Kokoro CPU is visible.

2. **Given** one or more assets are `missing` or `invalid`  
   **When** readiness is rendered in `conversion_presenter.py`  
   **Then** the user receives actionable remediation messages naming the missing asset and required action  
   **And** conversion start controls are disabled until status becomes `ready`.

3. **Given** conversion execution runs on `conversion_worker.py` with Qt signals  
   **When** readiness changes after a recheck action  
   **Then** UI status updates through signals without blocking the main UI thread  
   **And** failures are propagated as normalized errors using `result.py`.

4. **Given** observability is required for support diagnostics  
   **When** readiness checks are displayed or rechecked  
   **Then** JSONL events are emitted by `jsonl_logger.py` using `domain.action` names for `readiness.checked` and `readiness.displayed`  
   **And** event payload contains `correlation_id`, `stage`, `event`, `severity`, and UTC ISO-8601 `timestamp`.

## Tasks / Subtasks

- [x] Implement conversion readiness presentation boundary (AC: 1, 2)
  - [x] Create `src/ui/presenters/conversion_presenter.py` with a deterministic mapping from startup readiness payload to UI view model.
  - [x] Expose exactly two readiness states (`ready`, `not_ready`) in presenter output; do not leak internal model validation categories to view state.
  - [x] Include per-engine availability summary for Chatterbox and Kokoro in the view model.
  - [x] Normalize all presenter failures using `{ok, data, error}` and `errors.py` contract.

- [x] Implement conversion readiness UI view (AC: 1, 2)
  - [x] Create `src/ui/views/conversion_view.py` with a readiness panel, remediation list, and conversion start control.
  - [x] Ensure conversion start action is disabled when presenter state is `not_ready`.
  - [x] Render remediation items as actionable local steps (no cloud/network guidance).
  - [x] Keep MVP user-facing language in English.

- [x] Add non-blocking readiness recheck flow (AC: 3)
  - [x] Create `src/ui/workers/conversion_worker.py` signal contract for readiness refresh and failure propagation.
  - [x] Wire presenter ↔ worker ↔ view flow so readiness refresh does not block the main Qt event loop.
  - [x] Reuse startup readiness computation service instead of duplicating classification logic.
  - [x] Ensure error propagation reaches UI as normalized error object from `result.py` / `errors.py`.

- [x] Integrate readiness checks with app composition (AC: 1..3)
  - [x] Extend `src/app/dependency_container.py` to provide readiness-facing presenter dependencies without breaking existing non-Qt bootstrap tests.
  - [x] Reuse existing `container.startup_readiness` produced by `src/app/main.py` bootstrap as initial UI state.
  - [x] Add explicit recheck entrypoint that reruns model registry + engine health checks through service boundaries.

- [x] Emit observability events for readiness display and refresh (AC: 4)
  - [x] Emit `readiness.displayed` when readiness state is first rendered in conversion view.
  - [x] Emit `readiness.checked` on each explicit readiness recheck action.
  - [x] Ensure emitted payload uses required schema fields and UTC ISO-8601 timestamp format.
  - [x] Keep event naming strictly `domain.action` and `snake_case` payload fields.

- [x] Add tests for presenter/view/worker readiness behavior (AC: 1..4)
  - [x] Unit tests for readiness presenter mapping (`ready` vs `not_ready`, remediation list, engine availability).
  - [x] Unit tests for conversion control enable/disable logic based on readiness state.
  - [x] Unit tests for normalized failure mapping in readiness recheck flow.
  - [x] Integration test for non-blocking readiness refresh signal path.
  - [x] Integration test for JSONL events `readiness.displayed` and `readiness.checked` schema compliance.

## Dev Notes

### Story Intent

- This story converts backend readiness computation into user-actionable UI guidance.
- The user must understand *why* conversion is blocked and exactly what to fix locally.
- The implementation must preserve deterministic startup behavior introduced in Story 1.2.

### Story Context and Dependencies

- Story 1.1 established local bootstrap, migration baseline, normalized contracts, and JSONL logging.
- Story 1.2 added model validation, engine health checks, and aggregated startup readiness in `container.startup_readiness`.
- Story 1.3 must **reuse** this existing readiness pipeline; do not re-implement integrity checks in UI modules.

### Previous Story Intelligence (Critical Reuse)

- Use `StartupReadinessService.compute()` from `src/domain/services/startup_readiness_service.py` as single source of readiness truth.
- Use existing provider health normalization helper pattern from `src/app/main.py` as baseline for deterministic engine availability payload.
- Keep `dependency_container.py` framework-agnostic where possible; Qt-heavy wiring belongs in dedicated UI modules.
- Maintain normalized contract discipline (`result.py`, `errors.py`) at presenter and worker boundaries.

### Architecture Compliance Requirements

- Respect strict boundaries from architecture:
  - UI modules must not access SQLite or model files directly.
  - All readiness computation remains in services/domain layer.
  - Conversion fallback policy remains outside UI and provider adapters.
- Keep naming conventions:
  - Python modules/functions/variables: `snake_case`
  - Qt signal names: `snake_case`
  - Event names: `domain.action`
- Keep timestamps ISO-8601 UTC and payload fields in `snake_case`.

### Technical Guardrails for Dev Agent

- Do not create a second readiness algorithm in `conversion_presenter.py`; only transform service output for display.
- Do not infer readiness from individual provider statuses in UI directly if service aggregate says `not_ready`.
- Do not enable conversion controls while any required model is `missing` or `invalid`.
- Do not block the UI thread during refresh; use worker/signal flow.
- Do not emit free-form logs; use structured logger and required event schema fields.

### File Structure Requirements

- Add or modify only architecture-aligned paths:
  - `src/ui/views/conversion_view.py` (NEW)
  - `src/ui/presenters/conversion_presenter.py` (NEW)
  - `src/ui/workers/conversion_worker.py` (NEW)
  - `src/app/dependency_container.py` (MODIFY as needed for UI wiring)
  - `src/app/main_window.py` (NEW or MODIFY if used as composition root)
  - `src/infrastructure/logging/jsonl_logger.py` (MODIFY only if needed for readiness events)
  - `tests/unit/` readiness presenter/view tests (NEW)
  - `tests/integration/` readiness refresh/logging tests (NEW)

### Testing Requirements

- Validate deterministic `ready`/`not_ready` UI mapping from identical backend inputs.
- Validate conversion control disabled behavior under `not_ready`.
- Validate remediation text includes concrete local actions from model validation output.
- Validate non-blocking refresh behavior (no direct long-running call on main UI thread path).
- Validate `readiness.displayed` and `readiness.checked` logs include mandatory schema fields.

### References

- Epic source and ACs: `_bmad-output/planning-artifacts/epics.md` (Epic 1, Story 1.3)
- Architecture constraints and boundaries: `_bmad-output/planning-artifacts/architecture.md`
- Product requirements traceability: `_bmad-output/planning-artifacts/prd.md` (FR27, FR28, NFR1, NFR6, NFR9, NFR14)
- Previous story context: `_bmad-output/implementation-artifacts/1-2-validate-model-assets-and-engine-health-at-startup.md`
- Sprint tracking source: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log --oneline -n 5`
- `git log --name-only --pretty=format:'--- %h %s' -n 5`

### Completion Notes List

- Story context generated with explicit reuse guardrails from stories 1.1 and 1.2.
- Readiness UI guidance is scoped to deterministic state projection, actionable remediation, and non-blocking refresh flow.
- Logging expectations include `readiness.displayed` and `readiness.checked` with strict schema compliance.
- Implemented `ConversionPresenter`, `ConversionView`, and `ConversionWorker` with deterministic `ready`/`not_ready` projection and normalized `{ok,data,error}` handling.
- Added composition helpers in `dependency_container.py` to expose presenter/worker and explicit `recheck_startup_readiness` via existing domain services.
- Refactored startup engine-health normalization in `main.py` to reuse container-level collection path.
- Added unit and integration coverage for mapping, enable/disable control logic, non-blocking refresh callback path, and readiness JSONL event schema compliance.
- Validation run succeeded with `PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py'` (29 tests, all passing).

### File List

- _bmad-output/implementation-artifacts/1-3-surface-offline-readiness-status-and-actionable-remediation-in-ui.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/app/dependency_container.py
- src/app/main.py
- src/ui/presenters/__init__.py
- src/ui/presenters/conversion_presenter.py
- src/ui/views/__init__.py
- src/ui/views/conversion_view.py
- src/ui/workers/__init__.py
- src/ui/workers/conversion_worker.py
- tests/unit/test_conversion_presenter.py
- tests/unit/test_conversion_view.py
- tests/unit/test_conversion_worker.py
- tests/integration/test_readiness_events_and_refresh.py
- tests/integration/test_readiness_refresh_signal_path.py

## Change Log

- 2026-02-12: Implemented Story 1.3 readiness UI/presenter/worker flow, integrated recheck entrypoint in container, added observability events and full test coverage; status moved to `review`.
