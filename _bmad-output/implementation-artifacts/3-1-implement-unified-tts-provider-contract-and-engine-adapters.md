# Story 3.1: Implement Unified TTS Provider Contract and Engine Adapters

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user starting audio conversion,
I want both TTS engines to expose a unified contract,
so that the application can switch engines predictably without changing user workflow.

## Acceptance Criteria

1. **Given** both engines are configured locally  
   **When** the provider layer is initialized  
   **Then** a single contract exposes `synthesize_chunk`, `list_voices`, and `health_check`  
   **And** both engine adapters conform to identical input/output semantics.

2. **Given** engine capability discovery is required for voice selection  
   **When** available voices are requested  
   **Then** the response is normalized in a consistent structure  
   **And** failures return normalized errors with `code`, `message`, `details`, and `retryable`.

3. **Given** synthesis is executed on a text chunk  
   **When** a provider succeeds  
   **Then** audio chunk output and metadata are returned in standardized result format  
   **And** provider-specific internals are not leaked beyond the adapter boundary.

4. **Given** an adapter fails during health check or synthesis  
   **When** the failure is propagated upward  
   **Then** orchestration receives deterministic error categories for fallback handling  
   **And** logging emits structured events with correlation fields and UTC timestamps.

## Tasks / Subtasks

- [x] Define and enforce unified provider contract in domain boundary (AC: 1, 2, 3)
  - [x] Confirm canonical protocol for `synthesize_chunk`, `list_voices`, `health_check` in `src/domain/ports/tts_provider.py`.
  - [x] Align request/response DTOs to standardized `{ok, data, error}` and normalized error structure.
  - [x] Add explicit type hints and docstrings for deterministic adapter compliance.
- [x] Adapt Chatterbox provider to contract without fallback logic leakage (AC: 1, 3, 4)
  - [x] Ensure `src/adapters/tts/chatterbox_provider.py` maps provider-native payloads to canonical result envelope.
  - [x] Normalize exceptions to `code/message/details/retryable` with deterministic categories.
  - [x] Emit structured provider events usable by orchestration diagnostics.
- [x] Adapt Kokoro provider to same contract and semantics (AC: 1, 2, 3, 4)
  - [x] Ensure `src/adapters/tts/kokoro_provider.py` returns same shape and metadata conventions as Chatterbox.
  - [x] Normalize voice-listing output schema and failure behavior.
  - [x] Keep adapter responsibilities limited to provider integration (no policy decisions).
- [x] Preserve orchestration authority for deterministic fallback behavior (AC: 4)
  - [x] Verify `src/domain/services/tts_orchestration_service.py` owns all fallback decisions.
  - [x] Validate adapter failures are explicit enough for fallback decisioning but never execute fallback internally.
- [x] Add regression-safe unit/integration coverage (AC: 1..4)
  - [x] Unit tests for interface conformance and error normalization for both providers.
  - [x] Contract tests for consistent voice list and synthesis result schema across engines.
  - [x] Logging-focused tests ensuring required correlation/event fields are emitted.

## Dev Notes

### Story Intent

- Establish a strict, reusable provider contract across both local TTS engines before fallback orchestration work.
- Prevent provider-specific leakage into orchestration by standardizing result, error, and metadata payloads.
- Provide deterministic guardrails so Story 3.3 can implement fallback policy exclusively at orchestration layer.

### Story Context and Dependencies

- This story is the first implementation item in Epic 3 and unlocks downstream stories:
  - Story 3.2 (chunking) consumes normalized synthesis input/output boundaries.
  - Story 3.3 (fallback orchestration) depends on deterministic provider error categories.
  - Story 3.4 (resume) depends on stable provider failure semantics and logging payload consistency.
- Existing implementation baseline indicates providers currently exist as startup-validation stubs:
  - `src/adapters/tts/chatterbox_provider.py`
  - `src/adapters/tts/kokoro_provider.py`
  - `src/domain/ports/tts_provider.py`
- Current orchestration service remains intentionally minimal and must stay policy owner for fallback:
  - `src/domain/services/tts_orchestration_service.py`

### Developer Context Section

