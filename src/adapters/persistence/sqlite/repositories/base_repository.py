"""Base repository helpers for SQLite adapters."""

from __future__ import annotations

import sqlite3


class BaseRepository:
    """Base class for SQLite repositories."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

