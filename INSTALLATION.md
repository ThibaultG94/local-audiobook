# Installation (Python 3.12 + ROCm 7.2)

This guide installs the production TTS stack for Local Audiobook:

- **Chatterbox** on AMD GPU (ROCm 7.2)
- **Kokoro ONNX** on CPU fallback

## 1) System requirements

- Linux Mint (target distro)
- Python **3.12**
- ROCm **7.2** (for GPU path)
- AMD GPU (optional, CPU-only mode is supported)

## 2) Create environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e .
```

## 3) Install PyTorch 2.9.1 ROCm wheels (Radeon repo)

Use Radeon ROCm wheels for ROCm 7.2:

```bash
pip uninstall -y torch torchvision torchaudio triton pytorch-triton-rocm
pip install --no-cache-dir \
  --extra-index-url https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2/ \
  torch==2.9.1 torchvision==0.24.1 torchaudio==2.9.1
```

## 4) Install Triton ROCm (required)

```bash
pip install --no-cache-dir pytorch-triton-rocm
```

## 5) Install Chatterbox from source (with relaxed NumPy pin)

```bash
git clone https://github.com/resemble-ai/chatterbox.git runtime/chatterbox-src
sed -i -E 's/numpy([<>=!~ ,0-9.]+)/numpy>=1.26,<3/g' runtime/chatterbox-src/pyproject.toml
pip install -e runtime/chatterbox-src
```

## 6) Install Kokoro ONNX (CPU fallback)

```bash
pip install --no-cache-dir kokoro-onnx soundfile
```

## 7) Verification

### 7.1 Runtime checks

```bash
python - <<'PY'
import torch
print('torch', torch.__version__)
print('cuda_available', torch.cuda.is_available())
print('device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')
PY
```

### 7.2 Test suite

```bash
pytest tests/ -q
```

Expected: **270 passed**.

### 7.3 Model manifest readiness

```bash
python - <<'PY'
from src.domain.services.model_registry_service import ModelRegistryService

result = ModelRegistryService().validate_models('config/model_manifest.yaml')
if not result.ok:
    raise SystemExit(result.error)

summary = result.data['summary']
print(summary)
assert summary.get('installed') == 3, summary
assert summary.get('missing') == 0, summary
assert summary.get('invalid') == 0, summary
print('model_manifest: 3/3 installed')
PY
```

## 8) Notes

- If you run CPU-only, skip ROCm/PyTorch GPU validation and keep Kokoro ONNX active.
- `config/model_manifest.yaml` must point to real local model files (path/hash/size) for startup readiness to be `ready`.

## 9) Run the application

```bash
python -m src.app.main
```
