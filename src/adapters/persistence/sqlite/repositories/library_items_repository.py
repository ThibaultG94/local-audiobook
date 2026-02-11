"""Library items repository stub."""

from __future__ import annotations

import sqlite3

from .base_repository import BaseRepository


class LibraryItemsRepository(BaseRepository):
    """Repository boundary for library item persistence operations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection)

