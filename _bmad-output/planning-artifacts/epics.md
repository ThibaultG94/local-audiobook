<!-- --- -->
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/project-brief.md
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
FR31: User can launch batch conversion jobs across multiple documents post MVP  
FR32: User can search library items with advanced filters post MVP  
FR33: User can use advanced expressivity and emotion controls post MVP  
FR34: User can use voice cloning from a reference sample post MVP  
FR35: User can run the application on additional desktop operating systems post MVP

### NonFunctional Requirements

NFR1: UI interactions non blocking during conversion and playback  
NFR2: Stable long-document processing via chunking without pipeline interruption  
NFR3: Conversion time measurable per 10k words and traceable per engine  
NFR4: Controlled resume on chunk error with state preservation  
NFR5: Coherent final audio generation without concatenation corruption  
NFR6: Sufficient local logging for extraction conversion export diagnostics  
NFR7: No text or audio transmission to third-party services during execution  
NFR8: Local artifact storage with standard system permissions  
NFR9: Full offline operation after model bootstrap  
NFR10: MVP compatibility with Linux Mint and AMD RX 7900 XT via ROCm  
NFR11: CPU fallback operational via Kokoro when Chatterbox GPU is unavailable  
NFR12: Input support EPUB PDF TXT MD and output support MP3 WAV  
NFR13: Modular architecture separating extraction orchestration TTS post-processing library  
NFR14: Structured logs correlatable by document and pipeline stage  
NFR15: Clear engine voice language configuration without modifying application code

### Additional Requirements

- Starter template requirement: custom Python scaffold without third-party starter, with deterministic structure and explicit module boundaries; this must be treated as Epic 1 Story 1 implementation prerequisite.
- Project scaffolding and packaging requirement: pyproject-based workflow, separated unit and integration tests, and explicit package-oriented Python layout.
- Persistence requirement: SQLite as single source of truth for jobs, chunks, library, metadata, progress, and diagnostic states.
- Migration requirement: schema versioning with incremental SQL migrations from initial release.
- TTS contract requirement: unified `tts_provider` contract exposing `synthesize_chunk`, `list_voices`, and `health_check`.
- Fallback architecture requirement: deterministic fallback is orchestrated in `tts_orchestration_service`, never inside engine adapters.
- Conversion resilience requirement: phrase-first chunking with target character limits and resume from last non-validated chunk.
- Job lifecycle requirement: service-validated transitions over `queued`, `running`, `paused`, `failed`, `completed` with atomic persistence updates.
- Result and error normalization requirement: service responses as `{ok, data, error}` and errors as `{code, message, details, retryable}`.
- Observability requirement: JSONL logging with strict fields `correlation_id`, `job_id`, `chunk_index`, `engine`, `stage`, `event`, `severity`, `timestamp`.
- Threading requirement: dedicated conversion worker thread with Qt signals and slots for progress and error propagation to UI.
- Model governance requirement: `model_registry_service` with local manifest, installed missing invalid states, and integrity validation at startup before conversion.
- File structure requirement: implementation must follow the complete project directory structure defined in architecture including `src`, `tests`, `migrations`, `config`, and `runtime` boundaries.
- Extraction adapter requirement: EPUB via `ebooklib`, PDF via `PyPDF2`, and native TXT Markdown parsing.
- Runtime storage requirement: logs in `runtime/logs`, audio artifacts in `runtime/library/audio`, temporary files in `runtime/library/temp`.
- Platform requirement: MVP targets Linux Mint only with AMD ROCm primary path and Kokoro CPU fallback.
- UI language requirement: MVP interface language is English only.
- Security boundary requirement: no authentication in local MVP, no network API exposure, and no cloud data transfer after bootstrap.
- Out-of-scope enforcement requirement: batch multi-documents, advanced library search, advanced expressivity and emotion, voice cloning, Windows macOS portability, and auto-update remain excluded from MVP stories.

### FR Coverage Map

