---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
  - step-epic7-chapter-ux-library
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
lastUpdated: "2026-02-19T17:20:00.000Z"
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
NR1: Epic 7 - Detect chapters automatically in EPUB/PDF/TXT
NR2: Epic 7 - Propose alternative segmentation when no chapters detected
NR3: Epic 7 - Convert chapters/sections sequentially into separate audio files
NR4: Epic 7 - Display imported filename in Conversion view
NR5: Epic 7 - Allow user to choose output destination folder
NR6: Epic 7 - Allow user to set output filename
NR7: Epic 7 - Display and select chapters to convert (all selected by default)
NR8: Epic 7 - Speech rate defaults to 1.0 (normal speed)
NR9: Epic 7 - Merge Import tab into Conversion tab (remove Import tab)
NR10: Epic 7 - Display converted audio files in Library with configurable output folder
NR11: Epic 7 - Display metadata in Library (title, duration, date, source)
NR12: Epic 7 - Integrated audio player in Library
NR13: Epic 7 - Configurable Library output folder
NR14: Epic 7 - Voice preview with pre-filled French text in Conversion view

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

### Epic 7: Chapter-Aware Conversion, Unified UX, and Functional Library

Enable users to import large documents with automatic chapter detection, select which chapters to convert, control output destination and naming, and browse/play results in a fully functional Library with integrated audio player and voice preview.
**NRs covered:** NR1, NR2, NR3, NR4, NR5, NR6, NR7, NR8, NR9, NR10, NR11, NR12, NR13, NR14

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

## Epic 7: Chapter-Aware Conversion, Unified UX, and Functional Library

Enable users to import large documents with automatic chapter detection, select which chapters to convert, control output destination and naming, and browse/play results in a fully functional Library with integrated audio player and voice preview.

### Story 7.1: Detect and Segment Chapters or Sections from Imported Documents

As a user importing a large document,
I want the application to automatically detect chapters or propose a segmentation strategy,
So that I can convert each part separately without memory crashes.

**Acceptance Criteria:**

**Given** an EPUB file is imported
**When** extraction executes via the EPUB adapter
**Then** native EPUB chapters are detected from the TOC/spine structure and listed with title and index
**And** each chapter is stored as an independent extractable unit in the document record.

**Given** a PDF file is imported
**When** extraction executes via the PDF adapter
**Then** the system proposes page-based segmentation as sections
**And** each section is labeled with its page range (e.g. "Pages 1-20").

**Given** a TXT or MD file is imported without detectable chapter markers
**When** extraction executes via the text extractor
**Then** the system proposes segmentation by estimated audio duration (blocks of approximately 1500 words per segment)
**And** each segment is labeled with its estimated duration (e.g. "Segment 1 - ~10 min").

**Given** chapters or sections are detected
**When** the conversion pipeline runs
**Then** each chapter/section produces a separate audio file in the output folder
**And** files are named deterministically as `[source_name]_chapter_01.mp3`, `[source_name]_chapter_02.mp3`, etc.

**Given** a document with no detectable structure
**When** segmentation analysis completes
**Then** a single "Full document" entry is returned
**And** conversion behavior remains identical to the existing single-file pipeline.

### Story 7.2: Merge Import Flow into Conversion Tab

As a user,
I want to select and import my document directly from the Conversion tab,
So that I can start conversion without navigating between multiple tabs.

**Acceptance Criteria:**

**Given** the Conversion tab is open
**When** the user clicks "Select file"
**Then** a file dialog opens filtered to supported formats (EPUB, PDF, TXT, MD)
**And** the selected filename and file size are displayed at the top of the Conversion view.

**Given** a file is selected in the Conversion tab
**When** import validation and extraction complete successfully
**Then** the detected chapters/sections list is displayed immediately below the file info
**And** the Convert button becomes available.

**Given** import fails (unsupported format or unreadable file)
**When** the error is returned
**Then** a normalized actionable error message is displayed inline in the Conversion tab
**And** the user can select a different file without leaving the tab.

**Given** the Import tab previously existed as a separate tab
**When** this story is implemented
**Then** the Import tab is removed from the tab bar
**And** no regression occurs on the underlying import service and document persistence logic.

### Story 7.3: Display and Select Chapters to Convert

As a user with a detected chapter list,
I want to see all chapters and choose which ones to convert,
So that I can convert only the parts I need without processing the entire document.

**Acceptance Criteria:**

**Given** chapters or sections are detected after import
**When** the chapter list is rendered in the Conversion view
**Then** all chapters are checked by default
**And** each entry shows its title (or label), index, and estimated word count or duration.

**Given** the chapter list is displayed
**When** the user interacts with the list
**Then** individual chapters can be checked or unchecked
**And** "Select all" and "Deselect all" actions are available.

