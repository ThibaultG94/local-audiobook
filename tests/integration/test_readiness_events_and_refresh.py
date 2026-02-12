from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.main import bootstrap
from app.dependency_container import build_conversion_presenter, build_conversion_worker
from infrastructure.logging.event_schema import REQUIRED_EVENT_FIELDS, is_valid_utc_iso_8601
from ui.views.conversion_view import ConversionView


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


class TestReadinessEventsAndRefreshIntegration(unittest.TestCase):
    def test_readiness_displayed_and_checked_events_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            app_config, logging_config, events_file = _write_config_files(tmp_path)

            container = bootstrap(str(app_config), str(logging_config))
            presenter = build_conversion_presenter()
            worker = build_conversion_worker(container, "config/model_manifest.yaml")
            view = ConversionView(presenter=presenter, worker=worker, logger=container.logger)

            try:
                initial_readiness = container.startup_readiness_result
                view.render_initial(initial_readiness)
                future = worker.refresh_readiness()
                future.result(timeout=3)
            finally:
                worker.shutdown()
                container.connection.close()

            lines = [line for line in events_file.read_text(encoding="utf-8").splitlines() if line]
            events = [json.loads(line) for line in lines]

            target_events = [
                event for event in events if event.get("event") in {"readiness.displayed", "readiness.checked"}
            ]
            self.assertGreaterEqual(len(target_events), 2)

            event_names = [event["event"] for event in target_events]
            self.assertIn("readiness.displayed", event_names)
            self.assertIn("readiness.checked", event_names)

            for event in target_events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))