FR1: Epic 2 - Import EPUB source file  
FR2: Epic 2 - Import PDF source file  
FR3: Epic 2 - Import TXT source file  
FR4: Epic 2 - Import Markdown source file  
FR5: Epic 2 - Extract text from EPUB  
FR6: Epic 2 - Extract text from PDF  
FR7: Epic 2 - Extract text from TXT and Markdown  
FR8: Epic 2 - Provide actionable extraction error feedback  
FR9: Epic 3 - Start document-to-audio conversion  
FR10: Epic 3 - Select MP3 or WAV output format  
FR11: Epic 3 - Segment long text into chunks  
FR12: Epic 3 - Process chunks and assemble continuous final audio  
FR13: Epic 3 - Fallback to secondary engine when primary unavailable  
FR14: Epic 3 - Preserve state and logs on chunk failure  
FR15: Epic 3 - Select TTS engine Chatterbox or Kokoro  
FR16: Epic 3 - Select voice profile per engine  
FR17: Epic 3 - Select synthesis language FR or EN  
FR18: Epic 3 - Adjust basic speech rate  
FR19: Epic 4 - Play generated audio in application  
FR20: Epic 4 - Pause and resume playback  
FR21: Epic 4 - Seek playback position  
FR22: Epic 4 - View playback progress and current time  
FR23: Epic 4 - Store generated audio in local library  
FR24: Epic 4 - Persist audiobook metadata  
FR25: Epic 4 - Browse local library items  
FR26: Epic 4 - Reopen library item for playback  
FR27: Epic 1 - Operate fully offline after model bootstrap  
FR28: Epic 1 - Inform user about missing local model assets  
FR29: Epic 5 - Record local logs for extraction conversion fallback export events  
FR30: Epic 5 - Provide diagnostic information for failed conversions  

Out of scope for this MVP epic mapping iteration: FR31, FR32, FR33, FR34, FR35.

## Epic List

### Epic 1: Local Setup and Offline Readiness
Enable users to run the application confidently in a fully local mode by validating model availability and offline conversion readiness before processing.
**FRs covered:** FR27, FR28

### Epic 2: Multi-Format Import and Text Extraction
Enable users to bring documents from supported formats and obtain clean extractable text with actionable error guidance when extraction fails.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8

### Epic 3: Resilient Conversion to Audio
Enable users to configure engine voice language and output format, then complete robust long-document conversion through chunking deterministic fallback and resumable processing.
**FRs covered:** FR9, FR10, FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18

### Epic 4: Local Library and Integrated Playback
Enable users to manage and consume generated audiobooks by storing metadata browsing local content and controlling playback directly in the application.
**FRs covered:** FR19, FR20, FR21, FR22, FR23, FR24, FR25, FR26

### Epic 5: Diagnostics and Failure Transparency
Enable users and operators to understand failures and troubleshoot confidently through structured local observability and accessible diagnostics.
**FRs covered:** FR29, FR30

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic 1: Local Setup and Offline Readiness

Enable users to run the application confidently in a fully local mode by validating model availability and offline conversion readiness before processing.

### Story 1.1: Initialize Local Application Foundation and Persistent Job Store

As a privacy-first desktop user,
I want the application to initialize with local persistence and baseline schema migrations,
So that conversion jobs and offline readiness state are reliably stored on my machine.

**Acceptance Criteria:**

**Given** a fresh Linux Mint installation target and an empty runtime directory
**When** the app bootstrap is executed through `main.py` and SQLite connection setup in `connection.py`
**Then** a local SQLite database file is created and reachable through repository boundaries only
**And** no network dependency is required for this initialization path.

**Given** dependency wiring is required for service boundary enforcement
**When** the application bootstrap initializes service composition in `dependency_container.py`
**Then** core services repositories providers and logging are resolved through the container
**And** UI layers consume dependencies via container wiring rather than direct infrastructure instantiation.

**Given** the initial migration file `0001_initial_schema.sql`
**When** migrations are applied at startup
**Then** required MVP tables for documents jobs chunks library and diagnostics are created in `snake_case`
**And** migration state is persisted to prevent re-applying the same migration.

**Given** job state management in `tts_orchestration_service.py` will rely on persistence
**When** the persistence layer writes or updates job state
**Then** only allowed states `queued running paused failed completed` are accepted by service validation
**And** invalid transitions return normalized errors through `result.py` and `errors.py`.

**Given** observability is required from first executable increment
**When** startup and migration events occur
**Then** JSONL log events are emitted by `jsonl_logger.py` with fields `correlation_id job_id chunk_index engine stage event severity timestamp`
**And** events follow `domain.action` naming and UTC ISO-8601 timestamp formatting.

### Story 1.2: Validate Model Assets and Engine Health at Startup

As a desktop user preparing offline conversion,
I want the application to validate required local model assets and engine health during bootstrap,
So that I know conversion can start reliably without internet access.

**Acceptance Criteria:**

**Given** a local model manifest in `model_manifest.yaml` and registry logic in `model_registry_service.py`
**When** bootstrap validation runs at startup
**Then** each required model is classified with status `installed` `missing` or `invalid`
**And** integrity checks include expected version hash and size.

