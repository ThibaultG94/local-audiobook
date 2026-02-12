"""Model manifest loading and local integrity classification service."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from contracts.result import Result, failure, success

try:
    import yaml
except ImportError:  # pragma: no cover - optional at runtime
    yaml = None


class ModelRegistryService:
    """Validate required local model assets from a YAML manifest."""

    def validate_models(self, manifest_path: str | Path) -> Result[dict[str, Any]]:
        """Classify each model in the manifest as installed, missing, or invalid.

        Returns ``Result(ok=True, data=...)`` when the manifest was successfully
        parsed and every model was classified — even if some models are missing
        or invalid.  Callers MUST inspect ``data["has_missing_or_invalid"]`` to
        determine whether the system is ready for conversion.

        Returns ``Result(ok=False, ...)`` only when the manifest itself cannot
        be loaded or parsed (i.e. infrastructure-level failure).
        """
        manifest = Path(manifest_path)
        if not manifest.exists():
            return failure(
                code="model_manifest_not_found",
                message="Model manifest file is missing",
                details={"manifest_path": str(manifest)},
                retryable=False,
            )

        try:
            parsed = self._load_manifest(manifest)
        except Exception as exc:
            return failure(
                code="model_manifest_parse_error",
                message="Unable to parse model manifest",
                details={"manifest_path": str(manifest), "reason": str(exc)},
                retryable=False,
            )

        if not isinstance(parsed, dict):
            return failure(
                code="model_manifest_invalid_schema",
                message="Model manifest root must be a mapping",
                details={"manifest_path": str(manifest)},
                retryable=False,
            )

        model_items = parsed.get("models")
        if not isinstance(model_items, list):
            return failure(
                code="model_manifest_invalid_schema",
                message="Model manifest must contain a models list",
                details={"manifest_path": str(manifest), "field": "models"},
                retryable=False,
            )

        classified: list[dict[str, Any]] = []
        for raw_model in model_items:
            if not isinstance(raw_model, dict):
                classified.append(
                    {
                        "name": "unknown",
                        "engine": "unknown",
                        "version": "unknown",
                        "status": "invalid",
                        "path": "",
                        "issues": ["manifest_entry_invalid"],
                        "remediation": "Fix model manifest entry format",
                    }
                )
                continue

            name = str(raw_model.get("name", "unknown"))
            engine = str(raw_model.get("engine", "unknown"))
            version = str(raw_model.get("version", "unknown"))
            local_path = Path(str(raw_model.get("local_path", "")))
            expected_hash = str(raw_model.get("expected_hash", ""))
            expected_size = raw_model.get("expected_size", 0)

            issues: list[str] = []
            actual_size = 0
            actual_hash = ""

            if not local_path.exists():
                status = "missing"
                issues.append("file_missing")
            else:
                actual_size = local_path.stat().st_size
                if actual_size <= 0:
                    issues.append("file_empty")

                try:
                    expected_size_int = int(expected_size)
                except (TypeError, ValueError):
                    expected_size_int = -1
                    issues.append("manifest_expected_size_invalid")

                if expected_size_int >= 0 and actual_size != expected_size_int:
                    issues.append("size_mismatch")

                actual_hash = self._sha256(local_path)
                if actual_hash != expected_hash:
                    issues.append("hash_mismatch")

                status = "installed" if not issues else "invalid"

            classified.append(
                {
                    "name": name,
                    "engine": engine,
                    "version": version,
                    "status": status,
                    "path": str(local_path),
                    "expected_hash": expected_hash,
                    "expected_size": expected_size,
                    "actual_hash": actual_hash,
                    "actual_size": actual_size,
                    "issues": issues,
                    "remediation": self._build_remediation(local_path, issues),
                }
            )

        has_missing_or_invalid = any(item["status"] in {"missing", "invalid"} for item in classified)
        return success(
            {
                "models": classified,
                "summary": {
                    "installed": sum(1 for item in classified if item["status"] == "installed"),
                    "missing": sum(1 for item in classified if item["status"] == "missing"),
                    "invalid": sum(1 for item in classified if item["status"] == "invalid"),
                },
                "has_missing_or_invalid": has_missing_or_invalid,
            }
        )

    def _load_manifest(self, manifest: Path) -> dict[str, Any]:
        if yaml is not None:
            loaded = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            return loaded if loaded is not None else {}
        return self._fallback_manifest_loader(manifest)

    @staticmethod
    def _fallback_manifest_loader(manifest: Path) -> dict[str, Any]:
        """Very small fallback parser for model_manifest.yaml list format."""
        lines = manifest.read_text(encoding="utf-8").splitlines()
        models: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None

        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            if line == "models:":
                continue

            if line.startswith("- "):
                if current is not None:
                    models.append(current)
                current = {}
                remainder = line[2:].strip()
                if remainder and ":" in remainder:
                    key, value = remainder.split(":", 1)
                    current[key.strip()] = ModelRegistryService._parse_scalar(value.strip())
                continue

            if current is None:
                continue

            if ":" in line:
                key, value = line.split(":", 1)
                current[key.strip()] = ModelRegistryService._parse_scalar(value.strip())

        if current is not None:
            models.append(current)

        return {"models": models}

    @staticmethod
    def _parse_scalar(value: str) -> Any:
        cleaned = value.strip().strip('"').strip("'")
        if cleaned.lower() in {"null", "none", "~"}:
            return None
        if cleaned.lower() == "true":
            return True
        if cleaned.lower() == "false":
            return False
        if cleaned.isdigit() or (cleaned.startswith("-") and cleaned[1:].isdigit()):
            return int(cleaned)
        return cleaned

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as src:
            for chunk in iter(lambda: src.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _build_remediation(path: Path, issues: list[str]) -> str:
        if "file_missing" in issues:
            return f"Provide model file at {path}"
        if "file_empty" in issues:
            return f"Replace empty model file at {path}"
        if "size_mismatch" in issues and "hash_mismatch" in issues:
            return f"Replace corrupted model file at {path} with the expected version"
        if "size_mismatch" in issues:
            return f"Replace model file at {path} with correct size"
        if "hash_mismatch" in issues:
            return f"Replace model file at {path} with matching hash"
        if "manifest_expected_size_invalid" in issues:
            return "Fix expected_size in model manifest"
        if "manifest_entry_invalid" in issues:
            return "Fix malformed model entry in manifest"
        return "No remediation required"
