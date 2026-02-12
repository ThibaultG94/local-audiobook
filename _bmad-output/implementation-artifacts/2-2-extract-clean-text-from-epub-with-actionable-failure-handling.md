# Story 2.2: Extract Clean Text from EPUB with Actionable Failure Handling

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user importing an EPUB,
I want the system to extract readable text content reliably,
so that I can proceed to conversion without manual copy cleanup.

## Acceptance Criteria

1. **Given** an imported `.epub` document accepted by `import_service.py`  
   **When** extraction is executed through `epub_extractor.py`  
   **Then** textual content is returned in reading order with basic cleanup of empty structural nodes  
   **And** extraction output is normalized for downstream chunking inputs.

2. **Given** malformed EPUB structure or unreadable package resources  
   **When** extraction fails  
   **Then** the service returns standardized output with `ok=false`  
   **And** the error follows `{code, message, details, retryable}`.

3. **Given** extracted content must be auditable for troubleshooting  
   **When** extraction completes or fails  
   **Then** events are logged via `jsonl_logger.py` with `stage=extraction` and `engine=epub`  
   **And** each event includes `correlation_id`, `job_id`, `event`, `severity`, and ISO-8601 UTC `timestamp`.

4. **Given** the UI must provide immediate feedback  
   **When** EPUB extraction succeeds or fails  
   **Then** status and actionable message are surfaced through `conversion_presenter.py`  
   **And** user-facing text is in English for MVP consistency.

## Tasks / Subtasks

- [ ] Implement EPUB extractor adapter in `src/adapters/extraction/epub_extractor.py` with deterministic reading-order output (AC: 1)
  - [ ] Parse EPUB spine/resources via `ebooklib` and concatenate readable text sections in document order
  - [ ] Apply baseline cleanup (empty nodes, duplicate whitespace, trivial markup remnants)
  - [ ] Return normalized extraction payload ready for chunking service ingestion
- [ ] Wire extraction orchestration path for EPUB through service layer (AC: 1, 2, 4)
  - [ ] Route `.epub` documents from import/extraction flow to `epub_extractor.py`
  - [ ] Map extractor failures to normalized `{ok, data, error}` contract using shared error schema
  - [ ] Ensure presenter pathway emits actionable English feedback for success/failure states
- [ ] Add structured observability for EPUB extraction lifecycle (AC: 3)
  - [ ] Emit `domain.action` events for extraction start/success/failure with `stage=extraction` and `engine=epub`
  - [ ] Include required schema fields (`correlation_id`, `job_id`, `event`, `severity`, `timestamp`) in every log line
- [ ] Add test coverage for extraction quality, failures, and UI-facing behavior (AC: 1..4)
  - [ ] Unit tests for reading order and cleanup behavior on representative EPUB fixtures
  - [ ] Unit tests for malformed/unreadable EPUB mapping to normalized errors
  - [ ] Integration tests for event emission schema and presenter-facing actionable messaging

## Dev Notes

### Story Intent

- This story delivers EPUB-only extraction robustness for Epic 2 and must produce deterministic, chunking-ready text from valid `.epub` inputs.
- The goal is not to build generic import behavior again; Story 2.1 already established intake validation and document persistence.
- This story must harden extraction quality and failure semantics so downstream conversion can trust extractor outputs.

### Story Context and Dependencies

- Story dependency: [Story 2.1 import flow](./2-1-import-local-multi-format-documents-with-input-validation.md) is complete and provides file acceptance, normalized result/error contracts, and correlation-aware logging base.
- Upstream contract continuity required with:
  - `src/contracts/result.py` (`{ok, data, error}` envelope)
  - `src/contracts/errors.py` (`{code, message, details, retryable}` error schema)
- Downstream dependencies:
  - Story 2.5 relies on consistent extractor failure mapping for unified diagnostics
  - Epic 3 chunking/orchestration depends on clean extraction payload shape
- Scope boundary:
  - implement EPUB extractor behavior and integration path only
  - do not introduce fallback logic in adapters (fallback policy remains orchestration concern)

### Technical Requirements

- Extractor output contract must be deterministic for identical EPUB inputs:
  - stable section ordering from EPUB spine/navigation order
  - normalized text output with predictable newline handling
  - no UI-thread blocking operations in extraction path
- Standardized service-level result format is mandatory:
  - success/failure envelope `{ok, data, error}`
  - normalized error payload `{code, message, details, retryable}`
- Failure taxonomy for EPUB extraction should distinguish at minimum:
  - unreadable archive/container
  - malformed package metadata/spine
  - no extractable textual payload
  - unexpected parsing/runtime exception
- Logging requirements for extraction events:
  - `stage=extraction`, `engine=epub`
  - include `correlation_id`, `job_id`, `event`, `severity`, `timestamp`
  - keep event naming in `domain.action` convention
- MVP UX and privacy constraints:
  - actionable user-facing messages in English
  - no cloud/network calls in extraction flow

### Architecture Compliance

- Respect layered boundaries from architecture:
  - UI layer (`src/ui/`) displays state and triggers actions only
  - extraction logic lives in adapters (`src/adapters/extraction/`)
  - orchestration and result mapping remain in service/application layers
- Keep repository and persistence boundaries untouched for this story:
  - no schema or migration change is required strictly for EPUB parsing behavior
  - do not bypass repository abstractions from UI/presenter code
