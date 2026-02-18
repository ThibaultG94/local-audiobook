# Story 6.3: Complete Library View with Select and Delete Actions

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user managing imported documents,
I want a functional Library tab with selection and deletion,
so that I can control which documents are converted and retained.

## Acceptance Criteria

1. **Given** documents are present in local persistence
   **When** library tab is opened
   **Then** list shows title, format, size, import date, and conversion status
   **And** data refresh remains deterministic.

2. **Given** a user selects a document
   **When** conversion action is initiated from library context
   **Then** selected document is forwarded through presenter/service boundaries
   **And** UI does not access repositories directly.

3. **Given** a user confirms deletion
   **When** delete operation executes
   **Then** document and related local references are removed safely
   **And** failures are surfaced with normalized actionable errors.

## Tasks / Subtasks

- [x] Add deterministic library list state with all required display fields (AC: 1)
  - [x] Extend presenter/view state contract to expose title, format, byte size, import date, and conversion status.
  - [x] Keep refresh ordering deterministic (newest-first fallback to stable id order).
  - [x] Ensure library loading remains service-driven and resilient to empty-state conditions.
- [x] Implement explicit item selection workflow for library actions (AC: 2)
  - [x] Track selected item id in view state and expose it to convert/open actions.
  - [x] Route selection + action through `LibraryView` → `LibraryPresenter` → `LibraryService` boundaries only.
  - [x] Enforce no direct repository access from UI modules.
- [x] Implement safe delete flow for library items and linked local references (AC: 3)
  - [x] Add domain service delete operation with normalized `{ok, data, error}` responses.
  - [x] Delete metadata row and local artifact references atomically where possible.
  - [x] Surface actionable remediation when delete cannot complete.
- [x] Add/extend tests for list, selection, and deletion behavior (AC: 1, 2, 3)
  - [x] Unit tests for presenter/view mapping and selection state transitions.
  - [x] Unit tests for service/repository delete success/failure paths.
  - [x] Integration tests validating deterministic refresh and safe delete behavior.

## Dev Notes

### Developer Context Section

- Story selected from sprint backlog order in `sprint-status.yaml`: `6-3-complete-library-view-with-select-and-delete-actions`.
- Epic 6 objective is runtime stabilization and product polish; this story focuses on making Library interactions complete for day-to-day usage.
- Existing implementation already covers browse, open, and playback wiring through [`LibraryView`](src/ui/views/library_view.py:24), [`LibraryPresenter`](src/ui/presenters/library_presenter.py:37), and [`LibraryService`](src/domain/services/library_service.py:42).
- Gap to close for this story: complete library-management UX by adding explicit selection-to-conversion continuity and safe delete operations with normalized failures.
- Architecture direction is unchanged: keep repository access in adapters/services only; UI remains framework/presenter-driven without direct persistence calls.
- Business value: users can curate local content and reduce clutter while preserving deterministic, offline-first behavior.

### Technical Requirements

- Preserve normalized service contract for every library management operation: `{ok, data, error}` with structured error payload.
- Extend library browse payload to include deterministic display fields needed by AC1:
  - `title`
  - `format`
  - `byte_size`
  - `created_date` (import date surrogate from persisted timestamp)
  - conversion status (`ready` for persisted artifacts, with stable mapping rules)
- Keep deterministic ordering for list refresh: `created_at DESC, id DESC` as baseline from repository ordering.
- Add explicit selection semantics in view/presenter state:
  - `selected_item_id` must be updated only via presenter-driven actions
  - selection must be reusable for open/play/convert interactions without bypassing service boundaries
- Add safe delete flow in domain service with normalized failure categories:
  - input validation (`invalid_item_id`)
  - not found (`item_not_found`)
  - persistence failure (`delete_failed`)
  - local artifact handling failures (`artifact_cleanup_failed`), if cleanup is in scope
- Ensure delete operation removes local references consistently:
  - primary: library metadata row
  - secondary: associated local audio file only when safe and under runtime bounds
- Emit structured observability events for delete lifecycle at `stage=library_browse` or dedicated `stage=library_management`:
  - success event (e.g., `library.item_deleted`)
  - failure event (e.g., `library.item_delete_failed`)
- Preserve offline-only behavior: no network calls, no cloud fallback, no external metadata sync.

### Architecture Compliance

- Respect boundary flow defined by the current architecture: UI widget/view → presenter → domain service → repository.
- Keep repository calls out of UI modules:
  - no `sqlite3` access in `src/ui/**`
  - no repository imports in view/presenter modules except protocol typing abstractions.
