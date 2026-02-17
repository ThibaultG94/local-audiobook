# BMAD V6 Completion Report — Local Audiobook

Date: 2026-02-17

## 1) Executive Summary

The project delivered a local-first desktop audiobook conversion pipeline with five completed epics and 23 completed stories, including retrospective closure for each epic ([`sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml:42), [`epics.md`](_bmad-output/planning-artifacts/epics.md:134)).

At product level, the implemented flow is: import → extraction → chunking/orchestration → TTS synthesis → audio assembly → local library persistence ([`README.md`](/README.md:43), [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:443)).

Current stack in repository:

- Python desktop app with PyQt5 UI ([`pyproject.toml`](/pyproject.toml:10), [`pyproject.toml`](/pyproject.toml:15))
- Local persistence with SQLite migrations ([`0001_initial_schema.sql`](migrations/0001_initial_schema.sql), [`migration_runner.py`](src/adapters/persistence/sqlite/migration_runner.py))
- Extraction adapters for EPUB/PDF/TXT/MD ([`epub_extractor.py`](src/adapters/extraction/epub_extractor.py), [`pdf_extractor.py`](src/adapters/extraction/pdf_extractor.py:15), [`text_extractor.py`](src/adapters/extraction/text_extractor.py))
- Dual TTS engines through adapters: Chatterbox + Kokoro ([`chatterbox_provider.py`](src/adapters/tts/chatterbox_provider.py:22), [`kokoro_provider.py`](src/adapters/tts/kokoro_provider.py:34))
- Structured JSONL observability ([`jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py:31), [`event_schema.py`](src/infrastructure/logging/event_schema.py:10))

Status at BMAD closure: all epic/story items and retrospectives marked done ([`sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml:43), [`sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml:79)).

## 2) Architecture

### Architectural style

The implementation follows hexagonal / ports-and-adapters boundaries:

- Domain ports define contracts (for example [`TtsProvider`](src/domain/ports/tts_provider.py:43))
- Adapters implement infrastructure/provider details (for example [`ChatterboxProvider`](src/adapters/tts/chatterbox_provider.py:22), [`KokoroProvider`](src/adapters/tts/kokoro_provider.py:34))
- App layer wires dependencies centrally ([`build_container()`](src/app/dependency_container.py:146))
- UI layer consumes services/presenters/workers ([`ConversionView`](src/ui/views/conversion_view.py:38), [`MainWindow`](src/ui/main_window.py:15))

This matches both architecture planning and repository-level summary ([`architecture.md`](_bmad-output/planning-artifacts/architecture.md:313), [`README.md`](/README.md:36)).

### Result monad contract

Service and adapter flows use a normalized `Result` envelope `{ok, data, error}` ([`Result`](src/contracts/result.py:14), [`failure()`](src/contracts/result.py:33)).

This contract is used to avoid uncontrolled exception-driven propagation and to keep deterministic error payloads (`code`, `message`, `details`, `retryable`) through layers ([`errors.py`](src/contracts/errors.py), [`epics.md`](_bmad-output/planning-artifacts/epics.md:87)).

### Layer diagram (logical)

```text
UI (views/widgets/presenters/workers)
  ↓
Application wiring (dependency_container)
  ↓
Domain services + domain ports
  ↓
Adapters (tts/extraction/audio/playback/persistence)
  ↓
Infrastructure (logging) + SQLite + runtime artifacts
```

Mapped structure references: [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:344), [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:424).

## 3) Epics & Stories (5 epics / 23 stories)

| Epic                                             | Stories | Sprint status | Retrospective |
| ------------------------------------------------ | ------: | ------------- | ------------- |
| Epic 1 — Local Setup and Offline Readiness       |       3 | done          | done          |
| Epic 2 — Multi-Format Import and Text Extraction |       5 | done          | done          |
| Epic 3 — Resilient Conversion to Audio           |       6 | done          | done          |
| Epic 4 — Local Library and Integrated Playback   |       5 | done          | done          |
| Epic 5 — Diagnostics and Failure Transparency    |       4 | done          | done          |
| **Total**                                        |  **23** | **done**      | **done**      |

Sources: epic/story definitions ([`epics.md`](_bmad-output/planning-artifacts/epics.md:136), [`epics.md`](_bmad-output/planning-artifacts/epics.md:715)) and sprint completion states ([`sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml:42), [`sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml:79)).

## 4) Test Coverage

- BMAD/Passe-2 milestone reported: **270 passed** ([`PASSE_2_RAPPORT.md`](/PASSE_2_RAPPORT.md:66), [`PASSE_2_RAPPORT.md`](/PASSE_2_RAPPORT.md:70)).
- Current repository test organization remains split between unit and integration suites ([`tests/unit`](tests/unit), [`tests/integration`](tests/integration), [`pyproject.toml`](/pyproject.toml:28)).
- Current local collection snapshot (2026-02-17) indicates **274 collected**: **237 unit** + **37 integration** (command evidence captured during completion run).

Interpretation: 270 corresponds to the documented Passe-2 checkpoint; the repository currently includes additional tests beyond that checkpoint.

## 5) Architecture Decisions (key choices and rationale)

### Chatterbox + Kokoro (why two engines)

The architecture explicitly targets a GPU-first engine with CPU fallback for resilience/offline operation ([`project-brief.md`](_bmad-output/project-brief.md:93), [`epics.md`](_bmad-output/planning-artifacts/epics.md:71)).

Implementation evidence:

