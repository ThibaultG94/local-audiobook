"""
Test e2e réel : lance le vrai pipeline de l'application avec bootstrap().

Ce test utilise exactement le même wiring que src/app/main.py :
- bootstrap() réel (DB, migrations, logging, model registry)
- ImportService réel avec vrais extracteurs
- TtsOrchestrationService réel avec Kokoro et Chatterbox
- ConversionWorker réel avec toutes les dépendances

Exécution :
    python -m pytest tests/e2e/test_real_pipeline.py -v -s

Ou directement :
    python tests/e2e/test_real_pipeline.py
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path
from uuid import uuid4

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from adapters.extraction.epub_extractor import EpubExtractor
from adapters.extraction.pdf_extractor import PdfExtractor
from adapters.extraction.text_extractor import TextExtractor
from app.dependency_container import build_conversion_worker
from app.main import bootstrap
from domain.services.import_service import ImportService


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_TXT = FIXTURES_DIR / "sample_short.txt"
SAMPLE_MD = FIXTURES_DIR / "sample.md"


def _print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _print_result(label: str, result: object) -> None:
    if hasattr(result, "ok"):
        status = "✅ OK" if result.ok else "❌ FAIL"
        print(f"  {status} | {label}")
        if not result.ok and result.error:
            err = result.error.to_dict() if hasattr(result.error, "to_dict") else str(result.error)
            print(f"       Error: {json.dumps(err, indent=6, default=str)}")
        elif result.ok and result.data:
            data_preview = {k: v for k, v in (result.data or {}).items() if k not in ("chunk_results",)}
            print(f"       Data:  {json.dumps(data_preview, indent=6, default=str)}")
    else:
        print(f"  ℹ️  {label}: {result}")


def run_full_pipeline_test(
    file_path: Path,
    engine: str = "kokoro_cpu",
    voice_id: str = "ff_siwis",
    language: str = "FR",
    output_format: str = "mp3",
    speech_rate: float = 1.0,
) -> bool:
    """
    Lance le pipeline complet avec le vrai bootstrap().
    Retourne True si la conversion réussit, False sinon.
    """
    _print_section(f"TEST: {file_path.name} | engine={engine} | voice={voice_id} | fmt={output_format}")

    # ── 1. Bootstrap ──────────────────────────────────────────────────────────
    print("\n[1/5] Bootstrap de l'application...")
    try:
        container = bootstrap(
            app_config_path="config/app_config.yaml",
            logging_config_path="config/logging_config.yaml",
            model_manifest_path="config/model_manifest.yaml",
        )
        print(f"  ✅ Bootstrap OK")
        readiness = container.startup_readiness_result
        if readiness and readiness.data:
            print(f"  Readiness: {readiness.data.get('status', 'unknown')}")
    except Exception as exc:
        print(f"  ❌ Bootstrap FAILED: {exc}")
        traceback.print_exc()
        return False

    # ── 2. Construire ImportService ───────────────────────────────────────────
    print("\n[2/5] Construction de l'ImportService...")
    import_service = ImportService(
        documents_repository=container.repositories.documents,
        logger=container.logger,
        epub_extractor=EpubExtractor(logger=container.logger),
        pdf_extractor=PdfExtractor(logger=container.logger),
        text_extractor=TextExtractor(logger=container.logger),
    )
    print("  ✅ ImportService construit")

    # ── 3. Import du document ─────────────────────────────────────────────────
    print(f"\n[3/5] Import du fichier: {file_path}")
    import_result = import_service.import_document(str(file_path))
    _print_result("import_document()", import_result)
    if not import_result.ok:
        return False

    document_id = import_result.data["id"]
    print(f"  document_id = {document_id}")

    # ── 4. Construire le ConversionWorker ─────────────────────────────────────
    print("\n[4/5] Construction du ConversionWorker...")
    worker = build_conversion_worker(
        container,
        "config/model_manifest.yaml",
        import_service=import_service,
    )
    print("  ✅ ConversionWorker construit")

    # Enregistrer les callbacks pour voir les événements
    state_events: list[dict] = []
    error_events: list[dict] = []

    worker.on_conversion_state_changed(lambda s: state_events.append(dict(s)))
    worker.on_conversion_failed(lambda e: error_events.append(dict(e)))

    # ── 5. Lancer la conversion ───────────────────────────────────────────────
    job_id = str(uuid4())
    correlation_id = str(uuid4())
    conversion_config = {
        "engine": engine,
        "voice_id": voice_id,
        "language": language,
        "speech_rate": speech_rate,
        "output_format": output_format,
    }

    print(f"\n[5/5] Lancement de la conversion...")
    print(f"  job_id = {job_id}")
    print(f"  config = {json.dumps(conversion_config, indent=4)}")

    start_time = time.time()
    try:
        future = worker.execute_conversion_async(
            document_id=document_id,
            job_id=job_id,
            correlation_id=correlation_id,
            conversion_config=conversion_config,
        )
        result = future.result(timeout=300)  # 5 minutes max
    except Exception as exc:
        print(f"  ❌ Exception pendant la conversion: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        worker.shutdown()
        return False

    elapsed = time.time() - start_time
    print(f"\n  Durée: {elapsed:.1f}s")

    _print_result("execute_conversion_async()", result)

    # Afficher les événements d'état
    if state_events:
        print(f"\n  Événements d'état ({len(state_events)}):")
        for evt in state_events:
            print(f"    - status={evt.get('status')} progress={evt.get('progress_percent')}%")

    if error_events:
        print(f"\n  Événements d'erreur ({len(error_events)}):")
        for evt in error_events:
            err = evt.get("error", {})
            print(f"    - code={err.get('code')}")
            print(f"      message={err.get('message')}")
            details = err.get("details", {})
            if details:
                print(f"      details={json.dumps(details, indent=8, default=str)}")

    # Vérifier le job en DB
    job = container.repositories.conversion_jobs.get_job_by_id(job_id=job_id)
    if job:
        print(f"\n  Job en DB: state={job['state']}")
    else:
        print(f"\n  ⚠️  Job non trouvé en DB")

    # Vérifier les chunks
    chunks = container.repositories.chunks.list_chunks_for_job(job_id=job_id)
    print(f"  Chunks en DB: {len(chunks)}")
    for chunk in chunks[:5]:  # Afficher les 5 premiers
        print(f"    chunk[{chunk['chunk_index']}] status={chunk['status']} len={len(str(chunk['text_content']))}")

    worker.shutdown()
    return result.ok


def run_all_tests() -> None:
    """Lance tous les scénarios de test."""
    results: list[tuple[str, bool]] = []

    # Test 1: TXT avec Kokoro FR
    ok = run_full_pipeline_test(
        file_path=SAMPLE_TXT,
        engine="kokoro_cpu",
        voice_id="ff_siwis",
        language="FR",
        output_format="mp3",
        speech_rate=1.0,
    )
    results.append(("TXT + Kokoro FR (ff_siwis) + MP3", ok))

    # Test 2: TXT avec Kokoro EN
    ok = run_full_pipeline_test(
        file_path=SAMPLE_TXT,
        engine="kokoro_cpu",
        voice_id="af_heart",
        language="EN",
        output_format="wav",
        speech_rate=1.0,
    )
    results.append(("TXT + Kokoro EN (af_heart) + WAV", ok))

    # Test 3: MD avec Kokoro FR
    ok = run_full_pipeline_test(
        file_path=SAMPLE_MD,
        engine="kokoro_cpu",
        voice_id="ff_siwis",
        language="FR",
        output_format="mp3",
        speech_rate=1.0,
    )
    results.append(("MD + Kokoro FR (ff_siwis) + MP3", ok))

    # Résumé
    _print_section("RÉSUMÉ DES TESTS")
    all_ok = True
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status} | {name}")
        if not ok:
            all_ok = False

    print(f"\n{'='*60}")
    if all_ok:
        print("  🎉 TOUS LES TESTS PASSENT")
    else:
        print("  💥 CERTAINS TESTS ÉCHOUENT")
    print(f"{'='*60}\n")

    sys.exit(0 if all_ok else 1)


# ── pytest integration ────────────────────────────────────────────────────────

import pytest


@pytest.fixture(scope="module")
def app_container():
    """Bootstrap l'application une seule fois pour tous les tests du module."""
    container = bootstrap(
        app_config_path="config/app_config.yaml",
        logging_config_path="config/logging_config.yaml",
        model_manifest_path="config/model_manifest.yaml",
    )
    yield container


