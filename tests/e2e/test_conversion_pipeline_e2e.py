"""
Tests end-to-end du pipeline de conversion audio.

Ces tests exercent le pipeline COMPLET avec de vrais fichiers :
  - Vraie base SQLite (en mémoire, avec FK activées)
  - Vrais services (ImportService, TtsOrchestrationService, etc.)
  - Vrais extracteurs de texte (TextExtractor)
  - Vrai ConversionWorker avec toutes les dépendances câblées
  - Provider TTS stubbé (hérite de BaseTtsProvider, retourne du silence WAV valide)

Objectif : détecter les bugs d'intégration que les tests unitaires ne peuvent pas
trouver, notamment les violations de contraintes FK SQLite, les problèmes d'ordre
d'opérations, et les ruptures de contrat entre services.
"""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from src.adapters.audio.mp3_encoder import Mp3Encoder
from src.adapters.audio.wav_builder import WavBuilder
from src.adapters.extraction.text_extractor import TextExtractor
from src.adapters.persistence.sqlite.migration_runner import apply_migrations
from src.adapters.persistence.sqlite.repositories.chunks_repository import ChunksRepository
from src.adapters.persistence.sqlite.repositories.conversion_jobs_repository import (
    ConversionJobsRepository,
)
from src.adapters.persistence.sqlite.repositories.documents_repository import DocumentsRepository
from src.adapters.persistence.sqlite.repositories.library_items_repository import (
    LibraryItemsRepository,
)
from src.adapters.tts.base_tts_provider import BaseTtsProvider
from src.contracts.result import Result, success
from src.domain.ports.tts_provider import TtsVoice
from src.domain.services.audio_postprocess_service import AudioPostprocessService
from src.domain.services.chunking_service import ChunkingService
from src.domain.services.import_service import ImportService
from src.domain.services.library_service import LibraryService
from src.domain.services.tts_orchestration_service import TtsOrchestrationService
from src.infrastructure.logging.noop_logger import NoopLogger
from src.ui.workers.conversion_worker import ConversionWorker


# ── Chemins des fixtures ──────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_TXT = FIXTURES_DIR / "sample_short.txt"
SAMPLE_MEDIUM_TXT = FIXTURES_DIR / "sample_medium.txt"
SAMPLE_MD = FIXTURES_DIR / "sample.md"
MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"


# ── Provider TTS stub ─────────────────────────────────────────────────────────

class StubTtsProvider(BaseTtsProvider):
    """Provider TTS stub héritant de BaseTtsProvider.

    Retourne du silence WAV valide sans nécessiter de modèle ML.
    Respecte le contrat TtsSynthesisData : {"audio_bytes": bytes, "metadata": {...}}.
    """

    engine_name = "stub_tts"
    _SAMPLE_RATE = 24000

    def __init__(self) -> None:
        super().__init__(healthy=True)

    def _get_available_voice_ids(self) -> list[str]:
        return ["stub_voice", "stub_voice_fr"]

    def _get_sample_rate(self) -> int:
        return self._SAMPLE_RATE

    def _synthesize_audio(self, text: str, voice: str) -> bytes:
        """Génère du silence WAV proportionnel à la longueur du texte."""
        return self._generate_silence(len(text))

    def _build_voice_list(self) -> list[TtsVoice]:
        return [
            {
                "id": "stub_voice",
                "name": "Stub Voice (EN)",
                "engine": self.engine_name,
                "language": "en",
                "supports_streaming": False,
            },
            {
                "id": "stub_voice_fr",
                "name": "Stub Voice (FR)",
                "engine": self.engine_name,
                "language": "fr",
                "supports_streaming": False,
            },
        ]


# ── Helpers de construction ───────────────────────────────────────────────────

