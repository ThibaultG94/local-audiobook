"""Framework-agnostic dependency container for bootstrap wiring."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from src.contracts.result import Result
from src.adapters.audio.mp3_encoder import Mp3Encoder
from src.adapters.audio.wav_builder import WavBuilder
from src.adapters.tts.chatterbox_provider import ChatterboxProvider
from src.adapters.tts.kokoro_provider import KokoroProvider
from src.adapters.persistence.sqlite.repositories.conversion_jobs_repository import (
    ConversionJobsRepository,
)
from src.adapters.persistence.sqlite.repositories.diagnostics_events_repository import (
    DiagnosticsEventsRepository,
)
from src.adapters.persistence.sqlite.repositories.documents_repository import (
    DocumentsRepository,
)
from src.adapters.persistence.sqlite.repositories.library_items_repository import (
    LibraryItemsRepository,
)
from src.adapters.persistence.sqlite.repositories.chunks_repository import ChunksRepository
from src.domain.services.audio_postprocess_service import AudioPostprocessService
from src.domain.services.chunking_service import ChunkingService
from src.domain.services.library_service import LibraryService
from src.domain.services.model_registry_service import ModelRegistryService
from src.domain.services.startup_readiness_service import StartupReadinessService
from src.domain.services.tts_orchestration_service import TtsOrchestrationService
from src.infrastructure.logging.jsonl_logger import JsonlLogger


@dataclass(slots=True)
class Repositories:
    documents: DocumentsRepository
    conversion_jobs: ConversionJobsRepository
    chunks: ChunksRepository
    library_items: LibraryItemsRepository
    diagnostics_events: DiagnosticsEventsRepository


@dataclass(slots=True)
class Providers:
    chatterbox: ChatterboxProvider
    kokoro: KokoroProvider


@dataclass(slots=True)
class Services:
    tts_orchestration: TtsOrchestrationService
    audio_postprocess: AudioPostprocessService
    library: LibraryService
    chunking: ChunkingService
    model_registry: ModelRegistryService
    startup_readiness: StartupReadinessService


@dataclass(slots=True)
class AppContainer:
    connection: sqlite3.Connection
    repositories: Repositories
    providers: Providers
    services: Services
    logger: JsonlLogger
    startup_readiness_result: Result[dict[str, Any]] | None = None


def normalize_engine_health(result: Any) -> dict[str, Any]:
    """Normalize a provider health_check Result into a flat dict."""
    if result.ok:
        data = result.data or {}
        return {
            "engine": data.get("engine", "unknown"),
            "ok": bool(data.get("available", False)),
            "error": None,
        }
    return {
        "engine": "unknown",
        "ok": False,
        "error": result.error.to_dict() if result.error else {},
    }


def collect_engine_health(container: AppContainer) -> list[dict[str, Any]]:
    """Collect normalized health for all startup engines."""
    chatterbox_health = normalize_engine_health(container.providers.chatterbox.health_check())
    kokoro_health = normalize_engine_health(container.providers.kokoro.health_check())
    return [chatterbox_health, kokoro_health]


def recheck_startup_readiness(container: AppContainer, model_manifest_path: str) -> Result[dict[str, Any]]:
    """Re-run model registry + engine health through service boundaries."""
    model_registry_result = container.services.model_registry.validate_models(model_manifest_path)
    engine_health = collect_engine_health(container)
    readiness_result = container.services.startup_readiness.compute(
        models_result=model_registry_result,
        engines=engine_health,
    )
    container.startup_readiness_result = readiness_result
    return readiness_result


def build_conversion_presenter(*, logger: JsonlLogger | None = None) -> Any:
    """Build conversion presenter without introducing any UI runtime dependency."""
    from src.ui.presenters.conversion_presenter import ConversionPresenter

    return ConversionPresenter(logger=logger)


def build_library_presenter(container: AppContainer) -> Any:
    """Build library presenter through service boundaries only."""
    from src.ui.presenters.library_presenter import LibraryPresenter

    return LibraryPresenter(library_service=container.services.library)


def build_library_view(container: AppContainer) -> Any:
    """Build library view bound to presenter without direct DB access from UI."""
    from src.ui.views.library_view import LibraryView

    presenter = build_library_presenter(container)
    return LibraryView(presenter=presenter)


def build_conversion_worker(container: AppContainer, model_manifest_path: str) -> Any:
    """Build conversion worker with recheck entrypoint through service boundaries."""
    from src.ui.workers.conversion_worker import ConversionWorker

    return ConversionWorker(
        recheck_callable=lambda: recheck_startup_readiness(container, model_manifest_path),
        logger=container.logger,
        conversion_jobs_repository=container.repositories.conversion_jobs,
        conversion_launcher=container.services.tts_orchestration,
    )


def build_container(connection: sqlite3.Connection, logging_config: dict[str, Any]) -> AppContainer:
    logger = JsonlLogger(logging_config["logging"]["file_path"])
    repositories = Repositories(
        documents=DocumentsRepository(connection),
        conversion_jobs=ConversionJobsRepository(connection),
        chunks=ChunksRepository(connection),
        library_items=LibraryItemsRepository(connection),
        diagnostics_events=DiagnosticsEventsRepository(connection),
    )
    providers = Providers(
        chatterbox=ChatterboxProvider(logger=logger),
        kokoro=KokoroProvider(logger=logger),
    )
    audio_postprocess = AudioPostprocessService(
        wav_builder=WavBuilder(),
        mp3_encoder=Mp3Encoder(),
        logger=logger,
    )
    library_service = LibraryService(
        library_items_repository=repositories.library_items,
        logger=logger,
    )
    services = Services(
        tts_orchestration=TtsOrchestrationService(
            primary_provider=providers.chatterbox,
            fallback_provider=providers.kokoro,
            audio_postprocess_service=audio_postprocess,
            library_service=library_service,
            chunking_service=ChunkingService(),
            chunks_repository=repositories.chunks,
            conversion_jobs_repository=repositories.conversion_jobs,
            documents_repository=repositories.documents,
            logger=logger,
        ),
        audio_postprocess=audio_postprocess,
        library=library_service,
        chunking=ChunkingService(),
        model_registry=ModelRegistryService(),
        startup_readiness=StartupReadinessService(),
    )
    return AppContainer(
        connection=connection,
        repositories=repositories,
        providers=providers,
        services=services,
        logger=logger,
        startup_readiness_result=None,
    )
