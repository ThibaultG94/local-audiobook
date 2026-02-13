# Story 3.4: Persist Job Lifecycle and Resume Conversion from Last Failed Chunk

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user converting long documents,
I want conversion state to persist with controlled transitions and resume capability,
so that failures do not force restarting from the beginning.

## Acceptance Criteria

1. **Given** a conversion job is created and tracked in persistence  
   **When** state changes are requested during execution  
   **Then** only `queued`, `running`, `paused`, `failed`, `completed` transitions accepted by service rules are applied  
   **And** invalid transitions are rejected with normalized error payload.

2. **Given** chunk progress is persisted during synthesis  
   **When** a chunk fails and the job is retried  
   **Then** orchestration resumes from the last non validated chunk  
   **And** already successful chunks are not reprocessed unless explicitly requested.

3. **Given** resume behavior must remain deterministic  
   **When** retry is executed for the same job inputs  
   **Then** the same chunk order and state progression are preserved  
   **And** logs indicate resume start point and retry decision path.

4. **Given** operators need troubleshooting visibility  
   **When** job transitions and resume events occur  
   **Then** JSONL events include `correlation_id`, `job_id`, `chunk_index` when applicable, `stage`, `event`, `severity`, `timestamp`  
   **And** events use stable `domain.action` naming for transition and resume paths.

## Tasks / Subtasks

- [x] Enforce persisted job lifecycle transitions via service-level validator (AC: 1)
  - [x] Implement conversion-job repository methods to read/update job state atomically in [conversion_jobs_repository.py](src/adapters/persistence/sqlite/repositories/conversion_jobs_repository.py).
  - [x] Route all transition requests through [validate_job_state_transition()](src/domain/services/job_state_validator.py:18) before persistence updates.
  - [x] Return normalized errors (`code`, `message`, `details`, `retryable`) for invalid transitions.
- [x] Implement deterministic resume start-point selection from persisted chunk outcomes (AC: 2, 3)
  - [x] Extend orchestration in [synthesize_persisted_chunks_for_job()](src/domain/services/tts_orchestration_service.py:123) to skip already successful chunks by default.
  - [x] Compute resume index from persisted chunk statuses (`pending`, `failed`, `synthesized_*`) with deterministic ordering.
  - [x] Add explicit override flag for full reprocess only when requested.
- [x] Persist and emit transition/resume observability events (AC: 3, 4)
  - [x] Emit job transition events (for example `job.transition_requested`, `job.transition_applied`, `job.transition_rejected`) with required schema fields.
  - [x] Emit resume events (`conversion.resume_started`, `conversion.resume_checkpoint_selected`) with selected chunk index and retry decision path.
  - [x] Keep timestamps UTC ISO-8601 and event naming compliant with `domain.action` conventions.
- [x] Add regression coverage for resume and lifecycle persistence (AC: 1..4)
  - [x] Extend unit tests in [test_tts_orchestration_service.py](tests/unit/test_tts_orchestration_service.py) for resume selection, transition validation integration, and deterministic retry behavior.
  - [x] Extend integration tests in [test_chunk_persistence_and_resume_path.py](tests/integration/test_chunk_persistence_and_resume_path.py) for end-to-end resume from failed chunk and no reprocessing of successful chunks.
  - [x] Add repository-focused tests for conversion job state updates and transition rejection behavior.

## Dev Notes

- Story `3.4` étend directement les capacités livrées en [3-3-orchestrate-deterministic-conversion-with-engine-fallback.md](_bmad-output/implementation-artifacts/3-3-orchestrate-deterministic-conversion-with-engine-fallback.md): la base de synthèse ordonnée, fallback déterministe, et persist des statuts chunk existe déjà.
- La cible de cette story est la **reprise déterministe** et la **persistance du cycle de vie job**; ne pas réécrire la logique de fallback provider qui reste dans [synthesize_persisted_chunks_for_job()](src/domain/services/tts_orchestration_service.py:123).
- Le validateur d’états [validate_job_state_transition()](src/domain/services/job_state_validator.py:18) est la source d’autorité pour les transitions `queued|running|paused|failed|completed`.
- Le dépôt [ConversionJobsRepository](src/adapters/persistence/sqlite/repositories/conversion_jobs_repository.py) est actuellement un stub; cette story doit le rendre opérationnel pour lecture/écriture atomique de l’état job et `updated_at`.
- Les chunks persistés (`pending`, `failed`, `synthesized_*`) constituent la vérité terrain pour décider le point de reprise; la reprise ne doit pas retraiter les chunks déjà synthétisés sauf demande explicite.
- Les événements JSONL doivent rester conformes au schéma de [event_schema.py](src/infrastructure/logging/event_schema.py:1) avec nommage `domain.action` et timestamps UTC ISO-8601.

