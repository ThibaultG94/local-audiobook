# Story 5.3: Present Actionable Failure Diagnostics in Conversion UI

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user facing a failed conversion,
I want clear diagnostics in the interface,
so that I can understand what failed and what to do next.

## Acceptance Criteria

1. **Given** orchestration returns normalized errors with `code`, `message`, `details`, `retryable`  
   **When** failure state is rendered by `conversion_presenter.py`  
   **Then** UI shows concise error summary plus expandable details  
   **And** remediation guidance is actionable and English-only.

2. **Given** failure can occur at extraction, chunking, tts, postprocess, or persistence stages  
   **When** diagnostics are displayed  
   **Then** stage and engine context are visible to user when available  
   **And** retry recommendation reflects actual `retryable` value.

3. **Given** a user requests deeper diagnostics from the failure panel  
   **When** details are opened  
   **Then** related `correlation_id` and job context are surfaced for local support troubleshooting  
   **And** no raw internal trace is shown unless marked safe for user display.

4. **Given** diagnostics display must be observable  
   **When** failure panel is shown or user triggers retry  
   **Then** JSONL events are emitted with `stage=diagnostics_ui` and `domain.action` naming  
   **And** payload includes `correlation_id`, `job_id`, `event`, `severity`, and UTC ISO-8601 `timestamp`.

## Tasks / Subtasks

- [x] Implement diagnostics presentation mapping in presenter (AC: 1, 2)
  - [x] Add conversion-failure → UI-view-model mapping in `conversion_presenter.py` for summary/details/remediation blocks
  - [x] Ensure English-only user-facing diagnostics strings and deterministic message templates
  - [x] Include safe stage/engine context enrichment when available without exposing unsafe trace data
- [x] Add expandable diagnostics panel rendering in conversion UI (AC: 1, 3)
  - [x] Add/extend widgets in `conversion_view.py` for concise summary + expandable details section
  - [x] Surface `correlation_id` and job context in details view for support workflows
  - [x] Gate raw internals behind safe-display checks; hide unvetted traceback content
- [x] Wire retryability-aware action guidance (AC: 2)
  - [x] Bind retry CTA enablement to normalized `retryable` value
  - [x] Render non-retryable alternatives (re-import, model check, settings correction)
  - [x] Keep presenter/view state transitions non-blocking and signal-safe
- [x] Emit diagnostics UI observability events (AC: 4)
  - [x] Emit `diagnostics_ui.panel_shown` (or equivalent `domain.action`) with required schema fields
  - [x] Emit retry-intent/retry-trigger events with same correlation context
  - [x] Ensure payloads pass strict schema validation and UTC timestamp requirements
- [x] Add and update tests (AC: 1, 2, 3, 4)
  - [x] Unit tests for presenter mapping and retryability-driven guidance in `tests/unit/test_conversion_presenter.py`
  - [x] Unit tests for conversion view diagnostics panel rendering and state transitions in `tests/unit/test_conversion_view.py`
  - [x] Integration tests for diagnostics display + retry flow and event emissions in `tests/integration/test_conversion_configuration_integration.py` (or dedicated diagnostics integration test)

## Dev Notes

### Developer Context Section

- Story selected automatically from sprint tracker as first backlog item: `5-3-present-actionable-failure-diagnostics-in-conversion-ui`.
- Prior work from Story 5.2 already hardened event propagation and correlation continuity across stages; Story 5.3 must focus on **UI diagnostics presentation quality** and **safe user-facing remediation**.
- Failure diagnostics must consume normalized error payloads (`code`, `message`, `details`, `retryable`) emitted by orchestration and lower-level services, without inventing new incompatible error shapes.
- Primary implementation risk: exposing raw internal traces to end users (security/usability regression). Presenter/view layer must sanitize diagnostics details and only display safe content.
- UX must remain non-blocking: diagnostics panel rendering and retry affordances must not interfere with worker signal flow.

### Technical Requirements

- Preserve normalized result/error contracts in UI handoff:
  - Service responses remain `{ok, data, error}`.
  - Errors remain `{code, message, details, retryable}`.