- Keep provider adapters pure-integration components. They may map engine-native behavior, but must not encode cross-engine fallback logic.
- Preserve canonical contracts from existing architecture choices:
  - Success/failure envelope from `src/contracts/result.py` (`{ok, data, error}`)
  - Error shape from `src/contracts/errors.py` (`{code, message, details, retryable}`)
  - Logging schema contract from `src/infrastructure/logging/event_schema.py`
- Ensure adapter outputs are consistent enough that orchestration can switch engines based on deterministic error categories rather than free-form parsing.

### Technical Requirements

- Unified contract methods are mandatory and stable: `synthesize_chunk`, `list_voices`, `health_check`.
- `synthesize_chunk` must return audio bytes (or normalized failure) with no provider-internal object leakage.
- `list_voices` must expose deterministic, engine-scoped voice identifiers in a stable list format.
- `health_check` must provide normalized availability semantics aligned with model-registry state (`installed/missing/invalid`) when injected.
- Failures must map to deterministic error codes suitable for fallback decisioning (e.g., availability/config/runtime classes).
- Retry semantics must be explicit and data-driven via `retryable`, not inferred from message text.

### Architecture Compliance

- Respect defined boundary ownership from architecture:
  - Provider boundary: `src/domain/ports/tts_provider.py` and `src/adapters/tts/*`.
  - Orchestration boundary: `src/domain/services/tts_orchestration_service.py` owns fallback policy.
  - Logging boundary: `src/infrastructure/logging/jsonl_logger.py` + event schema validation.
- Keep code structure aligned with modular layout under `src/domain`, `src/adapters`, `src/app`, `src/infrastructure`.
- Maintain local-only execution constraints; no network/cloud calls from provider adapter paths.

### Library / Framework Requirements

- Python runtime baseline: `>=3.10` from `pyproject.toml`.
- Current dependencies relevant to this story:
  - `PyYAML>=6.0` (config surface)
  - Existing local engine integrations for Chatterbox (GPU/ROCm target) and Kokoro (CPU fallback) must remain optional and encapsulated.
- No new third-party dependency is required to complete Story 3.1 contract hardening.

### File Structure Requirements

- Primary files likely to implement/update:
  - `src/domain/ports/tts_provider.py`
  - `src/adapters/tts/chatterbox_provider.py`
  - `src/adapters/tts/kokoro_provider.py`
  - `src/domain/services/tts_orchestration_service.py` (only for adapter contract integration touchpoints, not fallback implementation expansion)
  - `src/app/dependency_container.py` (provider wiring and health normalization consistency)
- Supporting logging contract files if needed:
  - `src/infrastructure/logging/event_schema.py`
  - `src/infrastructure/logging/jsonl_logger.py`

### Testing Requirements

- Add/extend unit tests validating both providers conform identically to contract shape.
- Validate deterministic normalized failure categories for synthesis and health checks.
- Validate voice listing schema equivalence across engines.
- Validate no fallback behavior is executed inside provider adapters.
- Keep regression coverage for startup readiness integration using provider `health_check` outputs.

### Previous Story Intelligence

- Recent stories established strict contract-first patterns and deterministic error normalization.
- Story 2.5 emphasized local-only remediation, schema-valid diagnostics events, and retry semantics based strictly on `retryable`; reuse this rigor for provider failures.
- Prior code-review outcomes favored absolute imports, explicit input validation, centralized shared utilities, and stronger edge-case tests.

### Git Intelligence Summary

Recent commit history indicates an active hardening pattern that should be continued:

- `4a244c1` fix(story-2.5): review fixes (imports, validation, logger centralization, tests)
- `c5cd64d` implementation of unified extraction diagnostics
- `c9c27ce` story artifact creation and ready-for-dev setup
- `093c620` story 2.4 review fixes and edge-case quality improvements
- `9912d4e` story 2.4 implementation

Implementation implication: keep Story 3.1 focused on robust contracts, deterministic normalization, and comprehensive tests before adding orchestration complexity.

### Latest Tech Information

- Target environment remains Linux Mint with AMD ROCm path for Chatterbox GPU and Kokoro CPU fallback architecture.
- No mandatory dependency upgrade identified for this story; prioritize contract stability over introducing new libraries.
- Preserve compatibility with current project packaging and test execution strategy.

### Project Context Reference

