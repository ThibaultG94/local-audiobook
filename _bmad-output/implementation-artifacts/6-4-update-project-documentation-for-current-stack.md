# Story 6.4: Update Project Documentation for Current Stack

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a contributor onboarding the project,
I want accurate setup and architecture documentation,
so that I can install and run the application reliably.

## Acceptance Criteria

1. **Given** project docs are outdated
   **When** `README.md` and `INSTALLATION.md` are revised
   **Then** they describe current Python 3.12, ROCm 7.2, and venv setup with copy-pastable commands
   **And** outdated references (Python 3.11, ROCm 6.1, Coqui TTS) are removed.

2. **Given** architecture context is required for contributors
   **When** documentation update is complete
   **Then** a concise architecture overview and directory structure are included
   **And** instructions align with current implementation boundaries.

## Tasks / Subtasks

- [x] Audit current contributor-facing documentation for outdated stack references (AC: 1)
  - [x] Verify version references and commands in `README.md` and `INSTALLATION.md`.
  - [x] Identify and remove stale technology mentions (Python 3.11 / ROCm 6.1 / Coqui TTS).
- [x] Update setup documentation to match current runtime and installation flow (AC: 1)
  - [x] Ensure Python 3.12 + venv setup is copy-pastable and internally consistent.
  - [x] Ensure ROCm 7.2 guidance and CPU fallback path are explicit.
  - [x] Keep commands aligned with existing package/project entrypoints.
- [x] Refresh architecture summary and project structure guidance for contributors (AC: 2)
  - [x] Add/validate concise architecture overview in `README.md`.
  - [x] Align directory structure statements with the implemented boundaries in `src/`, `config/`, `migrations/`, `runtime/`, `tests/`.
- [x] Add regression checks for documentation accuracy and consistency (AC: 1, 2)
  - [x] Perform command-level sanity review for onboarding steps.
  - [x] Ensure docs match current code structure and do not reference non-existent modules.

## Dev Notes

### Developer Context Section

- Story selected from sprint backlog order in `sprint-status.yaml`: `6-4-update-project-documentation-for-current-stack`.
- Epic 6 objective remains runtime hardening and product polish; this story closes contributor-facing drift by aligning docs with the current stack and architecture.
- Existing documentation already includes Python 3.12 / ROCm 7.2 positioning, but Story 6.4 must guarantee consistency, remove stale references, and align wording with implementation boundaries.
- This is a documentation-focused story: implementation risk is primarily misinformation and onboarding friction, not runtime code changes.

### Technical Requirements

- Keep onboarding prerequisites explicit and current:
  - Python `3.12`
  - Linux Mint target
  - ROCm `7.2` for AMD GPU path
  - CPU fallback path documented with Kokoro ONNX.
- Commands must be copy-pastable and sequence-safe:
  - create/activate virtual environment
  - upgrade `pip`/build tooling
  - install project (`pip install -e .`)
  - run app via project entrypoint.
- Remove stale stack mentions if present anywhere in story scope docs:
  - Python 3.11
  - ROCm 6.1
  - Coqui TTS.
- Keep terminology consistent with current architecture and contracts (offline-first, local-only runtime, deterministic module boundaries).
- Do not introduce undocumented optional flows as defaults (e.g., avoid implying cloud setup or unsupported OS paths for MVP).

### Architecture Compliance

- Documentation must reflect established architecture boundaries from planning artifacts:
  - `src/app` for startup and dependency wiring
  - `src/domain` for business services and ports
  - `src/adapters` and `src/infrastructure` for integrations/persistence/logging
  - `src/ui` for presenters/views/workers.
- Keep project structure notes aligned with currently implemented directories in repository root (`config/`, `migrations/`, `runtime/`, `src/`, `tests/`).
- Preserve offline-first, no-cloud runtime guarantees in narrative and setup guidance.
- Do not document direct UI-to-repository coupling; retain service/presenter boundary language.

### Library / Framework Requirements

- Documentation should stay aligned with currently used stack and files:
  - Python 3.12 runtime target
  - PyQt5 desktop UI architecture
  - SQLite local persistence
  - local TTS providers (Chatterbox GPU path, Kokoro CPU fallback)
  - existing packaging/config from `pyproject.toml` and `config/*.yaml`.
- No new dependencies are required for this story; changes should focus on factual documentation corrections and clarity.

### Project Structure Notes

- Primary files in scope:
  - `README.md`
  - `INSTALLATION.md`
- Supporting references for factual alignment:
  - `_bmad-output/planning-artifacts/architecture.md`
  - `_bmad-output/planning-artifacts/prd.md`
  - current repository tree under `src/`, `config/`, `migrations/`, `runtime/`, `tests/`.
- Keep architecture overview concise in contributor docs while preserving critical boundaries and flow.

### Testing Requirements

- Validate documentation consistency by executing a documentation QA pass:
  - command correctness and ordering
  - stack version consistency across files
  - no stale references to removed/outdated technologies.
- If code/tests are touched while updating docs, run targeted regression tests for impacted modules; otherwise record docs-only verification evidence.
- Ensure documented project structure maps to existing paths in repository.

