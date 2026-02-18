# Story 6.1: Debug and Fix Conversion Pipeline Runtime Failure

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user launching conversion,
I want conversion to complete end-to-end without worker crashes,
so that imported documents reliably produce playable audio.

## Acceptance Criteria

1. **Given** the conversion worker catches runtime exceptions
   **When** an unhandled conversion failure occurs
   **Then** full traceback is captured and logged with `traceback.format_exc()`
   **And** diagnostics include enough context to identify root cause.

2. **Given** conversion is triggered from UI on a small TXT then PDF sample
   **When** pipeline executes through worker and orchestration
   **Then** end-to-end output is produced as WAV or MP3 without `worker_execution.unhandled_exception`
   **And** existing tests remain green with new regression tests added.

3. **Given** both engines are available in target environment
   **When** synthesis is executed with Chatterbox and with Kokoro
   **Then** each engine produces valid audio output
   **And** voice availability presented to UI matches real provider availability.

## Tasks / Subtasks

- [ ] Add traceback capture and structured diagnostics in conversion worker exception path (AC: 1)
  - [ ] Update unhandled exception branch in `src/ui/workers/conversion_worker.py` to include traceback text from `traceback.format_exc()` in normalized error details
  - [ ] Keep event emission non-blocking and preserve `worker_execution.failed` logging contract
  - [ ] Ensure diagnostic payload remains normalized (`code`, `message`, `details`, `retryable`) and correlation context is preserved
- [ ] Remove root causes producing `worker_execution.unhandled_exception` during end-to-end conversion (AC: 2)
  - [ ] Reproduce TXT and PDF conversion through UI worker path and identify failing stage
  - [ ] Apply fix in worker/service boundary (not in UI rendering layer) so conversion returns controlled failures or success
  - [ ] Confirm final audio completion path returns deterministic completed state
- [ ] Validate TTS engine execution and UI voice inventory consistency (AC: 3)
  - [ ] Run/adapt adapter tests to verify both Chatterbox and Kokoro produce valid outputs
  - [ ] Confirm voice inventory shown by presenter aligns with provider capability outputs
  - [ ] Add targeted guards if provider capability mismatches are found
- [ ] Add regression tests and verify full suite stability (AC: 2, 3)
  - [ ] Extend `tests/unit/test_conversion_worker.py` with traceback-presence assertion in unhandled exception normalization
  - [ ] Add/extend integration tests for TXT+PDF conversion completion path without `worker_execution.unhandled_exception`
  - [ ] Keep existing tests green after changes

## Dev Notes

### Developer Context Section

- Story selected from explicit user input: `6-1` (Epic 6, Story 1).
- Epic 6 goal is runtime hardening after integration: conversion stability, degraded readiness behavior, library polish, docs, and closure reporting.
- Immediate objective for this story is to eliminate crash-level conversion failures and improve diagnostics quality for root-cause analysis.
- Previous implementation context from Story 5.4 indicates diagnostic/event contracts are already standardized and should be reused.

### Technical Requirements

- Unhandled worker exceptions must include full traceback text (`traceback.format_exc()`) in diagnostic details.
- Keep normalized error contract end-to-end:
  - service result envelope: `{ok, data, error}`
  - error envelope: `{code, message, details, retryable}`
- Maintain deterministic event schema fields in worker events:
  - `event`, `stage`, `severity`, `correlation_id`, `job_id`, `timestamp`
  - include `chunk_index`, `engine`, and structured `extra` payload where applicable.
- Avoid introducing UI-thread blocking behavior while improving diagnostics and failure handling.

### Architecture Compliance

- Keep conversion execution orchestration in worker/service boundaries:
  - worker: `src/ui/workers/conversion_worker.py`
  - presenter/view: mapping and rendering only, no orchestration policy shifts.
- Preserve logging boundary in infrastructure logger components and event schema compatibility.
- Keep fallback policy deterministic in orchestration/service layer, not in engine adapters.
- Respect offline/privacy constraints: no remote diagnostics endpoint, no cloud telemetry.

