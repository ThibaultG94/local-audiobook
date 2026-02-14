"""Library items repository stub."""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from .base_repository import BaseRepository


class LibraryItemsRepository(BaseRepository):
    """Repository boundary for library item persistence operations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection)

    def create_item(self, record: dict[str, Any]) -> dict[str, Any]:
        """Insert one library item with explicit transaction semantics.

        The method uses a single transactional block (BEGIN/COMMIT), and
        performs rollback on any database exception.
        """
        normalized = {
            "id": str(record.get("id") or uuid4()),
            "document_id": str(record["document_id"]),
            "job_id": str(record.get("job_id") or ""),
            "audio_path": str(record["audio_path"]),
            "title": str(record.get("title") or ""),
            "source_path": str(record.get("source_path") or ""),
            "source_format": str(record.get("source_format") or ""),
            "format": str(record.get("format") or ""),
            "engine": str(record.get("engine") or ""),
            "voice": str(record.get("voice") or ""),
            "language": str(record.get("language") or ""),
            "duration_seconds": float(record.get("duration_seconds") or 0.0),
            "byte_size": int(record.get("byte_size") or 0),
            "created_at": str(record["created_at"]),
        }

        cursor = self._connection.cursor()
        try:
            cursor.execute("BEGIN")
            cursor.execute(
                """
                INSERT INTO library_items(
                    id,
                    document_id,
                    job_id,
                    audio_path,
                    title,
                    source_path,
                    source_format,
                    format,
                    engine,
                    voice,
                    language,
                    duration_seconds,
                    byte_size,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized["id"],
                    normalized["document_id"],
                    normalized["job_id"],
                    normalized["audio_path"],
                    normalized["title"],
                    normalized["source_path"],
                    normalized["source_format"],
                    normalized["format"],
                    normalized["engine"],
                    normalized["voice"],
                    normalized["language"],
                    normalized["duration_seconds"],
                    normalized["byte_size"],
                    normalized["created_at"],
                ),
            )
            self._connection.commit()
        except sqlite3.Error:
            self._connection.rollback()
            raise
        finally:
            cursor.close()

        return normalized