### Technical Requirements

- Étendre [ConversionJobsRepository](src/adapters/persistence/sqlite/repositories/conversion_jobs_repository.py) avec au minimum:
  - lecture d’un job par `id` (incluant `state`, `updated_at`),
  - mise à jour atomique de l’état avec contrôle du nombre de lignes affectées,
  - conservation de la cohérence transactionnelle SQLite.
- Intégrer le validateur [validate_job_state_transition()](src/domain/services/job_state_validator.py:18) dans le flux d’orchestration pour chaque transition demandée avant `UPDATE` SQL.
- Faire évoluer [synthesize_persisted_chunks_for_job()](src/domain/services/tts_orchestration_service.py:123) pour supporter la reprise:
  - calcul du `resume_start_index` depuis les statuts chunks persistés,
  - skip des chunks déjà `synthesized_*` par défaut,
  - option explicite pour forcer un rerun complet.
- Préserver les enveloppes normalisées:
  - succès: `{ok: true, data, error: null}`,
  - échec: `{ok: false, data: null, error:{code,message,details,retryable}}`.
- Propager les métadonnées de reprise dans `details` d’erreur/succès (`resume_start_index`, `attempted_engines`, `transition_intent`) pour diagnostic local.

### Architecture Compliance

- Respecter la séparation des couches définie dans l’architecture:
  - orchestration et règles métier dans [tts_orchestration_service.py](src/domain/services/tts_orchestration_service.py),
  - validation d’état via [job_state_validator.py](src/domain/services/job_state_validator.py),
  - persistance via repositories SQLite sous [repositories](src/adapters/persistence/sqlite/repositories),
  - observabilité via [jsonl_logger.py](src/infrastructure/logging/jsonl_logger.py).
- Ne pas déplacer la logique de fallback dans les providers [chatterbox_provider.py](src/adapters/tts/chatterbox_provider.py) ou [kokoro_provider.py](src/adapters/tts/kokoro_provider.py): cette story traite le cycle de vie job/reprise, pas la politique provider.
- Conserver l’ordre déterministe des chunks basé sur `chunk_index` tel qu’établi dans [synthesize_persisted_chunks_for_job()](src/domain/services/tts_orchestration_service.py:123).
- Maintenir la compatibilité avec le schéma SQL actuel de [0001_initial_schema.sql](migrations/0001_initial_schema.sql) et éviter toute dérive de contrat non couverte par migration.

### Library / Framework Requirements

- Conserver la baseline runtime Python `>=3.10` et éviter l’ajout de dépendances tierces pour cette story.
- Réutiliser les composants existants:
  - logger JSONL [JsonlLogger](src/infrastructure/logging/jsonl_logger.py),
  - schéma d’événements [event_schema.py](src/infrastructure/logging/event_schema.py),
  - contrats résultat/erreur [result.py](src/contracts/result.py) et [errors.py](src/contracts/errors.py).
- Conserver la compatibilité avec les versions de référence vérifiées pendant l’analyse (notamment PyQt5 `5.15.11` et PyYAML `6.0.3`) sans forcer de bump dans cette story.
- Ne pas introduire d’ORM ni de couche persistence alternative: SQLite direct via repositories reste la norme projet.

### File Structure Requirements

- Cibles d’implémentation principales:
  - [conversion_jobs_repository.py](src/adapters/persistence/sqlite/repositories/conversion_jobs_repository.py) (sortir du stub, CRUD minimal d’état),
  - [tts_orchestration_service.py](src/domain/services/tts_orchestration_service.py) (resume index, skip chunks déjà réussis, événements de reprise),
  - éventuellement [chunks_repository.py](src/adapters/persistence/sqlite/repositories/chunks_repository.py) si méthodes de filtrage/reprise manquent.
- Cibles de tests:
  - [test_tts_orchestration_service.py](tests/unit/test_tts_orchestration_service.py),
  - [test_job_state_validator.py](tests/unit/test_job_state_validator.py),
  - [test_chunk_persistence_and_resume_path.py](tests/integration/test_chunk_persistence_and_resume_path.py).
- Ne pas disperser la logique de transition/reprise dans UI ou adapters TTS:
  - pas de logique métier dans [conversion_worker.py](src/ui/workers/conversion_worker.py),
  - pas de logique de reprise dans [base_tts_provider.py](src/adapters/tts/base_tts_provider.py).
- Maintenir le pattern de nommage actuel (modules repository au pluriel) et l’organisation source/tests déjà utilisée dans les stories 3.2/3.3.

### Testing Requirements

