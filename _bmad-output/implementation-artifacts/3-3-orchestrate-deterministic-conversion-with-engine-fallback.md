# Story 3.3: Orchestrate Deterministic Conversion with Engine Fallback

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user launching conversion,
I want the system to orchestrate chunk synthesis with deterministic fallback,
so that conversion can continue when the primary engine fails.

## Acceptance Criteria

1. **Given** chunk records are available and providers implement unified contract  
   **When** conversion runs in `tts_orchestration_service.py`  
   **Then** chunks are synthesized in persisted index order  
   **And** orchestration emits normalized results `{ok, data, error}` for each processing stage.

2. **Given** primary engine failure on a chunk  
   **When** fallback rules are evaluated  
   **Then** fallback from Chatterbox to Kokoro is decided only in orchestration service  
   **And** provider adapters remain free of fallback policy logic.

3. **Given** engine and chunk processing events must be diagnosable  
   **When** orchestration processes each chunk  
   **Then** JSONL logs include `correlation_id`, `job_id`, `chunk_index`, `engine`, `stage`, `event`, `severity`, `timestamp`  
   **And** events use `domain.action` naming for start success fail fallback paths.

4. **Given** fallback cannot recover a chunk  
   **When** both providers fail for the same chunk  
   **Then** orchestration returns normalized error payload with deterministic code and retryability  
   **And** job state transition is delegated to validated service state handling.

## Tasks / Subtasks

- [ ] Implement deterministic orchestration pipeline over persisted chunks (AC: 1)
  - [ ] Add orchestration entrypoint in `src/domain/services/tts_orchestration_service.py` to process all chunks for a job in strict `chunk_index` order.
  - [ ] Fetch chunk rows only through `src/adapters/persistence/sqlite/repositories/chunks_repository.py` and reject execution when no persisted chunks exist.
  - [ ] Return normalized stage results using `src/contracts/result.py` and `src/contracts/errors.py` without leaking provider-specific internals.
- [ ] Keep fallback policy exclusively in orchestration layer (AC: 2)
  - [ ] Reuse/extend `synthesize_with_fallback(...)` policy in `tts_orchestration_service.py`; do not implement fallback branching in `src/adapters/tts/chatterbox_provider.py` or `src/adapters/tts/kokoro_provider.py`.
  - [ ] Enforce deterministic fallback trigger criteria (availability category and non-retryable semantics) and consistent error codes for both single-chunk and whole-job orchestration flows.
  - [ ] Persist/emit which engine actually synthesized each chunk so downstream diagnostics remain deterministic.
- [ ] Emit complete observability events per chunk lifecycle (AC: 3)
  - [ ] For each chunk, emit `tts.chunk_started`, `tts.chunk_succeeded`, `tts.chunk_failed`, and `tts.fallback_applied` (when applicable) through the event logger boundary.
  - [ ] Ensure payload includes required schema fields: `correlation_id`, `job_id`, `chunk_index`, `engine`, `stage`, `event`, `severity`, `timestamp`.
  - [ ] Keep event names in `domain.action` format and UTC ISO-8601 timestamps.
- [ ] Handle unrecoverable chunk failures with validated state ownership (AC: 4)
  - [ ] If both providers fail on a chunk, return deterministic normalized failure and stop further chunk synthesis for that job run.
  - [ ] Delegate any job status transition intent to validated state rules (`queued`, `running`, `paused`, `failed`, `completed`) via service-level transition validation.
  - [ ] Avoid direct UI-thread or adapter-side state mutation.
- [ ] Add robust regression coverage for orchestration and fallback (AC: 1..4)
  - [ ] Unit tests in `tests/unit/test_tts_orchestration_service.py` for strict index order, fallback conditions, and deterministic error behavior.
  - [ ] Integration tests in `tests/integration/test_chunk_persistence_and_resume_path.py` for persisted chunk execution order and failure path consistency.
  - [ ] Validate event contract shape in tests to ensure required JSONL fields and `domain.action` naming are preserved.

