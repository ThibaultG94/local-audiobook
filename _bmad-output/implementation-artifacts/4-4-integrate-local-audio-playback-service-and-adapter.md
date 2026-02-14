# Story 4.4: Integrate Local Audio Playback Service and Adapter

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user opening a generated audiobook,
I want the app to load and play local audio through a dedicated playback service,
so that playback is reliable across MP3 and WAV outputs.

## Acceptance Criteria

1. **Given** a library item is selected from `library_view.py`  
   **When** playback initialization is requested in `player_service.py`  
   **Then** the service resolves local file path and format compatibility  
   **And** delegates playback operations to `qt_audio_player.py` without bypassing service boundaries.

2. **Given** the selected audio file is missing unreadable or unsupported  
   **When** load is attempted  
   **Then** playback initialization fails with normalized output from `result.py`  
   **And** error payload format follows `errors.py` with actionable remediation details.

3. **Given** playback adapter emits runtime status updates  
   **When** playback starts stops or errors  
   **Then** status transitions are propagated back through `player_service.py` in deterministic form  
   **And** UI consumers receive stable state values suitable for presenter rendering.

4. **Given** playback operations must be diagnosable  
   **When** load play stop or error events occur  
   **Then** JSONL events are emitted by `jsonl_logger.py` with `stage=player`  
   **And** payload includes `correlation_id`, `event`, `severity`, and ISO-8601 UTC `timestamp`.

## Tasks / Subtasks

- [x] Define playback service boundary and contracts (AC: 1, 2, 3)
  - [x] Add [`PlayerService`](src/domain/services/player_service.py) with normalized service responses `{ok, data, error}`.
  - [x] Add repository-free service interface for load/play/pause/stop/seek/status methods.
  - [x] Enforce adapter orchestration only through service (no direct UI → adapter calls).
- [x] Implement local playback adapter for MP3/WAV in infra/adapters layer (AC: 1, 3)
  - [x] Create [`QtAudioPlayer`](src/adapters/playback/qt_audio_player.py) wrapper around Qt multimedia primitives.
  - [x] Normalize adapter status signals/events into deterministic state payloads (`idle`, `loading`, `playing`, `paused`, `stopped`, `error`).
  - [x] Ensure adapter does not perform conversion logic or persistence operations.
- [x] Add robust path and format validation for playback initialization (AC: 1, 2)
  - [x] Validate resolved path is within `runtime/library/audio` bounds before adapter load.
  - [x] Validate extension/format compatibility (`.mp3`, `.wav`) and fail fast with structured errors.
  - [x] Return actionable remediation for missing/unreadable artifacts (`relink`, `reconvert`, `check permissions`).
- [x] Integrate playback state propagation to presentation boundary (AC: 3)
  - [x] Add/update presenter contract so playback state updates can be consumed without leaking adapter internals.
  - [x] Preserve deterministic transition rules and avoid out-of-order UI state updates.
- [x] Add observability and diagnostics events for playback operations (AC: 4)
  - [x] Emit `domain.action` events for `player.load_requested`, `player.load_failed`, `player.play_started`, `player.paused`, `player.stopped`, `player.error`.
  - [x] Ensure `stage=player` and UTC ISO-8601 timestamp semantics.
  - [x] Include `correlation_id` and severity consistently, with optional `job_id` if available.
- [x] Add tests across service, adapter seam, and integration flow (AC: 1, 2, 3, 4)
  - [x] Unit test [`PlayerService`](src/domain/services/player_service.py) success/failure and normalization behavior.
  - [x] Unit test adapter wrapper behavior with mocked Qt media backend.
  - [x] Integration test reopen-from-library to player initialization path without re-running extraction/synthesis.

## Dev Notes

### Developer Context Section

- Story 4.4 démarre l’intégration de playback local après la disponibilité du contexte de réouverture livré par [`LibraryService.reopen_library_item()`](src/domain/services/library_service.py:94).
- Le système actuel sait déjà lister/réouvrir un item de bibliothèque avec validation de chemin via [`_validate_reopen_path()`](src/domain/services/library_service.py:406), mais ne possède pas encore de service playback dédié ni d’adapter audio Qt implémenté.
- Le flux attendu est strictement: UI/presenter → service playback → adapter playback, sans accès direct UI vers infrastructure.
- Le scope de cette story est limité à l’initialisation/contrôle playback local (MP3/WAV) et à la propagation d’état; aucune relance extraction/chunking/synthèse.
- Les contraintes MVP restent applicables: offline-only, messages UI en anglais, et observabilité locale via événements JSONL corrélés.

### Technical Requirements