**Given** TTS providers implementing `tts_provider.py`
**When** health validation is executed through `health_check` on each configured engine
**Then** readiness signals include per-engine availability for Chatterbox GPU and Kokoro CPU fallback
**And** provider-level failures are returned as normalized errors in `errors.py`.

**Given** offline operation is mandatory for MVP FR27 and FR28
**When** one or more required assets are `missing` or `invalid`
**Then** conversion readiness is set to `not_ready`
**And** the service returns actionable remediation details without attempting any cloud call.

**Given** startup diagnostics are required for supportability
**When** registry and health checks complete
**Then** JSONL events are emitted via `jsonl_logger.py` for stages `model_registry` and `engine_health`
**And** events include `correlation_id stage event severity` and ISO-8601 UTC `timestamp`.

### Story 1.3: Surface Offline Readiness Status and Actionable Remediation in UI

As a desktop user before launching conversion,
I want to see clear offline readiness and remediation guidance in the UI,
So that I can fix missing prerequisites and start conversion confidently.

**Acceptance Criteria:**

**Given** startup readiness output from `model_registry_service.py` and provider health checks from `tts_provider.py`
**When** the user opens the conversion entry view in `conversion_view.py`
**Then** the UI shows a deterministic readiness state `ready` or `not_ready`
**And** the active engine availability for Chatterbox GPU and Kokoro CPU is visible.

**Given** one or more assets are `missing` or `invalid`
**When** readiness is rendered in `conversion_presenter.py`
**Then** the user receives actionable remediation messages naming the missing asset and required action
**And** conversion start controls are disabled until status becomes `ready`.

**Given** conversion execution runs on `conversion_worker.py` with Qt signals
**When** readiness changes after a recheck action
**Then** UI status updates through signals without blocking the main UI thread
**And** failures are propagated as normalized errors using `result.py`.

**Given** observability is required for support diagnostics
**When** readiness checks are displayed or rechecked
**Then** JSONL events are emitted by `jsonl_logger.py` using `domain.action` names for `readiness.checked` and `readiness.displayed`
**And** event payload contains `correlation_id stage event severity` and UTC ISO-8601 `timestamp`.

## Epic 2: Multi-Format Import and Text Extraction

Enable users to bring documents from supported formats and obtain clean extractable text with actionable error guidance when extraction fails.

### Story 2.1: Import Local Multi-Format Documents with Input Validation

As a desktop user,
I want to import local EPUB PDF TXT and Markdown files through a single flow,
So that I can start extraction from a supported document without manual preprocessing.

**Acceptance Criteria:**

**Given** the import screen in `import_view.py`
**When** I select a local file with extension `.epub`, `.pdf`, `.txt`, or `.md`
**Then** the file is accepted and forwarded to `import_service.py`
**And** unsupported extensions are rejected with a normalized error from `errors.py`.

**Given** file metadata validation in `import_service.py`
**When** the selected file is unreadable, empty, or missing
**Then** the service returns `{ok, data, error}`
**And** the error includes `{code, message, details, retryable}` with actionable remediation.

**Given** accepted inputs must be traceable for downstream extraction
**When** an import succeeds
**Then** a document record is persisted via `document_repository.py`
**And** fields use `snake_case` conventions and ISO-8601 UTC timestamps.

**Given** observability requirements for import failures
**When** import is accepted or rejected
**Then** JSONL events are emitted via `jsonl_logger.py` using `domain.action` names such as `import.accepted` and `import.rejected`
**And** each event includes `correlation_id`, `stage`, `event`, `severity`, and `timestamp`.

### Story 2.2: Extract Clean Text from EPUB with Actionable Failure Handling

As a user importing an EPUB,
I want the system to extract readable text content reliably,
So that I can proceed to conversion without manual copy cleanup.

**Acceptance Criteria:**

**Given** an imported `.epub` document accepted by `import_service.py`
**When** extraction is executed through `epub_extractor.py`
**Then** textual content is returned in reading order with basic cleanup of empty structural nodes
**And** extraction output is normalized for downstream chunking inputs.

**Given** malformed EPUB structure or unreadable package resources
**When** extraction fails
**Then** the service returns standardized output with `ok=false`
**And** the error follows `{code, message, details, retryable}`.

**Given** extracted content must be auditable for troubleshooting
**When** extraction completes or fails
**Then** events are logged via `jsonl_logger.py` with `stage=extraction` and `engine=epub`
**And** each event includes `correlation_id`, `job_id`, `event`, `severity`, and ISO-8601 UTC `timestamp`.

