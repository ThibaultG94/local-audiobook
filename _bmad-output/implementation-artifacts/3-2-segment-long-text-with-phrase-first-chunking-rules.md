# Story 3.2: Segment Long Text with Phrase-First Chunking Rules

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user converting long documents,
I want text to be split into stable phrase-first chunks,
so that synthesis remains reliable and resumable across large inputs.

## Acceptance Criteria

1. **Given** extracted text is available from import and extraction services  
   **When** chunking runs in `chunking_service.py`  
   **Then** chunk boundaries prioritize sentence phrase integrity before max character threshold  
   **And** produced chunks are deterministic for the same input.

2. **Given** chunk metadata is needed for orchestration and resume  
   **When** chunk generation completes  
   **Then** each chunk gets persisted index ordering and content hash via `chunk_repository.py`  
   **And** chunk records are linked to the conversion job in SQLite.

3. **Given** invalid or empty extracted text  
   **When** chunking is requested  
   **Then** the service returns normalized failure in `result.py`  
   **And** errors follow `errors.py` with actionable details and retryability flag.

4. **Given** observability requirements for conversion pipeline  
   **When** chunking starts and ends  
   **Then** JSONL events are emitted by `jsonl_logger.py` with `stage=chunking` and `domain.action` events  
   **And** payload includes `correlation_id`, `job_id`, `event`, `severity`, and ISO-8601 UTC `timestamp`.

## Tasks / Subtasks

- [ ] Implement deterministic phrase-first chunking service (AC: 1, 3)
  - [ ] Create `src/domain/services/chunking_service.py` with a pure deterministic algorithm (same input => same output).
  - [ ] Enforce phrase/sentence-aware boundaries before hard max-character fallback.
  - [ ] Validate inputs (`text`, chunk size config, optional language hints) and return normalized failures for invalid/empty text.
- [ ] Persist chunk metadata for orchestration/resume (AC: 2)
  - [ ] Extend or add persistence repository methods for chunk creation/listing with stable index ordering and content hash.
  - [ ] Link each chunk record to a conversion job id and maintain transactional integrity.
  - [ ] Ensure schema compatibility with existing tables/repositories under `src/adapters/persistence/sqlite/repositories/`.
- [ ] Integrate chunking into orchestration boundary without leaking fallback policy (AC: 1, 2)
  - [ ] Wire chunk generation call sites in `src/domain/services/tts_orchestration_service.py` only where flow ownership is appropriate.
  - [ ] Preserve orchestration as fallback policy owner; chunking service remains single-responsibility.
- [ ] Emit structured logging for chunking lifecycle (AC: 4)
  - [ ] Emit `chunking.started` and `chunking.completed` (plus `chunking.failed` where relevant) through `src/infrastructure/logging/jsonl_logger.py`.
  - [ ] Include required fields: `correlation_id`, `job_id`, `stage`, `event`, `severity`, `timestamp`; include `chunk_index` only for per-chunk events.
- [ ] Add test coverage and regression safety (AC: 1..4)
  - [ ] Unit tests for deterministic chunk outputs and boundary behavior (sentence-first, fallback split, empty input failure).
  - [ ] Unit/integration tests for persistence of chunk index + hash + job linkage.
  - [ ] Tests for logging contract shape and `domain.action` naming during chunking lifecycle.

## Dev Notes

### Story Intent

- Build the chunking foundation that enables long-document stability before full conversion fallback/resume stories.
- Keep chunking deterministic and persistence-oriented so Story 3.3 and Story 3.4 can rely on stable ordering and reproducible resume behavior.
- Prevent regressions by enforcing strict result/error contracts and log schema consistency already established in prior stories.

### Story Context and Dependencies

- Story 3.2 depends on completed Story 3.1 contract normalization and provider/orchestration baseline.
- Story 3.2 unblocks:
  - Story 3.3 deterministic conversion with engine fallback.
  - Story 3.4 resume from last failed chunk based on persisted chunk metadata.
  - Story 3.6 worker progress updates that rely on known chunk counts/indexes.
- Existing relevant code baseline:
  - `src/domain/services/tts_orchestration_service.py`
  - `src/adapters/persistence/sqlite/repositories/chunks_repository.py`
  - `src/contracts/result.py`
  - `src/contracts/errors.py`
  - `src/infrastructure/logging/jsonl_logger.py`
  - `src/infrastructure/logging/event_schema.py`

### Developer Context Section

- Keep chunking logic isolated in domain service; do not bury splitting rules inside UI workers, adapters, or provider implementations.
- Preserve normalized service boundary:
  - success/failure envelope: `{ok, data, error}`
  - error envelope: `{code, message, details, retryable}`
- Determinism is mandatory: identical normalized input text and configuration must produce identical chunk array, indices, and hashes.
- Phrase-first policy means:
  1. Prefer sentence and punctuation boundaries.
  2. If a segment exceeds max threshold, split with deterministic fallback rules.
  3. Never produce empty chunks.

### Technical Requirements

- Implement chunk outputs with explicit metadata fields at minimum:
  - `job_id`
  - `chunk_index` (0-based or 1-based, but consistent and documented)
  - `text`
  - `content_hash`
  - `created_at` (ISO-8601 UTC)
- Validation rules:
  - reject empty/whitespace-only source text.
  - reject invalid chunk size bounds.
  - reject malformed configuration with normalized `code/message/details/retryable`.
- Hashing:
  - Use deterministic hash generation over normalized chunk text.
  - Keep algorithm stable and documented to support resume and diagnostics.
- Performance:
  - chunking must run without blocking UI thread execution path; heavy work must remain outside UI thread and compatible with worker architecture.

### Architecture Compliance

