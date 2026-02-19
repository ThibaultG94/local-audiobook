# Hotfix — Conversion Pipeline Runtime Failures

**Date:** 2026-02-19  
**Type:** Post-Epic-6 Hotfix  
**Status:** ✅ Resolved  
**Tests:** 294/294 passing

---

## Problem Statement

After Epic 6 delivery, the conversion pipeline still crashed at runtime with a `ProgrammingError` when clicking **Convert**. The support details JSON exposed two distinct root causes that were not caught by the BMAD agent during Epic 6 because it did not test through the actual running application.

```json
{
  "exception_type": "ProgrammingError",
  "document_id": "ui_document",
  "conversion_config": {
    "engine": "kokoro_cpu",
    "voice_id": "ff_siwis",
    "language": "FR",
    "speech_rate": 0.5,
    "output_format": "mp3"
  }
}
```

---

## Root Causes

### Bug 1 — SQLite Thread Safety

**File:** [`src/adapters/persistence/sqlite/connection.py`](../../src/adapters/persistence/sqlite/connection.py)

SQLite3 raises `ProgrammingError: SQLite objects created in a thread can only be used in that same thread` by default. The connection was created on the main thread in `bootstrap()` but used inside a `ThreadPoolExecutor` worker during TTS conversion.

**Fix:** Added `check_same_thread=False` to `sqlite3.connect()`.

```python
# Before
connection = sqlite3.connect(db_path)
# After
connection = sqlite3.connect(str(db_path), check_same_thread=False)
```

SQLite WAL mode (already enabled) makes concurrent reads safe.

---

### Bug 2 — Incomplete Pipeline: Missing Extraction + Chunking Step

**File:** [`src/ui/workers/conversion_worker.py`](../../src/ui/workers/conversion_worker.py)

`launch_conversion` called `synthesize_persisted_chunks_for_job` but **no extraction or chunking had ever been performed**. The `chunks` table was empty, causing an immediate failure with `tts_orchestration.no_persisted_chunks`.

The pipeline was missing the mandatory steps:

1. Fetch document record from `documents` table
2. Extract text via `ImportService.extract_document()`
3. Chunk text and persist via `TtsOrchestrationService.chunk_text_for_job()`

**Fix:** Added `_extract_and_chunk()` method to `ConversionWorker`, called as the first step of `_run_conversion()` before `_prepare_conversion_launch()`.

Three new ports added to the worker:

- `DocumentsRepositoryPort` — fetches document by id
- `ImportServicePort` — extracts text from document
- `TtsOrchestrationPort` — chunks text and persists chunks

When these services are not wired (legacy tests), the step is skipped gracefully (`success({"skipped": True})`), preserving backward compatibility.

---

### Bug 3 — Hardcoded `document_id = "ui_document"`

**Files:**

- [`src/ui/widgets/conversion_widget.py`](../../src/ui/widgets/conversion_widget.py)
- [`src/ui/widgets/import_widget.py`](../../src/ui/widgets/import_widget.py)
- [`src/ui/main_window.py`](../../src/ui/main_window.py)
- [`src/app/dependency_container.py`](../../src/app/dependency_container.py)
- [`src/app/main.py`](../../src/app/main.py)

`ConversionWidget._document_id` was hardcoded to `"ui_document"` which does not exist in the `documents` table. The Import tab and Conversion tab were completely disconnected.

**Fix:** Wired the Import → Conversion flow using a Qt signal:

1. `ImportWidget` emits `document_imported(str)` signal after a successful import
2. `ConversionWidget.set_document_id()` receives the real `document_id`
3. `MainWindow` connects `import_widget.document_imported → conversion_widget.set_document_id`
4. `ConversionWidget` blocks the Convert button until a document is imported
5. `build_conversion_worker()` now receives `import_service`, `documents_repository`, and `tts_orchestration`
6. `main.py` passes `import_service` to the worker

---

## Corrected End-to-End Flow

```
[Import tab]
  User selects file → ImportWidget → ImportService.import_document()
  → document persisted in DB → document_imported signal emitted
  → ConversionWidget.set_document_id(real_id)

[Conversion tab]
  User clicks Convert → ConversionWidget._on_convert_clicked()
  → execute_conversion_async(document_id=real_id, ...)
  → _run_conversion()
    1. _extract_and_chunk()
       a. documents_repository.get_document_by_id(document_id)
       b. import_service.extract_document(document)
       c. tts_orchestration.chunk_text_for_job(text, job_id)
    2. _prepare_conversion_launch()  ← creates job record in DB
    3. _invoke_launcher()
       → TtsOrchestrationService.launch_conversion()
         → synthesize_persisted_chunks_for_job()  ← chunks now exist ✓
         → audio_postprocess_service.assemble_and_render()
         → library_service.persist_final_artifact()
```

---

## Files Changed

| File                                                                                                   | Change                                                                                                                                                                                                                                          |
| ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`src/adapters/persistence/sqlite/connection.py`](../../src/adapters/persistence/sqlite/connection.py) | Added `check_same_thread=False` to `sqlite3.connect()`                                                                                                                                                                                          |
| [`src/ui/workers/conversion_worker.py`](../../src/ui/workers/conversion_worker.py)                     | Added `DocumentsRepositoryPort`, `ImportServicePort`, `TtsOrchestrationPort` protocols; added `documents_repository`, `import_service`, `tts_orchestration` fields; added `_extract_and_chunk()` method; called it first in `_run_conversion()` |
| [`src/ui/widgets/import_widget.py`](../../src/ui/widgets/import_widget.py)                             | Added `document_imported = pyqtSignal(str)` signal; emit it after successful import                                                                                                                                                             |
| [`src/ui/widgets/conversion_widget.py`](../../src/ui/widgets/conversion_widget.py)                     | Replaced hardcoded `"ui_document"` with `""`; added `set_document_id()` method; guard in `_on_convert_clicked()`                                                                                                                                |
| [`src/ui/main_window.py`](../../src/ui/main_window.py)                                                 | Connected `import_widget.document_imported → conversion_widget.set_document_id`                                                                                                                                                                 |
| [`src/app/dependency_container.py`](../../src/app/dependency_container.py)                             | `build_conversion_worker()` now accepts and wires `import_service`, `documents_repository`, `tts_orchestration`                                                                                                                                 |
| [`src/app/main.py`](../../src/app/main.py)                                                             | Passes `import_service` to `build_conversion_worker()`                                                                                                                                                                                          |

---

## Test Results

```
294 passed, 1 warning in 296.30s
```

All 294 existing tests pass. No regressions introduced. Backward compatibility preserved for tests that do not wire the extraction pipeline.

---

## Lessons Learned

1. **BMAD agents must test through the running application**, not just unit tests. Both bugs were invisible to the test suite because tests inject pre-populated chunks and bypass the UI flow entirely.

2. **UI wiring gaps are not caught by unit tests.** The hardcoded `"ui_document"` and the missing Import→Conversion signal connection required manual application testing to discover.

3. **SQLite `check_same_thread=False` is mandatory for any multi-threaded desktop app.** This should be part of the initial connection setup, not discovered at runtime.