## Dev Notes

### Story Intent

- Establish a production-grade orchestration path that executes persisted chunks in deterministic order and applies fallback consistently.
- Preserve architectural ownership: orchestration decides fallback and synthesis sequencing; providers only synthesize and report provider-local outcomes.
- Produce complete per-chunk observability so story `3.4` can reliably build resume/state behavior on top of the same execution trace.

### Story Requirements

- Source story key: `3-3-orchestrate-deterministic-conversion-with-engine-fallback` from sprint backlog ordering.
- Epic context: `Epic 3` focuses on resilient conversion and deterministic behavior across chunking, fallback, and resume.
- Functional targets in this story:
  - orchestrate chunk synthesis in persisted order;
  - keep fallback policy centralized;
  - emit diagnosable structured events;
  - fail deterministically when fallback cannot recover.

### Developer Context Section

- Current code already includes core fallback primitives in `src/domain/services/tts_orchestration_service.py`; this story extends that behavior from single-call fallback to full multi-chunk orchestration flow.
- `Story 3.2` already introduced deterministic chunking + persisted chunk metadata. Reuse that persisted contract; do not regenerate chunks differently inside orchestration.
- Keep orchestration deterministic for identical inputs:
  - same chunk iteration order,
  - same fallback criteria,
  - stable normalized error code patterns,
  - stable event sequence semantics.

### Technical Requirements

- Process chunks from persistence in ascending `chunk_index` order only.
- For each chunk:
  - call orchestration-owned fallback logic;
  - capture selected engine;
  - return normalized chunk result envelope.
- On non-recoverable dual-provider failure:
  - stop processing,
  - return deterministic normalized error with retryability flag,
  - include actionable details (`chunk_index`, provider errors, engine attempts).
- Keep all service outputs normalized:
  - success/failure envelope: `{ok, data, error}`
  - error envelope: `{code, message, details, retryable}`
- Ensure timestamps are UTC ISO-8601 and event naming is `domain.action`.

### Architecture Compliance

- Respect boundaries from architecture:
  - domain orchestration in `src/domain/services/`;
  - persistence access through repository adapters only;
  - logging through infrastructure/event logger port only.
- Do not add fallback logic to provider adapters.
- Do not bypass service-level state validation.
- Preserve `snake_case` naming and deterministic behavior standards.

### Library / Framework Requirements

- Project dependency baseline (`pyproject.toml`) remains compatible with current story scope:
  - `PyYAML>=6.0`
  - `EbookLib>=0.18`
  - `PyPDF2>=3.0.0`
- No additional third-party runtime dependency is required for Story 3.3.
- Python runtime target remains `>=3.10`.

### File Structure Requirements

- Primary implementation files:
  - `src/domain/services/tts_orchestration_service.py`
  - `src/adapters/persistence/sqlite/repositories/chunks_repository.py` (only if repository read/query support needs extension)
  - `src/domain/ports/event_logger_port.py` (if needed for stronger typing consistency)
- Primary verification tests:
  - `tests/unit/test_tts_orchestration_service.py`
  - `tests/integration/test_chunk_persistence_and_resume_path.py`
  - any event schema assertion tests already present for TTS/event contracts.

### Testing Requirements

- Unit tests must verify:
  - deterministic chunk processing order,
  - fallback used only on eligible error criteria,
  - no fallback attempted for ineligible errors,
  - deterministic dual-failure normalized error payload.
- Integration tests must verify:
  - persisted chunk order is respected end-to-end,
  - chunk failure halts orchestration as expected,
  - event payload contains required correlation and chunk fields.
- Regression gate:
  - existing Story 3.1 provider contract tests and Story 3.2 chunking/persistence tests remain green.

### Previous Story Intelligence

- From Story 3.2 implementation and review:
  - deterministic behavior and strict validation are already enforced in chunk generation;
  - `chunk_index` integrity checks and transactional chunk persistence were tightened;
  - centralized event logger port was introduced to reduce duplication.
