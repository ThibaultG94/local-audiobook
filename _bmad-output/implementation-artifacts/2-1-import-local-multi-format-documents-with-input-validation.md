# Story 2.1: Import Local Multi-Format Documents with Input Validation

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a desktop user,
I want to import local EPUB PDF TXT and Markdown files through a single flow,
so that I can start extraction from a supported document without manual preprocessing.

## Acceptance Criteria

1. **Given** the import screen in `import_view.py`  
   **When** I select a local file with extension `.epub`, `.pdf`, `.txt`, or `.md`  
   **Then** the file is accepted and forwarded to `import_service.py`  
   **And** unsupported extensions are rejected with a normalized error from `errors.py`.

2. **Given** file metadata validation in `import_service.py`  
   **When** the selected file is unreadable, empty, or missing  
   **Then** the service returns `{ok, data, error}`  
   **And** the error includes `{code, message, details, retryable}` with actionable remediation.

3. **Given** accepted inputs must be traceable for downstream extraction  
   **When** an import succeeds  
   **Then** a document record is persisted via `documents_repository.py`  
   **And** fields use `snake_case` conventions and ISO-8601 UTC timestamps.

4. **Given** observability requirements for import failures  
   **When** import is accepted or rejected  
   **Then** JSONL events are emitted via `jsonl_logger.py` using `domain.action` names such as `import.accepted` and `import.rejected`  
   **And** each event includes `correlation_id`, `stage`, `event`, `severity`, and `timestamp`.

## Tasks / Subtasks

- [x] Implement unified import entry flow in `import_view.py` and route accepted files to `import_service.py` (AC: 1)
  - [x] Add extension whitelist for `.epub`, `.pdf`, `.txt`, `.md`
  - [x] Reject unsupported extension selection with normalized error contract from `errors.py`
- [x] Implement file metadata validation service in `import_service.py` (AC: 2)
  - [x] Validate existence, readability, and non-empty content before persistence
  - [x] Return normalized `Result` payload `{ok, data, error}` on all code paths
- [x] Persist imported document metadata through SQLite repository boundary (AC: 3)
  - [x] Add/extend repository operations in `adapters/persistence/sqlite/repositories/documents_repository.py`
  - [x] Ensure persisted metadata uses `snake_case` fields and UTC ISO-8601 timestamps
- [x] Emit import observability events for accepted/rejected outcomes (AC: 4)
  - [x] Emit `import.accepted` and `import.rejected` via `infrastructure/logging/jsonl_logger.py`
  - [x] Enforce required schema fields (`correlation_id`, `stage`, `event`, `severity`, `timestamp`)
- [x] Add test coverage for import validation, persistence, and observability contracts (AC: 1..4)
  - [x] Unit tests for extension filtering and error normalization
  - [x] Unit/integration tests for persistence metadata and timestamp format
  - [x] Integration test for JSONL `import.accepted` / `import.rejected` schema compliance

## Dev Notes

### Story Intent

- This story is the import gateway for Epic 2 and must establish a single, deterministic intake path for supported file types.
- Implementation must maximize reuse of existing application boundaries (`ui` → `app/domain services` → `repositories`) rather than introducing parallel pipelines.
- Output of this story is not extraction logic itself; it is trusted ingestion plus normalized validation and observability needed by downstream extraction stories.

### Story Context and Dependencies

- Epic 1 is complete and already provides:
  - local app foundation and migrations,
  - model/engine readiness checks,
  - baseline structured JSONL logging and contracts.
- Epic 2 starts here; this story must prepare data and diagnostics contracts consumed by:
  - Story 2.2 (`epub_extractor.py`),
  - Story 2.3 (`pdf_extractor.py`),
  - Story 2.4 (`text_extractor.py`),
  - Story 2.5 (unified extraction diagnostics).
- Keep strict contract continuity with `src/contracts/result.py` and `src/contracts/errors.py` so later stories can compose behavior without adapter rewrites.

### Technical Requirements

- Use normalized contracts everywhere import decisions are made:
  - success/failure envelope from `src/contracts/result.py`,
  - error schema from `src/contracts/errors.py` with `{code, message, details, retryable}`.
- Enforce extension whitelist exactly for MVP: `.epub`, `.pdf`, `.txt`, `.md` (case-insensitive at validation boundary).
- Validate metadata before persistence and extraction handoff:
  - path exists,
  - path is readable,
  - file is non-empty,
  - extension is supported.
- Generate a stable `correlation_id` at import initiation and propagate it through persistence + logging calls.
- Timestamps persisted or logged by import flow must be UTC ISO-8601.
- Keep all payload keys in `snake_case`; avoid ad-hoc key naming.

### Architecture Compliance

- Preserve layered boundaries from the architecture document:
  - `src/ui/*` handles interaction and display only,
  - application/domain services perform validation and orchestration,
  - SQLite adapters/repositories handle storage.