- No `project-context.md` file discovered via configured pattern.
- Context derived from:
  - `_bmad-output/planning-artifacts/epics.md`
  - `_bmad-output/planning-artifacts/prd.md`
  - `_bmad-output/planning-artifacts/architecture.md`
  - `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Project Structure Notes

- Follow existing package layout with clear separation:
  - Domain ports under `src/domain/ports/`
  - Provider adapters under `src/adapters/tts/`
  - Wiring at `src/app/dependency_container.py`
  - Shared contracts in `src/contracts/`
  - Logging infrastructure in `src/infrastructure/logging/`
- Keep naming in `snake_case` for modules/files and explicit engine identifiers in payload details.
- Variance to track: architecture references `chunking_service.py` for later story; this file is not expected in Story 3.1 and should not be introduced prematurely.

### References

- Epic/story definition: `_bmad-output/planning-artifacts/epics.md` (Epic 3, Story 3.1)
- Product constraints and FR/NFR mapping: `_bmad-output/planning-artifacts/prd.md` (FR9-FR18, NFR1, NFR2, NFR4, NFR10, NFR11, NFR13, NFR14)
- Architecture constraints and boundary ownership: `_bmad-output/planning-artifacts/architecture.md` (TTSProvider contract, fallback in orchestration, domain.action logging)
- Current implementation baseline:
  - `src/domain/ports/tts_provider.py`
  - `src/adapters/tts/chatterbox_provider.py`
  - `src/adapters/tts/kokoro_provider.py`
  - `src/domain/services/tts_orchestration_service.py`
  - `src/app/dependency_container.py`
  - `tests/unit/test_tts_providers_health.py`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `cat ./_bmad/core/tasks/workflow.xml`
- `cat ./_bmad/bmm/workflows/4-implementation/create-story/instructions.xml`
- `cat ./_bmad-output/planning-artifacts/prd.md`
- `cat ./_bmad-output/planning-artifacts/architecture.md`
- `git log --oneline -n 5`
- `cat ./_bmad-output/implementation-artifacts/sprint-status.yaml`
- `python -m unittest tests.unit.test_tts_provider_contract -v`
- `PYTHONPATH=src python -m unittest tests.unit.test_tts_provider_contract tests.unit.test_tts_providers_health -v`
- `PYTHONPATH=src python -m unittest tests.unit.test_tts_provider_contract tests.unit.test_tts_providers_health tests.integration.test_tts_provider_events_schema -v`
- `PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py' -v`

### Completion Notes List

- Story scaffolded and set to `ready-for-dev`.
- Acceptance criteria copied from Epic 3 Story 3.1 and preserved in BDD format.
- Developer context includes architecture boundary ownership to prevent fallback logic leaking into provider adapters.
- Guidance emphasizes deterministic normalized errors and contract consistency between `ChatterboxProvider` and `KokoroProvider`.
- Story includes project structure constraints, test expectations, and prior-story quality learnings.
- Ultimate context engine analysis completed - comprehensive developer guide created.
- Unified TTS contract strengthened in `src/domain/ports/tts_provider.py` with typed DTOs for voices and synthesis payloads, plus explicit logging protocol shape.
- Chatterbox and Kokoro adapters now return canonical `Result[{audio_bytes, metadata}]` for synthesis, canonical voice descriptors, and normalized error categories (`availability`, `input`) with deterministic retry semantics.
- Provider adapters now emit structured `domain.action` events with correlation fields and UTC timestamps through existing JSONL logger wiring.
- Dependency container now injects the shared logger into both TTS providers to preserve observability consistency without adding fallback behavior to adapters.
- Added provider contract/unit coverage and integration logging coverage; full repository regression suite passes (`84` tests).

### File List

- _bmad-output/implementation-artifacts/3-1-implement-unified-tts-provider-contract-and-engine-adapters.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/domain/ports/tts_provider.py
- src/adapters/tts/chatterbox_provider.py
- src/adapters/tts/kokoro_provider.py
- src/app/dependency_container.py
- tests/unit/test_tts_provider_contract.py
- tests/integration/test_tts_provider_events_schema.py

## Change Log

- 2026-02-13: Implemented Story 3.1 unified provider contract/adapters, added contract and event-schema tests, and validated with full regression run.
