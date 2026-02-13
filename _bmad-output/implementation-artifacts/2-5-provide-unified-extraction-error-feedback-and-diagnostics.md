# Story 2.5: Provide Unified Extraction Error Feedback and Diagnostics

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user performing document import and extraction,
I want extraction failures to be reported consistently with clear remediation guidance,
so that I can quickly resolve issues and retry successfully.

## Acceptance Criteria

1. **Given** extraction outcomes from `epub_extractor.py`, `pdf_extractor.py`, and `text_extractor.py`  
   **When** any extractor returns a failure  
   **Then** the failure is mapped into a unified response format `{ok, data, error}`  
   **And** error payload includes `code`, `message`, `details`, and `retryable`.

2. **Given** UI error rendering in `conversion_presenter.py`  
   **When** a normalized extraction error is received  
   **Then** users see actionable English messages with next-step remediation  
   **And** retry controls are enabled only when `retryable=true`.

3. **Given** traceability requirements for diagnostics FR29 and FR30  
   **When** extraction errors are raised and displayed  
   **Then** JSONL events are logged by `jsonl_logger.py` with `stage=extraction` and stable `domain.action` names such as `extraction.failed` and `diagnostics.presented`  
   **And** each log includes `correlation_id`, `job_id`, `engine`, `event`, `severity`, and ISO-8601 UTC `timestamp`.

4. **Given** MVP scope excludes cloud dependencies  
   **When** remediation guidance is generated  
   **Then** all guidance remains local-only and references local corrective actions  
   **And** no network call is attempted in the error-handling path.

## Tasks / Subtasks

- [x] Unify extraction failure envelope at orchestration boundary in `src/domain/services/import_service.py` (AC: 1)
  - [x] Ensure every extractor failure path returns `{ok, data, error}` with normalized `AppError` shape.
  - [x] Standardize `details` fields across EPUB/PDF/TXT-MD paths (`source_path`, `source_format`, optional extractor-specific keys).
  - [x] Keep extractor-unavailable and unsupported-format failures deterministic and non-ambiguous.
- [x] Harden extraction UI diagnostics mapping in `src/ui/presenters/conversion_presenter.py` (AC: 2, 4)
  - [x] Map normalized extraction error codes to actionable English remediation messages.
  - [x] Surface retry affordance only when `retryable=true`.
  - [x] Keep remediation local-only (file integrity, encoding fix, file permissions, local re-import).
- [x] Add explicit diagnostics event emission for UI-facing failure presentation (AC: 3)
  - [x] Emit `diagnostics.presented` when extraction failure is transformed into user-facing guidance.
  - [x] Keep event payload compliant with required schema fields in `event_schema.py`.
  - [x] Preserve `domain.action` naming and ISO-8601 UTC timestamp behavior.
- [x] Add regression-safe tests for unified extraction diagnostics behavior (AC: 1..4)
  - [x] Unit tests for normalized error envelope consistency across extractor failure variants.
  - [x] Presenter tests for deterministic message mapping and retry toggle semantics.
  - [x] Integration tests for extraction failure logging plus `diagnostics.presented` event emission.

## Dev Notes

### Story Intent

- Consolidate extraction failure handling into one predictable diagnostics contract used by services, presenters, and logs.
- Prevent drift between extractor adapters and user-facing diagnostics wording.
- Preserve existing extraction behavior while hardening failure transparency and supportability.

### Story Context and Dependencies

- Prior stories established the extraction surface:
  - Story 2.2 (`epub_extractor.py`)
  - Story 2.3 (`pdf_extractor.py`)
  - Story 2.4 (`text_extractor.py`)
- Contract anchors already in place and must remain authoritative:
  - `src/contracts/result.py` for `{ok, data, error}`
  - `src/contracts/errors.py` for `{code, message, details, retryable}`
- Routing and failure aggregation boundary is `ImportService.extract_document()` in `src/domain/services/import_service.py`.

### Developer Context Section

Current baseline indicates extraction adapters already emit `extraction.started|succeeded|failed` and return normalized failures. This story should avoid adding parallel contracts and should instead tighten consistency and UI diagnostics quality:

