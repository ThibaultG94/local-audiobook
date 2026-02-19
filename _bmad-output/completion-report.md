# BMAD V6 Completion Report — local-audiobook

Date: 2026-02-19T15:57:00+01:00

## 1) Executive Summary

This report closes BMAD delivery with a factual, file-traceable summary across Epics 1–6.

- All Epics 1–6 are marked `done` in sprint tracking ([`development_status`](_bmad-output/implementation-artifacts/sprint-status.yaml:42), [`epic-6`](_bmad-output/implementation-artifacts/sprint-status.yaml:81)). Two post-delivery hotfixes were applied on 2026-02-19 to fix runtime pipeline failures discovered through real end-to-end tests.
- Delivered product scope is a local-first desktop pipeline: import → extraction → chunking/orchestration → TTS synthesis → audio assembly → local library/playback ([`README.md`](README.md:51), [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:443)).
- MVP boundaries remain explicit: Linux Mint target, offline-first after model bootstrap, no cloud runtime dependency ([`README.md`](README.md:16), [`README.md`](README.md:71), [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:170)).

## 2) Epic-by-Epic Delivery Traceability (Epics 1–6)

| Epic                                        | Scope delivered                                                                                                    | Story evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Sprint evidence                                                                                                                                                                                           |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Epic 1 — Local Setup & Offline Readiness    | Startup/bootstrap foundation, model readiness checks, readiness surfaced in UI                                     | [`1-1-initialize-local-application-foundation-and-persistent-job-store.md`](_bmad-output/implementation-artifacts/1-1-initialize-local-application-foundation-and-persistent-job-store.md), [`1-2-validate-model-assets-and-engine-health-at-startup.md`](_bmad-output/implementation-artifacts/1-2-validate-model-assets-and-engine-health-at-startup.md), [`1-3-surface-offline-readiness-status-and-actionable-remediation-in-ui.md`](_bmad-output/implementation-artifacts/1-3-surface-offline-readiness-status-and-actionable-remediation-in-ui.md)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | [`epic-1: done`](_bmad-output/implementation-artifacts/sprint-status.yaml:43)                                                                                                                             |
| Epic 2 — Multi-Format Import & Extraction   | Import/validation and extraction flows for EPUB/PDF/TXT/MD plus unified extraction diagnostics                     | [`2-1-import-local-multi-format-documents-with-input-validation.md`](_bmad-output/implementation-artifacts/2-1-import-local-multi-format-documents-with-input-validation.md), [`2-2-extract-clean-text-from-epub-with-actionable-failure-handling.md`](_bmad-output/implementation-artifacts/2-2-extract-clean-text-from-epub-with-actionable-failure-handling.md), [`2-3-extract-text-from-pdf-with-degraded-case-handling.md`](_bmad-output/implementation-artifacts/2-3-extract-text-from-pdf-with-degraded-case-handling.md), [`2-4-extract-and-normalize-txt-and-markdown-inputs.md`](_bmad-output/implementation-artifacts/2-4-extract-and-normalize-txt-and-markdown-inputs.md), [`2-5-provide-unified-extraction-error-feedback-and-diagnostics.md`](_bmad-output/implementation-artifacts/2-5-provide-unified-extraction-error-feedback-and-diagnostics.md)                                                                                                                                                                                                                                       | [`epic-2: done`](_bmad-output/implementation-artifacts/sprint-status.yaml:49)                                                                                                                             |
| Epic 3 — Resilient Conversion               | Unified provider contract, deterministic orchestration/fallback, persistence/resume, conversion worker threading   | [`3-1-implement-unified-tts-provider-contract-and-engine-adapters.md`](_bmad-output/implementation-artifacts/3-1-implement-unified-tts-provider-contract-and-engine-adapters.md), [`3-2-segment-long-text-with-phrase-first-chunking-rules.md`](_bmad-output/implementation-artifacts/3-2-segment-long-text-with-phrase-first-chunking-rules.md), [`3-3-orchestrate-deterministic-conversion-with-engine-fallback.md`](_bmad-output/implementation-artifacts/3-3-orchestrate-deterministic-conversion-with-engine-fallback.md), [`3-4-persist-job-lifecycle-and-resume-conversion-from-last-failed-chunk.md`](_bmad-output/implementation-artifacts/3-4-persist-job-lifecycle-and-resume-conversion-from-last-failed-chunk.md), [`3-5-configure-conversion-parameters-and-output-format-in-ui.md`](_bmad-output/implementation-artifacts/3-5-configure-conversion-parameters-and-output-format-in-ui.md), [`3-6-execute-conversion-in-dedicated-worker-with-non-blocking-ui-signals.md`](_bmad-output/implementation-artifacts/3-6-execute-conversion-in-dedicated-worker-with-non-blocking-ui-signals.md) | [`epic-3: done`](_bmad-output/implementation-artifacts/sprint-status.yaml:57)                                                                                                                             |
| Epic 4 — Library & Playback                 | Final audio assembly, persistence of library metadata/artifacts, browse/reopen, integrated playback controls       | [`4-1-assemble-synthesized-chunks-into-final-audio-output.md`](_bmad-output/implementation-artifacts/4-1-assemble-synthesized-chunks-into-final-audio-output.md), [`4-2-persist-final-audio-artifacts-and-library-metadata.md`](_bmad-output/implementation-artifacts/4-2-persist-final-audio-artifacts-and-library-metadata.md), [`4-3-browse-and-reopen-audiobooks-from-local-library-view.md`](_bmad-output/implementation-artifacts/4-3-browse-and-reopen-audiobooks-from-local-library-view.md), [`4-4-integrate-local-audio-playback-service-and-adapter.md`](_bmad-output/implementation-artifacts/4-4-integrate-local-audio-playback-service-and-adapter.md), [`4-5-provide-playback-controls-with-pause-resume-seek-and-progress.md`](_bmad-output/implementation-artifacts/4-5-provide-playback-controls-with-pause-resume-seek-and-progress.md)                                                                                                                                                                                                                                                 | [`epic-4: done`](_bmad-output/implementation-artifacts/sprint-status.yaml:66)                                                                                                                             |
| Epic 5 — Diagnostics & Failure Transparency | Correlated JSONL schema + instrumentation and user-facing diagnostics/support workflow                             | [`5-1-define-correlated-jsonl-event-schema-and-logging-contract.md`](_bmad-output/implementation-artifacts/5-1-define-correlated-jsonl-event-schema-and-logging-contract.md), [`5-2-instrument-end-to-end-pipeline-with-correlation-context.md`](_bmad-output/implementation-artifacts/5-2-instrument-end-to-end-pipeline-with-correlation-context.md), [`5-3-present-actionable-failure-diagnostics-in-conversion-ui.md`](_bmad-output/implementation-artifacts/5-3-present-actionable-failure-diagnostics-in-conversion-ui.md), [`5-4-provide-local-support-workflow-for-error-review-and-guided-remediation.md`](_bmad-output/implementation-artifacts/5-4-provide-local-support-workflow-for-error-review-and-guided-remediation.md)                                                                                                                                                                                                                                                                                                                                                                   | [`epic-5: done`](_bmad-output/implementation-artifacts/sprint-status.yaml:74)                                                                                                                             |
| Epic 6 — Runtime Fixes & Polish             | Runtime crash hardening, degraded readiness mode, library polish, documentation refresh, BMAD completion reporting | [`6-1-debug-and-fix-conversion-pipeline-runtime-failure.md`](_bmad-output/implementation-artifacts/6-1-debug-and-fix-conversion-pipeline-runtime-failure.md), [`6-2-implement-degraded-readiness-mode.md`](_bmad-output/implementation-artifacts/6-2-implement-degraded-readiness-mode.md), [`6-3-complete-library-view-with-select-and-delete-actions.md`](_bmad-output/implementation-artifacts/6-3-complete-library-view-with-select-and-delete-actions.md), [`6-4-update-project-documentation-for-current-stack.md`](_bmad-output/implementation-artifacts/6-4-update-project-documentation-for-current-stack.md)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | [`epic-6: done`](_bmad-output/implementation-artifacts/sprint-status.yaml:81)                                                                                                                             |
| Hotfix 2026-02-19 — Pipeline Runtime Bugs   | SQLite FK ordering fix, engine-specific routing in orchestration, real e2e test suite (Kokoro CPU)                 | [`hotfix-conversion-pipeline-2026-02-19.md`](_bmad-output/implementation-artifacts/hotfix-conversion-pipeline-2026-02-19.md), [`hotfix-engine-routing-2026-02-19.md`](_bmad-output/implementation-artifacts/hotfix-engine-routing-2026-02-19.md)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | [`hotfix-1-sqlite-fk-ordering: done`](_bmad-output/implementation-artifacts/sprint-status.yaml:90), [`hotfix-2-engine-routing-bypass: done`](_bmad-output/implementation-artifacts/sprint-status.yaml:91) |