**Given** the UI must provide immediate feedback
**When** EPUB extraction succeeds or fails
**Then** status and actionable message are surfaced through `conversion_presenter.py`
**And** user-facing text is in English for MVP consistency.

### Story 2.3: Extract Text from PDF with Degraded-Case Handling

As a user importing a PDF,
I want the system to extract usable text and flag degraded cases clearly,
So that I can decide whether to proceed or correct the source document.

**Acceptance Criteria:**

**Given** an imported `.pdf` accepted by `import_service.py`
**When** extraction runs through `pdf_extractor.py`
**Then** text is returned page by page in deterministic order
**And** blank or non-text pages are handled without crashing the extraction flow.

**Given** scanned-image PDFs or partially corrupted structures
**When** extraction quality is insufficient or parsing fails
**Then** the service returns normalized failure
**And** error payload includes `code`, `message`, `details`, and `retryable`.

**Given** the product requires local observability
**When** PDF extraction starts, completes, or fails
**Then** JSONL events are emitted through `jsonl_logger.py` with `stage=extraction` and `engine=pdf`
**And** each event carries `correlation_id`, `job_id`, `chunk_index` when relevant, `event`, `severity`, and UTC ISO-8601 `timestamp`.

**Given** users need clear feedback for remediation
**When** extraction result is rendered in `conversion_presenter.py`
**Then** success and failure messages are explicit and actionable in English
**And** downstream conversion controls remain blocked on extraction failure.

### Story 2.4: Extract and Normalize TXT and Markdown Inputs

As a user importing TXT or Markdown documents,
I want the system to parse and normalize text encoding consistently,
So that extracted content is ready for reliable chunking and synthesis.

**Acceptance Criteria:**

**Given** an imported `.txt` or `.md` file accepted by `import_service.py`
**When** extraction runs through `text_extractor.py`
**Then** UTF-8 content is parsed successfully and normalized line breaks are produced
**And** Markdown structural markers are converted into clean reading text suitable for TTS input.

**Given** files with encoding anomalies or unreadable byte sequences
**When** normalization fails
**Then** the service returns standardized output
**And** errors include `code`, `message`, `details`, and `retryable`.

**Given** very large TXT or Markdown inputs
**When** extraction completes
**Then** output remains deterministic and does not block the UI thread
**And** extracted payload is ready for downstream chunking without extra manual preprocessing.

**Given** observability and user feedback requirements
**When** extraction succeeds or fails
**Then** JSONL events are emitted via `jsonl_logger.py` with `stage=extraction` and `engine=text`
**And** presenter feedback in `conversion_presenter.py` remains actionable and English-only in MVP.

### Story 2.5: Provide Unified Extraction Error Feedback and Diagnostics

As a user performing document import and extraction,
I want extraction failures to be reported consistently with clear remediation guidance,
So that I can quickly resolve issues and retry successfully.

**Acceptance Criteria:**

**Given** extraction outcomes from `epub_extractor.py`, `pdf_extractor.py`, and `text_extractor.py`
**When** any extractor returns a failure
**Then** the failure is mapped into a unified response format `{ok, data, error}`
**And** error payload includes `code`, `message`, `details`, and `retryable`.

**Given** UI error rendering in `conversion_presenter.py`
**When** a normalized extraction error is received
**Then** users see actionable English messages with next-step remediation
**And** retry controls are enabled only when `retryable=true`.

**Given** traceability requirements for diagnostics FR29 and FR30
**When** extraction errors are raised and displayed
**Then** JSONL events are logged by `jsonl_logger.py` with `stage=extraction` and stable `domain.action` names such as `extraction.failed` and `diagnostics.presented`
**And** each log includes `correlation_id`, `job_id`, `engine`, `event`, `severity`, and ISO-8601 UTC `timestamp`.

**Given** MVP scope excludes cloud dependencies
**When** remediation guidance is generated
**Then** all guidance remains local-only and references local corrective actions
**And** no network call is attempted in the error-handling path.

## Epic 3: Resilient Conversion to Audio

Enable users to configure engine voice language and output format, then complete robust long-document conversion through chunking deterministic fallback and resumable processing.

Implementation sequencing note: `Story 3.6` may need to be implemented before or in parallel with `Story 3.5` so configured UI parameters can launch through the QThread execution path without blocking. Story order here reflects requirement grouping, not a mandatory sprint execution order.

### Story 3.1: Implement Unified TTS Provider Contract and Engine Adapters

