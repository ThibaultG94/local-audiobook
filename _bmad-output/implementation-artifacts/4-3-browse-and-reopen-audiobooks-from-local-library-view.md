# Story 4.3: Browse and Reopen Audiobooks from Local Library View

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user with previously converted audiobooks,
I want to browse my local library and reopen an item,
so that I can quickly resume listening without reconversion.

## Acceptance Criteria

1. **Given** library records exist in SQLite  
   **When** `library_view.py` loads through `library_presenter.py`  
   **Then** audiobooks are listed with core metadata title source language format created date  
   **And** listing order is deterministic and stable across refresh.

2. **Given** a user selects a library item  
   **When** open action is triggered from library UI  
   **Then** selected item details and audio path are resolved via `library_service.py`  
   **And** playback context is prepared without re-running extraction or synthesis.

3. **Given** missing file path or stale metadata can occur  
   **When** reopen is requested and audio artifact is unavailable  
   **Then** user receives actionable normalized error feedback  
   **And** diagnostics include remediation guidance to relink or reconvert locally.

4. **Given** library usage events are needed for troubleshooting  
   **When** list load item open or open failure happens  
   **Then** JSONL events are emitted with `stage=library_browse`  
   **And** payload includes `correlation_id`, `event`, `severity`, and UTC ISO-8601 `timestamp`.

## Tasks / Subtasks

- [ ] Add library browse domain flow and deterministic listing contract (AC: 1, 4)
  - [ ] Add read methods to [`LibraryItemsRepository`](src/adapters/persistence/sqlite/repositories/library_items_repository.py) for stable ordered listing and single-item lookup by id.
  - [ ] Define domain-level browse/read operations in [`LibraryService`](src/domain/services/library_service.py) returning normalized `{ok, data, error}` payloads.
  - [ ] Emit structured JSONL browse events with `stage=library_browse` and `domain.action` naming.
- [ ] Introduce UI surface for library browse and reopen actions (AC: 1, 2)
  - [ ] Create [`LibraryPresenter`](src/ui/presenters/library_presenter.py) to orchestrate list loading, selection, and normalized UI state.
  - [ ] Create [`LibraryView`](src/ui/views/library_view.py) to render deterministic list of local audiobooks and expose item-open actions.
  - [ ] Wire presenter↔view boundaries without direct SQLite access from the UI layer.
- [ ] Implement reopen flow with playback context preparation (AC: 2, 3)
  - [ ] Add a domain method in [`LibraryService`](src/domain/services/library_service.py) to resolve selected item details and validate artifact path existence.
  - [ ] Return normalized actionable failures for stale metadata / missing file with remediation guidance (relink or reconvert).
  - [ ] Ensure reopen action does not trigger extraction, chunking, synthesis, or post-processing paths.
- [ ] Integrate dependency wiring and boundaries (AC: 1, 2, 3)
  - [ ] Register library presenter/view dependencies in [`build_container()`](src/app/dependency_container.py:104) while preserving existing service boundaries.
  - [ ] Keep logging through existing logger boundary and avoid new ad-hoc logging mechanisms.
- [ ] Add test coverage across repository, service, and UI interaction seams (AC: 1, 2, 3, 4)
  - [ ] Add unit tests for repository deterministic ordering and item lookup.
  - [ ] Add unit tests for service browse/reopen success and normalized failure contracts.
  - [ ] Add unit tests for presenter behavior (load list, open item, error rendering signals/state mapping).
  - [ ] Add integration coverage to confirm end-to-end reopen preparation path and logging at `stage=library_browse`.

## Dev Notes

### Developer Context Section

- Story 4.3 is the first story that introduces explicit library browsing and reopen UX; no [`library_view.py`](src/ui/views/library_view.py) or [`library_presenter.py`](src/ui/presenters/library_presenter.py) currently exists in the codebase.
- Story 4.2 already established persistence and metadata contracts through [`LibraryService.persist_final_artifact()`](src/domain/services/library_service.py:48) and [`LibraryItemsRepository.create_item()`](src/adapters/persistence/sqlite/repositories/library_items_repository.py:18); Story 4.3 must reuse these contracts and extend read operations rather than creating parallel storage paths.
- Reopen must prepare playback context only; do not re-enter conversion flow in [`TtsOrchestrationService.launch_conversion()`](src/domain/services/tts_orchestration_service.py:127).
- Existing project boundaries enforce UI → presenter → domain services → adapters/repositories; direct DB calls from views are prohibited.

### Technical Requirements

- Implement deterministic browse API returning list items with fields required by AC: title, source, language, format, created date, plus id/audio path for reopen action.
- Implement reopen resolution API in [`LibraryService`](src/domain/services/library_service.py) with normalized outputs:
  - success: `{ok: true, data: {library_item, playback_context}, error: null}`
  - failure: `{ok: false, data: null, error: {code, message, details, retryable}}`
- Validate stale metadata conditions explicitly:
  - missing record by id
  - record exists but `audio_path` missing on disk
  - malformed path outside runtime bounds
- Emit browse/reopen observability events at `stage=library_browse` with stable names such as:
  - `library.list_loaded`
  - `library.item_opened`
  - `library.item_open_failed`
- Keep user-facing feedback actionable and English-only for MVP UI consistency.

### Architecture Compliance

- Respect architectural boundaries documented in [`_bmad-output/planning-artifacts/architecture.md`](_bmad-output/planning-artifacts/architecture.md):
  - no repository usage from views/presenters,
  - service layer owns validation and normalized error mapping,
  - adapters remain persistence concerns only.
