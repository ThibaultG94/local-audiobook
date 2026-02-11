"""Diagnostics events repository stub."""

from __future__ import annotations

import sqlite3

from .base_repository import BaseRepository


class DiagnosticsEventsRepository(BaseRepository):
    """Repository boundary for diagnostics event persistence operations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection)

