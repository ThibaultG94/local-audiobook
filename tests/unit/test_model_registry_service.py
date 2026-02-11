from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from domain.services.model_registry_service import ModelRegistryService


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class TestModelRegistryService(unittest.TestCase):
    def test_classifies_models_as_installed_missing_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            installed_path = base / "runtime" / "models" / "installed.bin"
            installed_path.parent.mkdir(parents=True, exist_ok=True)
            installed_bytes = b"installed-model"
            installed_path.write_bytes(installed_bytes)

            invalid_path = base / "runtime" / "models" / "invalid.bin"
            invalid_bytes = b"invalid-model"
            invalid_path.write_bytes(invalid_bytes)

            missing_path = base / "runtime" / "models" / "missing.bin"

            manifest = base / "model_manifest.yaml"
            manifest.write_text(
                "\n".join(
                    [
                        "models:",
                        "  - name: installed",
                        "    engine: chatterbox_gpu",
                        "    version: '1.0.0'",
                        f"    expected_hash: '{_sha256(installed_bytes)}'",
                        f"    expected_size: {len(installed_bytes)}",
                        f"    local_path: {installed_path}",
                        "  - name: missing",
                        "    engine: chatterbox_gpu",
                        "    version: '1.0.0'",
                        "    expected_hash: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'",
                        "    expected_size: 10",
                        f"    local_path: {missing_path}",
                        "  - name: invalid",
                        "    engine: kokoro_cpu",
                        "    version: '1.0.0'",
                        "    expected_hash: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'",
                        f"    expected_size: {len(invalid_bytes)}",
                        f"    local_path: {invalid_path}",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = ModelRegistryService().validate_models(str(manifest))
            self.assertTrue(result.ok)
            self.assertIsNotNone(result.data)

            statuses = {item["name"]: item["status"] for item in result.data["models"]}
            self.assertEqual(statuses["installed"], "installed")
            self.assertEqual(statuses["missing"], "missing")
            self.assertEqual(statuses["invalid"], "invalid")

    def test_returns_normalized_error_when_manifest_missing(self) -> None:
        missing_manifest = "does-not-exist-model-manifest.yaml"
        result = ModelRegistryService().validate_models(missing_manifest)

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        payload = result.error.to_dict()
        self.assertEqual(payload["code"], "model_manifest_not_found")
        self.assertIn("manifest", payload["message"].lower())
        self.assertIn("manifest_path", payload["details"])

    def test_integrity_mismatch_contains_actionable_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            file_path = base / "runtime" / "models" / "mismatch.bin"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"abc")

            manifest = base / "model_manifest.yaml"
            manifest.write_text(
                "\n".join(
                    [
                        "models:",
                        "  - name: mismatch",
                        "    engine: chatterbox_gpu",
                        "    version: '1.0.0'",
                        "    expected_hash: 'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'",
                        "    expected_size: 999",
                        f"    local_path: {file_path}",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = ModelRegistryService().validate_models(str(manifest))
            self.assertTrue(result.ok)
            self.assertIsNotNone(result.data)
            model = result.data["models"][0]
            self.assertEqual(model["status"], "invalid")
            self.assertIn("size_mismatch", model["issues"])
            self.assertIn("hash_mismatch", model["issues"])

