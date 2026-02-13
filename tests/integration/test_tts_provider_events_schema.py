from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.logging.event_schema import REQUIRED_EVENT_FIELDS, is_valid_utc_iso_8601
from infrastructure.logging.jsonl_logger import JsonlLogger
from adapters.tts.chatterbox_provider import ChatterboxProvider
from adapters.tts.kokoro_provider import KokoroProvider


class TestTtsProviderEventsSchema(unittest.TestCase):
    def test_providers_emit_structured_events_with_required_correlation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "events.jsonl"
            logger = JsonlLogger(events_file)

            chatterbox = ChatterboxProvider(logger=logger)
            kokoro = KokoroProvider(logger=logger)

            chatterbox.synthesize_chunk(
                "Chunk one",
                voice="default",
                correlation_id="corr-a",
                job_id="job-a",
                chunk_index=1,
            )
            kokoro.synthesize_chunk(
                "Chunk two",
                voice="default",
                correlation_id="corr-b",
                job_id="job-b",
                chunk_index=2,
            )

            lines = [line for line in events_file.read_text(encoding="utf-8").splitlines() if line]
            self.assertGreaterEqual(len(lines), 4)

            events = [json.loads(line) for line in lines]
            for event in events:
                self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event.keys()))
                self.assertTrue(is_valid_utc_iso_8601(event["timestamp"]))
                self.assertIn(".", event["event"])

            event_names = [event["event"] for event in events]
            self.assertIn("tts.synthesis_started", event_names)
            self.assertIn("tts.synthesis_completed", event_names)

            engines = {event["engine"] for event in events}
            self.assertIn("chatterbox_gpu", engines)
            self.assertIn("kokoro_cpu", engines)