- Preserve naming and contract conventions:
  - Python/file names in `snake_case`,
  - result envelope `{ok, data, error}` and error shape `{code, message, details, retryable}`,
  - event naming `domain.action`,
  - UTC ISO-8601 timestamps.
- Preserve offline-only guarantees: no external API/network dependency in browse/reopen paths.

### Library / Framework Requirements

- Reuse existing Python runtime and repository infrastructure; no additional persistence framework.
- Reuse existing logger interface consumed by [`LibraryService`](src/domain/services/library_service.py:220).
- Keep compatibility with current test stack (`unittest`) and existing test style under [`tests/unit`](tests/unit) and [`tests/integration`](tests/integration).
- No dependency upgrade required for this story based on current manifest in [`pyproject.toml`](pyproject.toml:5).

### Project Structure Notes

- Add missing UI files aligned with architecture structure expectations:
  - `src/ui/views/library_view.py`
  - `src/ui/presenters/library_presenter.py`
- Extend persistence repository in place:
  - `src/adapters/persistence/sqlite/repositories/library_items_repository.py`
- Extend domain service in place:
  - `src/domain/services/library_service.py`
- Add/extend tests:
  - `tests/unit/test_library_items_repository.py`
  - `tests/unit/test_library_service.py`
  - `tests/unit/test_library_presenter.py` (new)
  - `tests/integration/test_library_browse_reopen_integration.py` (new or equivalent extension)
- No structure conflict detected; this story closes an implementation gap (planned in architecture/epics, not yet implemented in code).

### Testing Requirements

- Repository tests must assert deterministic ordering across refresh (stable sort by `created_at` then `id` or explicit persisted ordering rule).
- Service tests must assert reopen behavior does not call synthesis/conversion services and returns normalized stale-artifact errors.
- Presenter tests must assert:
  - successful list load state mapping,
  - open selection flow,
  - actionable error mapping for missing artifacts.
- Integration tests should validate logging events (`library.list_loaded`, `library.item_opened`/`library.item_open_failed`) with `stage=library_browse`.

### Previous Story Intelligence

- Story 4.2 hardened path validation and metadata persistence; keep the same rigor for read/reopen validation.
- Story 4.2 code review changed orchestration behavior so library metadata failure does not block generated audio availability; Story 4.3 must account for possible stale/incomplete metadata and provide remediation UX.
- Continue contract-first implementation and avoid introducing alternate data contracts for UI-specific shortcuts.

### Git Intelligence Summary

- Recent commits (`3fff780`, `2ba3fa7`, `9283df3`, `2b025da`) indicate strong emphasis on:
  - normalized error contracts,
  - transaction safety,
  - regression tests,
  - story artifact traceability.
- Risk hotspots to preserve:
  - repository contract shape,
  - orchestration boundaries,
  - path safety checks.

### Latest Tech Information

- No new framework/library is necessary for this story.
- Existing stack (Python + SQLite + current project logging contract) is sufficient.
- Keep implementation aligned with currently pinned dependency baseline in [`pyproject.toml`](pyproject.toml:11).

### Project Context Reference

- No `project-context.md` file found by configured pattern `**/project-context.md`.
- Story context derived from:
  - [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md)
  - [`_bmad-output/planning-artifacts/architecture.md`](_bmad-output/planning-artifacts/architecture.md)
  - [`_bmad-output/planning-artifacts/prd.md`](_bmad-output/planning-artifacts/prd.md)
  - [`_bmad-output/implementation-artifacts/4-2-persist-final-audio-artifacts-and-library-metadata.md`](_bmad-output/implementation-artifacts/4-2-persist-final-audio-artifacts-and-library-metadata.md)

### References

- Epic/story source: [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md)
- Product requirements: [`_bmad-output/planning-artifacts/prd.md`](_bmad-output/planning-artifacts/prd.md)
- Architecture constraints: [`_bmad-output/planning-artifacts/architecture.md`](_bmad-output/planning-artifacts/architecture.md)
- Sprint tracking source: [`_bmad-output/implementation-artifacts/sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml)
- Previous story intelligence: [`_bmad-output/implementation-artifacts/4-2-persist-final-audio-artifacts-and-library-metadata.md`](_bmad-output/implementation-artifacts/4-2-persist-final-audio-artifacts-and-library-metadata.md)
- Existing library domain/persistence baseline:
  - [`LibraryService`](src/domain/services/library_service.py:36)
  - [`LibraryItemsRepository`](src/adapters/persistence/sqlite/repositories/library_items_repository.py:12)
- Orchestration boundary to avoid reusing for reopen:
  - [`TtsOrchestrationService.launch_conversion()`](src/domain/services/tts_orchestration_service.py:127)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log -n 5 --pretty=format:'%h|%s' --name-only`
- `rg -n "library|Library|player|Player" src`
- `rg -n "4\.3|Browse and Reopen" _bmad-output/planning-artifacts/epics.md`

### Completion Notes List

- Story context generated with exhaustive analysis of planning artifacts, architecture constraints, prior implementation story, current codebase boundaries, and recent git implementation patterns.
- This story is marked `ready-for-dev` with explicit implementation guardrails to prevent duplicate persistence paths, broken boundaries, and stale-artifact regressions.

### File List

- _bmad-output/implementation-artifacts/4-3-browse-and-reopen-audiobooks-from-local-library-view.md

## Story Completion Status

- Status set to: `ready-for-dev`
- Completion note: Ultimate context engine analysis completed - comprehensive developer guide created.
