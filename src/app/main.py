"""Application bootstrap entrypoint for Story 1.1 foundation."""

from __future__ import annotations

from pathlib import Path

from adapters.persistence.sqlite.connection import create_connection
from adapters.persistence.sqlite.migration_runner import apply_migrations
from app.dependency_container import AppContainer, build_container, collect_engine_health
from app.settings import load_simple_yaml


_REQUIRED_PATH_KEYS = frozenset(
    {"runtime_dir", "logs_dir", "library_audio_dir", "library_temp_dir", "database_path", "migrations_dir"}
)


def _validate_app_config(app_config: dict[str, object]) -> None:
    """Validate that required config keys are present."""
    if "paths" not in app_config or not isinstance(app_config["paths"], dict):
        raise ValueError(
            "app_config missing required 'paths' mapping — "
            "check config/app_config.yaml structure"
        )
    missing = _REQUIRED_PATH_KEYS - app_config["paths"].keys()
    if missing:
        raise ValueError(
            f"app_config.paths missing required keys: {sorted(missing)}"
        )


def _ensure_runtime_dirs(paths: dict[str, object]) -> None:
    runtime_dirs = [
        paths["runtime_dir"],
        paths["logs_dir"],
        paths["library_audio_dir"],
        paths["library_temp_dir"],
    ]
    for runtime_dir in runtime_dirs:
        Path(str(runtime_dir)).mkdir(parents=True, exist_ok=True)


def bootstrap(
    app_config_path: str = "config/app_config.yaml",
    logging_config_path: str = "config/logging_config.yaml",
    model_manifest_path: str = "config/model_manifest.yaml",
) -> AppContainer:
    app_config = load_simple_yaml(app_config_path)
    logging_config = load_simple_yaml(logging_config_path)

    _validate_app_config(app_config)
    paths = app_config["paths"]

    _ensure_runtime_dirs(paths)
    connection = create_connection(paths["database_path"])
    container = build_container(connection, logging_config)

    container.logger.emit(event="bootstrap.started", stage="bootstrap")
    container.logger.emit(event="migration.started", stage="migration")
    try:
        applied = apply_migrations(connection, paths["migrations_dir"])
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

    container.logger.emit(event="model_registry.started", stage="model_registry")
    model_registry_result = container.services.model_registry.validate_models(model_manifest_path)
    if model_registry_result.ok:
        container.logger.emit(event="model_registry.completed", stage="model_registry")
    else:
        details = model_registry_result.error.to_dict() if model_registry_result.error else {}
        container.logger.emit(
            event="model_registry.failed",
            stage="model_registry",
            severity="ERROR",
            extra={"error": details},
        )

    container.logger.emit(event="engine_health.started", stage="engine_health")
    engine_health = collect_engine_health(container)

    if all(item["ok"] for item in engine_health):
        container.logger.emit(event="engine_health.completed", stage="engine_health")
    else:
        container.logger.emit(
            event="engine_health.failed",
            stage="engine_health",
            severity="ERROR",
            extra={"engines": engine_health},
        )

    readiness_result = container.services.startup_readiness.compute(
        models_result=model_registry_result,
        engines=engine_health,
    )
    container.startup_readiness = readiness_result.to_dict()

    container.logger.emit(event="bootstrap.completed", stage="bootstrap")
    return container


if __name__ == "__main__":
    bootstrap()
