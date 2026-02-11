# Story 1.1: Initialize Local Application Foundation and Persistent Job Store

Status: ready-for-dev

## Story

As a privacy-first desktop user,
I want the application to initialize with local persistence and baseline schema migrations,
so that conversion jobs and offline readiness state are reliably stored on my machine.

## Acceptance Criteria

1. **Given** a fresh Linux Mint installation target and an empty runtime directory  
   **When** app bootstrap is executed through `main.py` and SQLite setup in `connection.py`  
   **Then** a local SQLite database file is created and reachable through repository boundaries only  
   **And** no network dependency is required for initialization.

2. **Given** dependency wiring is required for service boundary enforcement  
   **When** bootstrap initializes service composition in `dependency_container.py`  
   **Then** core services, repositories, providers, and logging are resolved through the container  
   **And** UI layers consume dependencies via container wiring rather than direct infrastructure instantiation.

3. **Given** initial migration file `0001_initial_schema.sql`  
   **When** migrations are applied at startup  
   **Then** required MVP tables for documents, jobs, chunks, library, and diagnostics are created in `snake_case`  
   **And** migration state is persisted to prevent re-applying the same migration.

4. **Given** job state management in `tts_orchestration_service.py` depends on persistence  
   **When** persistence layer writes or updates job state  
   **Then** only allowed states `queued`, `running`, `paused`, `failed`, `completed` are accepted by service validation  
   **And** invalid transitions return normalized errors via `result.py` and `errors.py`.

5. **Given** observability is required from first executable increment  
   **When** startup and migration events occur  
   **Then** JSONL log events are emitted by `jsonl_logger.py` with fields `correlation_id`, `job_id`, `chunk_index`, `engine`, `stage`, `event`, `severity`, `timestamp`  
   **And** events use `domain.action` naming and UTC ISO-8601 timestamps.

## Tasks / Subtasks

- [ ] Create baseline Python app scaffold and packaging files (AC: 1, 2)
  - [ ] Add `pyproject.toml`, `.python-version`, `.env.example`, `.gitignore`, `README.md`
  - [ ] Create folder boundaries from architecture: `src/`, `tests/`, `migrations/`, `config/`, `runtime/`
  - [ ] Create `config/app_config.yaml` with bootstrap-safe local defaults (paths, database file location, runtime directories)
  - [ ] Create `config/logging_config.yaml` with JSONL logger baseline configuration for local runtime
  - [ ] Add runtime subfolders: `runtime/logs`, `runtime/library/audio`, `runtime/library/temp`

- [ ] Implement bootstrap entrypoint and dependency wiring (AC: 1, 2)
  - [ ] Add `src/app/main.py` startup orchestration (settings, DB init, migration runner, logger bootstrap)
  - [ ] Add `src/app/dependency_container.py` for service/repository/provider construction
  - [ ] Keep `dependency_container.py` framework-agnostic (pure Python): no direct `PyQt5` imports in Story 1.1
  - [ ] Ensure future UI/service construction can consume container-provided dependencies without changing container internals

- [ ] Implement SQLite connectivity and repository boundary foundations (AC: 1, 2, 4)
  - [ ] Add `src/adapters/persistence/sqlite/connection.py` with local file DB initialization
  - [ ] Add repository stubs under `src/adapters/persistence/sqlite/repositories/`
  - [ ] Enforce no direct SQLite access from UI modules

- [ ] Implement migration mechanism with version tracking (AC: 3)
  - [ ] Add `migrations/0001_initial_schema.sql` with MVP tables: documents, conversion_jobs, chunks, library_items, diagnostics_events, schema_migrations
  - [ ] Keep `diagnostics_events` intentionally minimal in Story 1.1 scope (`id`, `correlation_id`, `timestamp`, `payload`) to satisfy baseline persistence without pre-implementing Epic 5 schema hardening
  - [ ] Add migration runner invoked during startup
  - [ ] Persist applied migration version/checksum in `schema_migrations`

- [ ] Implement normalized contracts for results/errors and job-state validation (AC: 4)
  - [ ] Add `src/contracts/result.py` for `{ok, data, error}`
  - [ ] Add `src/contracts/errors.py` for `{code, message, details, retryable}`
  - [ ] Add dedicated job transition validator in service layer for `queued/running/paused/failed/completed` (e.g. `src/domain/services/job_state_validator.py`)
  - [ ] If `src/domain/services/tts_orchestration_service.py` is introduced as stub in this story, validator is consumed there; transition rules must remain outside repositories

- [ ] Implement initial JSONL observability skeleton (AC: 5)
  - [ ] Add `src/infrastructure/logging/event_schema.py` required field contract
  - [ ] Add `src/infrastructure/logging/jsonl_logger.py` append-only JSONL writer
  - [ ] Emit startup/migration events: `bootstrap.started`, `bootstrap.completed`, `migration.started`, `migration.applied`, `migration.completed`, `migration.failed`