### Scope boundaries kept explicit

- MVP FR coverage maps to Epics 1–5 plus hardening Epic 6 ([`epics.md`](_bmad-output/planning-artifacts/epics.md:129), [`epics.md`](_bmad-output/planning-artifacts/epics.md:156)).
- Out-of-scope post-MVP items remain separated (FR31–FR35) ([`epics.md`](_bmad-output/planning-artifacts/epics.md:127)).

## 3) Architecture Decisions and Justifications

### A. Layered boundaries (UI / app / domain / adapters / infrastructure)

**Decision:** Keep strict separation to preserve maintainability and reduce coupling.

**Justification:** Architecture requires explicit boundaries and maps FRs to module layers ([`architecture.md`](_bmad-output/planning-artifacts/architecture.md:313), [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:426)). This decision was driven by:

- **Maintainability requirement:** NFR13 mandates modular architecture separating extraction/orchestration/TTS/post-processing/library ([`epics.md`](_bmad-output/planning-artifacts/epics.md:72)).
- **AI agent conflict reduction:** Explicit boundaries prevent concurrent modification conflicts during parallel story implementation.
- **Testability:** Layer isolation enables unit testing of domain logic without UI/infrastructure dependencies.
- **Alternative considered:** Monolithic structure was rejected due to complexity of long-running conversion orchestration and need for independent adapter evolution.

