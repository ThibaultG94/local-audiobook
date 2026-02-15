# Story 5.4: Provide Local Support Workflow for Error Review and Guided Remediation

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user troubleshooting repeated conversion failures,
I want a local support workflow that explains error codes and next steps,
so that I can resolve issues without external tools or cloud services.

## Acceptance Criteria

1. **Given** a failed job with persisted error context
   **When** support details are opened from the diagnostics UI
   **Then** user can view normalized fields `code`, `message`, `details`, and `retryable`
   **And** remediation guidance is matched to error category: extraction, chunking, engine_tts, export_postprocess, persistence.

2. **Given** retry decisions must be explicit  
   **When** an error is marked `retryable=true`  
   **Then** UI presents retry action with clear prerequisites  
   **And** non-retryable failures present alternative guidance such as re-import, model repair, or settings correction.

3. **Given** support workflow is local-first MVP  
   **When** guidance is displayed  
   **Then** all recommendations reference local actions only  
   **And** no external API call or cloud submission path is used.

4. **Given** support interactions must be traceable  
   **When** diagnostics are viewed copied or retry is initiated  
   **Then** JSONL events are emitted with `stage=support_workflow` and `domain.action` naming  
   **And** payload includes `correlation_id`, `job_id`, `event`, `severity`, and UTC ISO-8601 `timestamp`.

## Tasks / Subtasks

- [x] Extend diagnostics-to-support mapping in presenter (AC: 1, 2)
  - [x] Add deterministic mapping from normalized conversion errors to support-workflow view model in [`ConversionPresenter.map_conversion_error()`](src/ui/presenters/conversion_presenter.py:357)
  - [x] Add/extend category-level remediation routing for `extraction`, `chunking`, `engine/tts`, `export/postprocess`, `persistence` using local-only guidance
  - [x] Ensure displayed fields remain normalized and explicit: `code`, `message`/summary, `details`, `retryable`
- [x] Add support workflow panel behaviors in conversion UI (AC: 1, 2, 3)
  - [x] Extend diagnostics panel state in [`conversion_view.py`](src/ui/views/conversion_view.py) to include support guidance and retry prerequisites text
  - [x] Surface non-retryable alternatives (re-import, model repair/check, settings correction) in deterministic order
  - [x] Keep all user-facing guidance strictly local-first and English-only
- [x] Wire traceable support interactions into logging contract (AC: 4)
  - [x] Emit `support_workflow.viewed`, `support_workflow.copied`, and `support_workflow.retry_initiated` events through existing logger interface
  - [x] Ensure event names follow `domain.action` and include required fields: `correlation_id`, `job_id`, `event`, `severity`, `timestamp`
  - [x] Preserve non-blocking behavior if logging fails (no UI-thread interruption)
- [x] Add tests for support workflow coverage (AC: 1, 2, 3, 4)
  - [x] Unit tests in [`test_conversion_presenter.py`](tests/unit/test_conversion_presenter.py) for category mapping, retryability guidance, and normalized fields
  - [x] Unit tests in [`test_conversion_view.py`](tests/unit/test_conversion_view.py) for support panel rendering/copy/retry affordances
  - [x] Integration tests in [`test_conversion_configuration_integration.py`](tests/integration/test_conversion_configuration_integration.py) (or dedicated diagnostics integration file) validating support events and payload contract

## Dev Notes

### Developer Context Section

- Story selected automatically from sprint tracker as first backlog item: `5-4-provide-local-support-workflow-for-error-review-and-guided-remediation`.
- Previous story [`5-3-present-actionable-failure-diagnostics-in-conversion-ui.md`](_bmad-output/implementation-artifacts/5-3-present-actionable-failure-diagnostics-in-conversion-ui.md) established diagnostics mapping, safe detail filtering, and diagnostics UI eventing; this story extends that baseline into a **support workflow** focused on remediation execution.
- Core implementation objective: transform failure diagnostics into a guided local support flow that is explicit, deterministic, and aligned with normalized contracts.
- Primary risk to avoid: mixing user-safe support guidance with raw internal debug content; only sanitized payloads may be displayed in support-facing UI.
- Scope boundary: no new cloud path, no network escalation, no external support API; all support steps remain local and actionable in-app.
- UX continuity requirement: support interactions (view/copy/retry initiation) must remain non-blocking and compatible with existing presenter/view/worker signal flows.

