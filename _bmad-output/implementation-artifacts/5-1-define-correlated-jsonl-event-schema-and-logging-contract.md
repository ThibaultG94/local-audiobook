# Story 5.1: Define Correlated JSONL Event Schema and Logging Contract

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user and support operator,
I want all pipeline events to follow a consistent JSONL schema,
so that failures and performance issues can be diagnosed reliably.

## Acceptance Criteria

1. **Given** logging schema definitions in `event_schema.py`  
   **When** a pipeline event is emitted  
   **Then** payload enforces required fields `correlation_id`, `job_id`, `chunk_index`, `engine`, `stage`, `event`, `severity`, `timestamp`  
   **And** optional fields are explicitly nullable with stable typing.

2. **Given** logger implementation in `jsonl_logger.py`  
   **When** events are written to JSONL  
   **Then** one valid JSON object is persisted per line in append-only mode  
   **And** timestamps are ISO-8601 UTC.

3. **Given** naming consistency rules  
   **When** event names are produced by services  
   **Then** event names follow `domain.action`  
   **And** non-conformant events are rejected with normalized error output.

4. **Given** local diagnostics must work offline  
   **When** logging runs during conversion and playback flows  
   **Then** no network call is performed for log shipping  
   **And** logging failures are surfaced as structured local errors without crashing the UI thread.

## Tasks / Subtasks

- [x] Strengthen and finalize the event schema contract in `src/infrastructure/logging/event_schema.py` (AC: 1, 3)
  - [x] Enforce required fields with deterministic validation errors
  - [x] Validate UTC ISO-8601 timestamps and keep behavior stable for nullable optional fields
  - [x] Enforce `domain.action` naming consistently and document edge conditions
- [x] Harden JSONL writer behavior in `src/infrastructure/logging/jsonl_logger.py` (AC: 2, 4)
  - [x] Guarantee append-only one-JSON-object-per-line persistence
  - [x] Ensure logger failures are returned/raised as structured local failures without UI-thread crash propagation
  - [x] Preserve local-only behavior (no network transport path)
- [x] Align pipeline emitters with the schema contract across services/adapters (AC: 1, 3, 4)
  - [x] Confirm stage/event/severity payload quality in extraction, orchestration, playback, and UI presenter paths
  - [x] Normalize any non-conformant event names or missing required fields
- [x] Extend automated verification for schema + append-only behavior (AC: 1, 2, 3, 4)
  - [x] Add/expand unit tests for schema validator success/failure cases
  - [x] Add/expand integration coverage validating emitted JSONL lines from bootstrap and runtime flows

## Dev Notes

### Developer Context Section

- Story target selected from sprint tracker as first backlog item in Epic 5: `5-1-define-correlated-jsonl-event-schema-and-logging-contract`.
- Scope is observability hardening, not introducing a new logging subsystem from scratch:
  - existing schema contract already present in [`validate_event_payload()`](src/infrastructure/logging/event_schema.py:31)
  - existing append-only writer already present in [`JsonlLogger.emit()`](src/infrastructure/logging/jsonl_logger.py:19)
  - existing integration coverage already validates baseline bootstrap events in [`TestJsonlLoggingIntegration.test_bootstrap_emits_required_jsonl_events()`](tests/integration/test_jsonl_logging.py:55).
- This story must convert the baseline into a stricter contract that protects downstream diagnostics from malformed event payloads and inconsistent naming.
- Critical product intent from epic/PRD/architecture for this story:
  - deterministic local diagnostics for failures/performance investigations
  - strict `domain.action` naming for all events
  - UTC ISO-8601 timestamp consistency
  - local-only/offline behavior (no log shipping or network dependencies).

### Technical Requirements

- Preserve and harden required field enforcement anchored on [`REQUIRED_EVENT_FIELDS`](src/infrastructure/logging/event_schema.py:7):
  - `correlation_id`, `job_id`, `chunk_index`, `engine`, `stage`, `event`, `severity`, `timestamp` must always be present.
- Keep event name validation strict in [`validate_event_payload()`](src/infrastructure/logging/event_schema.py:31):
  - every event must follow `domain.action`
  - malformed names must be rejected deterministically before disk write.
- Maintain timestamp guarantees:
  - generated timestamps via [`utc_now_iso()`](src/infrastructure/logging/event_schema.py:19)
  - validator acceptance through [`is_valid_utc_iso_8601()`](src/infrastructure/logging/event_schema.py:23)
  - all persisted timestamps remain timezone-aware UTC ISO-8601 values.
- Preserve append-only JSONL semantics in [`JsonlLogger.emit()`](src/infrastructure/logging/jsonl_logger.py:19):
  - exactly one JSON object per line
  - UTF-8 encoding
  - no overwrite/truncate behavior during normal logging path.