**Given** a subset of chapters is selected
**When** conversion starts
**Then** only the selected chapters are processed by the TTS orchestration service
**And** progress displays "Chapter X of Y selected" during conversion.

**Given** a single-section document (no chapter structure)
**When** the chapter list renders
**Then** a single "Full document" entry is shown and checked
**And** conversion behavior is identical to the existing pipeline.

### Story 7.4: Configure Output Destination Folder and Output Filename

As a user launching conversion,
I want to choose where my audio files are saved and what they are named,
So that I can organize my audiobooks in my own file system.

**Acceptance Criteria:**

**Given** the Conversion view is open
**When** the user clicks "Choose output folder"
**Then** a folder selection dialog opens
**And** the selected path is displayed in the Conversion view.

**Given** an output folder is selected
**When** conversion completes
**Then** all audio files are written to the selected folder
**And** the selected path is persisted in app configuration for the next session.

**Given** a document is imported
**When** the output filename field is rendered
**Then** it is pre-filled with the source filename without extension
**And** the user can freely edit the base name before launching conversion.

**Given** no output folder has been configured
**When** conversion is launched
**Then** the default folder `runtime/library/audio/` is used
**And** an informational message displays the path being used.

**Given** the output folder or filename is invalid (e.g. read-only path)
**When** conversion is launched
**Then** a normalized error is displayed before conversion starts
**And** the user can correct the path without losing other configuration.

### Story 7.5: Set Speech Rate Default to 1.0

As a user opening the Conversion view,
I want the speech rate slider to default to 1.0 (normal speed),
So that I do not need to adjust it manually on every session.

**Acceptance Criteria:**

**Given** the application starts for the first time or with no persisted speech rate
**When** the Conversion view renders
**Then** the speech rate slider is positioned at 1.0
**And** the displayed value label reads "1.00".

**Given** the speech rate range is [0.5, 2.0] with step 0.05
**When** the default value is computed
**Then** the slider position corresponds to value 1.0 (step index 10 from minimum)
**And** the `ConversionView` state initializes `speech_rate.default` to 1.0.

**Given** the user modifies the speech rate during a session
**When** the next session starts
**Then** the last used value is restored from persisted configuration
**And** the displayed label reflects the restored value.

### Story 7.6: Functional Library with Audio Player and Configurable Output Folder

As a user who has converted audiobooks,
I want to browse my converted audio files with metadata and play them directly in the Library tab,
So that I can access and listen to my audiobooks without leaving the application.

**Acceptance Criteria:**

**Given** audio files have been produced by conversion
**When** the Library tab opens
**Then** the list displays title, format, file size, conversion date, and source filename for each item
**And** items are sorted by conversion date descending.

**Given** the Library tab is open
**When** the user clicks "Configure Library folder"
**Then** a folder selection dialog opens
**And** the Library refreshes to display audio files found in the newly selected folder.

**Given** a library item is selected
**When** the user clicks "Play"
**Then** an audio player panel appears at the bottom of the Library view with Play/Pause, seek bar, elapsed time, and total duration
**And** playback starts immediately.

**Given** the audio player is active
**When** the user selects a different item in the list
**Then** the currently playing item remains highlighted in the list
**And** the player continues playback until explicitly paused or a new item is opened.

**Given** a selected audio file is missing or unreadable
**When** the user attempts to play it
**Then** a normalized error message is displayed inline
**And** the player does not crash or enter an inconsistent state.

**Given** the Library folder is not yet configured
**When** the Library tab opens
**Then** the default folder `runtime/library/audio/` is scanned
**And** an informational message indicates the folder being used with an option to change it.

### Story 7.7: Voice Preview with Editable French Sample Text

As a user selecting a TTS voice,
I want to preview the selected voice with a short editable text before launching a full conversion,
So that I can choose the voice that suits me without waiting for a complete conversion.

**Acceptance Criteria:**

**Given** the Conversion view is open with a voice selected
**When** the user clicks "Preview voice"
**Then** a text area appears below the voice selector pre-filled with: "Bonjour, ceci est un test de la voix sélectionnée. Bonne écoute !"
**And** the text is fully editable by the user.

**Given** the preview text is ready
**When** the user clicks "Play preview"
**Then** TTS synthesis is triggered on the preview text only using the currently selected engine and voice
**And** the resulting audio plays directly in the application without being saved to the library.

**Given** a voice preview synthesis is in progress
**When** the user changes the voice selection
**Then** any in-progress preview is cancelled
**And** the preview text area remains visible with the current text.

**Given** voice preview synthesis fails
**When** the error is returned
**Then** a normalized error message is displayed below the preview area
**And** the user can modify the text and retry without restarting the application.

**Given** the preview audio plays successfully
**When** playback completes
**Then** the preview player resets to its initial state
**And** no library entry is created for the preview audio.
