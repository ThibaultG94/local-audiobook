# Hotfix — Engine Routing and FK Ordering Failures (2026-02-19)

Date: 2026-02-19T14:57:00+01:00

## Problem Statement

After the first hotfix (`hotfix-conversion-pipeline-2026-02-19.md`), two additional runtime
failures were discovered through real end-to-end tests that launch the full application stack
via `bootstrap()` with real TTS providers (Kokoro CPU).

---

## Bug 1 — SQLite FK Violation: Chunks Inserted Before Job Exists

### Symptom

```
exception_type: "IntegrityError"
FOREIGN KEY constraint failed
```

Chunks were inserted into the `chunks` table before the parent row existed in
`conversion_jobs`, violating the `FOREIGN KEY(job_id) REFERENCES conversion_jobs(id)`
constraint defined in [`0001_initial_schema.sql`](../../migrations/0001_initial_schema.sql).

### Root Cause

In [`_run_conversion()`](../../src/ui/workers/conversion_worker.py:309), the call order was:

```python
# BEFORE (broken)
self._extract_and_chunk(...)      # inserts chunks → FK violation
self._prepare_conversion_launch(...)  # creates job row
self._invoke_launcher(...)
```

### Fix

Swapped the order so the job row is created first:

```python
# AFTER (fixed)
self._prepare_conversion_launch(...)  # creates job row first
self._extract_and_chunk(...)          # inserts chunks safely
self._invoke_launcher(...)
```

**File changed:** [`src/ui/workers/conversion_worker.py`](../../src/ui/workers/conversion_worker.py)

---

## Bug 2 — Wrong Engine Selected: Fallback Policy Bypasses User Engine Choice

### Symptom

```json
{
  "attempted_engines": ["chatterbox_gpu"],
  "primary_error": {
    "code": "tts_voice_invalid",
    "message": "Voice 'ff_siwis' is not available for engine chatterbox_gpu"
  }
}
```

When the user explicitly selected `kokoro_cpu` with voice `ff_siwis`, the orchestration
service still tried Chatterbox (the primary provider) first. Chatterbox rejected the voice
with error code `tts_voice_invalid` (category `input`). Since `_should_fallback()` only
triggers on `category == "availability"`, Kokoro was never tried and the conversion failed
with `tts_orchestration.chunk_failed_unrecoverable`.

### Root Cause

[`_synthesize_with_policy()`](../../src/domain/services/tts_orchestration_service.py:738)
always started with the primary provider regardless of the `engine` parameter passed by the
user. The `engine` parameter was accepted but never used to route to the correct provider.

### Fix

Added `_resolve_provider_for_engine()` method and engine-specific routing at the top of
`_synthesize_with_policy()`:

```python
def _resolve_provider_for_engine(self, engine: str) -> "TtsProvider | None":
    """Return the provider whose engine_name matches the requested engine."""
    if not engine:
        return None
    if self._primary_provider is not None and self._primary_provider.engine_name == engine:
        return self._primary_provider
    if self._fallback_provider is not None and self._fallback_provider.engine_name == engine:
        return self._fallback_provider
    return None
```

When `engine` is specified, `_synthesize_with_policy()` now routes directly to the matching
provider and skips the primary→fallback chain entirely:

```python
requested_provider = self._resolve_provider_for_engine(engine)
if requested_provider is not None:
    trace["attempted_engines"] = [requested_provider.engine_name]
    result = requested_provider.synthesize_chunk(text, voice, ...)
    trace["selected_engine"] = requested_provider.engine_name
    if result.ok:
        return result, trace
    trace["primary_error"] = result.error.to_dict() if result.error else {}
    return result, trace
# fallthrough: no engine specified → primary→fallback chain as before
```

The `engine` parameter was also threaded through the call chain:

- [`launch_conversion(engine="")`](../../src/domain/services/tts_orchestration_service.py:127)
- [`synthesize_persisted_chunks_for_job(engine="")`](../../src/domain/services/tts_orchestration_service.py:255)
- [`_synthesize_with_policy(engine="")`](../../src/domain/services/tts_orchestration_service.py:738)

**File changed:** [`src/domain/services/tts_orchestration_service.py`](../../src/domain/services/tts_orchestration_service.py)

---