- Créer un service applicatif dédié [`PlayerService`](src/domain/services/player_service.py) qui encapsule:
  - `initialize_playback(...)`
  - `play(...)`
  - `pause(...)`
  - `stop(...)`
  - `seek(...)`
  - `get_status(...)`
- Toutes les méthodes service doivent retourner des enveloppes normalisées `{ok, data, error}` via [`Result`](src/contracts/result.py:1).
- Toutes les erreurs doivent respecter `{code, message, details, retryable}` et s’aligner sur [`errors.py`](src/contracts/errors.py:1).
- `initialize_playback(...)` doit:
  - consommer le `playback_context` produit par [`LibraryService.reopen_library_item()`](src/domain/services/library_service.py:94),
  - revérifier la validité/lisibilité du fichier audio,
  - valider le format (`mp3|wav`) avant appel adapter,
  - interdire toute relance de conversion (pas d’appel orchestration TTS).
- L’adapter playback doit traduire les états backend en états déterministes consommables UI: `idle`, `loading`, `playing`, `paused`, `stopped`, `error`.
- Les transitions invalides (ex. `pause` depuis `idle`) doivent retourner une erreur normalisée non ambiguë.

### Architecture Compliance

- Respecter les frontières d’architecture décrites dans [`architecture.md`](./_bmad-output/planning-artifacts/architecture.md):
  - UI/presenter ne manipule pas SQLite ni Qt multimedia directement.
  - Toute orchestration playback passe par [`PlayerService`](src/domain/services/player_service.py).
  - L’adapter [`QtAudioPlayer`](src/adapters/playback/qt_audio_player.py) reste une couche infrastructure (pas de logique métier).
- Préserver les conventions globales:
  - fichiers Python en `snake_case.py`;
  - classes en `PascalCase`;
  - événements en `domain.action`.
- Préserver les contrats transverses:
  - succès/échec via [`Result`](src/contracts/result.py:1);
  - mapping d’erreur via [`errors.py`](src/contracts/errors.py:1);
  - timestamps en ISO-8601 UTC dans la journalisation.
- Exigence de sécurité MVP:
  - playback local uniquement;
  - aucun appel réseau;
  - validation systématique de chemin audio dans les bornes `runtime/library/audio`.

### Library / Framework Requirements

- Baseline projet actuelle dans [`pyproject.toml`](pyproject.toml:1):
  - `PyYAML>=6.0`
  - `EbookLib>=0.18`
  - `PyPDF2>=3.0.0`
- Recherche versions récentes (2026-02-14):
  - `PyQt5` disponible en `5.15.11` (Qt pack `PyQt5-Qt5` jusqu’à `5.15.18`)
  - `PyYAML` disponible en `6.0.3`
  - `EbookLib` disponible en `0.20`
  - `PyPDF2` disponible en `3.0.1`
- Exigence story 4.4:
  - ne pas introduire de nouvelle stack audio externe si Qt multimédia couvre le besoin;
  - conserver compatibilité Linux Mint MVP;
  - si ajout de dépendance playback Qt nécessaire, documenter explicitement dans `pyproject.toml`/lock et justifier impact packaging.
- Bonnes pratiques à appliquer:
  - encapsuler APIs Qt dans [`QtAudioPlayer`](src/adapters/playback/qt_audio_player.py) pour éviter propagation de détails framework;
  - centraliser mapping d’erreurs backend→contrat dans [`PlayerService`](src/domain/services/player_service.py);
  - éviter comportement spécifique OS non couvert par le MVP Linux Mint.

### Project Structure Notes

- Cibles minimales à créer/mettre à jour pour cette story:
  - Nouveau service domaine: [`player_service.py`](src/domain/services/player_service.py)
  - Nouvel adapter playback: [`qt_audio_player.py`](src/adapters/playback/qt_audio_player.py)
  - Extension wiring DI: [`dependency_container.py`](src/app/dependency_container.py)
  - Mise à jour presenter/view qui consomment le playback context:
    - [`library_presenter.py`](src/ui/presenters/library_presenter.py)
    - [`library_view.py`](src/ui/views/library_view.py)
- Règle de placement:
  - logique métier playback dans `src/domain/services/`;
  - binding framework Qt multimédia dans `src/adapters/playback/`;
  - aucune logique métier dans la vue.
- Contraintes de cohérence:
  - conserver conventions `snake_case` et signatures explicites;
  - ne pas déplacer les responsabilités existantes de [`LibraryService`](src/domain/services/library_service.py:42), seulement consommer son `playback_context`.