- Implement deterministic diagnostics mapping in presenter:
  - concise summary message
  - expandable details payload
  - remediation actions bound to failure class and `retryable` flag
  - stage/engine context when available.
- Expose `correlation_id` and job context in diagnostics details panel for local support workflows.
- Emit diagnostics observability events in JSONL:
  - panel shown
  - details expanded
  - retry requested / retry triggered
  - guidance action selected.
- Keep all event names compliant with `domain.action` and payload schema requirements.

### Architecture Compliance

- Respect layer boundaries:
  - `conversion_presenter.py` handles mapping and UI state orchestration.
  - `conversion_view.py` handles rendering and user interaction only.
  - logging schema authority remains in `event_schema.py` + `jsonl_logger.py`.
- Do not bypass existing domain services for retries; presenter should invoke established pathways.
- Do not introduce network telemetry or cloud dependencies in diagnostics workflows.
- Keep MVP language policy: user-facing diagnostics text in English.

### Library / Framework Requirements

- Reuse current stack; no new dependency required for this story.
- PyQt signal/slot behavior must remain unchanged in worker ↔ presenter ↔ view interactions.
- Keep JSONL logger usage append-only and resilient to validation/write failures.

### File Structure Requirements

- Primary files likely touched:
  - `src/ui/presenters/conversion_presenter.py`
  - `src/ui/views/conversion_view.py`
  - `src/ui/workers/conversion_worker.py` (only if signal payload enrichment is needed)
  - `src/infrastructure/logging/event_schema.py` (only if diagnostics event payload fields need explicit schema alignment)
- Test files likely touched:
  - `tests/unit/test_conversion_presenter.py`
  - `tests/unit/test_conversion_view.py`
  - `tests/integration/test_conversion_configuration_integration.py` (or new focused diagnostics integration test)

### Testing Requirements

- Unit:
  - presenter mapping of normalized failures to summary/details/remediation models
  - retryability-based CTA enable/disable logic
  - safe filtering of trace/internal details
- UI/view tests:
  - diagnostics panel visibility and expandable details state
  - deterministic rendering for stage/engine/correlation fields
- Integration:
  - simulate failure path and verify diagnostics UI output
  - verify emitted diagnostics JSONL events and schema compliance
  - verify retry flow behavior for retryable vs non-retryable errors

### Previous Story Intelligence

- Story 5.2 established strong correlation propagation and normalized failure event envelopes; leverage those existing payloads directly.
- Avoid refactoring logging internals again; focus on presenter/view consumption and user-facing clarity.
- Keep consistency with recent player/library/worker event naming conventions introduced in latest commits.

### Git Intelligence Summary

- Recent commits indicate Epic 5 progression and relevant UI/logging touchpoints:
  - `9c2d8d5` — Story 5.2 code review fixes (correlation propagation + event coverage)
  - `acb9a31` — Story 5.2 implementation alignment
  - `886e207` — Story 5.2 story context creation
  - `0193235` / `9ddf32b` — Story 5.1 logger/schema hardening.
- Implication: Story 5.3 should be additive in UI diagnostics surfaces with low-risk changes to established contracts.

### Latest Tech Information

- Dependency checks from project environment:
  - PyQt5 latest: `5.15.11`
  - PyYAML latest: `6.0.3`
  - EbookLib installed/latest: `0.20`
  - PyPDF2 installed/latest: `3.0.1`
- No upgrade required to deliver Story 5.3 scope.

### Project Context Reference

- No `project-context.md` found for pattern `**/project-context.md`.
- Context sources used:
  - `_bmad-output/planning-artifacts/epics.md`
  - `_bmad-output/planning-artifacts/prd.md`
  - `_bmad-output/planning-artifacts/architecture.md`
  - `_bmad-output/implementation-artifacts/sprint-status.yaml`
  - `_bmad-output/implementation-artifacts/5-2-instrument-end-to-end-pipeline-with-correlation-context.md`

### Project Structure Notes

