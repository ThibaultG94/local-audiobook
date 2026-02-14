# Story 4.5: Provide Playback Controls with Pause Resume Seek and Progress

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user listening to an audiobook,
I want intuitive playback controls and real-time progress,
so that I can navigate content comfortably during listening sessions.

## Acceptance Criteria

1. **Given** playback is initialized through `player_service.py`  
   **When** I interact with controls in `player_view.py`  
   **Then** play pause and resume commands are executed successfully  
   **And** control state remains synchronized with actual player status.

2. **Given** active playback is running  
   **When** I seek to a target position  
   **Then** playback jumps to requested timestamp within valid bounds  
   **And** out-of-range seek attempts return actionable normalized errors.

3. **Given** users need temporal awareness  
   **When** audio is playing or paused  
   **Then** current time and total duration are displayed and updated consistently  
   **And** progress bar reflects true playback position without UI blocking.

4. **Given** playback failures or state changes occur  
   **When** events are emitted from `qt_audio_player.py`  
   **Then** presenter and view update deterministically with user-facing English feedback  
   **And** JSONL logs include `correlation_id`, `event`, `severity`, and UTC ISO-8601 `timestamp`.

## Tasks / Subtasks

- [x] Wire playback controls into existing UI flow (AC: 1, 3, 4)
  - [x] Extend [`LibraryPresenter`](src/ui/presenters/library_presenter.py) control handlers to expose deterministic play/pause/resume/seek actions through [`PlayerService`](src/domain/services/player_service.py)
  - [x] Keep control routing service-only (no direct UI call to [`QtAudioPlayer`](src/adapters/playback/qt_audio_player.py))
  - [x] Keep UI state synchronized with service state (`idle/loading/stopped/playing/paused/error`)
- [x] Implement seek guardrails and status synchronization (AC: 2, 3)
  - [x] Validate seek targets before/through [`PlayerService.seek()`](src/domain/services/player_service.py:190)
  - [x] Return normalized errors for out-of-range or invalid seek payloads via [`failure()`](src/contracts/result.py:48)
  - [x] Preserve deterministic transitions and prevent invalid command/state combinations
- [x] Expose playback timing/progress for rendering (AC: 3)
  - [x] Surface current position and total duration through presenter-friendly payloads
  - [x] Update progress representation without blocking UI thread
  - [x] Ensure progress rendering remains correct after pause/resume/seek
- [x] Preserve observability and diagnostics at player stage (AC: 4)
  - [x] Emit stable events (`player.play_started`, `player.paused`, `player.seeked`, `player.stopped`, `player.error`) through existing logging boundary
  - [x] Ensure minimum payload fields (`correlation_id`, `event`, `severity`, `timestamp`) are present
  - [x] Keep user-facing messages actionable and English-only for MVP
- [x] Add and update tests for control behavior and progress correctness (AC: 1, 2, 3, 4)
  - [x] Unit tests for presenter↔service command flow and error mapping
  - [x] Unit tests for seek validation/state transitions and status payloads
  - [x] Integration test for reopen → initialize playback → play/pause/resume/seek/progress updates

## Dev Notes

### Developer Context Section

- This story extends the playback baseline delivered in [`Story 4.4`](./_bmad-output/implementation-artifacts/4-4-integrate-local-audio-playback-service-and-adapter.md) where local load/play/pause/seek primitives and deterministic states already exist.
- Current playback stack to build on:
  - Presenter control entrypoint in [`LibraryPresenter`](src/ui/presenters/library_presenter.py)
  - Service orchestration and guardrails in [`PlayerService`](src/domain/services/player_service.py)
  - Qt backend adapter in [`QtAudioPlayer`](src/adapters/playback/qt_audio_player.py)
- Keep strict architecture boundary from [`architecture.md`](./_bmad-output/planning-artifacts/architecture.md): UI/presenter must never call adapter/backend directly; all commands go through service contracts.
- Story focus is control-plane and feedback quality (pause/resume/seek/progress visibility), not reconversion or library persistence changes.
- UX continuity requirement from epic/prd: controls must remain intuitive and non-blocking while preserving deterministic status feedback and actionable error text.

### Technical Requirements

- Reuse the existing playback control API already exposed by [`PlayerService.play()`](src/domain/services/player_service.py:133), [`PlayerService.pause()`](src/domain/services/player_service.py:152), [`PlayerService.seek()`](src/domain/services/player_service.py:190), and [`PlayerService.get_status()`](src/domain/services/player_service.py:224).
- Implement explicit resume behavior as `play` from `paused` state (do not introduce a separate backend-only resume path).
- Keep service response contracts normalized with project result envelope `{ok, data, error}` via [`Result`](src/contracts/result.py:1).
- Keep all player failures normalized to `{code, message, details, retryable}` using [`failure()`](src/contracts/result.py:48) patterns already used in [`PlayerService`](src/domain/services/player_service.py:374).
- Ensure control state synchronization between presenter state and service state transitions:
  - valid states: `idle`, `loading`, `stopped`, `playing`, `paused`, `error`
  - invalid commands from current state must fail deterministically and return actionable remediation.