- Enforce project-wide consistency rules:
  - `snake_case` keys and identifiers
  - UTC ISO-8601 timestamps in events
  - standardized result/error envelopes and `domain.action` event naming
- Preserve orchestration policy boundaries:
  - no engine fallback policy in extractor adapter
  - no direct coupling to conversion worker internals from extractor

### Library & Framework Requirements

- EPUB parsing implementation must use `ebooklib` as defined by PRD and architecture constraints.
- Existing logging infrastructure must be reused:
  - `src/infrastructure/logging/jsonl_logger.py`
  - `src/infrastructure/logging/event_schema.py`
- Existing normalized contracts must be reused without divergence:
  - `src/contracts/result.py`
  - `src/contracts/errors.py`
- No new extraction framework should be introduced for EPUB in MVP unless explicitly justified by a blocking defect.
- Keep compatibility with current Python project structure and testing approach (`tests/unit` and `tests/integration`).

### File Structure Requirements

- Primary implementation target for this story:
  - `src/adapters/extraction/epub_extractor.py`
- Service wiring / orchestration touchpoints (if missing or partial):
  - `src/domain/services/import_service.py` (or extraction orchestration service boundary)
  - `src/ui/presenters/conversion_presenter.py` for actionable success/failure messaging
- Logging/event integration points:
  - `src/infrastructure/logging/jsonl_logger.py`
  - `src/infrastructure/logging/event_schema.py`
- Test locations:
  - `tests/unit/` for extractor parsing and error mapping
  - `tests/integration/` for end-to-end extraction contract and event emission validation
- Do not place extractor logic in UI modules or repository classes.

### Testing Requirements

- Unit tests for EPUB extraction behavior:
  - preserves deterministic reading order across representative EPUB fixtures
  - removes empty/non-content structural artifacts without deleting meaningful text
  - yields chunking-ready normalized text payloads
- Unit tests for error normalization:
  - malformed EPUB container/package returns `{ok:false}` with normalized error object
  - unreadable/missing resource paths map to stable `code` values and actionable `message/details`
  - retryability semantics are explicit and consistent
- Integration tests for service + observability path:
  - extraction success emits expected `domain.action` event(s) with `stage=extraction`, `engine=epub`
  - extraction failure emits diagnostics events with required schema fields and UTC ISO-8601 timestamp
  - presenter receives actionable English message payload aligned with normalized result/error contracts
- Regression guardrails:
  - existing Story 2.1 import tests remain green
  - no regressions in startup/readiness test suites from Epic 1

### Previous Story Intelligence

- Reuse the import boundary created in Story 2.1 instead of re-validating file extensions in EPUB extraction internals.
- Keep contract consistency already established in Story 2.1:
  - return standardized result envelope and normalized errors only
  - include correlation-aware logging fields expected by integration tests
- Follow recently reinforced review fixes from Story 2.1:
  - avoid schema drift and naming drift (`snake_case` everywhere)
  - prefer centralized constants/contracts instead of duplicating literals across layers
  - preserve actionable, deterministic failure messaging for UI consumption
- Implementation focus for 2.2 is extraction correctness and failure handling; avoid expanding scope into PDF/TXT/MD extraction paths.

### Git Intelligence Summary

- Recent commits show strong momentum on Story 2.1 import flow and adversarial review hardening; Story 2.2 should preserve these hardened contracts.
- Files frequently touched in the latest 5 commits indicate current implementation center of gravity:
  - `src/domain/services/import_service.py`
  - `src/ui/views/import_view.py`
  - `src/adapters/persistence/sqlite/repositories/documents_repository.py`
  - integration/unit tests around import and readiness flows
- Actionable implications for Story 2.2:
  - integrate EPUB extraction through existing service pathways rather than introducing parallel flows
  - keep test-first discipline consistent with recent commits (unit + integration updates together)
  - maintain sprint artifact hygiene (`_bmad-output/implementation-artifacts/*.md` and sprint status updates) in same style

### Project Structure Notes

- Align implementation with architecture boundaries:
  - extraction adapter code under `src/adapters/extraction/`
  - orchestration and result mapping in service layer
  - presenter-only user feedback formatting in UI layer
- No project structure variance is required for this story if `epub_extractor.py` is created/updated in-place and wired through existing service paths.

### References

- Story and acceptance criteria source: `_bmad-output/planning-artifacts/epics.md` (Epic 2, Story 2.2)
- Product scope and non-functional constraints: `_bmad-output/planning-artifacts/prd.md` (FR5, FR8, NFR1, NFR6, NFR12, NFR14)
- Architecture boundaries and consistency rules: `_bmad-output/planning-artifacts/architecture.md`
- Previous implementation intelligence: `_bmad-output/implementation-artifacts/2-1-import-local-multi-format-documents-with-input-validation.md`
- Sprint tracking source: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log --oneline -n 5`
- `git log --name-only --pretty=format:'--- %h %s' -n 5`

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story status set to `ready-for-dev`.
- Story scoped to EPUB extraction quality, normalized failure handling, and actionable UI diagnostics.
- Reuse Story 2.1 contracts and observability baseline; avoid scope expansion into PDF/TXT/MD extractors.

### File List

- _bmad-output/implementation-artifacts/2-2-extract-clean-text-from-epub-with-actionable-failure-handling.md

## Change Log

- 2026-02-12: Story created with exhaustive implementation context for EPUB extraction, normalized failure handling, observability requirements, and architecture guardrails.