def _make_in_memory_db() -> sqlite3.Connection:
    """Crée une base SQLite en mémoire avec toutes les migrations appliquées."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    apply_migrations(conn, str(MIGRATIONS_DIR))
    return conn


def _make_services(conn: sqlite3.Connection) -> dict[str, Any]:
    """Construit tous les services avec une vraie DB et un provider TTS stub."""
    logger = NoopLogger()

    documents_repo = DocumentsRepository(conn)
    jobs_repo = ConversionJobsRepository(conn)
    chunks_repo = ChunksRepository(conn)
    library_items_repo = LibraryItemsRepository(conn)

    text_extractor = TextExtractor(logger=logger)

    audio_postprocess = AudioPostprocessService(
        wav_builder=WavBuilder(),
        mp3_encoder=Mp3Encoder(),
        logger=logger,
    )
    library_service = LibraryService(
        library_items_repository=library_items_repo,
        logger=logger,
    )
    stub_provider = StubTtsProvider()

    tts_orchestration = TtsOrchestrationService(
        primary_provider=None,
        fallback_provider=stub_provider,
        audio_postprocess_service=audio_postprocess,
        library_service=library_service,
        chunking_service=ChunkingService(),
        chunks_repository=chunks_repo,
        conversion_jobs_repository=jobs_repo,
        documents_repository=documents_repo,
        logger=logger,
    )

    import_service = ImportService(
        documents_repository=documents_repo,
        logger=logger,
        text_extractor=text_extractor,
    )

    return {
        "logger": logger,
        "documents_repo": documents_repo,
        "jobs_repo": jobs_repo,
        "chunks_repo": chunks_repo,
        "library_items_repo": library_items_repo,
        "import_service": import_service,
        "tts_orchestration": tts_orchestration,
    }


def _make_worker(services: dict[str, Any]) -> ConversionWorker:
    """Construit un ConversionWorker avec toutes les dépendances câblées."""
    return ConversionWorker(
        recheck_callable=lambda: success({"status": "ready"}),
        logger=services["logger"],
        conversion_jobs_repository=services["jobs_repo"],
        conversion_launcher=services["tts_orchestration"],
        documents_repository=services["documents_repo"],
        import_service=services["import_service"],
        tts_orchestration=services["tts_orchestration"],
    )


def _default_config(engine: str = "stub_tts") -> dict[str, Any]:
    return {
        "engine": engine,
        "voice_id": "stub_voice",
        "language": "EN",
        "speech_rate": 1.0,
        "output_format": "wav",
    }


# ── Tests e2e : pipeline complet ──────────────────────────────────────────────

class TestConversionPipelineE2E:
    """Tests end-to-end du pipeline complet Import → Conversion → Audio."""

    def test_pipeline_txt_file_completes_successfully(self, tmp_path: Path) -> None:
        """
        Pipeline complet avec un fichier TXT court.
        Vérifie : import → extraction → chunking → job creation → synthèse → succès.
        """
        conn = _make_in_memory_db()
        services = _make_services(conn)
        worker = _make_worker(services)

        # 1. Import
        import_result = services["import_service"].import_document(str(SAMPLE_TXT))
        assert import_result.ok, f"Import échoué : {import_result.error}"
        document_id = import_result.data["id"]

        # 2. Conversion
        job_id = str(uuid4())
        future = worker.execute_conversion_async(
            document_id=document_id,
            job_id=job_id,
            correlation_id=str(uuid4()),
            conversion_config=_default_config(),
        )
        result = future.result(timeout=60)

        # 3. Vérifications
        assert result.ok, (
            f"Conversion échouée : {result.error.to_dict() if result.error else 'unknown'}"
        )

        job = services["jobs_repo"].get_job_by_id(job_id=job_id)
        assert job is not None, "Le job doit exister en DB"
        assert job["state"] == "completed", f"État attendu 'completed', obtenu '{job['state']}'"

        chunks = services["chunks_repo"].list_chunks_for_job(job_id=job_id)
        assert len(chunks) > 0, "Des chunks doivent avoir été créés"

        worker.shutdown()

    def test_pipeline_md_file_completes_successfully(self, tmp_path: Path) -> None:
        """Pipeline complet avec un fichier Markdown."""
        conn = _make_in_memory_db()
        services = _make_services(conn)
        worker = _make_worker(services)

        import_result = services["import_service"].import_document(str(SAMPLE_MD))
        assert import_result.ok, f"Import MD échoué : {import_result.error}"
        document_id = import_result.data["id"]

        job_id = str(uuid4())
        future = worker.execute_conversion_async(
            document_id=document_id,
            job_id=job_id,
            correlation_id=str(uuid4()),
            conversion_config=_default_config(),
        )
        result = future.result(timeout=60)

        assert result.ok, (
            f"Conversion MD échouée : {result.error.to_dict() if result.error else 'unknown'}"
        )

        job = services["jobs_repo"].get_job_by_id(job_id=job_id)
        assert job is not None
        assert job["state"] == "completed"

        worker.shutdown()

    def test_pipeline_medium_txt_creates_chunks_all_synthesized(self, tmp_path: Path) -> None:
        """
        Pipeline avec un fichier TXT plus long.
        Vérifie que tous les chunks sont dans l'état synthesized_*.
        """
        conn = _make_in_memory_db()
        services = _make_services(conn)
        worker = _make_worker(services)

        import_result = services["import_service"].import_document(str(SAMPLE_MEDIUM_TXT))
        assert import_result.ok
        document_id = import_result.data["id"]

        job_id = str(uuid4())
        future = worker.execute_conversion_async(
            document_id=document_id,
            job_id=job_id,
            correlation_id=str(uuid4()),
            conversion_config=_default_config(),
        )
        result = future.result(timeout=60)

        assert result.ok, (
            f"Conversion échouée : {result.error.to_dict() if result.error else 'unknown'}"
        )

        chunks = services["chunks_repo"].list_chunks_for_job(job_id=job_id)
        assert len(chunks) >= 1, "Au moins un chunk doit avoir été créé"

        for chunk in chunks:
            assert str(chunk["status"]).startswith("synthesized_"), (
                f"Chunk {chunk['chunk_index']} a le statut '{chunk['status']}' "
                "au lieu de 'synthesized_*'"
            )

        worker.shutdown()

    def test_no_integrity_error_chunks_inserted_after_job(self, tmp_path: Path) -> None:
        """
        Régression critique : l'IntegrityError SQLite ne doit plus se produire.

        Bug original : les chunks étaient insérés AVANT le job dans conversion_jobs,
        violant la contrainte FK chunks.job_id → conversion_jobs(id).

        Fix : le job est maintenant créé (_prepare_conversion_launch) AVANT
        l'extraction et le chunking (_extract_and_chunk).
        """
        conn = _make_in_memory_db()
        services = _make_services(conn)
        worker = _make_worker(services)

        import_result = services["import_service"].import_document(str(SAMPLE_TXT))
        assert import_result.ok
        document_id = import_result.data["id"]

        job_id = str(uuid4())

        try:
            future = worker.execute_conversion_async(
                document_id=document_id,
                job_id=job_id,
                correlation_id=str(uuid4()),
                conversion_config=_default_config(),
            )
            result = future.result(timeout=60)
        except Exception as exc:
            pytest.fail(
                f"Exception inattendue (probablement IntegrityError) : "
                f"{type(exc).__name__}: {exc}"
            )

        assert result.ok, (
            f"La conversion a échoué avec : "
            f"{result.error.to_dict() if result.error else 'unknown'}\n"
            "Si c'est une IntegrityError, le bug FK chunks→conversion_jobs n'est pas corrigé."
        )

        # Vérifier que le job existe et que les chunks le référencent correctement
        job = services["jobs_repo"].get_job_by_id(job_id=job_id)
        assert job is not None, "Le job doit exister en DB"

        chunks = services["chunks_repo"].list_chunks_for_job(job_id=job_id)
        assert len(chunks) > 0, "Des chunks doivent exister en DB"

        for chunk in chunks:
            assert chunk["job_id"] == job_id, (
                f"Le chunk {chunk['chunk_index']} référence job_id='{chunk['job_id']}' "
                f"au lieu de '{job_id}'"
            )

        worker.shutdown()

    def test_conversion_with_unknown_document_id_fails_gracefully(self, tmp_path: Path) -> None:
        """
        Conversion avec un document_id inexistant : doit échouer proprement.
        """
        conn = _make_in_memory_db()
        services = _make_services(conn)
        worker = _make_worker(services)

        job_id = str(uuid4())
        future = worker.execute_conversion_async(
            document_id=str(uuid4()),  # document inexistant
            job_id=job_id,
            correlation_id=str(uuid4()),
            conversion_config=_default_config(),
        )
        result = future.result(timeout=30)

        assert not result.ok, "La conversion doit échouer si le document n'existe pas"
        assert result.error is not None, "Une erreur structurée doit être retournée"

        worker.shutdown()

    def test_conversion_progress_callbacks_fired(self, tmp_path: Path) -> None:
        """
        Vérifie que les callbacks de progression et d'état sont appelés.
        """
        conn = _make_in_memory_db()
        services = _make_services(conn)
        worker = _make_worker(services)

        state_events: list[dict[str, Any]] = []
        worker.on_conversion_state_changed(lambda s: state_events.append(dict(s)))

        import_result = services["import_service"].import_document(str(SAMPLE_TXT))
        assert import_result.ok
        document_id = import_result.data["id"]

        job_id = str(uuid4())
        future = worker.execute_conversion_async(
            document_id=document_id,
            job_id=job_id,
            correlation_id=str(uuid4()),
            conversion_config=_default_config(),
        )
        result = future.result(timeout=60)

        assert result.ok, (
            f"Conversion échouée : {result.error.to_dict() if result.error else 'unknown'}"
        )

        statuses = [e.get("status") for e in state_events]
        assert "completed" in statuses, (
            f"L'état 'completed' doit être émis, états reçus : {statuses}"
        )

        worker.shutdown()

    def test_two_conversions_same_document_independent_jobs(self, tmp_path: Path) -> None:
        """
        Deux conversions du même document avec des job_id différents.
        Vérifie que les jobs et chunks sont bien isolés.
        """
        conn = _make_in_memory_db()
        services = _make_services(conn)
        worker = _make_worker(services)

        import_result = services["import_service"].import_document(str(SAMPLE_TXT))
        assert import_result.ok
        document_id = import_result.data["id"]

        # Première conversion
        job_id_1 = str(uuid4())
        f1 = worker.execute_conversion_async(
            document_id=document_id,
            job_id=job_id_1,
            correlation_id=str(uuid4()),
            conversion_config=_default_config(),
        )
        r1 = f1.result(timeout=60)
        assert r1.ok, f"Première conversion échouée : {r1.error}"

        # Deuxième conversion
        job_id_2 = str(uuid4())
        f2 = worker.execute_conversion_async(
            document_id=document_id,
            job_id=job_id_2,
            correlation_id=str(uuid4()),
            conversion_config=_default_config(),
        )
        r2 = f2.result(timeout=60)
        assert r2.ok, f"Deuxième conversion échouée : {r2.error}"

        # Les deux jobs doivent être completed
        j1 = services["jobs_repo"].get_job_by_id(job_id=job_id_1)
        j2 = services["jobs_repo"].get_job_by_id(job_id=job_id_2)
        assert j1 is not None and j1["state"] == "completed"
        assert j2 is not None and j2["state"] == "completed"

        # Les chunks doivent être isolés par job
        chunks_1 = services["chunks_repo"].list_chunks_for_job(job_id=job_id_1)
        chunks_2 = services["chunks_repo"].list_chunks_for_job(job_id=job_id_2)
        assert all(c["job_id"] == job_id_1 for c in chunks_1)
        assert all(c["job_id"] == job_id_2 for c in chunks_2)

        worker.shutdown()


# ── Tests e2e : phase d'import ────────────────────────────────────────────────

class TestImportPipelineE2E:
    """Tests e2e de la phase d'import uniquement."""

    def test_import_txt_persists_document_in_db(self) -> None:
        """Import d'un fichier TXT : vérifie la persistance en DB."""
        conn = _make_in_memory_db()
        services = _make_services(conn)

        result = services["import_service"].import_document(str(SAMPLE_TXT))

        assert result.ok, f"Import échoué : {result.error}"
        assert result.data["id"], "L'ID du document doit être non vide"
        assert result.data["source_format"] == "txt"

        doc = services["documents_repo"].get_document_by_id(document_id=result.data["id"])
        assert doc is not None, "Le document doit être persisté en DB"
        assert doc["source_format"] == "txt"

    def test_import_md_persists_document_in_db(self) -> None:
        """Import d'un fichier Markdown : vérifie la persistance en DB."""
        conn = _make_in_memory_db()
        services = _make_services(conn)

        result = services["import_service"].import_document(str(SAMPLE_MD))

        assert result.ok, f"Import MD échoué : {result.error}"
        assert result.data["source_format"] == "md"

        doc = services["documents_repo"].get_document_by_id(document_id=result.data["id"])
        assert doc is not None
        assert doc["source_format"] == "md"

    def test_import_nonexistent_file_fails_with_structured_error(self) -> None:
        """Import d'un fichier inexistant : doit échouer proprement."""
        conn = _make_in_memory_db()
        services = _make_services(conn)

        result = services["import_service"].import_document("/nonexistent/path/file.txt")

        assert not result.ok
        assert result.error is not None
        assert result.error.code == "import.file_missing"

    def test_import_then_extract_txt_returns_readable_text(self) -> None:
        """Import puis extraction : vérifie que le texte est correctement extrait."""
        conn = _make_in_memory_db()
        services = _make_services(conn)

        import_result = services["import_service"].import_document(str(SAMPLE_TXT))
        assert import_result.ok
        document = import_result.data

        extract_result = services["import_service"].extract_document(
            document={k: str(v) for k, v in document.items()},
            correlation_id=str(uuid4()),
            job_id=str(uuid4()),
        )

        assert extract_result.ok, f"Extraction échouée : {extract_result.error}"
        text = extract_result.data.get("text", "")
        assert len(text) > 0, "Le texte extrait doit être non vide"
        # Le fichier sample_short.txt contient "quick brown fox"
        assert "fox" in text.lower() or "quick" in text.lower()

    def test_import_then_extract_md_strips_markdown_syntax(self) -> None:
        """Import puis extraction Markdown : la syntaxe MD doit être supprimée."""
        conn = _make_in_memory_db()
        services = _make_services(conn)

        import_result = services["import_service"].import_document(str(SAMPLE_MD))
        assert import_result.ok
        document = import_result.data

        extract_result = services["import_service"].extract_document(
            document={k: str(v) for k, v in document.items()},
            correlation_id=str(uuid4()),
            job_id=str(uuid4()),
        )

        assert extract_result.ok, f"Extraction MD échouée : {extract_result.error}"
        text = extract_result.data.get("text", "")
        assert len(text) > 0

        # Les marqueurs Markdown doivent être supprimés
        assert "## " not in text, "Les titres ## ne doivent pas apparaître dans le texte extrait"
        assert "# " not in text, "Les titres # ne doivent pas apparaître dans le texte extrait"


