"""SQLite connection management for local persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def ensure_database_file(database_path: str | Path) -> Path:
    """Ensure database parent directory exists and return normalized path."""
    db_path = Path(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        db_path.touch()
    return db_path


def create_connection(database_path: str | Path) -> sqlite3.Connection:
    """Create a SQLite connection to a local database file.

    ``check_same_thread=False`` is required because the connection is created
    on the main thread but used by background ``ThreadPoolExecutor`` workers
    during TTS conversion.  SQLite WAL mode makes concurrent reads safe.
    """
    db_path = ensure_database_file(database_path)
    connection = sqlite3.connect(str(db_path), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection
