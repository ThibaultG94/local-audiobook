# Story 2.4: Extract and Normalize TXT and Markdown Inputs

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user importing TXT or Markdown documents,
I want the system to parse and normalize text encoding consistently,
so that extracted content is ready for reliable chunking and synthesis.

## Acceptance Criteria

1. **Given** an imported `.txt` or `.md` file accepted by `import_service.py`  
   **When** extraction runs through `text_extractor.py`  
   **Then** UTF-8 content is parsed successfully and normalized line breaks are produced  
   **And** Markdown structural markers are converted into clean reading text suitable for TTS input.

2. **Given** files with encoding anomalies or unreadable byte sequences  
   **When** normalization fails  
   **Then** the service returns standardized output  
   **And** errors include `code`, `message`, `details`, and `retryable`.

3. **Given** very large TXT or Markdown inputs  
   **When** extraction completes  
   **Then** output remains deterministic and does not block the UI thread  
   **And** extracted payload is ready for downstream chunking without extra manual preprocessing.

4. **Given** observability and user feedback requirements  
   **When** extraction succeeds or fails  
   **Then** JSONL events are emitted via `jsonl_logger.py` with `stage=extraction` and `engine=text`  
   **And** presenter feedback in `conversion_presenter.py` remains actionable and English-only in MVP.

## Tasks / Subtasks

- [x] Implement TXT/Markdown extractor adapter in `src/adapters/extraction/text_extractor.py` with deterministic normalization output (AC: 1, 2, 3)
  - [x] Read `.txt` and `.md` files using UTF-8 first, with controlled fallback handling for encoding anomalies.
  - [x] Reuse shared normalization utilities from `text_normalization.py` to enforce stable whitespace and line-break behavior.
  - [x] Convert Markdown structural markers to clean reading text suitable for TTS input while preserving reading flow.
  - [x] Return normalized extraction payload with deterministic metadata (`source_format`, `sections`, `text_length`, warnings).
- [x] Wire extraction orchestration path for TXT/Markdown through `ImportService.extract_document()` (AC: 1, 2, 4)
  - [x] Route `.txt` and `.md` source formats to `text_extractor.py`.
  - [x] Preserve normalized envelope contract `{ok, data, error}` and error shape `{code, message, details, retryable}`.
  - [x] Ensure extractor-unavailable and unsupported-format failure paths stay deterministic and actionable.
- [x] Extend actionable presenter feedback in `conversion_presenter.py` for text-engine extraction outcomes (AC: 4)
  - [x] Keep all user-facing extraction messages English-only.
  - [x] Provide actionable failure messages for encoding and unreadable source failures.
  - [x] Preserve downstream conversion gating on extraction failure.
- [x] Add structured observability for text extraction lifecycle (AC: 4)
  - [x] Emit `extraction.started`, `extraction.succeeded`, `extraction.failed` with `stage=extraction` and `engine=text`.
  - [x] Ensure payload includes required fields: `correlation_id`, `job_id`, `chunk_index`, `event`, `severity`, `timestamp`.
  - [x] Add useful diagnostics (`source_format`, `text_length`, `encoding_warnings`, `normalization_warnings`).
- [x] Add test coverage for deterministic behavior, anomalies, and orchestration integration (AC: 1..4)
  - [x] Unit tests for UTF-8 parsing, line break normalization, markdown cleanup, and very large input guardrails.
  - [x] Unit tests for encoding anomalies and unreadable byte handling mapped to normalized errors.
  - [x] Orchestration tests for `.txt`/`.md` routing and extractor-unavailable behavior.
  - [x] Presenter tests for actionable English messaging and failure gating semantics.

## Dev Notes

### Story Intent

- Deliver robust extraction for `.txt` and `.md` with deterministic normalization so chunking and synthesis can consume consistent text.
- Preserve all established contracts from Stories 2.1–2.3: normalized result envelopes, local observability, and actionable UI messaging.
- Scope boundary: this story addresses text extraction and normalization only, not conversion orchestration redesign.

### Story Context and Dependencies

- Story dependency: `Story 2.1` established import intake validation and persistence flow.
- Story dependency: `Story 2.2` established EPUB extraction contract patterns and baseline observability.
- Story dependency: `Story 2.3` established degraded-case handling and extraction diagnostics style.
- Contract continuity required with:
  - `src/contracts/result.py` (`{ok, data, error}` envelope)
  - `src/contracts/errors.py` (`{code, message, details, retryable}` normalized errors)
- Existing extraction orchestration currently routes EPUB and PDF in `src/domain/services/import_service.py`; TXT/MD must be added without regression.

### Developer Context Section

Current extraction implementation context indicates:

- Existing adapters:
  - `src/adapters/extraction/epub_extractor.py`
  - `src/adapters/extraction/pdf_extractor.py`
- Shared normalization utility:
  - `src/adapters/extraction/text_normalization.py`
- Service routing point:
  - `src/domain/services/import_service.py`
- Presenter mapping point:
  - `src/ui/presenters/conversion_presenter.py`

Implementation must extend these established patterns instead of introducing parallel extraction pathways.

### Technical Requirements

- Deterministic extraction output for identical `.txt`/`.md` inputs:
  - stable file read behavior
  - stable normalized newline and whitespace rules
  - deterministic markdown cleanup result
- Encoding handling must be explicit and observable:
  - UTF-8-first read path
  - controlled fallback for anomalies
  - normalized failures when content is unreadable
