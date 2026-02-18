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

For full GPU/CPU engine setup (ROCm 7.2, PyTorch 2.9.1, Chatterbox build-from-source, Triton ROCm, Kokoro ONNX), see [INSTALLATION.md](INSTALLATION.md).

For development, install test dependencies:

```bash
pip install -e ".[dev]"
```

## Architecture (overview)

The codebase follows a **hexagonal architecture (ports and adapters)**:

- **Contracts** (`src/contracts`): shared result types, constants, and cross-cutting contracts
- **Domain** (`src/domain`): business services and port interfaces
- **Application** (`src/app`): dependency injection container and startup orchestration
- **Adapters** (`src/adapters`): external integrations (extraction, TTS, playback)
- **Infrastructure** (`src/infrastructure`): persistence (SQLite repositories) and logging
- **UI** (`src/ui`): PyQt5 presenters, views, and background workers

Core flow: document import → text extraction → chunking → TTS synthesis → audio assembly → library persistence → playback.

## Repository structure

Contributor-facing structure aligned with the current implementation:

- `config/`: local YAML configuration (app config, logging config, model manifest)
- `migrations/`: SQLite schema migration scripts
- `runtime/`: local runtime artifacts (e.g., Chatterbox source builds)
- `src/`: application source code
  - `app/`: dependency container and main entry point
  - `contracts/`: shared result types and constants
  - `domain/`: business services and port interfaces
  - `adapters/`: external integrations (extraction, TTS, playback)
  - `infrastructure/`: persistence (SQLite) and logging
  - `ui/`: PyQt5 presenters, views, and workers
- `tests/`: unit and integration test suites
- `pyproject.toml`: project metadata and dependencies
- `.python-version`: Python version pinning (3.12)

The application is offline-first and local-only by design: no cloud service is required for normal execution.

## License

MIT