- Keep implementation aligned with current repository structure and existing conversion UI architecture.
- Prefer extending existing diagnostics widgets/state models over introducing parallel UI components.
- Preserve strict separation between display logic (view) and decision logic (presenter).

### References

- Epic/story source: `_bmad-output/planning-artifacts/epics.md`
- Product requirements: `_bmad-output/planning-artifacts/prd.md`
- Architecture constraints: `_bmad-output/planning-artifacts/architecture.md`
- Sprint tracker: `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Previous story: `_bmad-output/implementation-artifacts/5-2-instrument-end-to-end-pipeline-with-correlation-context.md`
- Logging contracts:
  - `src/infrastructure/logging/event_schema.py`
  - `src/infrastructure/logging/jsonl_logger.py`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log -n 5 --date=iso --pretty=format:'%h|%ad|%an|%s' --name-status`
- `python -m pip index versions PyQt5`
- `python -m pip index versions PyYAML`
- `python -m pip index versions EbookLib`
- `python -m pip index versions PyPDF2`
- `PYTHONPATH=src python -m unittest tests.unit.test_conversion_presenter tests.unit.test_conversion_view tests.integration.test_conversion_configuration_integration`
- `PYTHONPATH=src python -m unittest discover -s tests`

### Completion Notes List

- Story 5.3 selected from sprint tracker as next backlog story in Epic 5.
- Comprehensive implementation context prepared for diagnostics UI mapping, safe detail rendering, retryability guidance, and observability events.
- Architecture and project-structure guardrails included to prevent regressions and ensure compatibility with established logging and service boundaries.
- Ultimate context engine analysis completed - comprehensive developer guide created.
- Added deterministic conversion failure diagnostics mapping in presenter with stage/engine inference, retryability guidance, correlation/job context surfacing, and safe internal-detail filtering.
- Extended conversion view state with an actionable diagnostics panel model (summary/details/remediation, expandable details state, retry CTA state) and non-blocking transitions.
- Added diagnostics UI observability emissions (`diagnostics_ui.panel_shown`, `diagnostics_ui.details_toggled`, `diagnostics_ui.retry_requested`) with required correlation context.
- Added/updated unit and integration coverage for diagnostics payload mapping, safe detail handling, UI panel behavior, retry flow events, and schema compliance.
- Restored extraction correlation-id validation contract in import service to keep full regression suite green.
- **Code review completed with 10 issues found and fixed:**
  - Fixed import paths in test_conversion_view.py (src. prefix)
  - Corrected extraction diagnostics stage to "diagnostics_ui" for consistency
  - Added retry-aware remediation messages for extraction errors
  - Implemented recursive sanitization for nested unsafe details
  - Removed duplicate message/summary field in error payload
  - Added diagnostics panel clearing on successful conversion completion
  - Propagated correlation_id in progress events
  - Added stderr fallback for failed diagnostics event emissions
  - Added integration test for extraction diagnostics events
  - Added unit test for recursive detail sanitization and panel clearing

### File List

- _bmad-output/implementation-artifacts/5-3-present-actionable-failure-diagnostics-in-conversion-ui.md
- src/ui/presenters/conversion_presenter.py
- src/ui/views/conversion_view.py
- src/domain/services/import_service.py
- tests/unit/test_conversion_presenter.py
- tests/unit/test_conversion_view.py
- tests/integration/test_conversion_configuration_integration.py
- _bmad-output/implementation-artifacts/sprint-status.yaml

## Change Log

- 2026-02-15: Story context created and marked ready-for-dev with exhaustive epic/architecture/git and dependency context.
- 2026-02-15: Implemented Story 5.3 diagnostics UI mapping/panel/events, added tests, ran full regression suite, and moved status to review.
- 2026-02-15: Code review completed - fixed 8 HIGH and 2 MEDIUM issues, all tests passing, moved status to done.

## Story Completion Status

- Story ID: `5.3`
- Story Key: `5-3-present-actionable-failure-diagnostics-in-conversion-ui`
- Status set to: `review`
- Completion note: Implemented actionable failure diagnostics UI and observability with passing regression suite.