- Keep library orchestration in domain services:
  - browse/open/delete operations in [`LibraryService`](src/domain/services/library_service.py:42)
  - playback controls remain in [`PlayerService`](src/domain/services/player_service.py:45).
- Preserve deterministic mapping behavior in presenter layer:
  - map domain errors to stable UI error structure with actionable remediation
  - maintain stable state keys used by current UI (`status`, `items`, `selected_item_id`, `error`, playback fields).
- Preserve runtime path safety constraints:
  - any artifact deletion must remain within `runtime/library/audio`
  - path traversal protections must remain enforced before file operations.
- Keep event schema compatibility with existing observability contracts (required fields, UTC timestamps, stage/event naming).

### Library / Framework Requirements

- Keep implementation within the existing stack already used in the project:
  - Python application modules under `src/`
  - `PyQt5` UI boundary (widgets/views) without direct DB coupling
  - SQLite persistence through existing repository adapters.
- Reuse existing contract utilities:
  - [`Result`](src/contracts/result.py:11), [`success()`](src/contracts/result.py:86), [`failure()`](src/contracts/result.py:94)
  - existing structured error envelope and remediation conventions.
- Reuse existing persistence modules instead of introducing new ORM/framework:
  - [`LibraryItemsRepository`](src/adapters/persistence/sqlite/repositories/library_items_repository.py:13)
  - any deletion extension should be added to current repository/service boundary.
- Reuse current logging and event schema infrastructure:
  - [`JsonlLogger`](src/infrastructure/logging/jsonl_logger.py:13)
  - required fields/schema helpers in [`event_schema.py`](src/infrastructure/logging/event_schema.py).
- No new third-party dependency is required for this story scope; changes are expected to be boundary-compliant extensions of existing modules.

### Project Structure Notes

- Likely implementation touchpoints for Story 6.3:
  - `src/domain/services/library_service.py` (delete use-case + browse payload enrichment)
  - `src/adapters/persistence/sqlite/repositories/library_items_repository.py` (delete/query extensions)
  - `src/ui/presenters/library_presenter.py` (selection + delete mapping)
  - `src/ui/views/library_view.py` (selection/delete actions and deterministic state refresh)
  - `src/ui/main_window.py` (Library tab action wiring, if needed)
- Existing playback integration paths should remain intact:
  - `src/domain/services/player_service.py`
  - `src/ui/presenters/library_presenter.py`
  - `src/ui/views/library_view.py`
- Keep runtime artifacts under `runtime/library/audio/` and never delete outside this base.
- Preserve current directory/module naming conventions and file boundaries established in previous stories.

### Testing Requirements

- Add/extend unit tests for presenter/view state:
  - deterministic list mapping includes required display fields (title/format/size/date/status)
  - selection state updates are stable and action-safe
  - delete failure mapping surfaces normalized actionable errors.
- Add/extend unit tests for domain service and repository:
  - delete success path removes metadata and handles artifact cleanup policy correctly
  - invalid id / not-found / persistence exceptions map to expected error codes
  - path-safety checks prevent deletion outside runtime bounds.
- Add/extend integration tests:
  - browse + select + delete scenario validates deterministic refresh after deletion
  - logger emits delete lifecycle events with required schema fields
  - existing browse/reopen/playback tests remain green (no regression).

### Previous Story Intelligence

- Story 6.2 hardened readiness semantics and reinforced strict state contracts; Story 6.3 should preserve those deterministic patterns and avoid introducing ad-hoc UI state.
- Recent Epic 6 work emphasizes normalized error envelopes and actionable remediation for users; delete/browse flows must follow the same structure.
- Existing integration emphasis (browse/reopen/playback) indicates that regression risk is primarily in presenter/view contract drift; maintain backward-compatible keys while extending fields.

### Git Intelligence Summary

- Recent commits confirm active sequence from Story 6.1 to 6.2 and now 6.3:
  - `c127c1f` refactor(story-6.2): apply code review fixes - add edge case tests and documentation
  - `2b634ae` feat: implement degraded readiness hardening and regression coverage
  - `75074a5` Create story 6.2 and mark sprint status ready-for-dev
  - `a8354ba` refactor(story-6.1): apply code review fixes for conversion worker and TTS providers
  - `f9e0be8` Harden conversion worker failure diagnostics and stabilize TTS import paths
- Implementation implication: keep changes incremental and contract-first; prioritize deterministic behavior and test protection over architectural rewrites.

### Latest Tech Information

