"""Conversion jobs repository operations."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from .base_repository import BaseRepository


class ConversionJobsRepository(BaseRepository):
    """Repository boundary for conversion job persistence operations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection)

    def get_job_by_id(self, *, job_id: str) -> dict[str, Any] | None:
        """Fetch a conversion job by id.

        Returns:
            Job payload containing at least ``id``, ``state`` and ``updated_at``;
            ``None`` if not found.
        """
        row = self._connection.execute(
            """
            SELECT id, document_id, state, updated_at
            FROM conversion_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            return None

        return {
            "id": row["id"],
            "document_id": row["document_id"],
            "state": row["state"],
            "updated_at": row["updated_at"],
        }

    def update_job_state_if_current(
        self,
        *,
        job_id: str,
        expected_state: str,
        next_state: str,
        updated_at: str | None = None,
    ) -> bool:
        """Atomically update state when current value matches ``expected_state``.

        Uses a compare-and-swap SQL update to guarantee deterministic transition
        application under concurrent access.
        """
        timestamp = updated_at or datetime.now(timezone.utc).isoformat()
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE conversion_jobs
                SET state = ?, updated_at = ?
                WHERE id = ? AND state = ?
                """,
                (next_state, timestamp, job_id, expected_state),
            )
        return cursor.rowcount == 1