As a user starting audio conversion,
I want both TTS engines to expose a unified contract,
So that the application can switch engines predictably without changing user workflow.

**Acceptance Criteria:**

**Given** both engines are configured locally
**When** the provider layer is initialized
**Then** a single contract exposes `synthesize_chunk`, `list_voices`, and `health_check`
**And** both engine adapters conform to identical input output semantics.

**Given** engine capability discovery is required for voice selection
**When** available voices are requested
**Then** the response is normalized in a consistent structure
**And** failures return normalized errors with `code`, `message`, `details`, and `retryable`.

**Given** synthesis is executed on a text chunk
**When** a provider succeeds
**Then** audio chunk output and metadata are returned in standardized result format
**And** provider-specific internals are not leaked beyond the adapter boundary.

**Given** an adapter fails during health check or synthesis
**When** the failure is propagated upward
**Then** orchestration receives deterministic error categories for fallback handling
**And** logging emits structured events with correlation fields and UTC timestamps.

### Story 3.2: Segment Long Text with Phrase-First Chunking Rules

As a user converting long documents,
I want text to be split into stable phrase-first chunks,
So that synthesis remains reliable and resumable across large inputs.

**Acceptance Criteria:**

**Given** extracted text is available from import and extraction services
**When** chunking runs in `chunking_service.py`
**Then** chunk boundaries prioritize sentence phrase integrity before max character threshold
**And** produced chunks are deterministic for the same input.

**Given** chunk metadata is needed for orchestration and resume
**When** chunk generation completes
**Then** each chunk gets persisted index ordering and content hash via `chunk_repository.py`
**And** chunk records are linked to the conversion job in SQLite.

**Given** invalid or empty extracted text
**When** chunking is requested
**Then** the service returns normalized failure in `result.py`
**And** errors follow `errors.py` with actionable details and retryability flag.

**Given** observability requirements for conversion pipeline
**When** chunking starts and ends
**Then** JSONL events are emitted by `jsonl_logger.py` with `stage=chunking` and `domain.action` events
**And** payload includes `correlation_id`, `job_id`, `event`, `severity`, and ISO-8601 UTC `timestamp`.

### Story 3.3: Orchestrate Deterministic Conversion with Engine Fallback

As a user launching conversion,
I want the system to orchestrate chunk synthesis with deterministic fallback,
So that conversion can continue when the primary engine fails.

**Acceptance Criteria:**

**Given** chunk records are available and providers implement unified contract
**When** conversion runs in `tts_orchestration_service.py`
**Then** chunks are synthesized in persisted index order
**And** orchestration emits normalized results `{ok, data, error}` for each processing stage.

**Given** primary engine failure on a chunk
**When** fallback rules are evaluated
**Then** fallback from Chatterbox to Kokoro is decided only in orchestration service
**And** provider adapters remain free of fallback policy logic.

**Given** engine and chunk processing events must be diagnosable
**When** orchestration processes each chunk
**Then** JSONL logs include `correlation_id`, `job_id`, `chunk_index`, `engine`, `stage`, `event`, `severity`, `timestamp`
**And** events use `domain.action` naming for start success fail fallback paths.

**Given** fallback cannot recover a chunk
**When** both providers fail for the same chunk
**Then** orchestration returns normalized error payload with deterministic code and retryability
**And** job state transition is delegated to validated service state handling.

### Story 3.4: Persist Job Lifecycle and Resume Conversion from Last Failed Chunk

As a user converting long documents,
I want conversion state to persist with controlled transitions and resume capability,
So that failures do not force restarting from the beginning.

**Acceptance Criteria:**

**Given** a conversion job is created and tracked in persistence
**When** state changes are requested during execution
**Then** only `queued`, `running`, `paused`, `failed`, `completed` transitions accepted by service rules are applied
**And** invalid transitions are rejected with normalized error payload.

**Given** chunk progress is persisted during synthesis
**When** a chunk fails and the job is retried
**Then** orchestration resumes from the last non validated chunk
**And** already successful chunks are not reprocessed unless explicitly requested.

**Given** resume behavior must remain deterministic
**When** retry is executed for the same job inputs
**Then** the same chunk order and state progression are preserved
**And** logs indicate resume start point and retry decision path.

**Given** operators need troubleshooting visibility
**When** job transitions and resume events occur
**Then** JSONL events include `correlation_id`, `job_id`, `chunk_index` when applicable, `stage`, `event`, `severity`, `timestamp`
**And** events use stable domain action naming for transition and resume paths.

