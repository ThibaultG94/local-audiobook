"""Extraction adapters."""

from .epub_extractor import EpubExtractor
from .pdf_extractor import PdfExtractor
from .text_extractor import TextExtractor

__all__ = ["EpubExtractor", "PdfExtractor", "TextExtractor"]
