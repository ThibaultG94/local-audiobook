# Story 4.1: Assemble Synthesized Chunks into Final Audio Output

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user completing document conversion,
I want synthesized chunks to be assembled into a single final audio file,
so that I can listen to a continuous audiobook in my selected format.

## Acceptance Criteria

1. **Given** synthesized chunk artifacts are available from orchestration  
   **When** post-processing runs in `audio_postprocess_service.py`  
   **Then** chunks are assembled in persisted order without loss or duplication  
   **And** continuity between chunk boundaries is preserved for listener experience.

2. **Given** output format is selected as WAV  
   **When** final rendering executes through `wav_builder.py`  
   **Then** a valid WAV file is produced at target path  
   **And** metadata needed for library indexing is returned in normalized response format.

3. **Given** output format is selected as MP3  
   **When** encoding executes through `mp3_encoder.py`  
   **Then** a valid MP3 file is produced at target path  
   **And** failures return normalized error payload with retryability semantics.

4. **Given** assembly and encoding are observable pipeline stages  
   **When** post-processing starts, succeeds, or fails  
   **Then** JSONL events are emitted through `jsonl_logger.py` with stable `domain.action` events  
   **And** event payload includes `correlation_id`, `job_id`, `stage`, `event`, `severity`, and UTC ISO-8601 `timestamp`.

## Tasks / Subtasks

- [ ] Implement post-processing service for deterministic chunk assembly and format rendering (AC: 1, 2, 3)
  - [ ] Add `audio_postprocess_service.py` with a single orchestration entrypoint that accepts job id, output format, and chunk artifacts.
  - [ ] Validate chunk ordering and continuity preconditions before assembly; fail fast with normalized errors on gaps/duplicates/missing payloads.
  - [ ] Produce normalized success payload containing output artifact metadata for downstream library persistence.
- [ ] Implement WAV and MP3 adapter boundaries (AC: 2, 3)
  - [ ] Add `wav_builder.py` to generate valid WAV output deterministically from assembled chunk audio.
  - [ ] Add `mp3_encoder.py` to generate valid MP3 output deterministically from assembled chunk audio.
  - [ ] Ensure adapter failures map to normalized `{code, message, details, retryable}` payloads.
- [ ] Wire post-processing into conversion flow without breaking existing orchestration ownership (AC: 1, 2, 3)
  - [ ] Integrate service wiring in `dependency_container.py`.
  - [ ] Extend domain orchestration/worker handoff so post-processing executes after successful synthesis while preserving existing lifecycle semantics.
  - [ ] Preserve UI non-blocking behavior and existing presenter/view contracts.
- [ ] Add observability for post-processing lifecycle (AC: 4)
  - [ ] Emit JSONL events for `postprocess.started`, `postprocess.succeeded`, and `postprocess.failed` (or equivalent stable `domain.action` names).
  - [ ] Include required fields: `correlation_id`, `job_id`, `stage`, `event`, `severity`, `timestamp` (+ `engine`/`chunk_index` where applicable).
- [ ] Add test coverage for assembly, format encoding, and observability (AC: 1..4)
  - [ ] Unit tests for order validation, normalized failure behavior, and metadata payload shape in post-processing service.
  - [ ] Adapter-focused tests for WAV/MP3 success and failure paths.
  - [ ] Integration test for end-of-conversion path proving final artifact creation and postprocess event emission.

## Dev Notes

### Developer Context Section

- This story starts Epic 4 and depends directly on persisted chunk synthesis outputs produced by orchestration in [TtsOrchestrationService.synthesize_persisted_chunks_for_job()](src/domain/services/tts_orchestration_service.py:146).
- The implementation must add post-processing as a distinct service boundary (`audio_postprocess_service`) and keep fallback/chunking ownership in domain orchestration, not in UI components.
- Existing project state already includes deterministic chunk ordering, lifecycle state handling, and correlated JSONL patterns; this story must extend those guarantees to final audio assembly.
- Keep contracts normalized across layers using existing result/error structures from [contracts.result](src/contracts/result.py:1) and [contracts.errors](src/contracts/errors.py:1).

### Technical Requirements

- Implement deterministic final assembly service that consumes persisted chunk synthesis outputs ordered by `chunk_index` and rejects missing/duplicate ordering with normalized errors.
- Provide format-specific rendering paths:
  - WAV via `wav_builder` adapter,
  - MP3 via `mp3_encoder` adapter.
- Return normalized response payload for post-processing with output metadata required by subsequent library indexing stories (path, format, duration if available, byte size if available).
- Preserve non-blocking execution posture inherited from prior conversion stories: heavy file operations must remain outside direct UI thread paths.
- Emit structured JSONL events for post-processing lifecycle (`started`, `succeeded`, `failed`) using `domain.action` naming and required schema fields.
- Ensure all timestamps are ISO-8601 UTC and naming remains `snake_case` for internal payload keys.

### Architecture Compliance

- Respect current boundaries from architecture decisions:
  - orchestration and chunk lifecycle remain in domain orchestration service,
  - post-processing assembly/encoding belongs to dedicated domain service + audio adapters,
  - UI continues to consume progress and status through presenter/worker paths without direct file-assembly logic.
