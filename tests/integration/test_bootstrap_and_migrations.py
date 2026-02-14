from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.main import bootstrap


def _write_config_files(base_dir: Path) -> tuple[Path, Path]:
    app_config = base_dir / "app_config.yaml"
    logging_config = base_dir / "logging_config.yaml"

    app_config.write_text(
        "\n".join(
            [
                "app:",
                "  name: local-audiobook",
                "  environment: local",
                "paths:",
                f"  runtime_dir: {base_dir / 'runtime'}",
                f"  database_path: {base_dir / 'runtime' / 'local_audiobook.db'}",
                "  migrations_dir: migrations",
                f"  logs_dir: {base_dir / 'runtime' / 'logs'}",
                f"  library_audio_dir: {base_dir / 'runtime' / 'library' / 'audio'}",
                f"  library_temp_dir: {base_dir / 'runtime' / 'library' / 'temp'}",
                "bootstrap:",
                "  apply_migrations_on_startup: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    logging_config.write_text(
        "\n".join(
            [
                "logging:",
                f"  file_path: {base_dir / 'runtime' / 'logs' / 'events.jsonl'}",
                "  logger_type: jsonl",
                "  level: INFO",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return app_config, logging_config


def _get_tables(connection: sqlite3.Connection) -> set[str]:
    cursor = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    return {row[0] for row in cursor.fetchall()}


def _write_manifest_with_invalid_asset(base_dir: Path) -> Path:
    models_dir = base_dir / "runtime" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    existing = models_dir / "existing.bin"
    existing.write_bytes(b"asset-present-but-invalid")

    invalid_hash = hashlib.sha256(b"different-content").hexdigest()
    manifest = base_dir / "model_manifest.yaml"
    manifest.write_text(
        "\n".join(
            [
                "models:",
                "  - name: required-model",
                "    engine: chatterbox_gpu",
                "    version: '1.0.0'",
                f"    expected_hash: '{invalid_hash}'",
                f"    expected_size: {len(b'different-content')}",
                f"    local_path: {existing}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return manifest


class TestBootstrapAndMigrationsIntegration(unittest.TestCase):
    def test_fresh_bootstrap_creates_database_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            app_config, logging_config = _write_config_files(tmp_path)

            container = bootstrap(str(app_config), str(logging_config))
            db_path = tmp_path / "runtime" / "local_audiobook.db"

            self.assertTrue(db_path.exists())

            tables = _get_tables(container.connection)
            self.assertTrue(
                {
                    "schema_migrations",
                    "documents",
                    "conversion_jobs",
                    "chunks",
                    "library_items",
                    "diagnostics_events",
                }.issubset(tables)
            )

            container.connection.close()

    def test_migrations_are_idempotent_when_bootstrap_reruns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            app_config, logging_config = _write_config_files(tmp_path)

            first = bootstrap(str(app_config), str(logging_config))
            first.connection.close()

            second = bootstrap(str(app_config), str(logging_config))
            cursor = second.connection.execute(
                "SELECT version, checksum FROM schema_migrations ORDER BY version"
            )
            rows = cursor.fetchall()

            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0][0], "0001_initial_schema")
            self.assertEqual(rows[1][0], "0002_add_source_format_to_documents")
            self.assertEqual(rows[2][0], "0003_extend_library_items_metadata")

            second.connection.close()

    def test_bootstrap_sets_not_ready_when_required_assets_are_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            app_config, logging_config = _write_config_files(tmp_path)
            manifest = _write_manifest_with_invalid_asset(tmp_path)

            container = bootstrap(
                str(app_config),
                str(logging_config),
                str(manifest),
            )

            self.assertIsNotNone(container.startup_readiness_result)
            self.assertTrue(container.startup_readiness_result.ok)
            self.assertEqual(container.startup_readiness_result.data["status"], "not_ready")
            self.assertGreaterEqual(len(container.startup_readiness_result.data["remediation"]), 1)

            container.connection.close()