**Implementation evidence:** top-level layer folders and container wiring are present ([`src/`](src), [`build_container()`](src/app/dependency_container.py:178), [`README.md`](README.md:42)).

### B. SQLite as local source of truth + migration discipline

**Decision:** Persist jobs/chunks/library/diagnostics in local SQLite, with incremental SQL migrations.

**Justification:** This supports offline-first reliability and deterministic recovery semantics ([`epics.md`](_bmad-output/planning-artifacts/epics.md:81), [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:141)). This decision was driven by:

- **Offline-first constraint:** NFR9 requires complete offline operation after model bootstrap; SQLite provides zero-network-dependency persistence ([`epics.md`](_bmad-output/planning-artifacts/epics.md:68)).
- **Resume/recovery requirement:** NFR4 mandates controlled resume on chunk failure with state preservation; transactional SQLite writes enable atomic state updates ([`epics.md`](_bmad-output/planning-artifacts/epics.md:63)).
- **Simplicity for MVP:** Single-user desktop target eliminates need for client-server database; SQLite reduces deployment complexity.
- **Alternatives considered:** JSON file storage was rejected due to lack of transactional guarantees and query capabilities; PostgreSQL/MySQL were rejected as over-engineered for local-only single-user MVP.

**Implementation evidence:** migration scripts and SQLite repositories exist ([`0001_initial_schema.sql`](migrations/0001_initial_schema.sql), [`0002_add_source_format_to_documents.sql`](migrations/0002_add_source_format_to_documents.sql), [`0003_extend_library_items_metadata.sql`](migrations/0003_extend_library_items_metadata.sql), [`migration_runner.py`](src/adapters/persistence/sqlite/migration_runner.py), [`repositories/`](src/adapters/persistence/sqlite/repositories)).

### C. Deterministic orchestration and fallback policy ownership

**Decision:** Keep fallback policy in orchestration service, not providers.

**Justification:** This was explicitly defined to ensure deterministic behavior and traceability for failures/resume ([`epics.md`](_bmad-output/planning-artifacts/epics.md:84), [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:127)). This decision was driven by:

- **Deterministic fallback requirement:** FR13 requires predictable engine switching on primary failure; centralizing policy in orchestration ensures single decision point ([`epics.md`](_bmad-output/planning-artifacts/epics.md:108)).
- **Provider contract simplicity:** Keeping providers stateless and policy-free enables independent adapter evolution and testing.
- **Observability:** Centralized fallback decisions enable correlated logging of engine transitions at orchestration level.
- **Alternative considered:** Provider-level fallback was rejected because it would distribute policy logic across adapters, making behavior harder to trace and test.

**Implementation evidence:** orchestration service is composed with primary+fallback providers in app wiring ([`TtsOrchestrationService`](src/domain/services/tts_orchestration_service.py), [`build_container()`](src/app/dependency_container.py:214), [`ChatterboxProvider`](src/adapters/tts/chatterbox_provider.py:13), [`KokoroProvider`](src/adapters/tts/kokoro_provider.py:14)).

### D. Local JSONL observability with correlation

**Decision:** use structured JSONL events with correlation metadata.

**Justification:** observability and diagnostics are explicit MVP requirements (FR29/FR30 + NFR observability) ([`epics.md`](_bmad-output/planning-artifacts/epics.md:124), [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:174)). This decision was driven by:

- **Diagnostic requirement:** FR30 requires actionable diagnostics for failed conversions; structured logs enable programmatic error analysis ([`epics.md`](_bmad-output/planning-artifacts/epics.md:125)).
- **End-to-end traceability:** NFR14 mandates correlatable logs by document/pipeline stage; JSONL with correlation_id enables cross-stage event linking ([`epics.md`](_bmad-output/planning-artifacts/epics.md:73)).
- **Local-only constraint:** NFR7 prohibits cloud transmission; local JSONL files provide zero-network observability ([`epics.md`](_bmad-output/planning-artifacts/epics.md:66)).
- **Alternatives considered:** Plain text logs were rejected due to lack of structure for programmatic parsing; cloud logging services were rejected due to offline-first constraint; binary formats were rejected for lack of human readability.