### Story 3.5: Configure Conversion Parameters and Output Format in UI

As a user preparing conversion,
I want to select engine voice language speech rate and output format,
So that generated audio matches my preferences and playback context.

**Acceptance Criteria:**

**Given** available engines and voices are exposed by `tts_provider.py`
**When** I open conversion controls in `conversion_view.py`
**Then** I can select engine Chatterbox or Kokoro and a compatible voice
**And** unavailable options are visibly disabled with explanatory guidance.

**Given** MVP language scope and parameter constraints
**When** I configure synthesis options via `conversion_presenter.py`
**Then** selectable languages are limited to FR and EN
**And** speech rate accepts only validated bounds with normalized error feedback on invalid input.

**Given** output generation supports MP3 and WAV
**When** I choose output format before launch
**Then** selected format is persisted with job configuration
**And** orchestration receives normalized settings payload for synthesis and post-processing.

**Given** parameter and format choices must be auditable
**When** configuration is saved or rejected
**Then** JSONL events are emitted by `jsonl_logger.py` with `stage=configuration` and stable `domain.action` events
**And** payload includes `correlation_id`, `job_id`, `event`, `severity`, and ISO-8601 UTC `timestamp`.

### Story 3.6: Execute Conversion in Dedicated Worker with Non-Blocking UI Signals

As a user running long conversion tasks,
I want conversion to run in a dedicated worker thread with live progress feedback,
So that the interface stays responsive while processing continues.

**Acceptance Criteria:**

**Given** conversion starts from the UI
**When** execution is launched through `conversion_worker.py`
**Then** processing runs in a dedicated QThread separate from the UI thread
**And** no blocking operation is performed on the main event loop.

**Given** orchestration emits chunk progress and state updates
**When** worker signals are propagated to `conversion_presenter.py` and `conversion_view.py`
**Then** progress percentage and status are updated incrementally
**And** users can observe running paused failed completed states in near real time.

**Given** runtime errors occur in worker execution
**When** exceptions or normalized failures are received from `tts_orchestration_service.py`
**Then** errors are relayed through Qt signals with normalized payload structure
**And** UI messaging remains actionable and English-only for MVP.

**Given** observability requirements for async execution
**When** worker starts emits progress fails or completes
**Then** JSONL events are written by `jsonl_logger.py` with `stage=worker_execution` and `domain.action` events
**And** each event includes `correlation_id`, `job_id`, `chunk_index` when applicable, `event`, `severity`, and ISO-8601 UTC `timestamp`.

## Epic 4: Local Library and Integrated Playback

Enable users to manage and consume generated audiobooks by storing metadata browsing local content and controlling playback directly in the application.

Implementation sequencing note: `Story 4.1` must be implemented before `Story 4.2` and `Story 4.3` because audio assembly output is required before library persistence and browsing. This story also depends directly on Epic 3 conversion outputs.

### Story 4.1: Assemble Synthesized Chunks into Final Audio Output

As a user completing document conversion,
I want synthesized chunks to be assembled into a single final audio file,
So that I can listen to a continuous audiobook in my selected format.

**Acceptance Criteria:**

**Given** synthesized chunk artifacts are available from orchestration
**When** post-processing runs in `audio_postprocess_service.py`
**Then** chunks are assembled in persisted order without loss or duplication
**And** continuity between chunk boundaries is preserved for listener experience.

**Given** output format is selected as WAV
**When** final rendering executes through `wav_builder.py`
**Then** a valid WAV file is produced at target path
**And** metadata needed for library indexing is returned in normalized response format.

**Given** output format is selected as MP3
**When** encoding executes through `mp3_encoder.py`
**Then** a valid MP3 file is produced at target path
**And** failures return normalized error payload with retryability semantics.

**Given** assembly and encoding are observable pipeline stages
**When** post-processing starts succeeds or fails
**Then** JSONL events are emitted through `jsonl_logger.py` with stable `domain.action` events
**And** event payload includes `correlation_id`, `job_id`, `stage`, `event`, `severity`, and UTC ISO-8601 `timestamp`.

### Story 4.2: Persist Final Audio Artifacts and Library Metadata

As a user who completed conversion,
I want final audio files and metadata to be saved in my local library,
So that I can reliably find and replay generated audiobooks later.

**Acceptance Criteria:**

**Given** a final MP3 or WAV output is generated by `audio_postprocess_service.py`
**When** persistence runs through `library_service.py`
**Then** the audio file path is stored under local runtime library conventions
**And** library metadata is written to SQLite as source of truth.