- Variance architecture anticipée:
  - la structure cible du document d’architecture mentionne potentiellement `player_view.py`; le repo actuel n’a pas ce fichier. Pour la story 4.4, intégrer playback via surfaces UI existantes puis introduire un `player_view` dédié seulement si nécessaire et justifié.

### Testing Requirements

- Unit tests service [`PlayerService`](src/domain/services/player_service.py):
  - initialisation playback réussie (MP3/WAV valides) ;
  - échecs normalisés pour `item_id` vide, chemin manquant, format non supporté, fichier illisible ;
  - transitions d’état invalides (`pause`/`seek` hors état compatible) renvoient des erreurs stables.
- Unit tests adapter [`QtAudioPlayer`](src/adapters/playback/qt_audio_player.py):
  - mapping backend Qt → états normalisés (`idle/loading/playing/paused/stopped/error`) ;
  - émission d’erreurs contrôlées sans exception non interceptée côté service.
- Unit tests presenter/view:
  - propagation d’état playback vers UI sans fuite d’objets Qt bas niveau ;
  - rendu messages actionnables en anglais pour erreurs playback.
- Integration tests:
  - chemin complet bibliothèque → reopen → initialize playback sans relancer conversion ;
  - logs `stage=player` émis sur load/play/pause/stop/error ;
  - vérification des champs minimaux `correlation_id,event,severity,timestamp`.
- Commandes de test recommandées:
  - `python -m unittest tests.unit.test_player_service`
  - `python -m unittest tests.unit.test_qt_audio_player`
  - `python -m unittest tests.integration.test_library_playback_integration`

### Previous Story Intelligence

- Réutiliser la logique de réouverture introduite en story 4.3 via [`LibraryService.reopen_library_item()`](src/domain/services/library_service.py:94) comme unique source de `playback_context`.
- Conserver la posture défensive appliquée en story 4.3:
  - validation stricte des chemins runtime,
  - erreurs normalisées actionnables,
  - journalisation structurée avec `exception_type` quand pertinent.
- Éviter les régressions sur les frontières déjà durcies:
  - pas d’accès repository direct depuis presenter/view,
  - pas de mélange de responsabilités entre library et player,
  - pas de bypass service en appelant l’adapter directement depuis l’UI.
- Maintenir continuité UX: les messages d’erreur playback doivent rester cohérents avec le ton/actionability déjà introduit en 4.3 (relink/reconvert/check local file).

### Git Intelligence Summary

- Tendances des 5 derniers commits (via `git log -n 5`):
  - forte activité récente sur artefacts de sprint/rétrospectives,
  - dernier changement code majeur sur story 4.3 (durcissement qualité/sécurité).
- Implications pour 4.4:
  - préserver le niveau de rigueur introduit en 4.3 (validation, logs, tests ciblés),
  - éviter les régressions sur [`library_service.py`](src/domain/services/library_service.py:42) qui vient d’être stabilisé,
  - garder un changement incrémental orienté nouveaux modules playback plutôt qu’un refactor large.
- Fichiers hotspot récents à traiter avec prudence:
  - [`src/domain/services/library_service.py`](src/domain/services/library_service.py:42)
  - [`src/ui/presenters/library_presenter.py`](src/ui/presenters/library_presenter.py:50)
  - [`tests/unit/test_library_service.py`](tests/unit/test_library_service.py:204)

### Latest Tech Information

- Versions observées via index package (2026-02-14):
  - `PyQt5` latest `5.15.11`
  - `PyQt5-Qt5` latest `5.15.18`
  - `PyYAML` latest `6.0.3`
  - `EbookLib` latest `0.20`
  - `PyPDF2` latest `3.0.1`
- Recommandation story 4.4:
  - garder l’implémentation compatible avec la baseline actuelle du projet [`pyproject.toml`](pyproject.toml:11);
  - n’introduire `PyQt5` (ou composants multimédia associés) dans les dépendances que si requis pour exécuter l’adapter playback;
  - documenter clairement tout ajout de dépendance playback avec justification Linux Mint MVP.
- Bonnes pratiques playback local à appliquer:
  - éviter tout couplage direct UI↔API Qt multimedia;
  - normaliser les erreurs d’initialisation média (fichier absent, format invalide, backend indisponible) en contrat projet;
  - privilégier une machine d’état explicite côté service pour éviter ambiguïté en UI.

### Project Context Reference

