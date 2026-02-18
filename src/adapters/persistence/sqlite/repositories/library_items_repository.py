"""Library items repository with defensive path validation and consistent transactions."""

from __future__ import annotations

import sqlite3
from pathlib import Path
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
            ValueError: If audio_path is invalid or outside runtime bounds
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
        
        # Defensive path validation at repository boundary
        audio_path = str(record["audio_path"])
        self._validate_audio_path(audio_path)
        
        # Validate byte_size is non-negative
        byte_size = int(record.get("byte_size") or 0)
        if byte_size < 0:
            raise ValueError(f"byte_size must be non-negative, got: {byte_size}")
        
        normalized = {
            "id": str(record.get("id") or uuid4()),
            "document_id": str(record["document_id"]),
            "job_id": str(record.get("job_id") or ""),
            "audio_path": audio_path,
            "title": str(record.get("title") or ""),
            "source_path": str(record.get("source_path") or ""),
            "source_format": str(record.get("source_format") or ""),
            "format": str(record.get("format") or ""),
            "engine": str(record.get("engine") or ""),
            "voice": str(record.get("voice") or ""),
            "language": str(record.get("language") or ""),
            "duration_seconds": float(record.get("duration_seconds") or 0.0),
            "byte_size": byte_size,
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
        Uses explicit transaction for consistent read isolation.
        """
        cursor = self._connection.cursor()
        try:
            cursor.execute("BEGIN")
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
            self._connection.commit()
        except sqlite3.Error:
            self._connection.rollback()
            raise
        finally:
            cursor.close()

        return [self._row_to_dict(row) for row in rows]

    def get_item_by_id(self, item_id: str) -> dict[str, Any] | None:
        """Return one library item by id, or None when absent.
        
        Uses explicit transaction for consistent read isolation.
        """
        cursor = self._connection.cursor()
        try:
            cursor.execute("BEGIN")
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
            self._connection.commit()
        except sqlite3.Error:
            self._connection.rollback()
            raise
        finally:
            cursor.close()

        if row is None:
            return None

        return self._row_to_dict(row)

    def delete_item_by_id(self, item_id: str) -> dict[str, Any] | None:
        """Delete one library item by id and return deleted row when present."""
        normalized_item_id = str(item_id or "")
        cursor = self._connection.cursor()
        try:
            cursor.execute("BEGIN")
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
                (normalized_item_id,),
            ).fetchone()

            if row is None:
                self._connection.commit()
                return None

            cursor.execute("DELETE FROM library_items WHERE id = ?", (normalized_item_id,))
            self._connection.commit()
            return self._row_to_dict(row)
        except sqlite3.Error:
            self._connection.rollback()
            raise
        finally:
            cursor.close()

    @staticmethod
    def _validate_audio_path(audio_path: str) -> None:
        """Validate audio path is under runtime/library/audio to prevent path traversal.
        
        Uses Path.is_relative_to() for secure path validation that prevents
        symlink attacks and path traversal vulnerabilities.
        
        Raises:
            ValueError: If path is invalid or outside expected bounds
        """
        if not audio_path or not audio_path.strip():
            raise ValueError("audio_path cannot be empty")
        
        try:
            input_path = Path(audio_path)
            resolved_path = input_path.resolve(strict=False)
            expected_base = Path("runtime/library/audio").resolve(strict=False)
            
            # Use is_relative_to() for secure path validation (Python 3.9+)
            # This prevents symlink attacks and sophisticated path traversal
            if not resolved_path.is_relative_to(expected_base):
                raise ValueError(
                    f"audio_path must be under runtime/library/audio/, got: {audio_path}"
                )
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError(f"Invalid audio_path: {audio_path}") from exc

    @staticmethod
    def _row_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
        """Convert SQLite row tuple to dictionary with named fields.
        
        Centralizes row mapping to avoid duplication and index fragility.
        """
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
