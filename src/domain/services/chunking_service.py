"""Deterministic phrase-first chunking service."""

from __future__ import annotations

from contracts.result import Result, failure, success


class ChunkingService:
    """Split extracted text into deterministic phrase-first chunks."""

    def chunk_text(
        self,
        *,
        text: str,
        max_chars: int,
        language_hint: str | None = None,
    ) -> Result[list[str]]:
        del language_hint  # Reserved for future language-specific heuristics.

        if not isinstance(text, str) or not text.strip():
            return failure(
                code="chunking.invalid_text",
                message="Chunking requires non-empty extracted text",
                details={"reason": "empty_or_whitespace_text"},
                retryable=False,
            )

        if not isinstance(max_chars, int) or max_chars <= 0:
            return failure(
                code="chunking.invalid_chunk_size",
                message="Chunking requires a positive max_chars integer",
                details={"max_chars": max_chars},
                retryable=False,
            )

        normalized_text = " ".join(text.split())
        if not normalized_text:
            return failure(
                code="chunking.invalid_text",
                message="Chunking requires non-empty extracted text",
                details={"reason": "normalized_text_empty"},
                retryable=False,
            )

        sentence_like_segments = self._split_sentence_like_segments(normalized_text)
        chunks: list[str] = []
        current = ""

        for segment in sentence_like_segments:
            if len(segment) <= max_chars:
                if not current:
                    current = segment
                    continue

                candidate = f"{current} {segment}"
                if len(candidate) <= max_chars:
                    current = candidate
                else:
                    chunks.append(current)
                    current = segment
                continue

            if current:
                chunks.append(current)
                current = ""

            chunks.extend(self._fallback_split_segment(segment, max_chars))

        if current:
            chunks.append(current)

        non_empty_chunks = [chunk for chunk in chunks if chunk]
        return success(non_empty_chunks)

    def _split_sentence_like_segments(self, text: str) -> list[str]:
        """Split by sentence punctuation while preserving deterministic ordering."""
        segments: list[str] = []
        start = 0

        for idx, char in enumerate(text):
            if char not in {".", "!", "?", ";", ":"}:
                continue

            end = idx + 1
            segment = text[start:end].strip()
            if segment:
                segments.append(segment)
            start = end

        tail = text[start:].strip()
        if tail:
            segments.append(tail)

        return segments if segments else [text]

    def _fallback_split_segment(self, segment: str, max_chars: int) -> list[str]:
        """Split long segments deterministically by words, then hard-size fallback."""
        words = segment.split(" ")
        chunks: list[str] = []
        current = ""

        for word in words:
            if not word:
                continue

            if len(word) > max_chars:
                if current:
                    chunks.append(current)
                    current = ""

                chunks.extend(self._hard_split_word(word, max_chars))
                continue

            if not current:
                current = word
                continue

            candidate = f"{current} {word}"
            if len(candidate) <= max_chars:
                current = candidate
            else:
                chunks.append(current)
                current = word

        if current:
            chunks.append(current)

        return chunks

    def _hard_split_word(self, word: str, max_chars: int) -> list[str]:
        """Split an oversized token into stable fixed-size chunks."""
        return [word[i : i + max_chars] for i in range(0, len(word), max_chars)]