## End-to-End Test Suite Added

A real end-to-end test suite was created to catch these classes of failures before they reach
production. The tests use the real `bootstrap()` function and real Kokoro CPU provider.

### Test files

| File                                                                                           | Description                                                                    |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| [`tests/e2e/test_real_pipeline.py`](../../tests/e2e/test_real_pipeline.py)                     | 3 real pipeline tests (Kokoro FR TXT→MP3, Kokoro EN TXT→WAV, Kokoro FR MD→MP3) |
| [`tests/e2e/test_conversion_pipeline_e2e.py`](../../tests/e2e/test_conversion_pipeline_e2e.py) | 17 stub-provider tests covering FK regression, ordering, pipeline TXT/MD       |
| [`tests/e2e/fixtures/sample_short.txt`](../../tests/e2e/fixtures/sample_short.txt)             | Short TXT fixture                                                              |
| [`tests/e2e/fixtures/sample_medium.txt`](../../tests/e2e/fixtures/sample_medium.txt)           | Multi-chapter TXT fixture                                                      |
| [`tests/e2e/fixtures/sample.md`](../../tests/e2e/fixtures/sample.md)                           | Markdown fixture                                                               |

### Key design decisions

- `scope="module"` fixtures for expensive `bootstrap()` calls (Kokoro model load ~2–5 s)
- Detailed failure messages expose `error_code`, `error_message`, `job_state`, and per-chunk
  status to accelerate diagnosis
- `StubTtsProvider` inherits from `BaseTtsProvider` to respect the `audio_bytes` contract
  (not `audio_data`) enforced by `AudioPostprocessService._extract_synthesis_payload()`

---

## Test Results

```
314 passed in Xs
```

- 17 e2e stub-provider tests: **pass**
- 3 e2e real-pipeline tests (Kokoro): **pass**
- 294 unit + integration tests: **pass**

---

## Files Changed

| File                                                                                                         | Change                                                                                                                            |
| ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| [`src/ui/workers/conversion_worker.py`](../../src/ui/workers/conversion_worker.py)                           | Swapped `_prepare_conversion_launch` before `_extract_and_chunk`                                                                  |
| [`src/domain/services/tts_orchestration_service.py`](../../src/domain/services/tts_orchestration_service.py) | Added `_resolve_provider_for_engine()`, engine routing in `_synthesize_with_policy()`, `engine` param threaded through call chain |
| [`tests/e2e/test_real_pipeline.py`](../../tests/e2e/test_real_pipeline.py)                                   | New: 3 real pipeline tests                                                                                                        |
| [`tests/e2e/test_conversion_pipeline_e2e.py`](../../tests/e2e/test_conversion_pipeline_e2e.py)               | New: 17 stub-provider e2e tests                                                                                                   |
| [`tests/e2e/__init__.py`](../../tests/e2e/__init__.py)                                                       | New: package marker                                                                                                               |
| [`tests/e2e/fixtures/sample_short.txt`](../../tests/e2e/fixtures/sample_short.txt)                           | New: short TXT fixture                                                                                                            |
| [`tests/e2e/fixtures/sample_medium.txt`](../../tests/e2e/fixtures/sample_medium.txt)                         | New: multi-chapter TXT fixture                                                                                                    |
| [`tests/e2e/fixtures/sample.md`](../../tests/e2e/fixtures/sample.md)                                         | New: Markdown fixture                                                                                                             |

---

## Lessons Learned

1. **FK ordering must be enforced at the call site, not just the schema.** The schema
   correctly declared the FK constraint; the bug was in the caller's ordering assumption.

2. **Engine selection must be explicit, not implicit.** When a user selects a specific engine,
   the orchestration layer must honour that choice directly rather than relying on the
   primary→fallback chain to eventually reach the right provider.

3. **Real e2e tests are essential.** Unit and integration tests with mocked providers cannot
   catch cross-layer wiring bugs. Only tests that exercise the full `bootstrap()` → worker →
   orchestration → provider → postprocess chain can surface these failures.

4. **Provider contract must be respected by test doubles.** `StubTtsProvider` must inherit
   from `BaseTtsProvider` (not implement the protocol directly) to guarantee the `audio_bytes`
   key in the synthesis payload, matching what `AudioPostprocessService` expects.