- Keep logging contract compatible with existing emitters across the pipeline (extraction, import, orchestration, playback, presenter, worker) identified in search results, e.g. [`pdf_extractor.py`](src/adapters/extraction/pdf_extractor.py:68), [`tts_orchestration_service.py`](src/domain/services/tts_orchestration_service.py:992), [`conversion_presenter.py`](src/ui/presenters/conversion_presenter.py:105).
- Logging failures must remain local structured failures and must not destabilize UI responsiveness (aligning with NFR1 and observability NFR14 from planning artifacts).

### Architecture Compliance

- Respect boundary enforcement from architecture:
  - schema and logger logic stay inside infrastructure logging layer ([`event_schema.py`](src/infrastructure/logging/event_schema.py:1), [`jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py:1))
  - domain/services/adapters/UI emit through logger interface, not ad-hoc file writes.
- Preserve event-system pattern from architecture (`domain.action`) and shared payload baseline (`correlation_id`, `job_id`, `stage`, `event`, `timestamp`) while keeping story-required fields mandatory.
- Keep service result/error normalization untouched:
  - this story validates logging payload contract, it does not replace existing `{ok, data, error}` and `{code, message, details, retryable}` conventions used by domain services.
- Maintain offline-first constraints:
  - no transport/export of logs
  - diagnostics remain local append-only JSONL under runtime path.
- Ensure no architectural leakage:
  - no UI-thread business policy in adapters
  - no direct persistence coupling from UI layer to logging file.

### Library / Framework Requirements

- Keep implementation within current project dependency envelope declared in [`pyproject.toml`](pyproject.toml):
  - Python standard library modules used by current logger (`json`, `pathlib`, `datetime`) are sufficient for this story.
- Do not introduce external logging transport dependencies (e.g., remote collectors, telemetry SDKs) for MVP scope.
- Preserve compatibility with existing UI/runtime stack and core dependencies already used in project:
  - `PyQt5` UI stack remains non-blocking consumer of logging behavior, not a dependency of logger internals.
  - `PyYAML`, `EbookLib`, `PyPDF2` are unrelated to schema contract enforcement and should not be coupled into logging core.
- Maintain append-only file handling via built-in file I/O as used in [`JsonlLogger.emit()`](src/infrastructure/logging/jsonl_logger.py:19).

### File Structure Requirements

- Primary implementation targets for Story 5.1:
  - [`src/infrastructure/logging/event_schema.py`](src/infrastructure/logging/event_schema.py)
  - [`src/infrastructure/logging/jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py)
- Primary verification targets:
  - [`tests/integration/test_jsonl_logging.py`](tests/integration/test_jsonl_logging.py)
  - any focused unit tests under [`tests/unit/`](tests/unit) for schema validation and logger behavior.
- Keep architectural boundaries intact:
  - emitters remain distributed in domain/adapters/UI layers
  - schema + write contract remains centralized in infrastructure logging.
- Do not create alternate logging paths outside runtime logs directory conventions from architecture (`runtime/logs`).

### Testing Requirements

- Preserve and extend integration assertions in [`test_bootstrap_emits_required_jsonl_events()`](tests/integration/test_jsonl_logging.py:55):
  - required bootstrap/migration/model-registry/engine-health event presence
  - required field coverage via [`REQUIRED_EVENT_FIELDS`](tests/integration/test_jsonl_logging.py:9)
  - timestamp validity via [`is_valid_utc_iso_8601()`](tests/integration/test_jsonl_logging.py:9).
- Add focused unit coverage for schema validator edge cases in [`validate_event_payload()`](src/infrastructure/logging/event_schema.py:31):
  - missing required field rejection
  - invalid `event` naming rejection (not `domain.action`)
  - invalid timestamp rejection
  - acceptance path for valid payload with nullable optional fields in `extra`.
- Add focused unit coverage for append-only writer semantics in [`JsonlLogger.emit()`](src/infrastructure/logging/jsonl_logger.py:19):
  - exactly one JSON object per line
  - consecutive emits append lines (no truncation)
  - payload validation executes before persistence.
- Validate that failures are local and structured:
  - logger validation exceptions are deterministic and actionable for developers
  - no networking side effects in any logging test scenario.

### Git Intelligence Summary

- Recent commit sequence indicates a completed playback hardening cycle and epic transition to diagnostics work:
  - `f425811` — Epic 4 retrospective completion and closure of playback follow-ups
  - `555cbcb` — Story 4.5 code-review hardening
  - `49f401a` — Story 4.5 implementation baseline
  - `bbe3eb1` — Story 4.5 context creation
  - `54d94ab` — Story 4.4 review fixes.
- Actionable implications for Story 5.1:
  - preserve stable event contracts already consumed by multiple services and tests
  - favor additive hardening over broad refactors in logging internals
  - avoid regressions in existing integration coverage that assumes required fields and UTC timestamps.

### Latest Tech Information

- Dependency checks (Python package index) confirm current versions remain aligned with project baseline:
  - `PyQt5` latest: `5.15.11`
  - `PyYAML` latest: `6.0.3`
  - `EbookLib` latest/installed: `0.20`
  - `PyPDF2` latest/installed: `3.0.1`.
- Story 5.1 does not require introducing or upgrading logging-specific third-party packages.
- Recommended implementation posture:
  - keep JSONL contract hardening on standard library primitives already in place
  - prioritize schema strictness and deterministic validation over package churn
  - keep event model stable for downstream diagnostics workflows.

### Project Context Reference

- No `project-context.md` file was discovered for pattern `**/project-context.md`.
- Effective context sources used for this story context:
  - [`_bmad-output/planning-artifacts/epics.md`](./_bmad-output/planning-artifacts/epics.md)
  - [`_bmad-output/planning-artifacts/prd.md`](./_bmad-output/planning-artifacts/prd.md)
  - [`_bmad-output/planning-artifacts/architecture.md`](./_bmad-output/planning-artifacts/architecture.md)
  - [`_bmad-output/implementation-artifacts/sprint-status.yaml`](./_bmad-output/implementation-artifacts/sprint-status.yaml)
  - Current logging implementation references:
    - [`event_schema.py`](src/infrastructure/logging/event_schema.py:1)
    - [`jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py:1)
    - [`test_jsonl_logging.py`](tests/integration/test_jsonl_logging.py:1)

### Project Structure Notes

- Keep all schema and logger contract logic in infrastructure logging modules only:
  - [`src/infrastructure/logging/event_schema.py`](src/infrastructure/logging/event_schema.py)
  - [`src/infrastructure/logging/jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py)
- Do not move validation logic into emitters (services/adapters/UI). Emitters should only provide valid payloads.
- Preserve runtime location boundaries for logs under `runtime/logs` and keep append-only behavior.

### References

- Epic/story source: [`_bmad-output/planning-artifacts/epics.md`](./_bmad-output/planning-artifacts/epics.md)
- Product requirements: [`_bmad-output/planning-artifacts/prd.md`](./_bmad-output/planning-artifacts/prd.md)
- Architecture constraints: [`_bmad-output/planning-artifacts/architecture.md`](./_bmad-output/planning-artifacts/architecture.md)
- Sprint tracker: [`_bmad-output/implementation-artifacts/sprint-status.yaml`](./_bmad-output/implementation-artifacts/sprint-status.yaml)
- Core implementation points:
  - [`validate_event_payload()`](src/infrastructure/logging/event_schema.py:31)
  - [`JsonlLogger.emit()`](src/infrastructure/logging/jsonl_logger.py:19)
  - [`test_bootstrap_emits_required_jsonl_events()`](tests/integration/test_jsonl_logging.py:55)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log -n 5 --pretty=format:'%h|%ad|%s' --date=iso`
- `python -m pip index versions PyQt5`
- `python -m pip index versions PyYAML`
- `python -m pip index versions EbookLib`
- `python -m pip index versions PyPDF2`
- `PYTHONPATH=src python -m unittest tests.unit.test_event_schema tests.unit.test_jsonl_logger -v`
- `PYTHONPATH=src python -m unittest tests.integration.test_jsonl_logging tests.integration.test_tts_provider_events_schema -v`
- `PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py' -v`

### Completion Notes List

- Story 5.1 selected as first backlog story from Epic 5 in sprint tracking.
- Comprehensive developer context generated for JSONL schema contract, naming validation, append-only semantics, and offline logging constraints.
- Pipeline-wide emitter alignment expectations documented to prevent event contract drift.
- Latest package-version context captured for dependency awareness without introducing new logging dependencies.
- Ultimate context engine analysis completed - comprehensive developer guide created.
- Strengthened event schema validation: strict `domain.action` regex, UTC-only ISO-8601 enforcement, and explicit nullable `extra` typing validation.
- Hardened JSONL logger contract: append-only one-object-per-line persistence with structured local exceptions (`logging.invalid_event_payload`, `logging.write_failed`).
- Added focused unit coverage for schema and logger edge cases, including malformed event names, non-UTC timestamps, append behavior, and structured write failures.
- Revalidated bootstrap and provider logging integrations plus full regression suite (216 tests passing).

### File List

- _bmad-output/implementation-artifacts/5-1-define-correlated-jsonl-event-schema-and-logging-contract.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/infrastructure/logging/event_schema.py
- src/infrastructure/logging/jsonl_logger.py
- tests/unit/test_event_schema.py
- tests/unit/test_jsonl_logger.py

## Change Log

- 2026-02-15: Implemented Story 5.1 logging contract hardening (schema validation, structured local logger errors, and automated verification expansion).

## Story Completion Status

- Story ID: `5.1`
- Story Key: `5-1-define-correlated-jsonl-event-schema-and-logging-contract`
- Status set to: `review`
- Completion note: Logging schema and JSONL writer hardened with strict validation, structured local failure semantics, and passing regression suite.