- Seek requirements:
  - non-negative seek targets only
  - reject invalid or out-of-bounds requests with actionable error details
  - preserve current playback state unless service contract explicitly changes it.
- Progress/timing requirements:
  - expose current position and total duration in presenter-friendly payloads
  - maintain progress consistency after play/pause/resume/seek
  - do not block UI thread while refreshing timing data.

### Architecture Compliance

- Respect architecture boundary described in [`architecture.md`](./_bmad-output/planning-artifacts/architecture.md): UI/presenter → domain service → adapter.
- UI layer (existing [`library_view.py`](src/ui/views/library_view.py:1)) must not call adapter or Qt backend directly.
- Presenter layer (existing [`LibraryPresenter`](src/ui/presenters/library_presenter.py:36)) remains the only UI orchestration entrypoint for playback commands.
- Preserve adapter isolation in [`QtAudioPlayer`](src/adapters/playback/qt_audio_player.py:66); no business rules should migrate into adapter.
- Preserve local-only MVP security model:
  - no network calls
  - no cloud telemetry
  - playback only for local artifacts under runtime library boundaries.

### Library / Framework Requirements

- Project dependency baseline from [`pyproject.toml`](pyproject.toml:11):
  - `PyQt5>=5.15.0`
  - `PyYAML>=6.0`
  - `EbookLib>=0.18`
  - `PyPDF2>=3.0.0`
- Latest package observations (2026-02-14):
  - PyQt5: `5.15.11`
  - PyYAML: `6.0.3`
  - EbookLib: `0.20`
  - PyPDF2: `3.0.1`
- Story 4.5 must remain compatible with current playback adapter contract in [`qt_audio_player.py`](src/adapters/playback/qt_audio_player.py:1) and avoid introducing additional media stack dependencies unless strictly required.

### File Structure Requirements

- Primary files expected to evolve in this story:
  - [`src/ui/presenters/library_presenter.py`](src/ui/presenters/library_presenter.py)
  - [`src/ui/views/library_view.py`](src/ui/views/library_view.py)
  - [`src/domain/services/player_service.py`](src/domain/services/player_service.py)
  - [`src/adapters/playback/qt_audio_player.py`](src/adapters/playback/qt_audio_player.py)
  - tests under [`tests/unit/`](tests/unit) and [`tests/integration/`](tests/integration)
- The epic AC references `player_view.py`, but current repository uses [`library_view.py`](src/ui/views/library_view.py:1) for playback interactions; implement in-place unless a dedicated player view becomes necessary and justified.
- Keep naming conventions from architecture:
  - files/modules/functions in `snake_case`
  - classes in `PascalCase`
  - events in `domain.action`.

### Testing Requirements

- Add or update unit tests for playback command flow in presenter and service:
  - play from `paused`/`stopped`
  - pause from `playing`
  - seek validation (negative, invalid type, out-of-range semantics)
  - status/progress payload consistency.
- Add integration verification for end-to-end control flow after library reopen:
  - reopen item
  - initialize playback
  - play/pause/resume/seek
  - status/progress remains deterministic and UI-safe.
- Ensure diagnostics expectations:
  - player-stage events emitted for control actions and failures
  - payload includes at least `correlation_id`, `event`, `severity`, `timestamp`.

### Previous Story Intelligence

- Reuse the hardening from [`Story 4.4`](./_bmad-output/implementation-artifacts/4-4-integrate-local-audio-playback-service-and-adapter.md):
  - strict local path validation
  - deterministic state mapping
  - normalized error mapping
  - service-boundary enforcement.
- Build on existing reopen flow from [`LibraryService.reopen_library_item()`](src/domain/services/library_service.py:94) and avoid regression in library browse/reopen behavior.
- Keep playback event naming and stage conventions established in Story 4.4 (`stage=player`, `player.*` events).

### Git Intelligence Summary

- Recent commits show stable playback baseline was completed in Story 4.4 and hardened by review fixes:
  - `54d94ab` review fixes for Story 4.4
  - `317c6a5` Story 4.4 implementation
  - `ec6d20e` Story 4.4 context creation.
- Implication for Story 4.5:
  - prefer incremental enhancement over refactor
  - preserve newly stabilized boundaries in [`player_service.py`](src/domain/services/player_service.py:55) and [`library_presenter.py`](src/ui/presenters/library_presenter.py:36)
  - avoid introducing breaking changes in playback state contracts.

### Latest Tech Information

- Current PyQt5 latest stable observed: `5.15.11`; implementation should remain compatible with Qt multimedia behavior used in [`QtAudioPlayer`](src/adapters/playback/qt_audio_player.py:52).
- No new external playback dependency required for this story if current Qt adapter supports needed command and state behavior.
- Continue following local-first best practices:
  - deterministic command handling
  - explicit normalized failures
  - non-blocking UI feedback for progress/time updates.

### Project Context Reference