- [ ] Add tests for bootstrap, migrations, and contracts (AC: 1..5)
  - [ ] Unit tests for result/error contracts and state-transition validator
  - [ ] Integration tests for fresh bootstrap creating DB and schema
  - [ ] Integration tests for migration idempotency (re-run does not re-apply)
  - [ ] Integration tests for JSONL events and required fields/timestamp format

## Dev Notes

### Story Scope and Intent

- This story creates the **implementation foundation** for the whole MVP: deterministic scaffold, SQLite persistence core, migration baseline, normalized contracts, and logging skeleton.
- It is intentionally infra-heavy and should avoid implementing later-story business behavior (import/extraction/conversion/playback) beyond required interfaces/stubs.

### Architecture Guardrails (Must Follow)

- **Layer boundaries:** UI must not directly access DB, provider adapters, or filesystem persistence internals.
- **Persistence boundary:** all DB access goes through repository adapters in `src/adapters/persistence/sqlite/repositories/`.
- **State boundary:** job-state transitions are validated in service layer only (never directly in UI/repository).
- **Validation placement:** transition rule logic must be in a dedicated domain/service module (e.g. `job_state_validator.py`) or service stub, never embedded in repository CRUD code.
- **Container boundary (Story 1.1):** `dependency_container.py` must remain pure Python and testable without Qt runtime; Qt wiring belongs to later UI stories.
- **Fallback boundary (future stories):** fallback policy belongs in orchestration service, not provider adapters.
- **Offline boundary:** initialization path must not perform network calls.

### Technical Requirements

- Stack: Python desktop architecture with PyQt5-oriented layering from architecture decisions.
- Persistence: SQLite as system source of truth for jobs/chunks/library/diagnostics metadata.
- Migrations: SQL migrations under `migrations/` with startup application and durable migration state.
- Contracts:
  - success/failure envelope: `{ok, data, error}`
  - error shape: `{code, message, details, retryable}`
- Naming conventions:
  - Python files/functions/variables/modules in `snake_case`
  - classes in `PascalCase`
  - DB tables/columns in `snake_case`
  - events in `domain.action`
- Time and format:
  - timestamps in UTC ISO-8601
  - JSON fields in `snake_case`

### File Structure Requirements

- Required top-level scaffold:
  - `config/` (app/logging/model manifests)
  - `migrations/` (versioned SQL)
  - `runtime/logs`, `runtime/library/audio`, `runtime/library/temp`
  - `src/` with boundaries `app`, `ui`, `domain`, `adapters`, `infrastructure`, `contracts`
  - `tests/unit` and `tests/integration`
- This story should establish these directories even if many files are placeholders.

### Testing Requirements

- Validate ACs with both unit and integration tests.
- Must include idempotency test for migrations.
- Must include contract tests for result/error envelope and job-state validation.
- Must include logging schema conformance tests for required keys and timestamp format.
- Must include a test that importing `dependency_container.py` succeeds in a non-Qt test context.
- Keep tests deterministic and local-only (no network, no external service calls).

### Anti-Patterns to Prevent

- Direct DB calls from UI/presenter/worker modules.
- Job status writes bypassing service validation.
- Job transition rules implemented inside repository methods.
- Importing `PyQt5` (or other UI runtime deps) inside `dependency_container.py`.
- Free-form exception strings returned to callers instead of normalized error objects.
- Emitting unstructured logs or missing required correlation fields.
- Creating non-architecture paths (e.g., ad-hoc folders outside prescribed structure).

### Dependencies and Sequencing

- Story 1.1 is the baseline dependency for Story 1.2 and all later epics.
- `diagnostics_events` exists in this story only as minimal bootstrap persistence; full diagnostics schema/contract enforcement is deferred to Epic 5 hardening stories.
- Keep implementation atomic and incremental:
  1. scaffold,
  2. DB connection,
  3. migration runner + schema,
  4. contracts,
  5. logging,
  6. tests.

### References

- Epic definition and AC source: `_bmad-output/planning-artifacts/epics.md` (Story 1.1)
- Architecture constraints and structure: `_bmad-output/planning-artifacts/architecture.md` (Core Architectural Decisions, Project Structure & Boundaries)
- Product requirements baseline: `_bmad-output/planning-artifacts/prd.md` (FR27, FR28, NFR1, NFR4, NFR6, NFR9, NFR13, NFR14)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- N/A (story creation phase)

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story is ready for implementation with architecture-compliant guardrails and explicit anti-pattern prevention.

### File List

- _bmad-output/implementation-artifacts/1-1-initialize-local-application-foundation-and-persistent-job-store.md
