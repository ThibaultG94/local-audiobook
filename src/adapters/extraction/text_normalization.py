"""Shared text normalization utilities for extraction adapters."""

from __future__ import annotations

import html
import re

# Compiled regex patterns for text normalization
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")

# Extraction constants
CHUNK_INDEX_NOT_APPLICABLE = -1
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500MB


def normalize_fragment(fragment: str, *, strip_html: bool = False) -> str:
    """
    Normalize a text fragment for chunking readiness.
    
    Args:
        fragment: Raw text fragment to normalize
        strip_html: Whether to strip HTML tags and unescape entities
        
    Returns:
        Normalized text with consistent whitespace and line breaks
    """
    text = fragment
    if strip_html:
        text = html.unescape(_TAG_RE.sub(" ", text))
    
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)