@pytest.fixture(scope="module")
def real_import_service(app_container):
    """ImportService réel avec tous les extracteurs."""
    return ImportService(
        documents_repository=app_container.repositories.documents,
        logger=app_container.logger,
        epub_extractor=EpubExtractor(logger=app_container.logger),
        pdf_extractor=PdfExtractor(logger=app_container.logger),
        text_extractor=TextExtractor(logger=app_container.logger),
    )


@pytest.fixture(scope="module")
def real_worker(app_container, real_import_service):
    """ConversionWorker réel avec toutes les dépendances."""
    worker = build_conversion_worker(
        app_container,
        "config/model_manifest.yaml",
        import_service=real_import_service,
    )
    yield worker
    worker.shutdown()


def _run_conversion(worker, app_container, document_id: str, config: dict) -> tuple:
    """Helper : lance une conversion et retourne (result, job, chunks)."""
    job_id = str(uuid4())
    error_details: list[dict] = []
    worker.on_conversion_failed(lambda e: error_details.append(dict(e)))

    future = worker.execute_conversion_async(
        document_id=document_id,
        job_id=job_id,
        correlation_id=str(uuid4()),
        conversion_config=config,
    )
    result = future.result(timeout=300)
    job = app_container.repositories.conversion_jobs.get_job_by_id(job_id=job_id)
    chunks = app_container.repositories.chunks.list_chunks_for_job(job_id=job_id)
    return result, job, chunks, error_details