- Practical carry-over for Story 3.3:
  - do not weaken deterministic semantics,
  - keep contracts explicit and test-proven,
  - avoid ad-hoc logging fields that violate schema expectations.

### Git Intelligence Summary

- Recent commits indicate strong quality and direction continuity:
  - `13c7bc7` review fixes for Story 3.2 (logger port centralization, validation hardening, test expansion),
  - `8f34ec8` deterministic chunking + persistence + logging implementation,
  - `291f92e` story generation for 3.2,
  - `2d98fa2` hardening of Story 3.1 orchestration/provider behavior,
  - `256e047` unified provider contract normalization.
- Implementation implication:
  - maintain the same "real behavior + strict contracts + comprehensive tests" quality bar,
  - avoid placeholder orchestration flows that skip persistence or logging requirements.

### Latest Tech Information

- Online package metadata check (PyPI) confirms latest stable versions at analysis time:
  - `PyYAML 6.0.3`
  - `EbookLib 0.20`
  - `PyPDF2 3.0.1`
  - `PyQt5 5.15.11`
- Story 3.3 does not require immediate dependency upgrades; however, implementation should remain compatible with currently declared minimum versions in `pyproject.toml`.

### Project Context Reference

- No `project-context.md` file was discovered via configured pattern.
- Context sources used for this story:
  - `_bmad-output/planning-artifacts/epics.md`
  - `_bmad-output/planning-artifacts/prd.md`
  - `_bmad-output/planning-artifacts/architecture.md`
  - `_bmad-output/implementation-artifacts/sprint-status.yaml`
  - `_bmad-output/implementation-artifacts/3-2-segment-long-text-with-phrase-first-chunking-rules.md`
  - current source files under `src/` and tests under `tests/`.

### Project Structure Notes

- Follow existing repository conventions in codebase (pluralized repository module names such as `chunks_repository.py`) even where architecture examples show singularized variants.
- Keep this story scoped to orchestration + fallback + observability guardrails; do not pull in post-processing, library browsing, or player controls from later epics.
- Preserve modular separation: UI workers invoke services, but orchestration logic remains in domain service layer.

### References

- Epic and acceptance criteria source: `_bmad-output/planning-artifacts/epics.md` (Epic 3 → Story 3.3)
- Product constraints source: `_bmad-output/planning-artifacts/prd.md` (FR9, FR13, FR14; NFR2, NFR4, NFR14)
- Architecture constraints source: `_bmad-output/planning-artifacts/architecture.md` (orchestration ownership, state transitions, event schema, boundaries)
- Sprint tracking source: `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Previous story context source: `_bmad-output/implementation-artifacts/3-2-segment-long-text-with-phrase-first-chunking-rules.md`
- Current implementation baseline:
  - `src/domain/services/tts_orchestration_service.py`
  - `src/domain/services/chunking_service.py`
  - `src/adapters/persistence/sqlite/repositories/chunks_repository.py`
  - `tests/unit/test_tts_orchestration_service.py`
  - `tests/integration/test_chunk_persistence_and_resume_path.py`

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
- `cat ./_bmad-output/implementation-artifacts/3-2-segment-long-text-with-phrase-first-chunking-rules.md`
- `git log --oneline -n 5`
- `git log --name-only --oneline -n 5`
- `python - <<'PY' ... (PyPI package metadata check) ... PY`

### Completion Notes List

- Story generated from first backlog item in sprint status: `3-3-orchestrate-deterministic-conversion-with-engine-fallback`.
- Comprehensive context assembled from epics, PRD, architecture, sprint tracking, previous story intelligence, and current codebase.
- Deterministic orchestration guardrails defined: persisted chunk order, fallback ownership, normalized failure behavior, and strict observability schema.
- Story status explicitly set to `ready-for-dev`.
- Ultimate context engine analysis completed - comprehensive developer guide created.

### File List

- _bmad-output/implementation-artifacts/3-3-orchestrate-deterministic-conversion-with-engine-fallback.md
