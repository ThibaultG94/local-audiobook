"""Chunks repository stub."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .base_repository import BaseRepository


class ChunksRepository(BaseRepository):
    """Repository boundary for chunk persistence operations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection)

    def replace_chunks_for_job(self, *, job_id: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Replace all chunks for a job with a deterministic ordered set.
        
        Validates that chunk_index values are sequential starting from 0.
        
        Args:
            job_id: Job identifier
            chunks: List of chunk dictionaries with chunk_index, text_content, etc.
            
        Returns:
            List of persisted chunk records
            
        Raises:
            ValueError: If chunk_index values are not sequential from 0
        """
        now = datetime.now(timezone.utc).isoformat()
        normalized: list[dict[str, Any]] = []

        # Validate chunk_index ordering
        expected_indices = set(range(len(chunks)))
        actual_indices = {int(item["chunk_index"]) for item in chunks}
        if actual_indices != expected_indices:
            raise ValueError(
                f"Chunk indices must be sequential from 0 to {len(chunks)-1}. "
                f"Expected: {sorted(expected_indices)}, Got: {sorted(actual_indices)}"
            )

        for item in chunks:
            normalized.append(
                {
                    "id": str(item.get("id") or uuid4()),
                    "job_id": job_id,
                    "chunk_index": int(item["chunk_index"]),
                    "text_content": str(item["text_content"]),
                    "content_hash": str(item.get("content_hash") or ""),
                    "status": str(item.get("status") or "pending"),
                    "created_at": str(item.get("created_at") or now),
                }
            )

        with self._connection:
            self._connection.execute("DELETE FROM chunks WHERE job_id = ?", (job_id,))
            for item in normalized:
                self._connection.execute(
                    """
                    INSERT INTO chunks(id, job_id, chunk_index, text_content, content_hash, audio_path, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"],
                        item["job_id"],
                        item["chunk_index"],
                        item["text_content"],
                        item["content_hash"],
                        None,
                        item["status"],
                        item["created_at"],
                    ),
                )

        return self.list_chunks_for_job(job_id=job_id)

    def list_chunks_for_job(self, *, job_id: str) -> list[dict[str, Any]]:
        """List chunks ordered by stable chunk index."""
        rows = self._connection.execute(
            """
            SELECT id, job_id, chunk_index, text_content, content_hash, audio_path, status, created_at
            FROM chunks
            WHERE job_id = ?
            ORDER BY chunk_index ASC
            """,
            (job_id,),
        ).fetchall()

        return [
            {
                "id": row["id"],
                "job_id": row["job_id"],
                "chunk_index": row["chunk_index"],
                "text_content": row["text_content"],
                "content_hash": row["content_hash"],
                "audio_path": row["audio_path"],
                "status": row["status"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def update_chunk_synthesis_outcome(self, *, job_id: str, chunk_index: int, status: str) -> None:
        """Persist deterministic synthesis outcome for one chunk."""
        with self._connection:
            self._connection.execute(
                """
                UPDATE chunks
                SET status = ?
                WHERE job_id = ? AND chunk_index = ?
                """,
                (status, job_id, int(chunk_index)),
            )