- Respect architecture ownership:
  - Domain rules in `src/domain/services/`.
  - Persistence only via repository layer under `src/adapters/persistence/sqlite/repositories/`.
  - Logging only via infrastructure logging components.
- Keep fallback policy out of adapters and chunking service; fallback remains in orchestration service.
- Maintain naming and formatting conventions (`snake_case`, `domain.action`, ISO-8601 UTC).

### Library / Framework Requirements

- No new third-party dependency is required for this story.
- Runtime baseline remains Python `>=3.10`.
- If text segmentation needs regex utilities, use Python standard library `re` and avoid introducing NLP-heavy dependencies for MVP.

### File Structure Requirements

- Primary implementation targets:
  - `src/domain/services/chunking_service.py` (new)
  - `src/domain/services/tts_orchestration_service.py` (integration touchpoints only)
  - `src/adapters/persistence/sqlite/repositories/chunks_repository.py`
  - `src/infrastructure/logging/jsonl_logger.py` (if event helpers needed)
- Primary test targets:
  - `tests/unit/test_chunking_service.py` (new)
  - `tests/unit/test_tts_orchestration_service.py` (extend as needed)
  - `tests/integration/test_chunk_persistence_and_resume_path.py` (new or equivalent integration test)

### Testing Requirements

- Unit: deterministic split behavior for punctuation-aware and hard-threshold fallback cases.
- Unit: normalization and failure behavior on empty/invalid inputs.
- Unit/integration: persistence ordering integrity and hash stability across repeated runs.
- Integration: ensure log events for chunking lifecycle match schema constraints and required fields.
- Regression: no breakage to Story 3.1 provider contract tests.

### Previous Story Intelligence

- Story 3.1 established strict contract enforcement, deterministic normalized errors, and strong tests for edge cases.
- Recent code-review fixes emphasized:
  - reducing duplication via shared base patterns,
  - stronger input validation,
  - explicit structured logging,
  - realistic behavior over stubs.
- Apply same discipline here: avoid placeholder chunking logic and ensure implementation is production-grade for MVP.

### Git Intelligence Summary

Recent relevant commits indicate the current implementation direction and quality bar:

- `2d98fa2` fix(story-3.1): adversarial code review fixes - real audio, orchestration, validation, tests
- `256e047` feat(tts): implement unified provider contract and adapter normalization
- `4c2b80f` chore(create-story): generate Story 3.1 and mark ready-for-dev
- `4a244c1` fix(story-2.5): code review fixes - absolute imports, validation, centralized NoopLogger, enhanced tests
- `c5cd64d` implement unified extraction diagnostics and review-ready Story 2.5

Implementation implication: follow the same “no stubs, deterministic contracts, comprehensive tests” standard for chunking.

### Latest Tech Information

- No mandatory dependency upgrade identified from current project manifest for Story 3.2.
- Use standard library-first chunking implementation to minimize risk and avoid introducing compatibility drift.
- Keep compatibility with local-only, offline-first MVP constraints and Linux Mint target runtime.

### Project Context Reference

- No `project-context.md` was found.
- Context sources used:
  - `_bmad-output/planning-artifacts/epics.md`
  - `_bmad-output/planning-artifacts/prd.md`
  - `_bmad-output/planning-artifacts/architecture.md`
  - `_bmad-output/implementation-artifacts/sprint-status.yaml`
  - `_bmad-output/implementation-artifacts/3-1-implement-unified-tts-provider-contract-and-engine-adapters.md`

### Project Structure Notes

- Keep implementation inside established project boundaries already present in repository.
- Architecture references singular repository naming in examples, while codebase currently uses pluralized repository modules (e.g., `chunks_repository.py`); follow actual repository conventions unless a dedicated refactor story is approved.
- Do not introduce premature player/library concerns into this story; focus scope on chunking + persistence + observability handoff to orchestration.

### References

- Epic/story specification: `_bmad-output/planning-artifacts/epics.md` (Epic 3, Story 3.2)
- Product constraints: `_bmad-output/planning-artifacts/prd.md` (FR11, FR14; NFR1, NFR2, NFR4, NFR14)
- Architecture constraints: `_bmad-output/planning-artifacts/architecture.md` (state rules, logging schema, boundaries)
- Sprint tracking source: `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Prior-story implementation intelligence: `_bmad-output/implementation-artifacts/3-1-implement-unified-tts-provider-contract-and-engine-adapters.md`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `cat ./_bmad/core/tasks/workflow.xml`
- `cat ./_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`
- `cat ./_bmad/bmm/workflows/4-implementation/create-story/instructions.xml`
- `cat ./_bmad-output/implementation-artifacts/sprint-status.yaml`
- `cat ./_bmad-output/planning-artifacts/epics.md`
- `cat ./_bmad-output/planning-artifacts/prd.md`
- `cat ./_bmad-output/planning-artifacts/architecture.md`
- `cat ./_bmad-output/implementation-artifacts/3-1-implement-unified-tts-provider-contract-and-engine-adapters.md`
- `git log --oneline -n 5`
- `git log --name-only --oneline -n 5`

### Completion Notes List

- Story 3.2 generated from first backlog item in sprint status.
- Status set to `ready-for-dev` with comprehensive developer context and guardrails.
- Acceptance criteria preserved in BDD format from Epic 3 Story 3.2.
- Added architecture-aligned constraints for deterministic chunking, persistence linkage, normalized errors, and structured logging.
- Incorporated prior story and git intelligence to prevent regressions and avoid low-fidelity implementation patterns.
- Ultimate context engine analysis completed - comprehensive developer guide created.

### File List

- _bmad-output/implementation-artifacts/3-2-segment-long-text-with-phrase-first-chunking-rules.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