### Technical Requirements

- Preserve normalized failure contracts end-to-end in support views:
  - service envelope: `{ok, data, error}`
  - error envelope: `{code, message, details, retryable}`
- Ensure support detail panels expose the normalized fields explicitly and deterministically for each failure context:
  - `code`
  - `message` (or stable summary)
  - `details` (sanitized for safe user display)
  - `retryable`
- Add category-driven remediation routing that maps to acceptance categories:
  - extraction
  - chunking
  - engine/tts
  - export/postprocess
  - persistence
- Enforce retry behavior rules:
  - if `retryable=true`, present retry action + clear prerequisites
  - if `retryable=false`, present alternative local actions (re-import, model repair/check, settings correction)
- Add support-workflow interaction observability with `stage=support_workflow` and `domain.action` event naming for viewed/copied/retry-initiated paths.
- Keep guidance text local-only and English-only in MVP, with no references to cloud uploads, remote incident tickets, or external APIs.

### Architecture Compliance

- Respect established layer boundaries from architecture artifacts:
  - presenter owns mapping/decision logic ([`conversion_presenter.py`](src/ui/presenters/conversion_presenter.py))
  - view owns rendering and interaction wiring ([`conversion_view.py`](src/ui/views/conversion_view.py))
  - logger/schema contracts remain in infrastructure logging components ([`event_schema.py`](src/infrastructure/logging/event_schema.py), [`jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py))
- Preserve deterministic error and state contracts already used across Epic 5 stories; avoid introducing alternate support-only payload shapes.
- Keep failure-category routing in presenter-level orchestration and do not shift support policy into low-level adapters.
- Maintain non-blocking UI behavior (NFR1) and avoid synchronous operations in UI-thread paths for support actions.
- Preserve strict offline/privacy boundary (NFR7, NFR9): support workflow must not call any remote endpoint or telemetry sink.
- Reuse existing observability patterns (`domain.action`, correlation continuity) to avoid regressions with Story 5.2 and Story 5.3 instrumentation.

### Library / Framework Requirements

- Reuse existing project stack; no additional third-party dependency is required for Story 5.4 implementation.
- Keep support workflow integration within current PyQt presentation boundaries and existing presenter interfaces.
- Continue using existing logging contracts and adapters rather than adding a parallel support logger implementation.
- Maintain compatibility with current normalized error/result contracts already enforced across services and UI layers.
- Prefer extension of existing diagnostics view models and widgets over introducing duplicate support-only rendering primitives.

### Project Structure Notes

- Primary implementation touchpoints for this story:
  - [`src/ui/presenters/conversion_presenter.py`](src/ui/presenters/conversion_presenter.py)
  - [`src/ui/views/conversion_view.py`](src/ui/views/conversion_view.py)
  - [`src/infrastructure/logging/event_schema.py`](src/infrastructure/logging/event_schema.py) (only if schema extension is required)
  - [`src/infrastructure/logging/jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py) (reuse existing logger path)
- Expected test touchpoints:
  - [`tests/unit/test_conversion_presenter.py`](tests/unit/test_conversion_presenter.py)
  - [`tests/unit/test_conversion_view.py`](tests/unit/test_conversion_view.py)
  - [`tests/integration/test_conversion_configuration_integration.py`](tests/integration/test_conversion_configuration_integration.py) or a dedicated support-workflow integration test file
- Structure rule: keep support-workflow behavior as an extension of existing diagnostics flow, not a parallel subsystem.
- Naming/contract rule: preserve `snake_case` payload fields and `domain.action` event names to stay consistent with established Epic 5 implementations.

### Testing Requirements

- Unit tests (presenter):
  - validate deterministic support guidance mapping by failure category (`extraction`, `chunking`, `tts/engine`, `postprocess/export`, `persistence`)
  - validate retryability-driven branching (`retryable=true` vs `retryable=false`) and prerequisite text presence
  - validate normalized field availability in support payload (`code`, `message`/summary, `details`, `retryable`)
  - validate sanitized detail filtering remains enforced for support-view rendering paths
- Unit tests (view):
  - verify support panel visibility and deterministic ordering of remediation actions
  - verify copy and retry interaction wiring without UI-thread blocking side effects
  - verify non-retryable alternatives render correctly and remain local-only in wording
- Integration tests:
  - simulate conversion failures across category variants and assert support workflow model correctness
  - assert support interaction events (`support_workflow.viewed`, `support_workflow.copied`, `support_workflow.retry_initiated`) include required correlation and severity fields
  - confirm no network-oriented behavior is introduced in support workflow paths

### Previous Story Intelligence

- Story 5.3 already introduced actionable diagnostics rendering, safe detail sanitization, and diagnostics-level event logging.
- Reuse existing failure mapping paths in [`ConversionPresenter.map_conversion_error()`](src/ui/presenters/conversion_presenter.py:357) rather than creating a second independent support mapper.
- Preserve deterministic remediation generation style from Story 5.3, then extend it with support-workflow specific actions (view/copy/retry guidance).
- Keep recursive unsafe-detail filtering behavior intact to avoid regressions that could surface tracebacks/internal internals in support UI.
- Maintain compatibility with the existing diagnostics panel model in [`conversion_view.py`](src/ui/views/conversion_view.py) and extend it incrementally.

### References

- Epic/story source: [Source: `epics.md` Epic 5 / Story 5.4](_bmad-output/planning-artifacts/epics.md)
- Product requirements and NFR boundaries: [Source: `prd.md` FR29/FR30, NFR1/NFR7/NFR9](_bmad-output/planning-artifacts/prd.md)
- Architecture constraints and layering rules: [Source: `architecture.md` Project Structure & Boundaries](_bmad-output/planning-artifacts/architecture.md)
- Sprint tracker status source: [Source: `sprint-status.yaml` development_status](_bmad-output/implementation-artifacts/sprint-status.yaml)
- Prior diagnostics baseline: [Source: Story 5.3 implementation artifact](_bmad-output/implementation-artifacts/5-3-present-actionable-failure-diagnostics-in-conversion-ui.md)

### Git Intelligence Summary

- Recent history confirms progression from Story 5.2 to Story 5.3 with direct edits in presenter/view/tests and sprint tracking:
  - `93fadf0` code-review fixes for Story 5.3 (presenter/view/tests + sprint status)
  - `a995133` diagnostics panel + observability integration for Story 5.3
  - `2121731` creation of Story 5.3 context artifact
- Implementation implication: Story 5.4 should extend the same diagnostics pathways and naming conventions, not introduce a divergent support architecture.

### Latest Tech Information

- Current ecosystem checks indicate no forced upgrade for this story scope:
  - `PyQt5` latest: `5.15.11`
  - `PyYAML` latest: `6.0.3`
  - `EbookLib` installed/latest: `0.20`
  - `PyPDF2` installed/latest: `3.0.1`
- Recommendation: maintain current dependency set and focus Story 5.4 on support workflow behavior and contract consistency.

### Project Context Reference

- `project-context.md` discovery pattern (`**/project-context.md`) returned no match in the repository.
- Context used for this story creation:
  - [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md)
  - [`_bmad-output/planning-artifacts/prd.md`](_bmad-output/planning-artifacts/prd.md)
  - [`_bmad-output/planning-artifacts/architecture.md`](_bmad-output/planning-artifacts/architecture.md)
  - [`_bmad-output/implementation-artifacts/sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml)
  - [`_bmad-output/implementation-artifacts/5-3-present-actionable-failure-diagnostics-in-conversion-ui.md`](_bmad-output/implementation-artifacts/5-3-present-actionable-failure-diagnostics-in-conversion-ui.md)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `python -m unittest -q tests.unit.test_conversion_presenter tests.unit.test_conversion_view tests.integration.test_conversion_configuration_integration`
- `PYTHONPATH=src python -m unittest discover -q`

### Implementation Plan

- Extend [`ConversionPresenter.map_conversion_error()`](src/ui/presenters/conversion_presenter.py:357) with deterministic support-workflow payload generation based on normalized error fields and stage/category mapping.
- Extend [`ConversionView._on_conversion_error()`](src/ui/views/conversion_view.py:177) diagnostics state with support details, retry prerequisites, and deterministic non-retryable alternatives.
- Add support interaction methods in [`ConversionView.open_support_details()`](src/ui/views/conversion_view.py:247), [`ConversionView.copy_support_details()`](src/ui/views/conversion_view.py:261), and [`ConversionView.request_retry()`](src/ui/views/conversion_view.py:242) to emit non-blocking support events.
- Validate via updated unit/integration tests and full regression execution with `PYTHONPATH=src`.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story 5.4 selected from sprint tracker as next backlog item in Epic 5.
- Story document expanded with deterministic support-workflow guardrails for error category guidance, retry prerequisites, local-only remediation, and event traceability.
- Context continuity integrated from Story 5.3 diagnostics implementation and recent Git patterns.
- Implemented support-workflow mapping in presenter with deterministic category routing (`extraction`, `chunking`, `engine_tts`, `export_postprocess`, `persistence`) and normalized support payload fields (`code`, `message`, `details`, `retryable`).
- Extended conversion diagnostics state with support details, retry prerequisites, and deterministic non-retryable alternatives.
- Added support-workflow interaction methods for view/copy/retry and emitted `support_workflow.viewed`, `support_workflow.copied`, and `support_workflow.retry_initiated` events with non-blocking logger failure handling.
- Added and updated unit/integration tests covering category mapping, retry prerequisites, local-only alternatives, and support workflow event schema contracts.
- Validation completed successfully with targeted and full-suite runs under local environment (`PYTHONPATH=src`).
- **Code review completed (2026-02-15):** Fixed 7 issues (3 CRITICAL, 4 MEDIUM) including AC documentation typo, missing test coverage for persistence category, fallback guidance testing, duplication of correlation context extraction, exception handling validation, nested sanitization verification, and added inline documentation for support workflow logic.

### File List

- _bmad-output/implementation-artifacts/5-4-provide-local-support-workflow-for-error-review-and-guided-remediation.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/ui/presenters/conversion_presenter.py
- src/ui/views/conversion_view.py
- tests/unit/test_conversion_presenter.py
- tests/unit/test_conversion_view.py
- tests/integration/test_conversion_configuration_integration.py

### Change Log

- 2026-02-15: Implemented Story 5.4 local support workflow mapping, support-panel behaviors, traceable `support_workflow.*` events, and comprehensive unit/integration coverage.
- 2026-02-15: Code review fixes applied - corrected AC1 documentation, added 3 missing unit tests (persistence category, fallback guidance, sanitization verification), refactored correlation context extraction to eliminate duplication, added 2 exception handling tests, and enhanced inline documentation for support workflow logic.

## Story Completion Status

- Story ID: `5.4`
- Story Key: `5-4-provide-local-support-workflow-for-error-review-and-guided-remediation`
- Status set to: `done`
- Completion note: Support-workflow remediation mapping, UI interaction logging, and automated coverage are implemented, validated, and code-reviewed with all critical and medium issues resolved.
