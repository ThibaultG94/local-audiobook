---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
---

# local-audiobook - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for local-audiobook, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: User can import source files in EPUB format
FR2: User can import source files in PDF format
FR3: User can import source files in TXT format
FR4: User can import source files in Markdown format
FR5: System can extract textual content from imported EPUB files
FR6: System can extract textual content from imported PDF files
FR7: System can extract textual content from imported TXT and Markdown files
FR8: System can report extraction failures with actionable error feedback
FR9: User can start a document-to-audio conversion from extracted text
FR10: User can select output format as MP3 or WAV
FR11: System can segment long texts into conversion chunks
FR12: System can process chunks and assemble a final continuous audio file
FR13: System can continue conversion by switching to fallback engine when primary engine is unavailable
FR14: System can preserve conversion state and logs when a chunk fails
FR15: User can select TTS engine between Chatterbox and Kokoro
FR16: User can select a voice profile available for the chosen engine
FR17: User can select language for synthesis with FR and EN available in MVP
FR18: User can adjust basic speech rate for output generation
FR19: User can play generated audio inside the application
FR20: User can pause and resume playback
FR21: User can seek to a specific playback position
FR22: User can view playback progress and current time
FR23: System can store generated audio files in a local library
FR24: System can persist basic metadata for each generated audiobook
FR25: User can browse locally stored audiobooks in the library view
FR26: User can reopen a selected library item for playback
FR27: System can operate without internet access after model bootstrap is completed
FR28: System can inform user when required local model assets are missing
FR29: System can record local logs for extraction, conversion, fallback, and export events
FR30: User can access diagnostic information for failed conversions
FR31: User can launch batch conversion jobs across multiple documents
FR32: User can search library items with advanced filters
FR33: User can use advanced expressivity and emotion controls
FR34: User can use voice cloning from a reference sample
FR35: User can run the application on additional desktop operating systems

### NonFunctional Requirements

NFR1: UI interactions non bloquantes pendant conversion et lecture
NFR2: Traitement stable des longs documents via chunking sans arrêt du pipeline
NFR3: Temps de conversion mesurable par 10k mots et traçable par moteur
NFR4: Reprise contrôlée sur erreur de chunk avec conservation d’état
NFR5: Génération audio finale cohérente sans corruption de concaténation
NFR6: Journalisation locale suffisante pour diagnostiquer extraction conversion export
NFR7: Aucune transmission de contenu texte ou audio vers des services tiers en exécution
NFR8: Stockage local des artefacts avec permissions système standard
NFR9: Fonctionnement offline complet après bootstrap modèles
NFR10: MVP compatible Linux Mint avec GPU AMD RX 7900 XT via ROCm
NFR11: Fallback CPU opérationnel via Kokoro quand Chatterbox GPU indisponible
NFR12: Support des formats entrée EPUB PDF TXT MD et sortie MP3 WAV
NFR13: Architecture modulaire séparant extraction orchestration TTS post-traitement bibliothèque
NFR14: Logs structurés corrélables par document et étape pipeline
NFR15: Configuration claire des moteurs voix langues sans modifier le code applicatif

### Additional Requirements

- Starter template explicitly selected in architecture: custom Python scaffold (no external starter template); initialization is manual with deterministic project layout.
- Epic 1 Story 1 implication: scaffold/bootstrap and foundational wiring must be treated as implementation prerequisite.
- Infrastructure/deployment constraints: Linux Mint MVP target, offline-first execution after model bootstrap, no cloud dependency in runtime.
- Persistence architecture: SQLite as single source of truth for documents, jobs, chunks, library metadata, diagnostics.
- Migration requirement: incremental SQL schema versioning from initial release.
- Integration contract requirement: unified TTS provider contract with synthesis, voice inventory, and health checks.
- Fallback policy requirement: deterministic fallback handled in orchestration service, not in engine adapters.
- Resilience requirement: phrase-first chunking with resume from last non-validated chunk.
- Job state governance: validated transitions (queued/running/paused/failed/completed) and atomic persistence updates.
- Error/result standardization: service responses must follow normalized result and structured error envelopes.
- Observability requirement: local JSONL logging with strict correlation and pipeline fields.
- Concurrency requirement: dedicated conversion worker thread with Qt signals/slots to keep UI responsive.
- Model governance requirement: local model registry with installed/missing/invalid states and startup integrity checks.
- Security requirement: no runtime network API exposure, no post-bootstrap cloud transfer, local permissions model.
- Project structure requirement: implementation must respect documented boundaries (`src`, `tests`, `migrations`, `config`, `runtime`).

