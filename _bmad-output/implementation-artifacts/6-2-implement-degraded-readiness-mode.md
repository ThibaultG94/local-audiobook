# Story 6.2: Implement Degraded Readiness Mode

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user with partial engine availability,
I want the app to run in degraded mode when fallback works,
so that I can still convert documents even if primary engine is down.

## Acceptance Criteria

1. **Given** startup checks detect primary engine unavailable and fallback engine healthy
   **When** readiness status is computed
   **Then** readiness is `degraded` instead of `not_ready`
   **And** conversion remains enabled with auto-selection of the working engine.

2. **Given** all engines are unavailable
   **When** readiness is recomputed
   **Then** status is `not_ready`
   **And** UI displays remediation steps per failed engine.

## Tasks / Subtasks

- [x] Extend readiness status computation to preserve degraded mode semantics (AC: 1, 2)
  - [x] Validate startup readiness status mapping in `StartupReadinessService.compute` for three states: `ready`, `degraded`, `not_ready`
  - [x] Ensure degraded is only returned when primary (`chatterbox_gpu`) is down and fallback (`kokoro_cpu`) is healthy
  - [x] Preserve deterministic remediation generation for every failed engine
- [x] Ensure UI allows conversion in degraded mode while preserving guardrails (AC: 1)
  - [x] Confirm presenter mapping keeps `start_enabled=true` for `degraded`
  - [x] Ensure conversion configuration options disable unavailable engines/voices and keep available fallback selectable
  - [x] Ensure conversion launch path continues to use selected/available engine without bypassing validation
- [x] Ensure `not_ready` remains strict when no engine is available (AC: 2)
  - [x] Verify presenter/view state keeps `start_enabled=false` for `not_ready`
  - [x] Confirm remediation list is surfaced in readiness and diagnostics UI paths
- [x] Add regression and integration coverage for degraded readiness behavior (AC: 1, 2)
  - [x] Extend unit tests for startup readiness service status transitions and remediation
  - [x] Extend presenter/view unit tests for degraded and not_ready behavior
  - [x] Extend readiness refresh integration tests to validate non-blocking updates with degraded outcomes

## Dev Notes

### Developer Context Section

- Story selected from sprint backlog order in `sprint-status.yaml`: `6-2-implement-degraded-readiness-mode`.
- Epic 6 objective is runtime hardening and polish; this story specifically stabilizes startup/readiness behavior under partial engine failure.
- Existing codebase already contains `degraded` readiness plumbing in domain, presenter, and view paths; implementation focus is correctness hardening + regression protection rather than new architecture.
- Business value: preserve usable conversion experience when fallback engine remains healthy, while keeping strict blocking behavior when all engines are down.

### Technical Requirements

- Preserve normalized service contract for readiness computation: result envelope must remain `{ok, data, error}`.
- Preserve readiness states as deterministic finite set: `ready`, `degraded`, `not_ready`.
- Degraded transition rule must remain explicit and test-protected:
  - `degraded` only when primary engine `chatterbox_gpu` is unavailable and fallback `kokoro_cpu` is available.
- `not_ready` must be returned when no engine is available, regardless of model status.
- Presenter mapping must keep `start_enabled = True` for `ready|degraded` and `False` for `not_ready`.
- UI configuration options must disable unavailable engines/voices while keeping compatible fallback options selectable.
- Remediation guidance must include one actionable item per failed engine and remain local-only.

### Architecture Compliance

- Keep readiness logic in service boundary only:
  - `src/domain/services/startup_readiness_service.py`
- Keep UI mapping and enable/disable rules in presenter/view boundary only:
  - `src/ui/presenters/conversion_presenter.py`
  - `src/ui/views/conversion_view.py`
  - `src/ui/widgets/conversion_widget.py`
- Do not move fallback policy into TTS adapters; engine fallback policy remains orchestrated at service level.
- Preserve contract boundaries:
  - UI must not read repositories directly.
  - Startup readiness recheck must continue through dependency container service wiring.
- Preserve offline-first and local-only constraints (no network checks or cloud remediation paths).

### Library / Framework Requirements

- Python runtime target in docs is 3.12; do not introduce syntax/features that break current packaging constraints (`pyproject.toml` currently allows `>=3.10`).
- Reuse current dependencies only:
  - `PyQt5`
  - `PyYAML`
  - `EbookLib`
  - `PyPDF2`
  - `pyttsx3`
- No new external dependency is required for this story; expected implementation is logic/tests hardening.
- Keep import style and package paths consistent with existing `src.*` conventions in UI/presenter/service modules.

### Project Structure Notes

- Primary implementation files expected for this story:
  - `src/domain/services/startup_readiness_service.py`
  - `src/ui/presenters/conversion_presenter.py`
  - `src/ui/views/conversion_view.py`
  - `src/ui/widgets/conversion_widget.py`
  - `src/app/dependency_container.py`