### Previous Story Intelligence

- Story 6.3 emphasized deterministic behavior, strict boundaries, and actionable error/reporting language; Story 6.4 should mirror this clarity in contributor docs.
- Recent Epic 6 pattern: incremental, contract-first updates with explicit validation. Apply same discipline to documentation updates (no ambiguous guidance, no speculative instructions).

### Git Intelligence Summary

- Recent commit sequence confirms Epic 6 progression and review hardening:
  - `7d6dcac` refactor(story-6.3): apply code review fixes - security, data integrity, and UX improvements
  - `3dd0e53` feat(story-6.3): complete library selection and safe delete workflows
  - `8357d0b` Create story 6.3 and mark it ready for development
  - `c127c1f` refactor(story-6.2): apply code review fixes - add edge case tests and documentation
  - `2b634ae` feat: implement degraded readiness hardening and regression coverage
- Implementation implication for this story: maintain same quality bar in docs—precise, validated, and aligned with current code reality.

### Latest Tech Information

- Current stack references relevant to this story are already aligned with target values in repository docs:
  - Python 3.12
  - ROCm 7.2
  - virtual environment first-run flow
  - Chatterbox GPU + Kokoro ONNX fallback.
- Story implementation should preserve this baseline and eliminate any inconsistent wording discovered during doc audit.

### Project Context Reference

- `project-context.md` not found for configured discovery pattern.
- Context used to build this story:
  - `_bmad-output/planning-artifacts/epics.md`
  - `_bmad-output/planning-artifacts/prd.md`
  - `_bmad-output/planning-artifacts/architecture.md`
  - `_bmad-output/implementation-artifacts/sprint-status.yaml`
  - `_bmad-output/implementation-artifacts/6-3-complete-library-view-with-select-and-delete-actions.md`
  - `README.md`
  - `INSTALLATION.md`

### References

- Epic/story source: `_bmad-output/planning-artifacts/epics.md`
- Product requirements: `_bmad-output/planning-artifacts/prd.md`
- Architecture constraints: `_bmad-output/planning-artifacts/architecture.md`
- Sprint tracking: `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Previous story: `_bmad-output/implementation-artifacts/6-3-complete-library-view-with-select-and-delete-actions.md`
- Documentation targets: `README.md`, `INSTALLATION.md`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log --oneline -n 5`
- `docs audit`: `README.md` and `INSTALLATION.md` cross-check against architecture and repository structure
- `search_files`: stale stack reference audit on `README.md` and `INSTALLATION.md` (Python 3.11 / ROCm 6.1 / Coqui)
- `.venv/bin/python -m pytest tests/ -q` → `294 passed, 1 warning`

### Implementation Plan

- Audit existing contributor docs for version references, command ordering, and stale technology mentions.
- Update `README.md` quick-start consistency and architecture/project structure guidance for contributors.
- Update `INSTALLATION.md` wording for ROCm 7.2 clarity and explicit application launch step.
- Run documentation QA checks plus full regression suite in project virtual environment.

### Completion Notes List

- Updated `README.md` quick start to use consistent pip/build-tooling upgrade command and added contributor-facing repository structure section aligned with current boundaries.
- Updated `INSTALLATION.md` wording to ROCm 7.2-specific guidance and added explicit run command via `python -m src.app.main`.
- Verified no stale references remain in scoped docs (`README.md`, `INSTALLATION.md`) for Python 3.11 / ROCm 6.1 / Coqui.
- Executed regression suite in project venv: `.venv/bin/python -m pytest tests/ -q` with `294 passed, 1 warning`.
- **Code review fixes applied:**
  - Fixed `pyproject.toml` to require Python >=3.12 (was >=3.10)
  - Enhanced README architecture overview with explicit mention of `src/contracts/` and clearer boundaries
  - Expanded repository structure section with detailed subdirectory breakdown
  - Added dev dependencies installation instructions to README
  - Corrected expected test count in INSTALLATION.md (294 passed, not 270)
  - Replaced `PASSE_2_RAPPORT.md` with historical note redirecting to current docs
  - Updated `project-brief.md` to remove Coqui TTS reference

### File List

- README.md
- INSTALLATION.md
- pyproject.toml
- PASSE_2_RAPPORT.md
- \_bmad-output/project-brief.md
- \_bmad-output/implementation-artifacts/6-4-update-project-documentation-for-current-stack.md
- \_bmad-output/implementation-artifacts/sprint-status.yaml

## Change Log

- 2026-02-18: Refreshed contributor documentation for current stack (Python 3.12, ROCm 7.2, venv flow), aligned architecture + repository structure guidance, and validated via full regression test run.
- 2026-02-18: Applied code review fixes - corrected pyproject.toml Python requirement, enhanced architecture overview, expanded repository structure, fixed test count, cleaned stale references from PASSE_2_RAPPORT.md and project-brief.md.

## Story Completion Status

- Story ID: `6.4`
- Story Key: `6-4-update-project-documentation-for-current-stack`
- Status set to: `done`
- Completion note: Documentation updated and validated against current stack and implementation boundaries. Code review fixes applied to ensure full AC compliance.
