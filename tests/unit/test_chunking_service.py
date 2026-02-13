from __future__ import annotations

import unittest

from domain.services.chunking_service import ChunkingService


class TestChunkingService(unittest.TestCase):
    def test_chunk_text_is_deterministic_for_same_input(self) -> None:
        service = ChunkingService()
        text = "Bonjour. Ceci est une phrase. Et encore une autre phrase." 

        first = service.chunk_text(text=text, max_chars=24)
        second = service.chunk_text(text=text, max_chars=24)

        self.assertTrue(first.ok)
        self.assertTrue(second.ok)
        self.assertEqual(first.data, second.data)

    def test_chunk_text_prefers_sentence_boundaries_before_threshold_fallback(self) -> None:
        service = ChunkingService()
        text = "Alpha beta gamma. Delta epsilon zeta. Eta theta iota."

        result = service.chunk_text(text=text, max_chars=30)

        self.assertTrue(result.ok)
        self.assertEqual(
            result.data,
            [
                "Alpha beta gamma.",
                "Delta epsilon zeta.",
                "Eta theta iota.",
            ],
        )

    def test_chunk_text_uses_word_aware_fallback_when_sentence_exceeds_limit(self) -> None:
        service = ChunkingService()
        text = "Phrase très longue sans ponctuation utile pour tenir dans la limite"

        result = service.chunk_text(text=text, max_chars=20)

        self.assertTrue(result.ok)
        self.assertEqual(
            result.data,
            [
                "Phrase très longue",
                "sans ponctuation",
                "utile pour tenir",
                "dans la limite",
            ],
        )

    def test_chunk_text_rejects_empty_text(self) -> None:
        service = ChunkingService()

        result = service.chunk_text(text="   ", max_chars=128)

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "chunking.invalid_text")
        self.assertFalse(result.error.retryable)

    def test_chunk_text_rejects_invalid_chunk_size(self) -> None:
        service = ChunkingService()

        result = service.chunk_text(text="Texte valide", max_chars=0)

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "chunking.invalid_chunk_size")
        self.assertFalse(result.error.retryable)


if __name__ == "__main__":
    unittest.main()
