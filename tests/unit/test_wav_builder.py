from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
import wave

from src.adapters.audio.wav_builder import WavBuilder


class TestWavBuilder(unittest.TestCase):
    def test_build_from_frames_writes_valid_wav_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target_path = tmp_path / "runtime" / "library" / "audio" / "sample.wav"

            pcm_frames = (b"\x00\x00" * 24000)
            builder = WavBuilder()

            result = builder.build_from_frames(
                target_path=str(target_path),
                pcm_frames=pcm_frames,
                sample_rate_hz=24000,
                channels=1,
                sample_width_bytes=2,
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.data["format"], "wav")
            self.assertEqual(result.data["path"], str(target_path))
            self.assertGreater(result.data["byte_size"], 44)

            with wave.open(BytesIO(target_path.read_bytes()), "rb") as check:
                self.assertEqual(check.getframerate(), 24000)
                self.assertEqual(check.getnchannels(), 1)
                self.assertEqual(check.getsampwidth(), 2)
                self.assertEqual(check.getnframes(), 24000)