- Unit tests à ajouter/étendre dans [test_tts_orchestration_service.py](tests/unit/test_tts_orchestration_service.py):
  - sélection déterministe de `resume_start_index` à partir d’un mix de statuts chunks,
  - validation que les chunks `synthesized_*` sont ignorés par défaut en reprise,
  - validation qu’un mode explicite permet le reprocess complet,
  - vérification des transitions d’état invalides avec erreurs normalisées.
- Unit tests repository pour [ConversionJobsRepository](src/adapters/persistence/sqlite/repositories/conversion_jobs_repository.py):
  - lecture d’état job,
  - update état + `updated_at`,
  - rejet sur job introuvable ou transition invalide (si la validation est câblée au service appelant).
- Integration tests dans [test_chunk_persistence_and_resume_path.py](tests/integration/test_chunk_persistence_and_resume_path.py):
  - scénario “échec chunk N puis reprise” sans retraitement des chunks antérieurs déjà synthétisés,
  - persistance des statuts avant/après reprise,
  - cohérence des événements `conversion.resume_*` et `job.transition_*`.
- Contrat observabilité:
  - tous les événements de transition/reprise incluent les champs requis du schéma [REQUIRED_EVENT_FIELDS](src/infrastructure/logging/event_schema.py:4),
  - timestamps validés via [is_valid_utc_iso_8601()](src/infrastructure/logging/event_schema.py:27),
  - nommage strict `domain.action`.

### Previous Story Intelligence

- Depuis [Story 3.3](_bmad-output/implementation-artifacts/3-3-orchestrate-deterministic-conversion-with-engine-fallback.md), les comportements déjà en place à préserver:
  - orchestration déterministe sur `chunk_index`,
  - fallback strictement piloté par orchestration,
  - persist de résultat chunk via [update_chunk_synthesis_outcome()](src/adapters/persistence/sqlite/repositories/chunks_repository.py:107),
  - événements `tts.chunk_started|succeeded|failed|fallback_applied`.
- Leçons de review déjà appliquées en 3.3 à ne pas régresser:
  - typage renforcé et contrats explicites,
  - pas de silence sur erreurs critiques de persistance,
  - couverture tests sur erreurs déterministes et schéma événements.
- Implication directe pour 3.4:
  - implémenter la reprise comme extension du flux existant dans [synthesize_persisted_chunks_for_job()](src/domain/services/tts_orchestration_service.py:123),
  - ne pas contourner le statut chunk persistant,
  - ne pas introduire de logique parallèle non corrélée au flux JSONL déjà normalisé.

### Git Intelligence Summary

- Historique récent pertinent (5 derniers commits):
  - `92fc18b` — hardening Story 3.3 (type safety, error handling, deduplication),
  - `a2708c8` — persisted-chunk orchestration déterministe + diagnostics,
  - `0822b3d` — création story 3.3,
  - `13c7bc7` — fix Story 3.2 (logger port centralization, validations, tests),
  - `8f34ec8` — chunking déterministe + persistance + logging.
- Fichiers fréquemment touchés sur ce flux Epic 3:
  - [tts_orchestration_service.py](src/domain/services/tts_orchestration_service.py),
  - [chunks_repository.py](src/adapters/persistence/sqlite/repositories/chunks_repository.py),
  - [test_tts_orchestration_service.py](tests/unit/test_tts_orchestration_service.py),
  - [test_chunk_persistence_and_resume_path.py](tests/integration/test_chunk_persistence_and_resume_path.py),
  - artifacts story/sprint-status sous [_bmad-output/implementation-artifacts](_bmad-output/implementation-artifacts).
- Guidance actionnable pour 3.4:
  - conserver le niveau de qualité “contrats stricts + tests ciblés + pas de silent failure”,
  - implémenter la reprise en continuité du design existant au lieu d’un nouveau pipeline,
  - inclure les tests de non-régression sur ordre chunk, transitions d’état, et schéma événements.

### Latest Tech Information

- Vérification ponctuelle des versions publiées (PyPI) pendant cette phase:
  - `PyQt5 5.15.11`,
  - `PyYAML 6.0.3`.
- Aucune mise à niveau obligatoire pour Story 3.4; l’objectif est la robustesse des flux état/reprise sur le socle actuel.
- Bonnes pratiques à appliquer dans cette story:
  - horodatages UTC ISO-8601 uniformes pour faciliter corrélation locale,
  - enveloppes d’erreurs stables et strictes pour automatisation UI/support,
  - pas d’introduction de dépendances externes pour la logique resume/state.

### Project Structure Notes

