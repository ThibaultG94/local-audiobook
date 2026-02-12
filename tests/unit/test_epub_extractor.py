from __future__ import annotations

import unittest

from adapters.extraction.epub_extractor import EpubExtractor


class _FakeItem:
    def __init__(self, content: str) -> None:
        self._content = content

    def get_content(self) -> bytes:
        return self._content.encode("utf-8")


class _FakeBook:
    def __init__(self, spine: list[tuple[str, str]], items: dict[str, _FakeItem]) -> None:
        self.spine = spine
        self._items = items

    def get_item_with_id(self, item_id: str) -> _FakeItem | None:
        return self._items.get(item_id)


class TestEpubExtractor(unittest.TestCase):
    def test_extract_preserves_spine_order_and_normalizes_whitespace(self) -> None:
        extractor = EpubExtractor()

        fake_book = _FakeBook(
            spine=[("nav", "yes"), ("chapter-2", "yes"), ("chapter-1", "yes")],
            items={
                "chapter-1": _FakeItem("<html><body><p> First   chapter </p></body></html>"),
                "chapter-2": _FakeItem("<html><body><h1>Second</h1><p>  chapter</p></body></html>"),
            },
        )

        extractor._read_epub = lambda _: fake_book  # type: ignore[method-assign]

        result = extractor.extract("/tmp/book.epub", correlation_id="corr-epub-1", job_id="job-1")

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.data)
        text = result.data["text"]
        self.assertEqual(text, "Second chapter\nFirst chapter")

    def test_extract_returns_normalized_error_when_no_textual_content(self) -> None:
        extractor = EpubExtractor()

        fake_book = _FakeBook(
            spine=[("nav", "yes"), ("empty", "yes")],
            items={
                "empty": _FakeItem("<html><body><div>    </div></body></html>"),
            },
        )

        extractor._read_epub = lambda _: fake_book  # type: ignore[method-assign]

        result = extractor.extract("/tmp/empty.epub", correlation_id="corr-epub-2", job_id="job-2")

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "extraction.no_text_content")
        self.assertIn("source_path", result.error.details)
