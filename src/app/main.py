"""Application bootstrap entrypoint for Story 1.1 foundation."""

from __future__ import annotations

from pathlib import Path

from adapters.persistence.sqlite.connection import create_connection
from adapters.persistence.sqlite.migration_runner import apply_migrations
from app.dependency_container import AppContainer, build_container
from app.settings import load_simple_yaml


def _ensure_runtime_dirs(app_config: dict[str, object]) -> None:
    paths = app_config["paths"]
    runtime_dirs = [
        paths["runtime_dir"],
        paths["logs_dir"],
        paths["library_audio_dir"],
        paths["library_temp_dir"],
    ]
    for runtime_dir in runtime_dirs:
        Path(runtime_dir).mkdir(parents=True, exist_ok=True)


def bootstrap(
    app_config_path: str = "config/app_config.yaml",
    logging_config_path: str = "config/logging_config.yaml",
) -> AppContainer:
    app_config = load_simple_yaml(app_config_path)
    logging_config = load_simple_yaml(logging_config_path)

    _ensure_runtime_dirs(app_config)
    connection = create_connection(app_config["paths"]["database_path"])
    container = build_container(connection, logging_config)

    container.logger.emit(event="bootstrap.started", stage="bootstrap")
    container.logger.emit(event="migration.started", stage="migration")
    try:
        applied = apply_migrations(connection, app_config["paths"]["migrations_dir"])
        for version in applied:
            container.logger.emit(
                event="migration.applied",
                stage="migration",
                extra={"migration_version": version},
            )
        container.logger.emit(event="migration.completed", stage="migration")
    except Exception as exc:  # pragma: no cover - failure path validated by behavior
        container.logger.emit(
            event="migration.failed",
            stage="migration",
            severity="ERROR",
            extra={"error": str(exc)},
        )
        raise

    container.logger.emit(event="bootstrap.completed", stage="bootstrap")
    return container


if __name__ == "__main__":
    bootstrap()