### FR Coverage Map

FR1: Epic 2 - Import EPUB source file
FR2: Epic 2 - Import PDF source file
FR3: Epic 2 - Import TXT source file
FR4: Epic 2 - Import Markdown source file
FR5: Epic 2 - Extract text from EPUB files
FR6: Epic 2 - Extract text from PDF files
FR7: Epic 2 - Extract text from TXT/MD files
FR8: Epic 2 - Surface actionable extraction errors
FR9: Epic 3 - Start document-to-audio conversion
FR10: Epic 3 - Select MP3 or WAV output
FR11: Epic 3 - Chunk long text reliably
FR12: Epic 3 - Assemble chunk outputs into final audio
FR13: Epic 3 - Fallback to secondary engine on primary failure
FR14: Epic 3 - Preserve state/logs on chunk failure
FR15: Epic 3 - Select TTS engine
FR16: Epic 3 - Select voice profile
FR17: Epic 3 - Select synthesis language (FR/EN)
FR18: Epic 3 - Adjust basic speech rate
FR19: Epic 4 - Play generated audio in app
FR20: Epic 4 - Pause/resume playback
FR21: Epic 4 - Seek playback position
FR22: Epic 4 - Display playback progress/time
FR23: Epic 4 - Store generated audio in local library
FR24: Epic 4 - Persist audiobook metadata
FR25: Epic 4 - Browse local library items
FR26: Epic 4 - Reopen selected library item for playback
FR27: Epic 1 - Operate fully offline after model bootstrap
FR28: Epic 1 - Inform user of missing local model assets
FR29: Epic 5 - Record local diagnostic logs across pipeline
FR30: Epic 5 - Expose diagnostics for failed conversions

Out of scope for MVP mapping: FR31, FR32, FR33, FR34, FR35.

## Epic List

### Epic 1: Local Setup and Offline Readiness

Enable users to run the application in a fully local mode by validating model availability and offline conversion readiness before processing.
**FRs covered:** FR27, FR28

### Epic 2: Multi-Format Import and Text Extraction

Enable users to import EPUB/PDF/TXT/MD documents and obtain clean extractable text with actionable error guidance.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8

### Epic 3: Resilient Conversion to Audio

Enable users to configure engine/voice/language/output and complete robust long-document conversion through chunking, deterministic fallback, and resume-friendly processing.
**FRs covered:** FR9, FR10, FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18

### Epic 4: Local Library and Integrated Playback

Enable users to store, browse, and replay generated audiobooks with in-app playback controls.
**FRs covered:** FR19, FR20, FR21, FR22, FR23, FR24, FR25, FR26

### Epic 5: Diagnostics and Failure Transparency

Enable users/operators to understand and troubleshoot failures through structured local observability and actionable diagnostics.
**FRs covered:** FR29, FR30

### Epic 6: Runtime Fixes & Polish

Stabilize runtime behavior after integration by fixing conversion crashes, introducing degraded readiness behavior, completing Library UI functionality, and finalizing documentation and completion reporting.
**FRs covered:** Hardening epic (cross-cutting, no new PRD FR IDs)

## Epic 1: Local Setup and Offline Readiness

Enable users to run the application in a fully local mode by validating model availability and offline conversion readiness before processing.

### Story 1.1: Initialize Local Runtime, SQLite, and Baseline Migrations

As a desktop user,
I want the application to initialize local persistence and runtime folders at startup,
So that conversion state and artifacts are reliably stored on my machine.

**Acceptance Criteria:**

**Given** a fresh environment with no existing runtime database
**When** the app starts through `src/app/main.py`
**Then** runtime directories and the SQLite database are initialized locally
**And** no network call is required for initialization.

