"""Conversion jobs repository stub."""

from __future__ import annotations

import sqlite3

from .base_repository import BaseRepository


class ConversionJobsRepository(BaseRepository):
    """Repository boundary for conversion job persistence operations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection)