- Aligner la reprise et les transitions d’état sur la structure existante Epic 3 sans créer de nouveau service “resume”.
- Garder le cœur métier dans [tts_orchestration_service.py](src/domain/services/tts_orchestration_service.py) et la persistance d’état dans [conversion_jobs_repository.py](src/adapters/persistence/sqlite/repositories/conversion_jobs_repository.py).
- Préserver le flux de statuts chunk déjà établi dans [chunks_repository.py](src/adapters/persistence/sqlite/repositories/chunks_repository.py) pour garantir la compatibilité avec les tests existants.
- Maintenir la séparation source/tests actuelle: logique dans `src/`, preuves de comportement dans `tests/unit` et `tests/integration`.

### References

- Story source: [epics.md](_bmad-output/planning-artifacts/epics.md)
- Product constraints: [prd.md](_bmad-output/planning-artifacts/prd.md)
- Architecture constraints: [architecture.md](_bmad-output/planning-artifacts/architecture.md)
- Sprint tracking and status transitions: [sprint-status.yaml](_bmad-output/implementation-artifacts/sprint-status.yaml)
- Previous implementation intelligence: [3-3-orchestrate-deterministic-conversion-with-engine-fallback.md](_bmad-output/implementation-artifacts/3-3-orchestrate-deterministic-conversion-with-engine-fallback.md)
- State transition authority: [validate_job_state_transition()](src/domain/services/job_state_validator.py:18)
- Resume/orchestration baseline: [synthesize_persisted_chunks_for_job()](src/domain/services/tts_orchestration_service.py:123)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `cat ./_bmad/core/tasks/workflow.xml`
- `cat ./_bmad/bmm/workflows/4-implementation/dev-story/workflow.yaml`
- `cat ./_bmad/bmm/workflows/4-implementation/dev-story/instructions.xml`
- `cat ./_bmad-output/implementation-artifacts/sprint-status.yaml`
- `python -m unittest -q tests.unit.test_tts_orchestration_service tests.unit.test_job_state_validator tests.unit.test_conversion_jobs_repository tests.integration.test_chunk_persistence_and_resume_path`
- `PYTHONPATH=src python -m unittest -q`

### Implementation Plan

- Implémenter le repository jobs SQLite pour lecture d’état et transition atomique compare-and-swap.
- Intégrer transitions de cycle de vie et événements `job.transition_*` dans l’orchestrateur.
- Ajouter reprise déterministe (`resume_start_index`) avec skip des chunks `synthesized_*` et option `force_reprocess`.
- Étendre la couverture tests unitaires/intégration sur transitions, reprise, observabilité et régressions.

### Completion Notes List

- Story selected from first backlog entry in sprint status: `3-4-persist-job-lifecycle-and-resume-conversion-from-last-failed-chunk`.
- Implémentation de [ConversionJobsRepository](src/adapters/persistence/sqlite/repositories/conversion_jobs_repository.py): `get_job_by_id()` + `update_job_state_if_current()` atomique avec contrôle de lignes affectées.
- Extension de [synthesize_persisted_chunks_for_job()](src/domain/services/tts_orchestration_service.py:146) avec sélection déterministe de `resume_start_index`, skip des chunks déjà synthétisés, et mode explicite `force_reprocess`.
- Ajout des transitions de cycle de vie persistées et validées via [validate_job_state_transition()](src/domain/services/job_state_validator.py:18), avec erreurs normalisées et événements `job.transition_requested|applied|rejected`.
- Ajout des événements de reprise `conversion.resume_checkpoint_selected` et `conversion.resume_started` avec `retry_decision_path`.
- Wiring du repository jobs dans [build_container()](src/app/dependency_container.py:117) pour activer la persistance des transitions.
- Couverture de tests étendue:
  - [test_tts_orchestration_service.py](tests/unit/test_tts_orchestration_service.py),
  - [test_chunk_persistence_and_resume_path.py](tests/integration/test_chunk_persistence_and_resume_path.py),
  - nouveau [test_conversion_jobs_repository.py](tests/unit/test_conversion_jobs_repository.py).
- Validation exécutée et verte: `32 tests` ciblés puis `127 tests` de régression (`OK`).

### File List

- _bmad-output/implementation-artifacts/3-4-persist-job-lifecycle-and-resume-conversion-from-last-failed-chunk.md
- src/adapters/persistence/sqlite/repositories/conversion_jobs_repository.py
- src/domain/services/tts_orchestration_service.py
- src/app/dependency_container.py
- tests/unit/test_tts_orchestration_service.py
- tests/integration/test_chunk_persistence_and_resume_path.py
- tests/unit/test_conversion_jobs_repository.py

## Change Log

- 2026-02-13: Implémentation complète story 3.4 (transitions job persistées, reprise déterministe, observabilité transition/reprise, couverture de tests unitaires/intégration/régression), statut passé à `review`.