**Given** migration scripts are present in `migrations/`
**When** startup migration execution runs
**Then** required MVP tables are created with deterministic ordering
**And** migration status is persisted to prevent duplicate re-application.

### Story 1.2: Validate Model Assets and Engine Health at Startup

As a user preparing conversion,
I want startup checks to validate model assets and engine health,
So that I know whether conversion can run fully offline.

**Acceptance Criteria:**

**Given** model manifest and registry service configuration
**When** startup readiness checks execute
**Then** each required model is classified as installed, missing, or invalid
**And** integrity failures include actionable remediation details.

**Given** both TTS providers are wired in dependency injection
**When** health checks execute for Chatterbox and Kokoro
**Then** per-engine availability is returned in a normalized result envelope
**And** provider errors are normalized with code, message, details, and retryable fields.

### Story 1.3: Surface Readiness State in Conversion UI

As a user before conversion,
I want clear readiness status and prerequisites in the conversion interface,
So that I can fix setup issues before launching work.

**Acceptance Criteria:**

**Given** readiness results are available from startup services
**When** the conversion screen is loaded
**Then** readiness state is displayed as ready or not_ready
**And** missing prerequisites are shown with actionable steps.

**Given** readiness is not_ready
**When** the user tries to launch conversion
**Then** conversion action is blocked
**And** the UI explains what must be fixed locally.

## Epic 2: Multi-Format Import and Text Extraction

Enable users to import EPUB/PDF/TXT/MD documents and obtain clean extractable text with actionable error guidance.

### Story 2.1: Import EPUB/PDF/TXT/MD with Validation

As a user,
I want to import supported document formats through one flow,
So that I can start conversion without manual preprocessing.

**Acceptance Criteria:**

**Given** the import workflow is opened in the UI
**When** I choose a `.epub`, `.pdf`, `.txt`, or `.md` file
**Then** the file is accepted and forwarded to import service validation
**And** unsupported extensions are rejected with actionable errors.

**Given** an unreadable or missing selected file
**When** import validation executes
**Then** the service returns a normalized failure result
**And** error details include clear local remediation guidance.

### Story 2.2: Extract Text from EPUB and PDF

As a user importing EPUB or PDF documents,
I want extraction to produce deterministic text output,
So that conversion receives stable input.

**Acceptance Criteria:**

**Given** an imported EPUB file
**When** extraction is executed via EPUB adapter
**Then** readable text content is returned in deterministic order
**And** malformed content failures are reported in normalized form.

**Given** an imported PDF file
**When** extraction is executed via PDF adapter
**Then** pages are processed deterministically with graceful handling of blank/non-text pages
**And** extraction failures include actionable error context.

### Story 2.3: Extract and Normalize TXT/MD with Unified Error Feedback

As a user importing TXT or Markdown,
I want normalized text extraction and consistent extraction error reporting,
So that downstream chunking remains reliable.

**Acceptance Criteria:**

**Given** a TXT or Markdown document
**When** extraction runs in the text extractor
**Then** output is normalized for encoding and line-break consistency
**And** markdown markers are transformed into TTS-friendly plain text.

**Given** any extractor fails
**When** failure is presented to UI
**Then** presenter displays a unified actionable message
**And** diagnostics are logged with extraction stage metadata.

## Epic 3: Resilient Conversion to Audio

Enable users to configure engine/voice/language/output and complete robust long-document conversion through chunking, deterministic fallback, and resume-friendly processing.

### Story 3.1: Expose Unified Provider Contract for Chatterbox and Kokoro

As a user selecting synthesis options,
I want both engines to follow one provider contract,
So that engine switching is predictable and maintainable.

**Acceptance Criteria:**

**Given** engine adapters are initialized
**When** provider capabilities are queried
**Then** both adapters expose consistent methods for synthesize, voice list, and health check
**And** outputs follow normalized result format.

**Given** provider-specific errors occur
**When** failures propagate to orchestration
**Then** error categories remain deterministic for fallback handling
**And** implementation details are not leaked across layer boundaries.

### Story 3.2: Implement Chunking, Orchestration, and Deterministic Fallback

