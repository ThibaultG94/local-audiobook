from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.adapters.audio.mp3_encoder import Mp3Encoder


class TestMp3Encoder(unittest.TestCase):
    def test_encode_from_frames_writes_mp3_like_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target_path = tmp_path / "runtime" / "library" / "audio" / "sample.mp3"

            encoder = Mp3Encoder()
            pcm_frames = (b"\x00\x00" * 24000)
            result = encoder.encode_from_frames(
                target_path=str(target_path),
                pcm_frames=pcm_frames,
                sample_rate_hz=24000,
                channels=1,
                sample_width_bytes=2,
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.data["format"], "mp3")
            self.assertEqual(result.data["path"], str(target_path))
            self.assertGreater(result.data["byte_size"], 0)

            mp3_bytes = target_path.read_bytes()
            self.assertGreaterEqual(len(mp3_bytes), 4)
            self.assertEqual(mp3_bytes[:2], b"\xFF\xFB")