- Existing adapter failure emitters:
  - `src/adapters/extraction/epub_extractor.py`
  - `src/adapters/extraction/pdf_extractor.py`
  - `src/adapters/extraction/text_extractor.py`
- Existing presenter error mapping:
  - `src/ui/presenters/conversion_presenter.py`
- Existing schema enforcement:
  - `src/infrastructure/logging/event_schema.py`
  - `src/infrastructure/logging/jsonl_logger.py`

### Technical Requirements

- Unified extraction failure contract must be preserved end-to-end without ad-hoc payload formats.
- `details` must remain structured (no free-form-only strings) and include enough context for local remediation.
- Presenter must convert technical failures into concise, actionable, English-only guidance.
- Retry semantics must be data-driven from `retryable`, not inferred from message text.

### Architecture Compliance

- Keep adapter logic in `src/adapters/extraction/`.
- Keep cross-extractor failure normalization in service layer (`src/domain/services/`).
- Keep user-facing phrasing and display semantics in presenter layer (`src/ui/presenters/`).
- Keep diagnostics events in centralized logging infrastructure (`src/infrastructure/logging/`).
- No cloud/service integrations in extraction diagnostics pathways.

### Library / Framework Requirements

- No new dependency is required for this story.
- Maintain current extraction dependencies from `pyproject.toml`:
  - `EbookLib>=0.18`
  - `PyPDF2>=3.0.0`
- Use existing stdlib+current helpers for text and markdown normalization.

### File Structure Requirements

- Primary implementation files:
  - `src/domain/services/import_service.py`
  - `src/ui/presenters/conversion_presenter.py`
  - `src/infrastructure/logging/jsonl_logger.py` (only if diagnostics event instrumentation needs extension)
- Likely test coverage files:
  - `tests/unit/test_extraction_orchestration.py`
  - `tests/unit/test_conversion_presenter.py`
  - `tests/integration/test_import_flow_integration.py`

### Testing Requirements

- Verify contract consistency for failures from EPUB, PDF, and TXT/MD extraction flows.
- Verify presenter output is deterministic and actionable for each known extraction error class.
- Verify retry control semantics strictly follow `retryable`.
- Verify `diagnostics.presented` logging event payload passes `validate_event_payload` requirements.

### Previous Story Intelligence

- Story 2.4 reinforced deterministic extraction and strict normalized error mapping; preserve that approach.
- Previous extraction stories used contract-first implementation and broad regression coverage; continue same discipline.
- Prior review hardening emphasized absolute imports, explicit edge-case validation, and predictable messages.

### Git Intelligence Summary

Recent commits indicate extraction and diagnostics hardening trajectory:

- `093c620` code-review fixes for Story 2.4
- `9912d4e` implementation of Story 2.4 text/markdown extraction
- `7918757` story artifact generation for Story 2.4
- `e2015fd` robustness/test fixes for Story 2.3
- `14d35d1` PDF extraction flow implementation

Implementation implication: Story 2.5 should focus on consistency, diagnostics clarity, and regression-safe integration rather than introducing new architecture.

### Latest Tech Information

- No framework upgrade is required to satisfy this story.
- Stability priority is strict contract conformance and diagnostics event quality.
- Existing dependency floor (`Python >=3.10`) and extractor package set are sufficient for AC coverage.

### Project Context Reference

- No `project-context.md` file was found using configured discovery pattern.
- Context for this story is derived from `epics.md`, `prd.md`, `architecture.md`, sprint tracking, and existing implementation artifacts.

### References

- Story source: `_bmad-output/planning-artifacts/epics.md` (Epic 2, Story 2.5)
- Product constraints: `_bmad-output/planning-artifacts/prd.md` (FR8, FR29, FR30; NFR6, NFR14)
- Architecture guardrails: `_bmad-output/planning-artifacts/architecture.md`
- Prior implementation artifacts:
  - `_bmad-output/implementation-artifacts/2-2-extract-clean-text-from-epub-with-actionable-failure-handling.md`
  - `_bmad-output/implementation-artifacts/2-3-extract-text-from-pdf-with-degraded-case-handling.md`
  - `_bmad-output/implementation-artifacts/2-4-extract-and-normalize-txt-and-markdown-inputs.md`
