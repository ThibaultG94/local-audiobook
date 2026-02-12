# Story 2.3: Extract Text from PDF with Degraded-Case Handling

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user importing a PDF,
I want the system to extract usable text and flag degraded cases clearly,
so that I can decide whether to proceed or correct the source document.

## Acceptance Criteria

1. **Given** an imported `.pdf` accepted by `import_service.py`  
   **When** extraction runs through `pdf_extractor.py`  
   **Then** text is returned page by page in deterministic order  
   **And** blank or non-text pages are handled without crashing the extraction flow.

2. **Given** scanned-image PDFs or partially corrupted structures  
   **When** extraction quality is insufficient or parsing fails  
   **Then** the service returns normalized failure  
   **And** error payload includes `code`, `message`, `details`, and `retryable`.

3. **Given** the product requires local observability  
   **When** PDF extraction starts, completes, or fails  
   **Then** JSONL events are emitted through `jsonl_logger.py` with `stage=extraction` and `engine=pdf`  
   **And** each event carries `correlation_id`, `job_id`, `chunk_index` when relevant, `event`, `severity`, and UTC ISO-8601 `timestamp`.

4. **Given** users need clear feedback for remediation  
   **When** extraction result is rendered in `conversion_presenter.py`  
   **Then** success and failure messages are explicit and actionable in English  
   **And** downstream conversion controls remain blocked on extraction failure.

## Tasks / Subtasks

- [x] Implement PDF extractor adapter in `src/adapters/extraction/pdf_extractor.py` with deterministic page-order output (AC: 1)
  - [x] Parse PDF pages with `PyPDF2` and concatenate extracted text in stable page sequence.
  - [x] Normalize whitespace/newlines and preserve readable paragraph boundaries for chunking readiness.
  - [x] Handle pages with no extractable text without crashing, while recording per-page diagnostics.
- [x] Wire extraction orchestration path for PDF through service layer (AC: 1, 2, 4)
  - [x] Route `.pdf` documents to `pdf_extractor.py` from `ImportService.extract_document()`.
  - [x] Map degraded/failed extraction outcomes to normalized `{ok, data, error}` with `{code, message, details, retryable}`.
  - [x] Ensure presenter pathway surfaces actionable English success/failure feedback and blocks conversion launch on failed extraction.
- [x] Add structured observability for PDF extraction lifecycle (AC: 3)
  - [x] Emit `domain.action` events for extraction start/success/failure with `stage=extraction` and `engine=pdf`.
  - [x] Include required schema fields: `correlation_id`, `job_id`, `chunk_index`, `event`, `severity`, `timestamp`.
  - [x] Add degraded-case telemetry (e.g., non-text page count / extraction quality warnings) in `extra` payload.
- [x] Add test coverage for extraction quality, degraded cases, failures, and UI-facing behavior (AC: 1..4)
  - [x] Unit tests for deterministic page order, normalization, and empty-page handling.
  - [x] Unit tests for malformed/corrupted PDFs and scanned/non-text degraded cases mapped to normalized errors.
  - [x] Integration tests for event emission schema and presenter feedback consistency.

## Dev Notes

### Story Intent

- This story delivers robust PDF extraction for Epic 2 with explicit degraded-case handling, so downstream conversion can make deterministic go/no-go decisions.
- Scope is extraction and feedback quality, not conversion orchestration redesign.
- The implementation must preserve normalized contracts already established in import and EPUB extraction flows.

### Story Context and Dependencies

- Story dependency: [`Story 2.1`](./2-1-import-local-multi-format-documents-with-input-validation.md) provides import validation and persistence.
- Story dependency: [`Story 2.2`](./2-2-extract-clean-text-from-epub-with-actionable-failure-handling.md) establishes extraction contract patterns and observability baseline.
- Contract continuity required with [`result envelope`](src/contracts/result.py:1) and [`error schema`](src/contracts/errors.py:1).
- Current extraction orchestration exists in [`ImportService.extract_document()`](src/domain/services/import_service.py:139) and currently supports EPUB only; PDF path must be added without regression.
- Existing extraction adapter style in [`EpubExtractor`](src/adapters/extraction/epub_extractor.py:32) is the reference for deterministic output, event emission, and normalized failures.

### Technical Requirements

- Extraction output contract must stay deterministic for identical PDF inputs:
  - stable page-order traversal (`page_index` ascending)
  - normalized text output with predictable newline/whitespace handling
  - explicit degraded-case metadata (e.g., empty pages, extraction warnings)