### Library / Framework Requirements

- Python runtime in project docs targets 3.12; avoid introducing incompatible syntax for current packaging constraints.
- Reuse current dependencies from `pyproject.toml` (PyQt5, PyYAML, EbookLib, PyPDF2, pyttsx3) unless strictly required.
- No new third-party dependency is expected for this story; focus on runtime robustness and diagnostics completeness.

### Project Structure Notes

- Primary code touchpoints:
  - `src/ui/workers/conversion_worker.py`
  - `src/ui/presenters/conversion_presenter.py` (only if mapping fields must surface new diagnostic details)
- Likely integration touchpoints (depending on root cause):
  - `src/domain/services/*` (orchestration/chunking/postprocess services)
  - `src/adapters/tts/*` (provider behavior parity checks)
- Test touchpoints:
  - `tests/unit/test_conversion_worker.py`
  - `tests/integration/test_conversion_configuration_integration.py`
  - `tests/integration/test_tts_adapters_functional.py`

### Testing Requirements

- Add regression for traceback capture in normalized unhandled exception payload.
- Verify conversion flow for at least one small TXT and one small PDF path completes without `worker_execution.unhandled_exception`.
- Verify both engine adapters pass functional expectations in current environment constraints (or deterministic skip behavior if environment is unavailable).
- Run and keep green relevant unit and integration suites after fixes.

### Previous Story Intelligence

- Story 5.4 reinforced strict normalized diagnostics and local observability; this story must extend the same contracts instead of introducing ad-hoc error payloads.
- Existing tests already assert normalized unhandled exception code in worker path; this can be extended to assert traceback presence for AC1.

### Git Intelligence Summary

- Recent commits show a transition from feature implementation to Epic 6 planning/polish:
  - `8aa438f` Create Epic 6 and finalize epics and stories breakdown
  - `711adca` Add BMAD V6 completion report and update gitignore
  - `63505d5` docs refresh for Python 3.12 and ROCm 7.2
  - `96a5e48` conversion view + async worker integration
  - `97c6cd4` import widget wiring
- Implementation implication: prefer targeted hardening over architectural rewrites.

### Latest Tech Information

- No mandatory dependency upgrade identified for this story scope.
- Keep implementation aligned with current stack and contracts already present in repository.

### Project Context Reference

- `project-context.md` was not found via `**/project-context.md` pattern in the repository.
- Context used for this story:
  - `_bmad-output/planning-artifacts/epics.md`
  - `_bmad-output/planning-artifacts/prd.md`
  - `_bmad-output/planning-artifacts/architecture.md`
  - `_bmad-output/implementation-artifacts/sprint-status.yaml`
  - `_bmad-output/implementation-artifacts/5-4-provide-local-support-workflow-for-error-review-and-guided-remediation.md`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `python -m unittest -q tests.unit.test_conversion_worker`
- `python -m unittest -q tests.integration.test_conversion_configuration_integration`
- `python -m unittest -q tests.integration.test_tts_adapters_functional`

### Implementation Plan

- Reproduce unhandled conversion failure path and identify failing operation boundary in worker or launcher invocation.
- Add traceback capture in unhandled exception normalization while preserving normalized schema.
- Fix root cause for TXT and PDF end-to-end path through worker+orchestration.
- Validate provider behavior parity and UI voice availability consistency.
- Expand regression tests and run target suites.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story created for Epic 6 runtime stabilization and marked ready-for-dev.

### File List

- \_bmad-output/implementation-artifacts/6-1-debug-and-fix-conversion-pipeline-runtime-failure.md
- \_bmad-output/implementation-artifacts/sprint-status.yaml

## Story Completion Status

- Story ID: `6.1`
- Story Key: `6-1-debug-and-fix-conversion-pipeline-runtime-failure`
- Status set to: `ready-for-dev`
- Completion note: Ultimate context engine analysis completed - comprehensive developer guide created.