**Implementation evidence:** event schema and logger implementation are present ([`event_schema.py`](src/infrastructure/logging/event_schema.py), [`jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py), [`5-1-define-correlated-jsonl-event-schema-and-logging-contract.md`](_bmad-output/implementation-artifacts/5-1-define-correlated-jsonl-event-schema-and-logging-contract.md)).

## 4) Quality & Test Coverage Summary

### Test structure evidence

- Test framework is configured through pytest in project metadata ([`tool.pytest.ini_options`](pyproject.toml:28)).
- Test suite is split into three directories: unit, integration, and e2e ([`tests/unit`](tests/unit), [`tests/integration`](tests/integration), [`tests/e2e`](tests/e2e)).

### Current repository inventory (traceable)

- Unit test modules detected: **32**
- Integration test modules detected: **12**
- E2E test modules detected: **2** (added 2026-02-19)
- Total `test_*.py` modules detected: **46**

These counts were produced from repository state inspection of [`tests/unit`](tests/unit), [`tests/integration`](tests/integration), and [`tests/e2e`](tests/e2e).

### E2E test suite (added 2026-02-19)

Two end-to-end test modules were added to catch cross-layer wiring bugs that unit/integration tests with mocked providers cannot detect:

| Module                                                                         | Provider                                       | Tests | Scope                                    |
| ------------------------------------------------------------------------------ | ---------------------------------------------- | ----- | ---------------------------------------- |
| [`test_conversion_pipeline_e2e.py`](tests/e2e/test_conversion_pipeline_e2e.py) | `StubTtsProvider` (inherits `BaseTtsProvider`) | 17    | FK regression, ordering, TXT/MD pipeline |
| [`test_real_pipeline.py`](tests/e2e/test_real_pipeline.py)                     | Real Kokoro CPU                                | 3     | FR TXT→MP3, EN TXT→WAV, FR MD→MP3        |

Test fixtures: [`tests/e2e/fixtures/`](tests/e2e/fixtures) (sample_short.txt, sample_medium.txt, sample.md).

### Execution posture

- All 314 tests pass when run with `python -m pytest` in the project environment.
- Real e2e tests require Kokoro model assets to be present (see [`INSTALLATION.md`](INSTALLATION.md:1)).
- `scope="module"` fixtures are used for expensive `bootstrap()` calls to keep suite runtime acceptable.

## 5) Known Issues, Constraints, and Future Work

### Known constraints (current)

1. **MVP platform boundary remains Linux Mint-focused**
   - Cross-platform desktop support is intentionally post-MVP ([`README.md`](README.md:16), [`epics.md`](_bmad-output/planning-artifacts/epics.md:127)).

2. **No cloud runtime dependency by design**
   - This remains a deliberate constraint, not a defect ([`README.md`](README.md:12), [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:152)).

3. **Real e2e tests require Kokoro model assets**
   - `test_real_pipeline.py` is skipped automatically if Kokoro is unavailable; stub-provider e2e tests run without model assets.

### Future work (post-MVP backlog)

The following remain explicitly out of MVP scope and should be treated as future increments:

- Batch conversion jobs (FR31)
- Advanced library search and filters (FR32)
- Advanced expressivity controls (FR33)
- Voice cloning (FR34)
- Additional OS targets (FR35)

Source of truth: [`epics.md`](_bmad-output/planning-artifacts/epics.md:127).

### Process lessons from retrospectives

Key insights from Epic 1, Epic 3 retrospectives, and post-delivery hotfixes inform future iterations:

- **Epic 1 retrospective findings** ([`epic-1-retro-2026-02-14.md`](_bmad-output/implementation-artifacts/epic-1-retro-2026-02-14.md)):
  - Story creation workflow benefits from explicit architecture/PRD references in Dev Notes.
  - Migration discipline established early prevents schema drift in later epics.
  - Readiness checks at startup reduce runtime surprises during conversion.

- **Epic 3 retrospective findings** ([`epic-3-retro-2026-02-14.md`](_bmad-output/implementation-artifacts/epic-3-retro-2026-02-14.md)):
  - Artifact closure consistency requires explicit reconciliation between story status and sprint tracking.
  - Code review cycles benefit from upfront traceability requirements in story creation.
  - Deterministic fallback policy centralization proved correct under runtime testing.

- **Post-delivery hotfix findings** ([`hotfix-engine-routing-2026-02-19.md`](_bmad-output/implementation-artifacts/hotfix-engine-routing-2026-02-19.md)):
  - FK ordering must be enforced at the call site, not just the schema level.
  - Engine selection must be explicit: user-selected engine must bypass the primary→fallback chain.
  - Real e2e tests with `bootstrap()` are essential — unit/integration tests with mocked providers cannot catch cross-layer wiring bugs.
  - Test doubles must inherit from `BaseTtsProvider` to respect the `audio_bytes` payload contract.

## 6) Approvals

This completion report requires formal sign-off before project closure:

| Role          | Name                   | Date             | Signature              |
| ------------- | ---------------------- | ---------------- | ---------------------- |
| Product Owner | **\*\***\_\_\_**\*\*** | \***\*\_\_\*\*** | **\*\***\_\_\_**\*\*** |
| Tech Lead     | **\*\***\_\_\_**\*\*** | \***\*\_\_\*\*** | **\*\***\_\_\_**\*\*** |
| QA Lead       | **\*\***\_\_\_**\*\*** | \***\*\_\_\*\*** | **\*\***\_\_\_**\*\*** |

## 7) Final Closure Statement

This completion artifact now provides a single auditable narrative across Epics 1–6 plus post-delivery hotfixes, with explicit references to planning artifacts, implementation stories, architecture constraints, repository structure, and quality posture.

Primary closure references:

- Scope and epic intent: [`epics.md`](_bmad-output/planning-artifacts/epics.md:129)
- Architecture constraints and justifications: [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:111)
- Story-by-story delivery status: [`sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml:42)
- Current stack baseline docs: [`README.md`](README.md:3), [`INSTALLATION.md`](INSTALLATION.md:1), [`pyproject.toml`](pyproject.toml:5)
- Post-delivery hotfix reports: [`hotfix-conversion-pipeline-2026-02-19.md`](_bmad-output/implementation-artifacts/hotfix-conversion-pipeline-2026-02-19.md), [`hotfix-engine-routing-2026-02-19.md`](_bmad-output/implementation-artifacts/hotfix-engine-routing-2026-02-19.md)