As a user converting long documents,
I want chunk processing with deterministic fallback,
So that conversion can complete despite primary engine failures.

**Acceptance Criteria:**

**Given** extracted text is available
**When** chunking service processes text
**Then** chunks are produced in deterministic order with phrase-first rules
**And** chunk metadata is persisted for resume support.

**Given** Chatterbox fails for a chunk
**When** orchestration evaluates fallback policy
**Then** it switches deterministically to Kokoro in service layer
**And** adapters do not contain fallback policy logic.

### Story 3.3: Persist Conversion State and Resume from Failed Chunk

As a user running long conversions,
I want failed jobs to resume from the last failed point,
So that I do not restart the entire process.

**Acceptance Criteria:**

**Given** a running conversion job
**When** state transitions are requested
**Then** only allowed states are accepted by orchestration rules
**And** invalid transitions return normalized errors.

**Given** a chunk failure followed by retry
**When** resume execution starts
**Then** processing continues from last non-validated chunk
**And** previously successful chunks are not recomputed.

### Story 3.4: Configure Conversion Parameters in UI and Launch Worker Execution

As a user launching conversion,
I want to configure engine, voice, language, speech rate, and output format,
So that generated audio matches my preferences while UI stays responsive.

**Acceptance Criteria:**

**Given** provider configuration options are available
**When** conversion settings are rendered in conversion view
**Then** user can choose engine, voice, FR/EN language, speech rate, and MP3/WAV output
**And** invalid values are blocked with actionable messages.

**Given** conversion is started from the UI
**When** conversion worker executes in QThread
**Then** progress and status are emitted via Qt signals
**And** the main UI thread remains responsive.

## Epic 4: Local Library and Integrated Playback

Enable users to store, browse, and replay generated audiobooks with in-app playback controls.

### Story 4.1: Assemble Final Audio and Persist Library Metadata

As a user completing conversion,
I want synthesized chunks assembled and indexed in my local library,
So that finished audiobooks are available for later listening.

**Acceptance Criteria:**

**Given** chunk audio artifacts are available
**When** post-processing runs
**Then** chunks are assembled in deterministic order into valid MP3 or WAV
**And** assembly/encoding failures return normalized errors.

**Given** final audio exists
**When** library persistence executes
**Then** metadata and file paths are stored in SQLite according to schema rules
**And** writes are transactional to avoid partial library state.

### Story 4.2: Implement Library View Listing and Selection

As a user with converted audiobooks,
I want to browse and select library items,
So that I can quickly reopen previously generated content.

**Acceptance Criteria:**

**Given** library records are present
**When** library view loads
**Then** it displays title, format, size, import date, and conversion status
**And** ordering remains deterministic across refreshes.

**Given** a user selects a document in library view
**When** selection is confirmed
**Then** the selected item is available for conversion or playback context
**And** no direct repository access is performed from UI layer.

### Story 4.3: Integrate Player Controls (Play/Pause/Resume/Seek/Progress)

As a user listening in-app,
I want reliable playback controls and progress display,
So that I can navigate audio comfortably.

**Acceptance Criteria:**

**Given** a valid local audio item is selected
**When** playback starts through player service
**Then** audio plays via adapter with stable state updates
**And** missing/unreadable files produce normalized user-facing errors.

**Given** active playback
**When** user pauses, resumes, or seeks
**Then** commands are applied within valid bounds
**And** UI progress/time remain synchronized with player state.

## Epic 5: Diagnostics and Failure Transparency

Enable users/operators to understand and troubleshoot failures through structured local observability and actionable diagnostics.

### Story 5.1: Define and Enforce JSONL Event Schema

As a support-minded user,
I want all pipeline logs to follow one correlated schema,
So that failures are diagnosable end-to-end.

**Acceptance Criteria:**

**Given** logging infrastructure is initialized
**When** services emit runtime events
**Then** each JSONL event includes required correlation and stage fields
**And** timestamps are ISO-8601 UTC.

**Given** an invalid event payload is produced
**When** schema validation is applied
**Then** invalid events are rejected or normalized deterministically
**And** logging failures do not crash the UI thread.

### Story 5.2: Instrument End-to-End Pipeline and Diagnostics UI

