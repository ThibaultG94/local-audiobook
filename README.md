# Local Audiobook

Desktop Python application (PyQt5) that converts documents into audiobooks, fully offline.

## What it does

- Import and process **EPUB / PDF / TXT / MD** files
- Generate audio with:
  - **Chatterbox** on GPU (AMD ROCm)
  - **Kokoro** on CPU (`kokoro-onnx`) fallback
- Manage a local audiobook library (metadata + generated audio)
- Run 100% locally (no cloud dependency)

## Requirements

- **OS**: Linux Mint (target environment)
- **Python**: 3.12
- **Runtime**:
  - AMD GPU with ROCm 7.2 (recommended), or
  - CPU-only mode

## Quick start

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e .
python -m src.app.main
```

For full GPU/CPU engine setup (ROCm 7.2, PyTorch 2.9.1, Chatterbox build-from-source, Triton ROCm, Kokoro ONNX), use [`INSTALLATION.md`](INSTALLATION.md).

## Architecture (overview)

The codebase follows a **hexagonal architecture (ports and adapters)**:

- **Domain** (`src/domain`): business rules and ports
- **Application** (`src/app`): dependency wiring and startup
- **Adapters** (`src/adapters`, `src/infrastructure`): persistence, extraction, logging, TTS integrations
- **UI** (`src/ui`): PyQt5 presenters, views, workers

Core flow: input import → normalized text extraction → chunking/orchestration → TTS provider → audio assembly → library persistence.

## Repository structure

Contributor-facing structure aligned with the current implementation:

- `config/`: local YAML configuration (including model manifest)
- `migrations/`: SQLite schema migration scripts
- `runtime/`: local runtime artifacts (for example local source builds)
- `src/`: application source code (`app`, `domain`, `adapters`, `infrastructure`, `ui`)
- `tests/`: unit and integration test suites

The application is offline-first and local-only by design: no cloud service is required for normal execution.

## License

MIT