- Standardized service-level result format is mandatory:
  - success/failure envelope `{ok, data, error}`
  - normalized error payload `{code, message, details, retryable}`
- Failure taxonomy should distinguish at minimum:
  - unreadable/missing file
  - malformed/corrupted PDF structure
  - no extractable text (fully scanned/image-only or blank)
  - runtime parsing exception
- Logging requirements for PDF extraction events:
  - `stage=extraction`, `engine=pdf`
  - include `correlation_id`, `job_id`, `chunk_index`, `event`, `severity`, `timestamp`
  - event names follow `domain.action`
- MVP UX/privacy constraints:
  - user-facing remediation messages in English only
  - no cloud/network dependency in extraction path

### Architecture Compliance

- Respect layered boundaries from architecture:
  - UI layer under `src/ui/` only renders state and user feedback
  - extraction logic remains in `src/adapters/extraction/`
  - orchestration and result mapping remain in service layer
- Keep persistence boundaries untouched for this story:
  - no migration/schema change required specifically for PDF extraction behavior
  - no direct repository calls from views/presenters for extraction decisions
- Enforce project-wide consistency rules:
  - `snake_case` naming for payload keys
  - UTC ISO-8601 timestamp format in events
  - normalized result/error contracts and `domain.action` events
- Preserve orchestration policy boundaries:
  - no engine fallback policy in extractor adapters
  - no coupling between PDF extractor and worker thread internals

### Library & Framework Requirements