# ── Tests e2e : contraintes DB ────────────────────────────────────────────────

class TestDatabaseConstraintsE2E:
    """Tests vérifiant les contraintes FK SQLite."""

    def test_insert_chunks_without_job_raises_integrity_error(self) -> None:
        """
        Régression : insérer des chunks sans job parent doit lever une IntegrityError.
        Cela confirme que les FK sont bien activées.
        """
        conn = _make_in_memory_db()
        chunks_repo = ChunksRepository(conn)

        fake_job_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with pytest.raises(Exception):
            # Doit lever sqlite3.IntegrityError (FK violation)
            chunks_repo.replace_chunks_for_job(
                job_id=fake_job_id,
                chunks=[{
                    "chunk_index": 0,
                    "text_content": "Hello world.",
                    "content_hash": "abc123",
                    "status": "pending",
                    "created_at": now,
                }],
            )

    def test_insert_job_without_document_raises_integrity_error(self) -> None:
        """
        Insérer un job avec un document_id inexistant doit lever une IntegrityError.
        """
        conn = _make_in_memory_db()
        jobs_repo = ConversionJobsRepository(conn)

        now = datetime.now(timezone.utc).isoformat()

        with pytest.raises(Exception):
            jobs_repo.create_job(
                job_id=str(uuid4()),
                document_id=str(uuid4()),  # document inexistant
                state="queued",
                engine="stub_tts",
                voice="stub_voice",
                language="EN",
                speech_rate=1.0,
                output_format="wav",
                created_at=now,
                updated_at=now,
            )

    def test_correct_order_document_then_job_then_chunks_succeeds(self) -> None:
        """
        L'ordre correct document → job → chunks doit réussir sans erreur FK.
        """
        conn = _make_in_memory_db()
        documents_repo = DocumentsRepository(conn)
        jobs_repo = ConversionJobsRepository(conn)
        chunks_repo = ChunksRepository(conn)

        now = datetime.now(timezone.utc).isoformat()

        # 1. Créer le document
        doc = documents_repo.create_document({
            "source_path": str(SAMPLE_TXT),
            "title": "Test",
            "source_format": "txt",
        })

        # 2. Créer le job
        job_id = str(uuid4())
        jobs_repo.create_job(
            job_id=job_id,
            document_id=doc["id"],
            state="queued",
            engine="stub_tts",
            voice="stub_voice",
            language="EN",
            speech_rate=1.0,
            output_format="wav",
            created_at=now,
            updated_at=now,
        )

        # 3. Insérer les chunks → doit réussir
        chunks = chunks_repo.replace_chunks_for_job(
            job_id=job_id,
            chunks=[
                {
                    "chunk_index": 0,
                    "text_content": "Hello world.",
                    "content_hash": "abc",
                    "status": "pending",
                    "created_at": now,
                },
                {
                    "chunk_index": 1,
                    "text_content": "Second sentence.",
                    "content_hash": "def",
                    "status": "pending",
                    "created_at": now,
                },
            ],
        )

        assert len(chunks) == 2
        assert all(c["job_id"] == job_id for c in chunks)