- No `project-context.md` file discovered for configured pattern `**/project-context.md`.
- Effective context sources used:
  - [`_bmad-output/planning-artifacts/epics.md`](./_bmad-output/planning-artifacts/epics.md)
  - [`_bmad-output/planning-artifacts/prd.md`](./_bmad-output/planning-artifacts/prd.md)
  - [`_bmad-output/planning-artifacts/architecture.md`](./_bmad-output/planning-artifacts/architecture.md)
  - [`_bmad-output/implementation-artifacts/4-4-integrate-local-audio-playback-service-and-adapter.md`](./_bmad-output/implementation-artifacts/4-4-integrate-local-audio-playback-service-and-adapter.md)
  - [`_bmad-output/implementation-artifacts/sprint-status.yaml`](./_bmad-output/implementation-artifacts/sprint-status.yaml)

### Project Structure Notes

- Align with existing runtime playback path and architecture boundaries; do not create alternate control pathways bypassing presenter/service contracts.
- Reuse existing UI surfaces in [`library_view.py`](src/ui/views/library_view.py:1) for MVP scope unless there is a clear and justified need for a dedicated `player_view`.
- Maintain compatibility with existing integration tests that validate library browse/reopen and playback handoff.

### References

- Epic/story source: [`_bmad-output/planning-artifacts/epics.md`](./_bmad-output/planning-artifacts/epics.md)
- Product requirements: [`_bmad-output/planning-artifacts/prd.md`](./_bmad-output/planning-artifacts/prd.md)
- Architecture constraints: [`_bmad-output/planning-artifacts/architecture.md`](./_bmad-output/planning-artifacts/architecture.md)
- Previous story context: [`_bmad-output/implementation-artifacts/4-4-integrate-local-audio-playback-service-and-adapter.md`](./_bmad-output/implementation-artifacts/4-4-integrate-local-audio-playback-service-and-adapter.md)
- Sprint tracker: [`_bmad-output/implementation-artifacts/sprint-status.yaml`](./_bmad-output/implementation-artifacts/sprint-status.yaml)
- Core playback implementation points:
  - [`PlayerService`](src/domain/services/player_service.py:55)
  - [`QtAudioPlayer`](src/adapters/playback/qt_audio_player.py:66)
  - [`LibraryPresenter`](src/ui/presenters/library_presenter.py:36)
  - [`library_view.py`](src/ui/views/library_view.py:1)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `cat ./_bmad-output/implementation-artifacts/sprint-status.yaml`
- `git log -n 5 --pretty=format:'%h|%ad|%s' --date=iso --name-only`
- `python -m pip index versions PyQt5`
- `python -m pip index versions PyYAML`
- `python -m pip index versions EbookLib`
- `python -m pip index versions PyPDF2`
- `find . -type f \( -name '*ux*.md' -o -name 'project-context.md' \) | sort`
- `ls -1 ./src/ui/views`
- `python -m unittest tests.unit.test_player_service tests.unit.test_library_presenter tests.unit.test_library_view tests.unit.test_qt_audio_player tests.integration.test_library_playback_integration`
- `python -m unittest discover -s tests`
- `python -m unittest tests.unit.test_player_service tests.unit.test_library_presenter tests.unit.test_library_view tests.unit.test_qt_audio_player tests.integration.test_library_playback_integration`

### Completion Notes List

- Story 4.5 selected as next backlog story from sprint status and contexted with epic/prd/architecture inputs.
- Comprehensive developer guardrails provided for playback controls, seek validation, state synchronization, and progress rendering.
- Previous story (4.4) implementation intelligence incorporated to minimize regressions and preserve architecture boundaries.
- Story status set to `ready-for-dev` with direct sprint tracking update prepared.
- Ultimate context engine analysis completed - comprehensive developer guide created.
- Added playback control methods in presenter/view layers (`play`, `pause`, `seek`, `refresh_playback_status`) and kept strict service-boundary routing.
- Added seek guardrails in player service for invalid payloads, finite numeric validation, and out-of-range detection using duration-aware checks.
- Exposed deterministic timing payloads (`position_seconds`, `duration_seconds`, `progress`) from adapter/service to presenter/view state.
- Preserved/extended player event observability (`player.play_started`, `player.paused`, `player.seeked`, `player.stopped`, `player.error`) with required event schema fields.
- Added and updated unit/integration tests for command flow, seek validation, progress consistency, and reopen→initialize→play/pause/resume/seek/status lifecycle.

### File List

- _bmad-output/implementation-artifacts/4-5-provide-playback-controls-with-pause-resume-seek-and-progress.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/adapters/playback/qt_audio_player.py
- src/domain/services/player_service.py
- src/ui/presenters/library_presenter.py
- src/ui/views/library_view.py
- tests/unit/test_library_presenter.py
- tests/unit/test_library_view.py
- tests/unit/test_player_service.py
- tests/unit/test_qt_audio_player.py
- tests/integration/test_library_playback_integration.py

### Change Log

- 2026-02-14: Implemented playback controls wiring, seek guardrails, progress/timing payload flow, and test coverage for Story 4.5; set story to review.

## Story Completion Status

- Status set to: `review`
- Completion note: Story 4.5 implementation completed with passing targeted unit/integration playback tests and updated diagnostics/progress handling.