- Keep repository boundaries intact: no direct DB writes from audio adapters; persistence integration for final artifact indexing is deferred to following library story.
- Follow established event contract (`domain.action`, correlated payload fields, UTC timestamps) already used across extraction/chunking/worker stages.
- Maintain deterministic behavior assumptions required by resume/lifecycle mechanisms implemented in previous stories.
- Do not introduce cloud/network dependencies; all assembly and encoding paths remain strictly local runtime operations.

### Library / Framework Requirements

- Use Python standard library capabilities for stream-safe file handling where possible; avoid adding dependencies for base concatenation flow.
- Integrate with existing project adapters and contracts:
  - domain service: `audio_postprocess_service.py` (to create),
  - audio adapters: `wav_builder.py` and `mp3_encoder.py` (to create),
  - observability: existing `jsonl_logger.py` event emitter.
- Reuse existing `Result` / normalized error patterns rather than introducing custom post-processing response shapes.
- Preserve compatibility with existing conversion outputs from orchestration and worker launch model; no changes to provider interfaces are required for this story.

### Project Structure Notes

- New domain service file expected: `src/domain/services/audio_postprocess_service.py`.
- New audio adapter files expected:
  - `src/adapters/audio/wav_builder.py`
  - `src/adapters/audio/mp3_encoder.py`
- Dependency wiring updates expected in `src/app/dependency_container.py` to register and expose post-processing components.
- Existing orchestration integration touchpoints likely in:
  - `src/domain/services/tts_orchestration_service.py` (handoff to post-processing),
  - `src/ui/workers/conversion_worker.py` (surface final artifact metadata via existing payload patterns, if needed).
- Runtime output location must align with architecture conventions under `runtime/library/audio/`.
- No direct UI-layer creation of audio files: `src/ui/views/` and `src/ui/presenters/` remain consumers of status/results only.

### Git Intelligence Summary

- Recent commits show a stabilization pattern around conversion worker behavior, orchestration contracts, and conversion configuration validation.
- Integration should be minimally invasive: extend existing orchestration/worker flow rather than introducing parallel execution paths.
- Current test strategy is contract-first with strong unit coverage on worker/presenter/service boundaries; Story 4.1 should follow the same approach to avoid regressions.

### Latest Tech Information

- No mandatory dependency upgrade is required for this story scope.
- Prefer implementation with existing stack and local adapters; focus on deterministic assembly correctness and robust error mapping.
- If MP3 encoding implementation requires codec-specific handling, keep adapter boundary explicit so behavior remains testable and replaceable without domain-level refactoring.

### Project Context Reference

- No `project-context.md` file was found via configured discovery pattern.
- Context for this story is derived from planning artifacts, architecture decisions, sprint status, previous story outcomes, git history, and the current codebase.

### References

- Story source: [epics.md](_bmad-output/planning-artifacts/epics.md)
- Product constraints: [prd.md](_bmad-output/planning-artifacts/prd.md)
- Architecture constraints: [architecture.md](_bmad-output/planning-artifacts/architecture.md)
- Sprint tracking: [sprint-status.yaml](_bmad-output/implementation-artifacts/sprint-status.yaml)
- Previous story context: [3-6-execute-conversion-in-dedicated-worker-with-non-blocking-ui-signals.md](_bmad-output/implementation-artifacts/3-6-execute-conversion-in-dedicated-worker-with-non-blocking-ui-signals.md)
- Orchestration baseline: [src/domain/services/tts_orchestration_service.py](src/domain/services/tts_orchestration_service.py)
- Worker baseline: [src/ui/workers/conversion_worker.py](src/ui/workers/conversion_worker.py)
- Logger baseline: [src/infrastructure/logging/jsonl_logger.py](src/infrastructure/logging/jsonl_logger.py)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log -n 5 --pretty=format:'%h|%s' --name-only`
- `find . -name 'project-context.md' -print`
- `PYTHONPATH=src python -m unittest tests.unit.test_conversion_worker tests.unit.test_tts_orchestration_service`
- `PYTHONPATH=src python -m unittest discover -s tests`

### Completion Notes List

- Story selected from first backlog entry in sprint status: `4-1-assemble-synthesized-chunks-into-final-audio-output`.
- Comprehensive context assembled from epics, PRD, architecture, sprint tracking, previous implementation artifact, recent commit history, and current source baseline.
- Story file generated as implementation-ready context with explicit guardrails for deterministic assembly, adapter boundaries, normalized errors, and observability.
- Story status set to `ready-for-dev` for direct handoff to `dev-story`.

### File List

- _bmad-output/implementation-artifacts/4-1-assemble-synthesized-chunks-into-final-audio-output.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/domain/services/audio_postprocess_service.py
- src/adapters/audio/wav_builder.py
- src/adapters/audio/mp3_encoder.py
- src/app/dependency_container.py
- src/domain/services/tts_orchestration_service.py
- src/ui/workers/conversion_worker.py
- tests/unit/test_audio_postprocess_service.py
- tests/unit/test_wav_builder.py
- tests/unit/test_mp3_encoder.py
- tests/integration/test_postprocess_pipeline_integration.py

## Story Completion Status

- Status set to: `ready-for-dev`
- Completion note: Ultimate context engine analysis completed - comprehensive developer guide created.