- Output payload must be chunking-ready and contain enough metadata for diagnostics.

### Architecture Compliance

- Respect module boundaries from architecture:
  - adapters in `src/adapters/extraction/`
  - orchestration in `src/domain/services/`
  - UI messaging in `src/ui/presenters/`
- Keep local-only execution and diagnostics behavior (no network dependency) per PRD and architecture NFRs.
- Maintain non-blocking behavior for extraction-related user flows and avoid introducing UI-thread-heavy operations.

### Library / Framework Requirements

- No new parsing framework is required to satisfy this story.
- Use Python standard file I/O plus existing shared normalization helpers in `text_normalization.py`.
- Preserve compatibility with current dependency baseline in `pyproject.toml` (`requires-python >=3.10`, existing extraction dependencies unchanged unless justified).

### File Structure Requirements

- Expected implementation locations:
  - New: `src/adapters/extraction/text_extractor.py`
  - Update: `src/adapters/extraction/__init__.py`
  - Update: `src/domain/services/import_service.py`
  - Update: `src/ui/presenters/conversion_presenter.py`
  - New tests in `tests/unit/` and integration updates in `tests/integration/` where required
- Do not place domain logic in UI or persistence layers.

### Testing Requirements

- Unit coverage required for:
  - deterministic normalization behavior
  - markdown marker cleanup behavior
  - encoding anomaly handling
  - large input guardrails and unreadable-source error mapping
- Orchestration and presenter coverage required for:
  - `.txt` and `.md` routing
  - normalized failure propagation
  - actionable English feedback output
- Regression expectation: run focused tests first, then full suite.

### Previous Story Intelligence

From prior completed story artifacts:

- Reuse the adapter pattern and failure taxonomy style used by `epub_extractor.py` and `pdf_extractor.py`.
- Keep extraction event naming and payload structure aligned with existing JSONL schema practices.
- Preserve strong test discipline: adapter tests + orchestration tests + integration verification.

### Git Intelligence Summary

Recent commits show extraction-first iteration with review hardening:

- `e2015fd`: robustness and test coverage fixes
- `14d35d1`: PDF extraction implementation
- `59f8ef7`: EPUB story review fixes

Implication: Story 2.4 should follow the same hardened approach (contract-first, observability-first, regression-safe).

### Latest Tech Information

- Text and markdown extraction for this scope can remain stdlib-driven and deterministic.
- Priority is not introducing latest third-party markdown stack; priority is stable extraction contract and predictable behavior.

### Project Context Reference

- No `project-context.md` file was discovered in workspace patterns during analysis.
- Story context derived from planning artifacts, architecture, existing implementation artifacts, and current codebase state.

### References

- Story source: `_bmad-output/planning-artifacts/epics.md` (Epic 2, Story 2.4)
- Product constraints: `_bmad-output/planning-artifacts/prd.md` (FR3, FR4, FR7, FR8; NFR1, NFR6, NFR12, NFR14)
- Architecture guardrails: `_bmad-output/planning-artifacts/architecture.md`
- Previous stories:
  - `_bmad-output/implementation-artifacts/2-2-extract-clean-text-from-epub-with-actionable-failure-handling.md`
  - `_bmad-output/implementation-artifacts/2-3-extract-text-from-pdf-with-degraded-case-handling.md`
- Sprint tracking: `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Story Completion Status

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story status set to `ready-for-dev`.
- Story contains architecture-aligned constraints, implementation guardrails, and regression-aware guidance.

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `cat _bmad-output/implementation-artifacts/sprint-status.yaml`
- `cat _bmad-output/planning-artifacts/epics.md`
- `cat _bmad-output/planning-artifacts/architecture.md`
- `cat _bmad-output/planning-artifacts/prd.md`
- `git log --oneline -n 5`
- `PYTHONPATH=src python -m unittest tests.unit.test_text_extractor tests.unit.test_extraction_orchestration tests.integration.test_import_flow_integration`
- `PYTHONPATH=src python -m unittest discover -s tests -t .`

### Completion Notes List

- Story scaffolded and marked `ready-for-dev`.
- Acceptance criteria aligned with Epic 2 Story 2.4 in planning artifacts.
- Developer context includes architecture constraints, prior-story learnings, git intelligence, and implementation guardrails.
- Story intentionally emphasizes deterministic normalization, normalized error contract continuity, and local observability.
- Implemented `TextExtractor` with deterministic TXT/Markdown normalization, markdown cleanup, UTF-8-first decoding, and normalized error handling for encoding anomalies.
- Wired `.txt` / `.md` routing in `ImportService.extract_document()` with deterministic extractor-unavailable behavior.
- Extended presenter messaging for actionable English-only text encoding failures.
- Added unit + orchestration + integration coverage for text extraction flow and observability payload expectations.
- Ran full regression suite: `68` tests passed.

### File List

- _bmad-output/implementation-artifacts/2-4-extract-and-normalize-txt-and-markdown-inputs.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/adapters/extraction/__init__.py
- src/adapters/extraction/text_extractor.py
- src/domain/services/import_service.py
- src/ui/presenters/conversion_presenter.py
- tests/integration/test_import_flow_integration.py
- tests/unit/test_extraction_orchestration.py
- tests/unit/test_text_extractor.py

## Change Log

- 2026-02-13: Implemented Story 2.4 TXT/Markdown extraction, observability, orchestration routing, presenter messaging, and regression-safe test coverage.
