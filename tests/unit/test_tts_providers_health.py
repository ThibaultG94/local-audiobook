from __future__ import annotations

import unittest

from adapters.tts.chatterbox_provider import ChatterboxProvider
from adapters.tts.kokoro_provider import KokoroProvider


class TestTtsProvidersHealth(unittest.TestCase):
    def test_chatterbox_health_success_and_failure_are_normalized(self) -> None:
        ok_provider = ChatterboxProvider(healthy=True)
        ok = ok_provider.health_check()
        self.assertTrue(ok.ok)
        self.assertEqual(ok.data["engine"], "chatterbox_gpu")
        self.assertTrue(ok.data["available"])

        fail_provider = ChatterboxProvider(healthy=False)
        failed = fail_provider.health_check()
        self.assertFalse(failed.ok)
        payload = failed.error.to_dict()
        self.assertEqual(payload["code"], "tts_engine_unavailable")
        self.assertIn("chatterbox_gpu", payload["details"]["engine"])

    def test_kokoro_health_success_and_failure_are_normalized(self) -> None:
        ok_provider = KokoroProvider(healthy=True)
        ok = ok_provider.health_check()
        self.assertTrue(ok.ok)
        self.assertEqual(ok.data["engine"], "kokoro_cpu")
        self.assertTrue(ok.data["available"])

        fail_provider = KokoroProvider(healthy=False)
        failed = fail_provider.health_check()
        self.assertFalse(failed.ok)
        payload = failed.error.to_dict()
        self.assertEqual(payload["code"], "tts_engine_unavailable")
        self.assertIn("kokoro_cpu", payload["details"]["engine"])

