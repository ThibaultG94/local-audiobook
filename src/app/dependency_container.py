"""Framework-agnostic dependency container for bootstrap wiring."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from adapters.tts.chatterbox_provider import ChatterboxProvider
from adapters.tts.kokoro_provider import KokoroProvider
from adapters.persistence.sqlite.repositories.conversion_jobs_repository import (
    ConversionJobsRepository,
)
from adapters.persistence.sqlite.repositories.diagnostics_events_repository import (
    DiagnosticsEventsRepository,
)
from adapters.persistence.sqlite.repositories.documents_repository import (
    DocumentsRepository,
)
from adapters.persistence.sqlite.repositories.library_items_repository import (
    LibraryItemsRepository,
)
from adapters.persistence.sqlite.repositories.chunks_repository import ChunksRepository
from domain.services.model_registry_service import ModelRegistryService
from domain.services.startup_readiness_service import StartupReadinessService
from domain.services.tts_orchestration_service import TtsOrchestrationService
from infrastructure.logging.jsonl_logger import JsonlLogger


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
    model_registry: ModelRegistryService
    startup_readiness: StartupReadinessService


@dataclass(slots=True)
class AppContainer:
    connection: sqlite3.Connection
    repositories: Repositories
    providers: Providers
    services: Services
    logger: JsonlLogger
    startup_readiness: dict[str, Any] | None = None


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
        chatterbox=ChatterboxProvider(),
        kokoro=KokoroProvider(),
    )
    services = Services(
        tts_orchestration=TtsOrchestrationService(),
        model_registry=ModelRegistryService(),
        startup_readiness=StartupReadinessService(),
    )
    return AppContainer(
        connection=connection,
        repositories=repositories,
        providers=providers,
        services=services,
        logger=logger,
        startup_readiness=None,
    )