**Given** metadata persistence uses `library_repository.py`
**When** a new audiobook record is created
**Then** required fields include title source format engine voice language duration and created timestamp
**And** all persisted fields follow `snake_case` naming and ISO-8601 UTC time format.

**Given** persistence can fail due to disk or database errors
**When** write operations fail
**Then** the service returns normalized `{ok, data, error}` with structured error object
**And** partial writes are avoided using transactional behavior.

**Given** observability is required for library integrity
**When** library item creation succeeds or fails
**Then** JSONL events are emitted via `jsonl_logger.py` with `stage=library_persistence`
**And** events include `correlation_id`, `job_id`, `event`, `severity`, and UTC ISO-8601 `timestamp`.

### Story 4.3: Browse and Reopen Audiobooks from Local Library View

As a user with previously converted audiobooks,
I want to browse my local library and reopen an item,
So that I can quickly resume listening without reconversion.

**Acceptance Criteria:**

**Given** library records exist in SQLite
**When** `library_view.py` loads through `library_presenter.py`
**Then** audiobooks are listed with core metadata title source language format created date
**And** listing order is deterministic and stable across refresh.

**Given** a user selects a library item
**When** open action is triggered from library UI
**Then** selected item details and audio path are resolved via `library_service.py`
**And** playback context is prepared without re-running extraction or synthesis.

**Given** missing file path or stale metadata can occur
**When** reopen is requested and audio artifact is unavailable
**Then** user receives actionable normalized error feedback
**And** diagnostics include remediation guidance to relink or reconvert locally.

**Given** library usage events are needed for troubleshooting
**When** list load item open or open failure happens
**Then** JSONL events are emitted with `stage=library_browse`
**And** payload includes `correlation_id`, `event`, `severity`, and UTC ISO-8601 `timestamp`.

### Story 4.4: Integrate Local Audio Playback Service and Adapter

As a user opening a generated audiobook,
I want the app to load and play local audio through a dedicated playback service,
So that playback is reliable across MP3 and WAV outputs.

**Acceptance Criteria:**

**Given** a library item is selected from `library_view.py`
**When** playback initialization is requested in `player_service.py`
**Then** the service resolves local file path and format compatibility
**And** delegates playback operations to `qt_audio_player.py` without bypassing service boundaries.

**Given** the selected audio file is missing unreadable or unsupported
**When** load is attempted
**Then** playback initialization fails with normalized output from `result.py`
**And** error payload format follows `errors.py` with actionable remediation details.

**Given** playback adapter emits runtime status updates
**When** playback starts stops or errors
**Then** status transitions are propagated back through `player_service.py` in deterministic form
**And** UI consumers receive stable state values suitable for presenter rendering.

**Given** playback operations must be diagnosable
**When** load play stop or error events occur
**Then** JSONL events are emitted by `jsonl_logger.py` with `stage=player`
**And** payload includes `correlation_id`, `event`, `severity`, and ISO-8601 UTC `timestamp`.

### Story 4.5: Provide Playback Controls with Pause Resume Seek and Progress

As a user listening to an audiobook,
I want intuitive playback controls and real-time progress,
So that I can navigate content comfortably during listening sessions.

**Acceptance Criteria:**

**Given** playback is initialized through `player_service.py`
**When** I interact with controls in `player_view.py`
**Then** play pause and resume commands are executed successfully
**And** control state remains synchronized with actual player status.

**Given** active playback is running
**When** I seek to a target position
**Then** playback jumps to requested timestamp within valid bounds
**And** out-of-range seek attempts return actionable normalized errors.

**Given** users need temporal awareness
**When** audio is playing or paused
**Then** current time and total duration are displayed and updated consistently
**And** progress bar reflects true playback position without UI blocking.

**Given** playback failures or state changes occur
**When** events are emitted from `qt_audio_player.py`
**Then** presenter and view update deterministically with user-facing English feedback
**And** JSONL logs include `correlation_id`, `event`, `severity`, and UTC ISO-8601 `timestamp`.

## Epic 5: Diagnostics and Failure Transparency

Enable users and operators to understand failures and troubleshoot confidently through structured local observability and accessible diagnostics.

Implementation sequencing note: a minimal JSONL logging skeleton in `jsonl_logger.py` and `event_schema.py` is expected from `Story 1.1` to satisfy earlier epic acceptance criteria. `Story 5.1` and `Story 5.2` should be treated as hardening and completion of observability coverage, not first introduction of logging.

### Story 5.1: Define Correlated JSONL Event Schema and Logging Contract

