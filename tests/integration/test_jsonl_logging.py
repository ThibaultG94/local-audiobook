from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.main import bootstrap
from infrastructure.logging.event_schema import REQUIRED_EVENT_FIELDS, is_valid_utc_iso_8601


def _write_config_files(base_dir: Path) -> tuple[Path, Path, Path]:
    runtime = base_dir / "runtime"
    events_file = runtime / "logs" / "events.jsonl"
    app_config = base_dir / "app_config.yaml"
    logging_config = base_dir / "logging_config.yaml"

    app_config.write_text(
        "\n".join(
            [
                "app:",
                "  name: local-audiobook",
                "  environment: local",
                "paths:",
                f"  runtime_dir: {runtime}",
                f"  database_path: {runtime / 'local_audiobook.db'}",
                "  migrations_dir: migrations",
                f"  logs_dir: {runtime / 'logs'}",
                f"  library_audio_dir: {runtime / 'library' / 'audio'}",
                f"  library_temp_dir: {runtime / 'library' / 'temp'}",
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
                f"  file_path: {events_file}",
                "  logger_type: jsonl",
                "  level: INFO",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return app_config, logging_config, events_file


class TestJsonlLoggingIntegration(unittest.TestCase):
    def test_bootstrap_emits_required_jsonl_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            app_config, logging_config, events_file = _write_config_files(tmp_path)

            container = bootstrap(str(app_config), str(logging_config))
            container.connection.close()

            self.assertTrue(events_file.exists())
            lines = [line for line in events_file.read_text(encoding="utf-8").splitlines() if line]
            self.assertGreaterEqual(len(lines), 5)

            events = [json.loads(line) for line in lines]
            event_names = [event["event"] for event in events]

            for required in [
                "bootstrap.started",
                "migration.started",
                "migration.applied",
                "migration.completed",
                "bootstrap.completed",
            ]:
                self.assertIn(required, event_names)

            for event in events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))
                self.assertIn(".", event["event"])