- Do not put extraction-format-specific logic in UI modules; keep import acceptance generic and route by service contracts.
- Keep fallback policy out of import adapters; deterministic fallback remains centralized in orchestration services for later conversion stories.
- Respect local-first constraints:
  - no cloud calls,
  - no remote telemetry,
  - structured logs remain local JSONL only.
- Maintain compatibility with existing migration and repository conventions; do not introduce ad-hoc tables outside migration workflow.

### Library & Framework Requirements

- Python application conventions already established in this repository must be reused (module naming, packaging, tests split).
- UI implementation must remain aligned with the current Qt-based UI layer patterns in `src/ui/`.
- Persistence must remain SQLite-backed through existing adapter/repository layer (`src/adapters/persistence/sqlite/repositories/`).
- Logging must use `src/infrastructure/logging/jsonl_logger.py` and schema definitions from `src/infrastructure/logging/event_schema.py`.
- Import format support in this story is intake validation only for `.epub`, `.pdf`, `.txt`, `.md`; extractor-specific libraries and parsing behavior are implemented in Stories 2.2–2.4.

### File Structure Requirements

- New UI import entrypoints should live under `src/ui/views/` and/or `src/ui/presenters/` following existing conversion UI patterns.
- Import service/orchestration code should live under `src/domain/services/` (or app-layer orchestration if consistent with existing composition), not in adapters.
- Persistence logic must remain in `src/adapters/persistence/sqlite/repositories/documents_repository.py` and related repository abstractions.
- Contract/data-shape changes must remain centralized in `src/contracts/` to avoid drift in error/result envelopes.
- Observability changes must remain in `src/infrastructure/logging/` without introducing parallel logging mechanisms.
- Tests should be placed in:
  - `tests/unit/` for import validation and mapping behavior,
  - `tests/integration/` for repository persistence + JSONL schema compliance paths.

### Testing Requirements

- Unit tests must cover whitelist acceptance/rejection behavior for `.epub`, `.pdf`, `.txt`, `.md` and unsupported extensions.
- Unit tests must verify normalized error mapping for missing/unreadable/empty files (`code`, `message`, `details`, `retryable`).
- Integration tests must verify successful import persistence path to documents repository with `snake_case` fields and UTC ISO-8601 timestamps.
- Integration tests must verify JSONL emissions for `import.accepted` and `import.rejected` with required schema fields.
- Regression guard: existing Epic 1 readiness and logging tests must keep passing; no import changes may break current startup/readiness flows.

### Project Structure Notes

- Align implementation with existing layered boundaries already present under `src/` (`ui`, `app/domain services`, `adapters`, `infrastructure`).
- Keep import acceptance/validation minimal and composable so extraction-specific logic is implemented in subsequent stories.
- Reuse existing repository and logging infrastructure; avoid introducing alternative persistence or telemetry paths.

### References

- Epic and AC source: `_bmad-output/planning-artifacts/epics.md` (Epic 2, Story 2.1)
- Product requirements traceability: `_bmad-output/planning-artifacts/prd.md` (FR1–FR8, NFR1, NFR12, NFR14)
- Architecture constraints and boundaries: `_bmad-output/planning-artifacts/architecture.md`
- Sprint tracking source: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log --oneline -n 5`
- `git log --name-only --pretty=format:'--- %h %s' -n 5`
- `PYTHONPATH=src python -m unittest tests.unit.test_import_flow tests.integration.test_import_flow_integration -v`
- `PYTHONPATH=src python -m unittest discover -s tests -v`

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story status set to `ready-for-dev`.
- Story scoped to import intake validation and observability only; extraction implementations deferred to Stories 2.2–2.4.
- Added framework-neutral import intake flow in `src/ui/views/import_view.py` with whitelist gating for `.epub`, `.pdf`, `.txt`, `.md` and normalized rejection contract.
- Implemented `src/domain/services/import_service.py` for metadata validation (missing/unreadable/empty), normalized `Result` responses, persistence orchestration, and correlation-aware `import.accepted` / `import.rejected` event emission.
- Extended `src/adapters/persistence/sqlite/repositories/documents_repository.py` with create operation persisting snake_case metadata and UTC ISO-8601 timestamps.
- Added unit and integration coverage for import validation, persistence contract, and JSONL schema requirements; executed full regression suite successfully (37 tests passing).

### File List

- _bmad-output/implementation-artifacts/2-1-import-local-multi-format-documents-with-input-validation.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/ui/views/import_view.py
- src/domain/services/import_service.py
- src/adapters/persistence/sqlite/repositories/documents_repository.py
- tests/unit/test_import_flow.py
- tests/integration/test_import_flow_integration.py

## Change Log

- 2026-02-12: Implemented Story 2.1 import intake flow, metadata validation service, repository persistence, import observability events, and test coverage for AC1–AC4.
