from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.adapters.audio.mp3_encoder import Mp3Encoder
from src.adapters.audio.wav_builder import WavBuilder
from src.adapters.tts.chatterbox_provider import ChatterboxProvider
from src.domain.services.audio_postprocess_service import AudioPostprocessService


class _CapturingLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def emit(self, **payload: object) -> None:
        self.events.append(payload)


class TestAudioPostprocessService(unittest.TestCase):
    def test_assemble_and_render_wav_returns_normalized_artifact_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target_path = tmp_path / "runtime" / "library" / "audio" / "job-pp-1.wav"

            provider = ChatterboxProvider(healthy=True)
            first = provider.synthesize_chunk("Phrase une", correlation_id="corr-pp", job_id="job-pp-1", chunk_index=0)
            second = provider.synthesize_chunk("Phrase deux", correlation_id="corr-pp", job_id="job-pp-1", chunk_index=1)

            logger = _CapturingLogger()
            service = AudioPostprocessService(
                wav_builder=WavBuilder(),
                mp3_encoder=Mp3Encoder(),
                logger=logger,
            )

            result = service.assemble_and_render(
                job_id="job-pp-1",
                correlation_id="corr-pp",
                output_format="wav",
                chunk_artifacts=[
                    {"chunk_index": 0, "synthesis": first.to_dict(), "engine": "chatterbox_gpu"},
                    {"chunk_index": 1, "synthesis": second.to_dict(), "engine": "chatterbox_gpu"},
                ],
                target_path=str(target_path),
            )

            self.assertTrue(result.ok)
            artifact = result.data["output_artifact"]
            self.assertEqual(artifact["format"], "wav")
            self.assertEqual(artifact["path"], str(target_path))
            self.assertGreater(artifact["byte_size"], 44)
            self.assertGreaterEqual(float(artifact["duration_seconds"]), 1.0)

            event_names = [event.get("event") for event in logger.events]
            self.assertIn("postprocess.started", event_names)
            self.assertIn("postprocess.succeeded", event_names)

    def test_assemble_and_render_rejects_duplicate_chunk_indices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target_path = tmp_path / "runtime" / "library" / "audio" / "job-pp-dup.wav"

            provider = ChatterboxProvider(healthy=True)
            synthesis = provider.synthesize_chunk("Texte", correlation_id="corr-dup", job_id="job-pp-dup", chunk_index=0)

            logger = _CapturingLogger()
            service = AudioPostprocessService(
                wav_builder=WavBuilder(),
                mp3_encoder=Mp3Encoder(),
                logger=logger,
            )

            result = service.assemble_and_render(
                job_id="job-pp-dup",
                correlation_id="corr-dup",
                output_format="wav",
                chunk_artifacts=[
                    {"chunk_index": 0, "synthesis": synthesis.to_dict(), "engine": "chatterbox_gpu"},
                    {"chunk_index": 0, "synthesis": synthesis.to_dict(), "engine": "chatterbox_gpu"},
                ],
                target_path=str(target_path),
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "audio_postprocess.duplicate_chunk_index")
            failed_events = [event for event in logger.events if event.get("event") == "postprocess.failed"]
            self.assertEqual(len(failed_events), 1)