As a user facing runtime issues,
I want diagnostics to show meaningful stage-aware failure information,
So that I can retry or remediate confidently.

**Acceptance Criteria:**

**Given** a conversion job runs from import to playback
**When** each pipeline stage executes
**Then** correlated events are emitted for start/success/failure paths
**And** chunk-level events include engine and chunk_index when relevant.

**Given** a conversion failure is returned to presenter
**When** diagnostics panel is opened
**Then** the UI displays normalized error code/message/details/retryable
**And** remediation guidance is actionable and local-only.

## Epic 6: Runtime Fixes & Polish

Stabilize runtime behavior after integration by fixing conversion crashes, introducing degraded readiness behavior, completing Library UI functionality, and finalizing documentation and completion reporting.

### Story 6.1: Debug and Fix Conversion Pipeline Runtime Failure

As a user launching conversion,
I want conversion to complete end-to-end without worker crashes,
So that imported documents reliably produce playable audio.

**Acceptance Criteria:**

**Given** the conversion worker catches runtime exceptions
**When** an unhandled conversion failure occurs
**Then** full traceback is captured and logged with `traceback.format_exc()`
**And** diagnostics include enough context to identify root cause.

**Given** conversion is triggered from UI on a small TXT then PDF sample
**When** pipeline executes through worker and orchestration
**Then** end-to-end output is produced as WAV or MP3 without `worker_execution.unhandled_exception`
**And** existing tests remain green with new regression tests added.

**Given** both engines are available in target environment
**When** synthesis is executed with Chatterbox and with Kokoro
**Then** each engine produces valid audio output
**And** voice availability presented to UI matches real provider availability.

### Story 6.2: Implement Degraded Readiness Mode

As a user with partial engine availability,
I want the app to run in degraded mode when fallback works,
So that I can still convert documents even if primary engine is down.

**Acceptance Criteria:**

**Given** startup checks detect primary engine unavailable and fallback engine healthy
**When** readiness status is computed
**Then** readiness is `degraded` instead of `not_ready`
**And** conversion remains enabled with auto-selection of the working engine.

**Given** all engines are unavailable
**When** readiness is recomputed
**Then** status is `not_ready`
**And** UI displays remediation steps per failed engine.

### Story 6.3: Complete Library View with Select and Delete Actions

As a user managing imported documents,
I want a functional Library tab with selection and deletion,
So that I can control which documents are converted and retained.

**Acceptance Criteria:**

**Given** documents are present in local persistence
**When** library tab is opened
**Then** list shows title, format, size, import date, and conversion status
**And** data refresh remains deterministic.

**Given** a user selects a document
**When** conversion action is initiated from library context
**Then** selected document is forwarded through presenter/service boundaries
**And** UI does not access repositories directly.

**Given** a user confirms deletion
**When** delete operation executes
**Then** document and related local references are removed safely
**And** failures are surfaced with normalized actionable errors.

### Story 6.4: Update Project Documentation for Current Stack

As a contributor onboarding the project,
I want accurate setup and architecture documentation,
So that I can install and run the application reliably.

**Acceptance Criteria:**

**Given** project docs are outdated
**When** `README.md` and `INSTALLATION.md` are revised
**Then** they describe current Python 3.12, ROCm 7.2, and venv setup with copy-pastable commands
**And** outdated references (Python 3.11, ROCm 6.1, Coqui TTS) are removed.

**Given** architecture context is required for contributors
**When** documentation update is complete
**Then** a concise architecture overview and directory structure are included
**And** instructions align with current implementation boundaries.

### Story 6.5: Produce BMAD Completion Report Covering All Epics

As a product owner,
I want a completion report summarizing delivery and decisions,
So that project status and future work are explicit and auditable.

**Acceptance Criteria:**

**Given** epics and implementation artifacts exist
**When** `_bmad-output/completion-report.md` is finalized
**Then** it covers Epics 1 through 6 with factual references
**And** architecture decisions include justifications.

**Given** quality tracking is required
**When** report is generated
**Then** test coverage summary and known issues/future work are included
**And** statements are traceable to source files and current project state.
