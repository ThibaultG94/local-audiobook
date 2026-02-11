"""SQLite migration runner with version tracking."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    path: Path
    sql: str
    checksum: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load_migrations(migrations_dir: str | Path) -> list[Migration]:
    directory = Path(migrations_dir)
    if not directory.exists():
        return []

    migrations: list[Migration] = []
    for file_path in sorted(directory.glob("*.sql")):
        sql = file_path.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=file_path.stem,
                path=file_path,
                sql=sql,
                checksum=_compute_checksum(sql),
            )
        )
    return migrations


def _ensure_schema_migrations_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    connection.commit()


def _already_applied(connection: sqlite3.Connection, version: str) -> tuple[bool, str | None]:
    cursor = connection.execute(
        "SELECT checksum FROM schema_migrations WHERE version = ?",
        (version,),
    )
    row = cursor.fetchone()
    if row is None:
        return False, None
    return True, row[0]


def apply_migrations(connection: sqlite3.Connection, migrations_dir: str | Path) -> list[str]:
    """Apply migrations from disk if not already applied.

    Returns the list of versions that were applied during this run.
    """
    _ensure_schema_migrations_table(connection)
    applied_versions: list[str] = []

    for migration in _load_migrations(migrations_dir):
        is_applied, existing_checksum = _already_applied(connection, migration.version)
        if is_applied:
            if existing_checksum != migration.checksum:
                raise RuntimeError(
                    f"Checksum mismatch for already applied migration {migration.version}"
                )
            continue

        with connection:
            connection.executescript(migration.sql)
            connection.execute(
                "INSERT INTO schema_migrations(version, checksum, applied_at) VALUES (?, ?, ?)",
                (migration.version, migration.checksum, _utc_now_iso()),
            )
        applied_versions.append(migration.version)

    return applied_versions