- No dependency upgrade is required for this story scope.
- Continue with current stack conventions:
  - Python + `unittest` test strategy
  - PyQt5 for UI boundaries
  - SQLite repositories for local persistence.
- Keep local-only/privacy constraints intact for library management operations (no remote deletion/index synchronization).

### Project Context Reference

- `project-context.md` not found for configured discovery pattern.
- Context used to build this story:
  - `_bmad-output/planning-artifacts/epics.md`
  - `_bmad-output/planning-artifacts/prd.md`
  - `_bmad-output/planning-artifacts/architecture.md`
  - `_bmad-output/implementation-artifacts/sprint-status.yaml`
  - `_bmad-output/implementation-artifacts/6-2-implement-degraded-readiness-mode.md`

### References

- Epic/story source: `_bmad-output/planning-artifacts/epics.md`
- Product requirements: `_bmad-output/planning-artifacts/prd.md`
- Architecture constraints: `_bmad-output/planning-artifacts/architecture.md`
- Sprint tracking: `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Previous story: `_bmad-output/implementation-artifacts/6-2-implement-degraded-readiness-mode.md`
- Existing implementation baseline:
  - `src/ui/presenters/library_presenter.py`
  - `src/ui/views/library_view.py`
  - `src/domain/services/library_service.py`
  - `src/adapters/persistence/sqlite/repositories/library_items_repository.py`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log --oneline -n 5`
- `python3 -m unittest -q tests.integration.test_library_browse_reopen_integration tests.integration.test_library_playback_integration`
- `python3 -m unittest -q tests.unit.test_library_service tests.unit.test_library_items_repository`
- `python3 -m unittest -q tests.unit.test_library_service tests.unit.test_library_items_repository tests.unit.test_library_presenter tests.unit.test_library_view tests.integration.test_library_browse_reopen_integration tests.integration.test_library_playback_integration`

### Completion Notes List

- Extended browse payload mapping with deterministic UI fields (`byte_size`, `created_date`, `conversion_status`) while preserving stable ordering from repository (`created_at DESC, id DESC`).
- Implemented explicit selection workflow through `LibraryView` → `LibraryPresenter` → `LibraryService`, including conversion preparation payloads without repository access from UI layers.
- Added safe library delete flow with normalized errors (`invalid_item_id`, `item_not_found`, `delete_failed`, `artifact_cleanup_failed`) and bounded artifact cleanup under `runtime/library/audio`.
- Added delete lifecycle and conversion-preparation observability events at stage `library_management` (`library.item_prepared_for_convert`, `library.item_deleted`, `library.item_delete_failed`, `library.item_artifact_deleted`).
- Added/extended unit and integration tests for deterministic browse fields, selection state transitions, repository delete behavior, safe artifact cleanup, and browse-select-delete integration.

### Code Review Fixes Applied (2026-02-18)

**Security & Data Integrity:**

- Fixed path traversal vulnerability by replacing `str.startswith()` with `Path.is_relative_to()` for secure path validation
- Fixed transaction ordering in delete: now deletes DB metadata first (transactional), then cleans up artifact (best-effort) to prevent orphaned metadata
- Added byte_size validation to reject negative values at repository boundary
- Enhanced observability: delete events now include title, audio_path, and byte_size for complete audit trail

**Reliability & UX:**

- Added mandatory confirmation parameter to delete operations to prevent accidental data loss (AC3 compliance)
- Fixed memory leak: increased auto-refresh thread timeout from 0.2s to 2.0s with retry logic and proper cleanup
- Documented timeout constant with clear rationale

**Total fixes:** 10 issues resolved (8 High, 2 Medium)

### File List

- \_bmad-output/implementation-artifacts/6-3-complete-library-view-with-select-and-delete-actions.md
- src/adapters/persistence/sqlite/repositories/library_items_repository.py
- src/domain/services/library_service.py
- src/ui/presenters/library_presenter.py
- src/ui/views/library_view.py
- tests/integration/test_library_browse_reopen_integration.py
- tests/unit/test_library_items_repository.py
- tests/unit/test_library_presenter.py
- tests/unit/test_library_service.py
- tests/unit/test_library_view.py

## Change Log

- 2026-02-18: Implemented Story 6.3 library management completion (deterministic fields, selection-to-conversion flow, safe delete lifecycle, and regression coverage).

## Story Completion Status

- Story ID: `6.3`
- Story Key: `6-3-complete-library-view-with-select-and-delete-actions`
- Status set to: `review`
- Completion note: Story implementation complete with deterministic browse fields, selection/convert routing, safe delete flow, and passing targeted regression suite.
