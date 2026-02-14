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
        
        Raises:
            sqlite3.IntegrityError: If document_id foreign key constraint fails
            sqlite3.Error: For other database errors
        """
        # Validate that document_id exists before attempting insert
        document_id = str(record["document_id"])
        cursor = self._connection.cursor()
        try:
            doc_exists = cursor.execute(
                "SELECT 1 FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            if doc_exists is None:
                raise sqlite3.IntegrityError(
                    f"FOREIGN KEY constraint failed: document_id '{document_id}' does not exist in documents table"
                )
        finally:
            cursor.close()
        
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

    def list_items_ordered(self) -> list[dict[str, Any]]:
        """Return library items sorted deterministically for browse UIs.

        Stable ordering rule: newest first using created_at DESC, then id DESC.
        """
        cursor = self._connection.cursor()
        try:
            rows = cursor.execute(
                """
                SELECT
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
                FROM library_items
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        finally:
            cursor.close()

        items: list[dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "id": row[0],
                    "document_id": row[1],
                    "job_id": row[2],
                    "audio_path": row[3],
                    "title": row[4],
                    "source_path": row[5],
                    "source_format": row[6],
                    "format": row[7],
                    "engine": row[8],
                    "voice": row[9],
                    "language": row[10],
                    "duration_seconds": row[11],
                    "byte_size": row[12],
                    "created_at": row[13],
                }
            )
        return items

    def get_item_by_id(self, item_id: str) -> dict[str, Any] | None:
        """Return one library item by id, or None when absent."""
        cursor = self._connection.cursor()
        try:
            row = cursor.execute(
                """
                SELECT
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
                FROM library_items
                WHERE id = ?
                """,
                (str(item_id),),
            ).fetchone()
        finally:
            cursor.close()

        if row is None:
            return None

        return {
            "id": row[0],
            "document_id": row[1],
            "job_id": row[2],
            "audio_path": row[3],
            "title": row[4],
            "source_path": row[5],
            "source_format": row[6],
            "format": row[7],
            "engine": row[8],
            "voice": row[9],
            "language": row[10],
            "duration_seconds": row[11],
            "byte_size": row[12],
            "created_at": row[13],
        }