As a user and support operator,
I want all pipeline events to follow a consistent JSONL schema,
So that failures and performance issues can be diagnosed reliably.

**Acceptance Criteria:**

**Given** logging schema definitions in `event_schema.py`
**When** a pipeline event is emitted
**Then** payload enforces required fields `correlation_id`, `job_id`, `chunk_index`, `engine`, `stage`, `event`, `severity`, `timestamp`
**And** optional fields are explicitly nullable with stable typing.

**Given** logger implementation in `jsonl_logger.py`
**When** events are written to JSONL
**Then** one valid JSON object is persisted per line in append-only mode
**And** timestamps are ISO-8601 UTC.

**Given** naming consistency rules
**When** event names are produced by services
**Then** event names follow `domain.action`
**And** non-conformant events are rejected with normalized error output.

**Given** local diagnostics must work offline
**When** logging runs during conversion and playback flows
**Then** no network call is performed for log shipping
**And** logging failures are surfaced as structured local errors without crashing the UI thread.

### Story 5.2: Instrument End-to-End Pipeline with Correlation Context

As a support-minded user,
I want every pipeline stage to emit correlated events,
So that I can trace a failed conversion from import to playback diagnostics.

**Acceptance Criteria:**

**Given** a conversion job is launched
**When** stages execute across import extraction chunking synthesis postprocess library and player
**Then** each stage emits JSONL events with a shared `correlation_id` and job-scoped context
**And** stage-specific fields include `stage`, `event`, `severity`, and UTC `timestamp`.

**Given** chunk-level processing occurs in orchestration
**When** chunk events are emitted
**Then** payload includes `chunk_index` and active `engine`
**And** event sequences remain ordered enough to reconstruct chunk lifecycle.

**Given** failures can happen at any stage
**When** an error is raised
**Then** the emitted event carries normalized error envelope fields `code`, `message`, `details`, `retryable`
**And** error and success events share the same schema contract.

**Given** instrumentation must not degrade UX
**When** event writing is active during long conversions
**Then** UI responsiveness is preserved and worker flow remains non-blocking
**And** logging backpressure failures are handled locally with structured fallback behavior.

### Story 5.3: Present Actionable Failure Diagnostics in Conversion UI

As a user facing a failed conversion,
I want clear diagnostics in the interface,
So that I can understand what failed and what to do next.

**Acceptance Criteria:**

**Given** orchestration returns normalized errors with `code`, `message`, `details`, `retryable`
**When** failure state is rendered by `conversion_presenter.py`
**Then** UI shows concise error summary plus expandable details
**And** remediation guidance is actionable and English-only.

**Given** failure can occur at extraction chunking tts postprocess or persistence stages
**When** diagnostics are displayed
**Then** stage and engine context are visible to user when available
**And** retry recommendation reflects actual `retryable` value.

**Given** a user requests deeper diagnostics from the failure panel
**When** details are opened
**Then** related `correlation_id` and job context are surfaced for local support troubleshooting
**And** no raw internal trace is shown unless marked safe for user display.

**Given** diagnostics display must be observable
**When** failure panel is shown or user triggers retry
**Then** JSONL events are emitted with `stage=diagnostics_ui` and domain action naming
**And** payload includes `correlation_id`, `job_id`, `event`, `severity`, and UTC ISO-8601 `timestamp`.

### Story 5.4: Provide Local Support Workflow for Error Review and Guided Remediation

As a user troubleshooting repeated conversion failures,
I want a local support workflow that explains error codes and next steps,
So that I can resolve issues without external tools or cloud services.

**Acceptance Criteria:**

**Given** a failed job with persisted error context
**When** support details are opened from the diagnostics UI
**Then** user can view normalized fields `code`, `message`, `details`, and `retryable`
**And** remediation guidance is matched to error category extraction chunking engine export persistence.

**Given** retry decisions must be explicit
**When** an error is marked `retryable=true`
**Then** UI presents retry action with clear prerequisites
**And** non-retryable failures present alternative guidance such as re-import, model repair, or settings correction.

**Given** support workflow is local-first MVP
**When** guidance is displayed
**Then** all recommendations reference local actions only
**And** no external API call or cloud submission path is used.

**Given** support interactions must be traceable
**When** diagnostics are viewed copied or retry is initiated
**Then** JSONL events are emitted with `stage=support_workflow` and `domain.action` naming
**And** payload includes `correlation_id`, `job_id`, `event`, `severity`, and UTC ISO-8601 `timestamp`.