- Sprint tracking: `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Story Completion Status

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story status set to `ready-for-dev`.
- Story includes implementation guardrails for unified failure contracts, actionable diagnostics, and event-level traceability.

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `cat _bmad-output/implementation-artifacts/sprint-status.yaml`
- `cat _bmad-output/planning-artifacts/epics.md`
- `cat _bmad-output/planning-artifacts/prd.md`
- `cat _bmad-output/planning-artifacts/architecture.md`
- `git log --oneline -n 5`
- `python -m unittest tests.unit.test_extraction_orchestration tests.integration.test_import_flow_integration`
- `PYTHONPATH=src python -m unittest tests.unit.test_extraction_orchestration tests.integration.test_import_flow_integration`
- `PYTHONPATH=src python -m unittest discover -s tests`
- `git status --short`

### Completion Notes List

- Story scaffolded and marked `ready-for-dev`.
- Acceptance criteria aligned to Epic 2 Story 2.5.
- Developer context includes architecture constraints, previous story learnings, and diagnostics-focused guardrails.
- Implementation guidance emphasizes normalized error envelope consistency, deterministic presenter mapping, and extraction diagnostics event coverage.
- Implemented extraction failure normalization in `ImportService.extract_document()` to guarantee deterministic `{ok, data, error}` failures with consistent `details` keys (`source_path`, `source_format`, `correlation_id`, `job_id`) across unsupported/extractor-unavailable and propagated adapter failures.
- Hardened extraction diagnostics in `ConversionPresenter.map_extraction()` with local-only remediation wording, explicit retry gating via `retryable`, and standardized UI payload field `retry_enabled`.
- Added `diagnostics.presented` event emission from presenter failure mapping with schema-compatible payload (`stage`, `event`, `severity`, `correlation_id`, `job_id`, `engine`, `timestamp`) through injected logger.
- Updated dependency wiring so presenter can receive logger injection via `build_conversion_presenter(logger=...)` without introducing network/cloud behavior.
- Added/updated regression coverage for normalized error details, retry semantics, and diagnostics event emission in unit/integration suites.
- Validation complete: `PYTHONPATH=src python -m unittest discover -s tests` → 72 tests passed.
- **Code review fixes applied (2026-02-13):**
  - Fixed absolute imports in `src/app/dependency_container.py` (was using relative imports, now uses `src.*` prefix)
  - Added validation for non-empty `correlation_id` and `job_id` in `ImportService.extract_document()` with explicit error codes
  - Added contract violation logging when extractors return invalid error payloads (missing error or non-dict details)
  - Added type validation for `extraction_result.error.details` to prevent runtime crashes
  - Centralized `NoopLogger` implementation in `src/infrastructure/logging/noop_logger.py` to eliminate duplication
  - Updated `ConversionPresenter` to use shared `NoopLogger` instead of local duplicate
  - Enhanced remediation messages to explicitly mention "local" operations (AC4 compliance)
  - Added comprehensive test coverage for edge cases: empty IDs, invalid details types, None logger handling
  - Added integration tests for PDF and TXT extraction failure diagnostics event emission
  - All tests passing: 78 tests in 2.034s

### File List

- _bmad-output/implementation-artifacts/2-5-provide-unified-extraction-error-feedback-and-diagnostics.md
- src/domain/services/import_service.py
- src/ui/presenters/conversion_presenter.py
- src/app/dependency_container.py
- src/infrastructure/logging/noop_logger.py
- tests/unit/test_extraction_orchestration.py
- tests/integration/test_import_flow_integration.py
- _bmad-output/implementation-artifacts/sprint-status.yaml

## Change Log

- 2026-02-13: Story created with comprehensive developer context and set to `ready-for-dev`.
- 2026-02-13: Implemented unified extraction diagnostics contract, presenter retry/local remediation mapping, `diagnostics.presented` logging, and regression coverage; story moved to `review`.