- PDF parsing implementation must use [`PyPDF2`](pyproject.toml:14) for this story to stay aligned with current dependency set.
- Existing logging infrastructure must be reused:
  - [`jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py:1)
  - [`event_schema.py`](src/infrastructure/logging/event_schema.py:1)
- Existing normalized contracts must be reused without divergence:
  - [`result.py`](src/contracts/result.py:1)
  - [`errors.py`](src/contracts/errors.py:1)
- Technical watch (step 4): latest published versions observed are `PyPDF2 3.0.1`, `pypdf 6.7.0`, `EbookLib 0.20`; implementation should remain compatible with pinned major behavior and avoid deprecated calls.

### File Structure Requirements

- Primary implementation target for this story:
  - `src/adapters/extraction/pdf_extractor.py`
- Service wiring/orchestration touchpoints:
  - `src/domain/services/import_service.py`
  - `src/adapters/extraction/__init__.py` (if adapter export wiring is needed)
- UI feedback mapping touchpoint:
  - `src/ui/presenters/conversion_presenter.py`
- Logging integration points:
  - `src/infrastructure/logging/jsonl_logger.py`
  - `src/infrastructure/logging/event_schema.py`
- Test locations:
  - `tests/unit/` for extractor behavior and error mapping
  - `tests/integration/` for extraction pipeline and observability contract checks

### Testing Requirements

- Unit tests for PDF extraction behavior:
  - deterministic page-order extraction on representative fixtures
  - normalization quality and non-crashing handling of blank/non-text pages
  - output shape compatibility with downstream chunking requirements
- Unit tests for error normalization:
  - malformed/corrupted PDF maps to stable normalized error codes
  - unreadable source path maps to actionable normalized failure
  - no-text-content degraded-case maps to deterministic failure semantics and retryability
- Integration tests for service + observability + presenter path:
  - extraction start/success/failure emits required JSONL fields
  - `stage=extraction`, `engine=pdf` are correctly set
  - presenter receives explicit actionable English feedback for both success and failure paths
- Regression guardrails:
  - Story 2.1 import tests stay green
  - Story 2.2 EPUB extraction tests stay green

### Previous Story Intelligence

- Reuse the extraction orchestration extension pattern introduced in Story 2.2 rather than adding parallel pathways.
- Keep strict contract discipline from Story 2.2:
  - normalized result envelope and normalized error payload only
  - schema-complete extraction events with correlation context
- Preserve the same anti-regression posture:
  - centralized constants/contracts over scattered literals
  - deterministic, actionable failures instead of ambiguous free-text errors
- Scope guard: do not broaden into TXT/Markdown extraction within this story.

### Git Intelligence Summary

- Recent commits indicate active hardening of extraction contracts and tests around Story 2.2.
- Most relevant touched files for implementation alignment:
  - `src/adapters/extraction/epub_extractor.py`
  - `src/domain/services/import_service.py`
  - `src/ui/presenters/conversion_presenter.py`
  - extraction-related unit/integration tests
- Actionable implications for Story 2.3:
  - mirror EPUB adapter quality bar for deterministic extraction + observability
  - extend existing extraction orchestration path rather than introducing divergent APIs
  - keep test-first, contract-first updates with synchronized story artifact updates

### Latest Tech Information

- `PyPDF2` latest observed release: `3.0.1`.
- `pypdf` (successor project line) latest observed release: `6.7.0`.
- Current project dependency already includes `PyPDF2>=3.0.0`; story implementation should:
  - avoid deprecated parser calls
  - centralize extraction logic behind adapter boundary for future migration to `pypdf` if needed
  - include explicit degraded-case diagnostics to reduce support ambiguity on scanned/image-only PDFs

### Project Structure Notes

- Align implementation with architecture boundaries:
  - adapter code in `src/adapters/extraction/`
  - service orchestration in `src/domain/services/`
  - user-facing messaging in `src/ui/presenters/`
- Runtime and persistence boundaries remain unchanged for this story (`runtime/`, SQLite repositories unchanged unless strictly necessary).

### References

- Story source: `_bmad-output/planning-artifacts/epics.md` (Epic 2, Story 2.3).
- Product constraints: `_bmad-output/planning-artifacts/prd.md` (FR2, FR6, FR8; NFR1, NFR6, NFR12, NFR14).
- Architecture guardrails: `_bmad-output/planning-artifacts/architecture.md`.
- Previous story intelligence: `./2-2-extract-clean-text-from-epub-with-actionable-failure-handling.md`.
- Sprint tracking: `_bmad-output/implementation-artifacts/sprint-status.yaml`.

### Story Completion Status

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story status set to `ready-for-dev`.
- Story context enriched with architecture constraints, previous implementation learnings, and latest package intelligence for PDF extraction.

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log --oneline -n 5`
- `git log --name-only --pretty=format:'--- %h %s' -n 5`
- `python - <<'PY' ...` (PyPI package metadata check for PyPDF2/pypdf/EbookLib)
- `PYTHONPATH=src python -m unittest tests.unit.test_pdf_extractor tests.unit.test_extraction_orchestration tests.integration.test_import_flow_integration -v`
- `PYTHONPATH=src python -m unittest discover -s tests -v`

### Completion Notes List

- Story scaffolded and marked `ready-for-dev`.
- Acceptance criteria and implementation tasks aligned to Epic 2 Story 2.3.
- Developer guardrails include deterministic extraction, degraded-case diagnostics, and strict normalized contract requirements.
- Implemented `PdfExtractor` with deterministic page-order extraction, newline/whitespace normalization, per-page diagnostics, and degraded-case metadata.
- Added PDF routing in import orchestration with normalized extractor-unavailable handling for `.pdf` sources.
- Extended presenter extraction messaging to remain actionable in English for both EPUB and PDF failure modes.
- Ensured extraction error details include `source_format` for accurate presenter feedback and observability consistency.
- Added unit/integration coverage for PDF extraction behavior, orchestration routing, event schema compliance, and presenter messaging.
- Executed full regression suite successfully (`59` tests passing after code review fixes).
- Applied code review fixes: added file size validation, improved exception handling, extracted shared normalization utilities, enhanced diagnostics, added comprehensive test coverage.

### File List

- _bmad-output/implementation-artifacts/2-3-extract-text-from-pdf-with-degraded-case-handling.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/adapters/extraction/__init__.py
- src/adapters/extraction/epub_extractor.py
- src/adapters/extraction/pdf_extractor.py
- src/adapters/extraction/text_normalization.py
- src/domain/services/import_service.py
- src/ui/presenters/conversion_presenter.py
- tests/integration/test_import_flow_integration.py
- tests/unit/test_extraction_orchestration.py
- tests/unit/test_pdf_extractor.py

### Change Log

- 2026-02-12: Implemented Story 2.3 end-to-end (PDF extractor, service wiring, observability, presenter feedback, and automated tests).
- 2026-02-12: Applied adversarial code review fixes - added file size validation, improved exception handling, extracted shared text normalization utilities, enhanced page diagnostics with word counts, added comprehensive test coverage for edge cases (file too large, missing file, malformed PDF, Unicode content).
