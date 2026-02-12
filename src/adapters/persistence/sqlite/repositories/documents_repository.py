"""Documents repository stub."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from .base_repository import BaseRepository


class DocumentsRepository(BaseRepository):
    """Repository boundary for document persistence operations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection)

    def create_document(self, record: dict[str, str]) -> dict[str, str]:
        """Persist a document record and return normalized snake_case payload."""
        now = datetime.now(timezone.utc).isoformat()
        document_id = record.get("id", str(uuid4()))
        source_path = record["source_path"]
        title = record.get("title", "")
        source_format = record.get("source_format", "")

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO documents(id, source_path, title, source_format, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (document_id, source_path, title, source_format, now, now),
            )

        return {
            "id": document_id,
            "source_path": source_path,
            "title": title,
            "source_format": source_format,
            "created_at": now,
            "updated_at": now,
        }
