# Story 1.2: Validate Model Assets and Engine Health at Startup

Status: review

## Story

As a desktop user preparing offline conversion,
I want the application to validate required local model assets and engine health during bootstrap,
so that I know conversion can start reliably without internet access.

## Acceptance Criteria

1. **Given** a local model manifest in `model_manifest.yaml` and registry logic in `model_registry_service.py`  
   **When** bootstrap validation runs at startup  
   **Then** each required model is classified with status `installed`, `missing`, or `invalid`  
   **And** integrity checks include expected version, hash, and size.

2. **Given** TTS providers implementing `tts_provider.py`  
   **When** health validation is executed through `health_check` on each configured engine  
   **Then** readiness signals include per-engine availability for Chatterbox GPU and Kokoro CPU fallback  
   **And** provider-level failures are returned as normalized errors in `errors.py`.

3. **Given** offline operation is mandatory for MVP FR27 and FR28  
   **When** one or more required assets are `missing` or `invalid`  
   **Then** conversion readiness is set to `not_ready`  
   **And** the service returns actionable remediation details without attempting any cloud call.

4. **Given** startup diagnostics are required for supportability  
   **When** registry and health checks complete  
   **Then** JSONL events are emitted via `jsonl_logger.py` for stages `model_registry` and `engine_health`  
   **And** events include `correlation_id`, `stage`, `event`, `severity`, and ISO-8601 UTC `timestamp`.

## Tasks / Subtasks

- [x] Implement model manifest and registry service contract (AC: 1, 3)
  - [x] Add `config/model_manifest.yaml` with required model entries (engine, version, expected hash, expected size, local path).
  - [x] Add `src/domain/services/model_registry_service.py` to load manifest and classify each model as `installed`/`missing`/`invalid`.
  - [x] Implement integrity checks (existence, non-empty file, size equality, SHA-256 hash equality).
  - [x] Return normalized service result shape `{ok, data, error}` and normalized errors `{code, message, details, retryable}`.

- [x] Establish domain TTS port and adapter implementations with health checks (AC: 2)
  - [x] Create `src/domain/ports/__init__.py` and `src/domain/ports/tts_provider.py` as the canonical provider port (ABC with `synthesize_chunk`, `list_voices`, `health_check`).
  - [x] Create `src/adapters/tts/__init__.py`, `src/adapters/tts/chatterbox_provider.py` (stub), and `src/adapters/tts/kokoro_provider.py` (stub) implementing the domain port.
  - [x] Remove deprecated `src/adapters/providers/tts_provider.py` and migrate all references.
  - [x] Ensure provider failures are mapped to normalized error codes and do not raise raw exceptions past service boundary.

- [x] Wire startup readiness validation into bootstrap and dependency wiring (AC: 1, 2, 3)
  - [x] Integrate registry + provider health calls into `src/app/main.py` bootstrap flow after migrations complete.
  - [x] Update `src/app/dependency_container.py` to wire providers from `src/domain/ports` + `src/adapters/tts` locations.
  - [x] Compute startup readiness aggregate (`ready`/`not_ready`) from model states and provider health outcomes.
  - [x] Persist or expose actionable remediation details for UI/presenter consumption in later story work.
  - [x] Enforce no network calls in this path.

- [x] Emit startup diagnostics events (AC: 4)
  - [x] Emit `model_registry.started|completed|failed` at stage `model_registry`.
  - [x] Emit `engine_health.started|completed|failed` at stage `engine_health`.
  - [x] Include required fields from `src/infrastructure/logging/event_schema.py` and UTC ISO-8601 timestamps.

- [x] Add tests for model/engine readiness behavior (AC: 1..4)
  - [x] Unit tests for manifest parsing and model state classification including `installed`, `missing`, `invalid`.
  - [x] Unit tests for hash/size integrity mismatch behavior and normalized error payloads.
  - [x] Unit tests for readiness aggregate logic with mixed provider outcomes.
  - [x] Integration test for bootstrap flow asserting readiness `not_ready` when required assets invalid/missing.
  - [x] Integration test verifying JSONL events for `model_registry` and `engine_health` stages.

## Dev Notes

### Story Intent

- Deliver deterministic startup readiness guardrails before conversion starts.
- Prevent conversion entry when required assets or engine health are not acceptable.
- Keep implementation local-first and offline-safe.

### Cross-Story Context (from Story 1.1)

- Foundation already exists for bootstrap, migrations, normalized result/error contracts, and JSONL logging.
- Reuse existing boundaries from `src/app/main.py`, `src/contracts/result.py`, `src/contracts/errors.py`, and `src/infrastructure/logging/jsonl_logger.py`.
- Do not bypass the established service-layer validation pattern introduced in Story 1.1.

### Architecture Compliance Requirements

- Maintain layer boundaries: no UI direct DB/provider access.
- Keep fallback policy in orchestration layer (future stories), not in provider adapters.
- Keep naming conventions: Python and JSON fields in `snake_case`, event names in `domain.action`.
- Keep timestamp format ISO-8601 UTC.

### Library / Framework Requirements

- Use current project dependency baseline from `pyproject.toml` (Python >= 3.10, `PyYAML>=6.0`).
- Prefer Python stdlib for file integrity checks (`hashlib`, `pathlib`, `os`).
- Do not add cloud SDKs, remote APIs, or network-dependent packages.

### File Structure Requirements

- Add / modify only architecture-aligned locations:
  - `config/model_manifest.yaml` (NEW)
  - `src/domain/ports/__init__.py` (NEW)
  - `src/domain/ports/tts_provider.py` (NEW - ABC port)
  - `src/domain/services/model_registry_service.py` (NEW)
  - `src/adapters/tts/__init__.py` (NEW)
  - `src/adapters/tts/chatterbox_provider.py` (NEW - stub)
  - `src/adapters/tts/kokoro_provider.py` (NEW - stub)
  - `src/adapters/providers/tts_provider.py` (DELETE)
  - `src/app/dependency_container.py` (MODIFY)
  - `src/app/main.py` (MODIFY)
- Keep runtime model paths under local project/runtime/config conventions.

### Testing Requirements

- Validate ACs with deterministic local tests.
- Ensure tests cover negative paths (`missing`, `invalid`, provider failure).
- Verify emitted JSONL events include required schema fields.
- Verify no network operations are required for bootstrap readiness.

### Previous Story Intelligence

- Recent work established strict normalization contracts and migration/bootstrap patterns; follow these patterns exactly.
- Maintain non-Qt-safe dependency wiring principles in foundational bootstrap logic.
- Keep implementation incremental and test-backed before broad feature expansion.

### Git Intelligence Summary

- Recent commits indicate active schema hardening and config robustness:
  - `chore(schema): add foreign key indexes for jobs and chunks`
  - `chore(schema): add diagnostics correlation index`
  - `chore(schema): enrich initial tables for upcoming stories`
  - `fix(config): use PyYAML loader with safer fallback scalar coercion`
  - `feat(story-1.1): initialize local foundation, sqlite migrations, contracts, logging and tests`
- Implication: preserve backward-compatible startup behavior and avoid breaking existing migration/bootstrap tests.

### Latest Technical Information

- Within this offline workflow run, no external web fetch was performed.
- Apply current best-practice defaults for Python 3.10+ local integrity checks:
  - SHA-256 hashing for manifest validation.
  - Explicit error categorization for IO vs integrity mismatch.
  - Fast-fail classification with actionable remediation text.

### Project Context Reference

- No concrete `project-context.md` was found in repository runtime context during this workflow execution.

### References

- Source epic and ACs: `_bmad-output/planning-artifacts/epics.md` (Epic 1, Story 1.2)
- Architecture constraints and boundaries: `_bmad-output/planning-artifacts/architecture.md`
- Product requirement traceability: `_bmad-output/planning-artifacts/prd.md` (FR27, FR28, NFR9, NFR14)
- Sprint tracking source: `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Previous story context: `_bmad-output/implementation-artifacts/1-1-initialize-local-application-foundation-and-persistent-job-store.md`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log --oneline -n 5`
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v`

### Implementation Plan

- Added local model manifest contract and registry validation service with file existence, size, and SHA-256 checks.
- Introduced canonical domain TTS provider port and two local adapters (Chatterbox GPU, Kokoro CPU) with normalized health checks.
- Integrated startup readiness flow in bootstrap after migrations with JSONL diagnostics for `model_registry` and `engine_health` stages.
- Added readiness aggregation service returning deterministic `ready` / `not_ready` with actionable remediation details.
- Expanded unit and integration tests for model states, provider health normalization, readiness aggregation, and startup not-ready behavior.

### Completion Notes List

- Story context generated with architecture guardrails, anti-pattern prevention, and implementation-ready task decomposition.
- Startup status for this story is set to `ready-for-dev` by create-story workflow output requirement.
- Implemented model manifest + registry validation with normalized result/error contracts and offline-safe integrity checks.
- Migrated TTS provider boundary from `src/adapters/providers/tts_provider.py` to canonical port/adapters in `src/domain/ports` and `src/adapters/tts`.
- Added bootstrap startup readiness pipeline with `model_registry` and `engine_health` events and persisted aggregate readiness in container.
- Added comprehensive tests (unit + integration) covering model classification, integrity mismatches, provider health failures, readiness aggregation, and bootstrap `not_ready` path.
- Full test suite executed successfully with `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v` (20 tests, OK).

### File List

- _bmad-output/implementation-artifacts/1-2-validate-model-assets-and-engine-health-at-startup.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- config/model_manifest.yaml
- src/domain/ports/__init__.py
- src/domain/ports/tts_provider.py
- src/domain/services/model_registry_service.py
- src/domain/services/startup_readiness_service.py
- src/adapters/tts/__init__.py
- src/adapters/tts/chatterbox_provider.py
- src/adapters/tts/kokoro_provider.py
- src/adapters/providers/tts_provider.py (deleted)
- src/app/dependency_container.py
- src/app/main.py
- tests/unit/test_model_registry_service.py
- tests/unit/test_tts_providers_health.py
- tests/unit/test_startup_readiness_service.py
- tests/integration/test_bootstrap_and_migrations.py

## Change Log

- 2026-02-11: Created Story 1.2 comprehensive implementation context and marked story status `ready-for-dev`.
- 2026-02-11: Implemented Story 1.2 startup model/engine readiness validation, added diagnostics events, migrated TTS provider boundary, added tests, and set status to `review`.