class TestRealPipelineKokoro:
    """Tests e2e avec le vrai provider Kokoro (nécessite les modèles)."""

    def test_kokoro_fr_txt_mp3(self, real_worker, app_container, real_import_service):
        """Conversion TXT → MP3 avec Kokoro FR (voix ff_siwis)."""
        import_result = real_import_service.import_document(str(SAMPLE_TXT))
        assert import_result.ok, f"Import échoué: {import_result.error}"

        result, job, chunks, errors = _run_conversion(
            real_worker, app_container,
            document_id=import_result.data["id"],
            config={
                "engine": "kokoro_cpu",
                "voice_id": "ff_siwis",
                "language": "FR",
                "speech_rate": 1.0,
                "output_format": "mp3",
            },
        )

        if not result.ok:
            err = result.error.to_dict() if result.error else {}
            pytest.fail(
                f"Conversion Kokoro FR échouée:\n"
                f"  code: {err.get('code')}\n"
                f"  message: {err.get('message')}\n"
                f"  details: {json.dumps(err.get('details', {}), indent=4, default=str)}\n"
                f"  job_state: {job['state'] if job else 'N/A'}\n"
                f"  chunks: {len(chunks)}\n"
                f"  error_events: {json.dumps(errors, indent=4, default=str)}"
            )

        assert job is not None, "Le job doit exister en DB"
        assert job["state"] == "completed", f"État attendu 'completed', obtenu '{job['state']}'"
        assert len(chunks) > 0, "Des chunks doivent avoir été créés"

    def test_kokoro_en_txt_wav(self, real_worker, app_container, real_import_service):
        """Conversion TXT → WAV avec Kokoro EN (voix af_heart)."""
        import_result = real_import_service.import_document(str(SAMPLE_TXT))
        assert import_result.ok, f"Import échoué: {import_result.error}"

        result, job, chunks, errors = _run_conversion(
            real_worker, app_container,
            document_id=import_result.data["id"],
            config={
                "engine": "kokoro_cpu",
                "voice_id": "af_heart",
                "language": "EN",
                "speech_rate": 1.0,
                "output_format": "wav",
            },
        )

        if not result.ok:
            err = result.error.to_dict() if result.error else {}
            pytest.fail(
                f"Conversion Kokoro EN échouée:\n"
                f"  code: {err.get('code')}\n"
                f"  message: {err.get('message')}\n"
                f"  details: {json.dumps(err.get('details', {}), indent=4, default=str)}\n"
                f"  job_state: {job['state'] if job else 'N/A'}\n"
                f"  chunks: {len(chunks)}\n"
                f"  error_events: {json.dumps(errors, indent=4, default=str)}"
            )

        assert job["state"] == "completed"
        assert len(chunks) > 0

    def test_kokoro_fr_md_mp3(self, real_worker, app_container, real_import_service):
        """Conversion MD → MP3 avec Kokoro FR."""
        import_result = real_import_service.import_document(str(SAMPLE_MD))
        assert import_result.ok, f"Import MD échoué: {import_result.error}"

        result, job, chunks, errors = _run_conversion(
            real_worker, app_container,
            document_id=import_result.data["id"],
            config={
                "engine": "kokoro_cpu",
                "voice_id": "ff_siwis",
                "language": "FR",
                "speech_rate": 1.0,
                "output_format": "mp3",
            },
        )

        if not result.ok:
            err = result.error.to_dict() if result.error else {}
            pytest.fail(
                f"Conversion Kokoro FR MD échouée:\n"
                f"  code: {err.get('code')}\n"
                f"  message: {err.get('message')}\n"
                f"  details: {json.dumps(err.get('details', {}), indent=4, default=str)}\n"
                f"  job_state: {job['state'] if job else 'N/A'}\n"
                f"  chunks: {len(chunks)}\n"
                f"  error_events: {json.dumps(errors, indent=4, default=str)}"
            )

        assert job["state"] == "completed"


if __name__ == "__main__":
    run_all_tests()