- Primary test touchpoints:
  - `tests/unit/test_startup_readiness_service.py`
  - `tests/unit/test_conversion_presenter.py`
  - `tests/unit/test_conversion_view.py`
  - `tests/unit/test_conversion_worker.py`
  - `tests/integration/test_readiness_refresh_signal_path.py`
  - `tests/integration/test_readiness_events_and_refresh.py`
- Keep all changes within existing `src/`, `tests/`, and `_bmad-output/implementation-artifacts/` boundaries; no new top-level folders.

### Testing Requirements

- Add/maintain unit coverage proving deterministic readiness transitions:
  - `degraded` when `chatterbox_gpu` is down and `kokoro_cpu` is up.
  - `not_ready` when both engines are down.
  - `ready` when at least one valid ready path exists per current service contract.
- Add/maintain presenter/view tests confirming:
  - `start_enabled=True` for `degraded`.
  - `start_enabled=False` for `not_ready`.
  - Engine/voice options are disabled for unavailable engines with actionable reasons.
- Maintain non-blocking readiness refresh behavior in integration tests:
  - worker callback updates view state correctly for degraded and ready transitions.
- Keep structured event schema integrity for readiness and diagnostics events (no contract regression on event names/stages/correlation fields).

### Previous Story Intelligence

- Story 6.1 delivered runtime hardening and stronger diagnostics in conversion worker paths; Story 6.2 should preserve those guarantees and avoid regressions in error normalization.
- Existing patterns in Epic 5 + Story 6.1 emphasize deterministic result/error envelopes and structured local events; degraded readiness changes must align with these contracts rather than introducing ad-hoc status handling.
- Recent review fixes in Story 6.1 added stricter failure-context capture and fallback stderr logging in UI event emission; readiness changes should not remove these operational safety nets.

### Git Intelligence Summary

- Recent commits indicate Story 6.2 is the active next step after Story 6.1 hardening:
  - `a8354ba` refactor(story-6.1): apply code review fixes for conversion worker and TTS providers
  - `f9e0be8` Harden conversion worker failure diagnostics and stabilize TTS import paths
  - `34b41ce` Create story 6.1 and mark Epic 6 as in progress
  - `8aa438f` Create Epic 6 and finalize epics and stories breakdown
  - `711adca` Add BMAD V6 completion report and update gitignore
- Implementation implication: prefer minimal, targeted behavior hardening and regression tests over architectural rewrites.

### Latest Tech Information

- No mandatory dependency upgrade is required for this story scope.
- Keep implementation aligned with currently used stack and existing readiness contracts.
- Continue prioritizing deterministic behavior and local-only runtime constraints over framework expansion.

### Project Context Reference

- `project-context.md` was not found via configured discovery pattern `**/project-context.md`.
- Context used for this story:
  - `_bmad-output/planning-artifacts/epics.md`
  - `_bmad-output/planning-artifacts/prd.md`
  - `_bmad-output/planning-artifacts/architecture.md`
  - `_bmad-output/implementation-artifacts/sprint-status.yaml`
  - `_bmad-output/implementation-artifacts/6-1-debug-and-fix-conversion-pipeline-runtime-failure.md`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `python3 -m unittest -q tests.unit.test_startup_readiness_service`
- `python3 -m unittest -q tests.unit.test_conversion_presenter tests.unit.test_conversion_view tests.unit.test_conversion_worker`
- `python3 -m unittest -q tests.integration.test_readiness_refresh_signal_path tests.integration.test_readiness_events_and_refresh`
- `PYTHONPATH=src python3 -m unittest -q tests.unit.test_startup_readiness_service tests.unit.test_dependency_container_readiness tests.unit.test_conversion_presenter tests.unit.test_conversion_view tests.unit.test_conversion_worker tests.integration.test_readiness_refresh_signal_path tests.integration.test_readiness_events_and_refresh`

### Completion Notes List

- Hardened readiness status computation so `degraded` is emitted only when `chatterbox_gpu` is explicitly down and `kokoro_cpu` is explicitly healthy.
- Preserved deterministic remediation behavior while keeping strict `not_ready` when no engine is available.
- Updated engine health normalization to preserve provider engine identity on failed checks, ensuring stable fallback/degraded mapping.
- Added targeted regression tests for dependency container readiness normalization and executed full story test matrix successfully.

### File List

- \_bmad-output/implementation-artifacts/6-2-implement-degraded-readiness-mode.md
- src/domain/services/startup_readiness_service.py
- src/app/dependency_container.py
- tests/unit/test_dependency_container_readiness.py

### Change Log

- 2026-02-18: Implemented degraded readiness hardening, preserved deterministic remediation behavior, and added regression coverage for failed-engine identity normalization.

## Story Completion Status

- Story ID: `6.2`
- Story Key: `6-2-implement-degraded-readiness-mode`
- Status set to: `review`
- Completion note: Degraded readiness behavior validated end-to-end with strict fallback gating and regression coverage.