- Chatterbox adapter ([`chatterbox_provider.py`](src/adapters/tts/chatterbox_provider.py:22))
- Kokoro adapter ([`kokoro_provider.py`](src/adapters/tts/kokoro_provider.py:34))
- Deterministic fallback owned by orchestration requirements ([`epics.md`](_bmad-output/planning-artifacts/epics.md:84), [`epics.md`](_bmad-output/planning-artifacts/epics.md:472)).

### Result pattern vs exceptions

The project standardizes result/error envelopes for deterministic cross-layer behavior ([`result.py`](src/contracts/result.py:14), [`result.py`](src/contracts/result.py:33), [`epics.md`](_bmad-output/planning-artifacts/epics.md:87)).

### Structured JSONL logging

Observability contract requires correlated JSONL events with fixed required fields ([`event_schema.py`](src/infrastructure/logging/event_schema.py:10), [`jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py:38), [`epics.md`](_bmad-output/planning-artifacts/epics.md:88)).

### SQLite for local persistence

SQLite is defined as single source of truth for jobs/chunks/library/diagnostics in architecture and requirements ([`epics.md`](_bmad-output/planning-artifacts/epics.md:81), [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:141), [`connection.py`](src/adapters/persistence/sqlite/connection.py)).

## 6) Post-BMAD Integration (Passes 1–3)

### Pass 1 — Stabilization baseline

Post-BMAD baseline remained aligned with BMAD architecture constraints and startup/readiness mechanics, with dependency wiring and service boundaries preserved ([`dependency_container.py`](src/app/dependency_container.py:146), [`startup_readiness_service.py`](src/domain/services/startup_readiness_service.py), [`conversion_worker.py`](src/ui/workers/conversion_worker.py)).

### Pass 2 — Documented TTS installation/validation checkpoint

Pass-2 report documents engine installation effort, pipeline validation, and the 270-test checkpoint ([`PASSE_2_RAPPORT.md`](/PASSE_2_RAPPORT.md:1), [`PASSE_2_RAPPORT.md`](/PASSE_2_RAPPORT.md:66)).

### Pass 3 — Real engine integration in codebase

Current source shows concrete real-engine bindings rather than placeholders:

- Chatterbox via `chatterbox.tts_turbo` + `torchaudio` ([`chatterbox_provider.py`](src/adapters/tts/chatterbox_provider.py:11), [`chatterbox_provider.py`](src/adapters/tts/chatterbox_provider.py:46))
- Kokoro via `kokoro_onnx` ([`kokoro_provider.py`](src/adapters/tts/kokoro_provider.py:10), [`kokoro_provider.py`](src/adapters/tts/kokoro_provider.py:68))
- Model manifest with concrete hashes/sizes/paths ([`model_manifest.yaml`](config/model_manifest.yaml:1), [`model_manifest.yaml`](config/model_manifest.yaml:7)).

## 7) Known Gaps

1. **UI Import/Conversion only partially surfaced in top-level shell**
   - Main window still contains placeholder for library tab and fallback “unavailable” labels in some paths ([`main_window.py`](src/ui/main_window.py:62), [`main_window.py`](src/ui/main_window.py:67)).

2. **`model_manifest` contains absolute local path for Chatterbox artifact**
   - This reduces portability across machines ([`model_manifest.yaml`](config/model_manifest.yaml:7)).

3. **PDF stack currently based on `PyPDF2`; migration to `pypdf` should be planned**
   - Current dependency and import points: [`pyproject.toml`](/pyproject.toml:14), [`pdf_extractor.py`](src/adapters/extraction/pdf_extractor.py:15).

## 8) Maintenance Guide (practical extension paths)

### Add a new TTS engine

1. Implement a new adapter conforming to [`TtsProvider`](src/domain/ports/tts_provider.py:43).
2. Register it in [`build_container()`](src/app/dependency_container.py:146).
3. Keep fallback policy only in orchestration service (not in adapter) per architecture rule ([`epics.md`](_bmad-output/planning-artifacts/epics.md:84)).
4. Add/extend tests in [`tests/unit`](tests/unit) and [`tests/integration`](tests/integration).

### Add a new extraction format

1. Add an extraction adapter in [`src/adapters/extraction`](src/adapters/extraction).
2. Wire routing through [`ImportService`](src/domain/services/import_service.py) / extraction orchestration path.
3. Extend supported extension constraints in [`import_constants.py`](src/contracts/import_constants.py).
4. Add failure normalization and diagnostics parity with existing extractors ([`result.py`](src/contracts/result.py:14), [`event_schema.py`](src/infrastructure/logging/event_schema.py:45)).

### Evolve observability safely

1. Preserve required event fields and `domain.action` naming ([`event_schema.py`](src/infrastructure/logging/event_schema.py:10), [`event_schema.py`](src/infrastructure/logging/event_schema.py:25)).
2. Emit only through [`JsonlLogger.emit()`](src/infrastructure/logging/jsonl_logger.py:38).
3. Keep logging failures local and non-fatal for UI threads ([`jsonl_logger.py`](src/infrastructure/logging/jsonl_logger.py:78), [`conversion_view.py`](src/ui/views/conversion_view.py:324)).

### Preserve persistence integrity

1. Add schema changes via incremental SQL migrations under [`migrations`](migrations).
2. Keep repositories as the only DB access boundary ([`dependency_container.py`](src/app/dependency_container.py:148), [`architecture.md`](_bmad-output/planning-artifacts/architecture.md:429)).
3. Keep service-level state transition validation for conversion jobs ([`job_state_validator.py`](src/domain/services/job_state_validator.py), [`epics.md`](_bmad-output/planning-artifacts/epics.md:86)).