- Aucun fichier `project-context.md` détecté pour le pattern configuré `**/project-context.md`.
- Contexte de référence utilisé pour cette story:
  - [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md)
  - [`_bmad-output/planning-artifacts/prd.md`](_bmad-output/planning-artifacts/prd.md)
  - [`_bmad-output/planning-artifacts/architecture.md`](_bmad-output/planning-artifacts/architecture.md)
  - [`_bmad-output/implementation-artifacts/4-3-browse-and-reopen-audiobooks-from-local-library-view.md`](_bmad-output/implementation-artifacts/4-3-browse-and-reopen-audiobooks-from-local-library-view.md)
  - [`_bmad-output/implementation-artifacts/sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml)

### References

- Epic & story source: [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md)
- Product requirements: [`_bmad-output/planning-artifacts/prd.md`](_bmad-output/planning-artifacts/prd.md)
- Architecture constraints and boundaries: [`_bmad-output/planning-artifacts/architecture.md`](_bmad-output/planning-artifacts/architecture.md)
- Sprint tracking source: [`_bmad-output/implementation-artifacts/sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml)
- Previous story intelligence: [`_bmad-output/implementation-artifacts/4-3-browse-and-reopen-audiobooks-from-local-library-view.md`](_bmad-output/implementation-artifacts/4-3-browse-and-reopen-audiobooks-from-local-library-view.md)
- Reopen context and path validation baseline:
  - [`LibraryService.reopen_library_item()`](src/domain/services/library_service.py:94)
  - [`LibraryService._validate_reopen_path()`](src/domain/services/library_service.py:406)
- Contracts:
  - [`Result`](src/contracts/result.py:1)
  - [`errors.py`](src/contracts/errors.py:1)
- Dependency baseline: [`pyproject.toml`](pyproject.toml:1)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex

### Debug Log References

- `git log -n 5 --pretty=format:'%h|%ad|%s' --date=iso --name-only`
- `python -m pip index versions PyQt5`
- `python -m pip index versions PyQt5-Qt5`
- `python -m pip index versions PyYAML`
- `python -m pip index versions EbookLib`
- `python -m pip index versions PyPDF2`
- `rg -n "player|playback|qt_audio|QMediaPlayer" src --glob "*.py"`
- `python -m unittest tests.unit.test_player_service tests.unit.test_qt_audio_player tests.unit.test_library_presenter tests.unit.test_library_view tests.integration.test_library_playback_integration`
- `PYTHONPATH=src:. python -m unittest discover -s tests`

### Completion Notes List

- Story context assembled with exhaustive cross-artifact analysis for Epic 4 / Story 4.4.
- Developer guardrails added for architecture boundaries, normalized contracts, local path safety, and observability.
- Previous story learnings (4.3) integrated to prevent regressions and service-boundary violations.
- Latest dependency/version context added for playback-related technical decisions.
- Implemented `PlayerService` with deterministic state machine, local-path and format guardrails, and normalized error mapping.
- Implemented `QtAudioPlayer` adapter as infrastructure-only playback wrapper with deterministic state normalization and backend failure normalization.
- Integrated library reopen flow with playback initialization through service boundaries in presenter/view and DI wiring.
- Added player-stage JSONL observability (`player.load_requested`, `player.load_failed`, `player.play_started`, `player.paused`, `player.stopped`, `player.seeked`, `player.error`) with UTC timestamps.
- Added unit tests for player service, adapter seam, presenter/view propagation, and integration test for reopen→initialize→controls flow.
- Validated targeted and full test suites successfully (194 tests passing with project PYTHONPATH settings).
- Story status set to `review`.
- **Code review completed (2026-02-14):** Fixed 9 issues (7 HIGH, 2 MEDIUM) including PyQt5 dependency, path traversal security, format validation, seek logging, test coverage, and code cleanup.
- All 197 tests passing after review fixes.
- Story status updated to `done`.

### File List

- _bmad-output/implementation-artifacts/4-4-integrate-local-audio-playback-service-and-adapter.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- pyproject.toml
- src/adapters/playback/__init__.py
- src/adapters/playback/qt_audio_player.py
- src/domain/services/player_service.py
- src/app/dependency_container.py
- src/ui/presenters/library_presenter.py
- src/ui/views/library_view.py
- tests/unit/test_player_service.py
- tests/unit/test_qt_audio_player.py
- tests/unit/test_library_view.py
- tests/unit/test_library_presenter.py
- tests/integration/test_library_playback_integration.py

## Change Log

- 2026-02-14: Implemented Story 4.4 playback service/adapter integration, observability, DI wiring, UI propagation, and tests; moved status to `review`.
- 2026-02-14: Code review completed - fixed 9 issues (PyQt5 dependency, path traversal security, format validation, seek logging, test coverage, code cleanup); all 197 tests passing; moved status to `done`.

## Story Completion Status

- Status set to: `done`
- Completion note: Story implemented with playback service/adapter integration, deterministic state propagation, diagnostics events, passing test suite, and code review fixes applied.