# ── Tests e2e : worker avec fichier temporaire ────────────────────────────────

class TestWorkerWithTempFiles:
    """Tests e2e utilisant des fichiers temporaires créés à la volée."""

    def test_pipeline_with_custom_txt_content(self, tmp_path: Path) -> None:
        """
        Pipeline avec un fichier TXT créé dynamiquement.
        Vérifie que le contenu personnalisé est correctement traité.
        """
        # Créer un fichier TXT temporaire
        test_file = tmp_path / "custom_test.txt"
        test_file.write_text(
            "This is a custom test document.\n"
            "It has multiple sentences to verify the pipeline.\n"
            "Each sentence should be processed correctly by the TTS engine.\n",
            encoding="utf-8",
        )

        conn = _make_in_memory_db()
        services = _make_services(conn)
        worker = _make_worker(services)

        import_result = services["import_service"].import_document(str(test_file))
        assert import_result.ok, f"Import échoué : {import_result.error}"

        job_id = str(uuid4())
        future = worker.execute_conversion_async(
            document_id=import_result.data["id"],
            job_id=job_id,
            correlation_id=str(uuid4()),
            conversion_config=_default_config(),
        )
        result = future.result(timeout=60)

        assert result.ok, (
            f"Conversion échouée : {result.error.to_dict() if result.error else 'unknown'}"
        )

        job = services["jobs_repo"].get_job_by_id(job_id=job_id)
        assert job["state"] == "completed"

        worker.shutdown()

    def test_pipeline_with_french_text(self, tmp_path: Path) -> None:
        """
        Pipeline avec du texte français.
        Vérifie que les caractères accentués sont correctement traités.
        """
        test_file = tmp_path / "french_test.txt"
        test_file.write_text(
            "Bonjour, ceci est un test en français.\n"
            "Les caractères accentués comme é, è, à, ù doivent être supportés.\n"
            "Ce texte sera converti en audio par le moteur TTS.\n",
            encoding="utf-8",
        )

        conn = _make_in_memory_db()
        services = _make_services(conn)
        worker = _make_worker(services)

        import_result = services["import_service"].import_document(str(test_file))
        assert import_result.ok, f"Import FR échoué : {import_result.error}"

        job_id = str(uuid4())
        future = worker.execute_conversion_async(
            document_id=import_result.data["id"],
            job_id=job_id,
            correlation_id=str(uuid4()),
            conversion_config={
                "engine": "stub_tts",
                "voice_id": "stub_voice",
                "language": "FR",
                "speech_rate": 1.0,
                "output_format": "wav",
            },
        )
        result = future.result(timeout=60)

        assert result.ok, (
            f"Conversion FR échouée : {result.error.to_dict() if result.error else 'unknown'}"
        )

        job = services["jobs_repo"].get_job_by_id(job_id=job_id)