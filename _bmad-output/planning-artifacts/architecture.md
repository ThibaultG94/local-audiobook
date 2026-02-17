---
stepsCompleted:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/project-brief.md
workflowType: "architecture"
lastStep: 8
status: "complete"
project_name: "local-audiobook"
user_name: "Thibault"
date: "2026-02-10T22:36:38.699Z"
completedAt: "2026-02-11T15:49:45.455Z"
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
Le produit couvre une chaîne complète document vers audio en local, depuis l’import multi-format jusqu’à la lecture intégrée. Le noyau MVP impose la robustesse sur longs documents via segmentation chunking, conversion séquentielle tolérante aux pannes, assemblage final et accès bibliothèque. Les capacités FR31 à FR35 existent mais sont explicitement post-MVP et ne doivent pas influencer les décisions de structure MVP.

**Non-Functional Requirements:**
Les NFR imposent une architecture orientée robustesse opérationnelle locale: interface non bloquante pendant conversion et lecture, observabilité exploitable pour diagnostiquer extraction conversion export, reprise contrôlée sur erreur de chunk, fonctionnement offline total après bootstrap, et compatibilité Linux Mint avec fallback CPU opérationnel.

**Scale & Complexity:**
Le périmètre est MVP, mais la complexité technique est medium à cause du couplage entre orchestration multi-moteur, gestion d’état de jobs longs et exigences de résilience.

- Primary domain: Desktop local AI media processing
- Complexity level: Medium
- Estimated architectural components: 8 à 10 composants applicatifs principaux

### Technical Constraints & Dependencies

Contraintes confirmées: stack desktop Python avec interface PyQt5, extraction via ebooklib et PyPDF2 avec parsing natif TXT MD, sortie MP3 WAV, exécution Linux Mint ciblée, dépendance hardware ROCm pour moteur principal GPU et fallback CPU garanti. Le système doit rester 100 pourcent local après téléchargement initial des modèles.

### Cross-Cutting Concerns Identified

- Responsiveness UI sous charge longue conversion
- Gestion d’état, reprise et idempotence de traitement chunk
- Politique de fallback déterministe et traçable
- Journalisation structurée corrélée document job chunk moteur
- Gouvernance des assets modèles local cache validation intégrité
- Cohérence entre métadonnées bibliothèque et fichiers audio exportés

## Starter Template Evaluation

### Primary Technology Domain

Desktop Python application with native UI and local AI processing pipeline.

### Starter Options Considered

- Option A: External PyQt boilerplate community templates.
- Option B: Generic desktop wrappers not aligned with Python first constraints.
- Option C: Custom Python scaffold with deterministic project layout and explicit module boundaries.

### Selected Starter

Custom Python scaffold no third party project starter.

**Rationale for Selection:**

- Alignement strict avec les décisions techniques verrouillées Python et PyQt5.
- Réduction du risque de dépendance à un template peu maintenu.
- Contrôle total sur l’architecture modulaire en 5 modules MVP.

**Initialization Command:**

Initialisation manuelle du repository applicatif avec structure src tests config scripts et dépendances verrouillées.

**Architectural Decisions Provided by Starter:**

**Language and Runtime:**

Python project layout orienté package applicatif.

**UI Foundation:**

PyQt5 as presentation layer.

**Build Tooling:**

pyproject based dependency and packaging workflow.

**Testing:**

unit and integration layers séparées par module.

**Code Organization:**

boundaries explicites import orchestration postprocess library player.

**Development Experience:**

logging structuré configuration centralisée environnement local.

Note: L’initialisation du scaffold sera la première story d’implémentation.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions Block Implementation**

- Persistance principale sur SQLite, avec artefacts audio stockés sur disque et chemins référencés en base
- Exécution longue via thread dédié par conversion avec worker QObject et signaux slots pour progression et erreurs
- Contrat unifié TTSProvider avec orchestration de fallback au niveau service
- Chunking phrase first avec limite cible en caractères et reprise au dernier chunk non validé
- Logging structuré JSON Lines avec clés de corrélation pipeline
- Gestion des modèles via ModelRegistry local avec manifest version hash taille et validation intégrité au démarrage

**Important Decisions Shape Architecture**

- Source de vérité unique applicative côté SQLite pour bibliothèque, jobs, progression, erreurs et métadonnées
- Fallback déterministe centralisé dans le service d’orchestration plutôt que dans les adaptateurs moteur
- Stratégie de reprise par état chunk persistant pour garantir idempotence et robustesse sur longs documents

**Deferred Decisions Post MVP**

- Recherche avancée bibliothèque
- Batch multi documents
- Voice cloning
- Contrôles expressivité avancés
- Portabilité Windows macOS
- Auto update

### Data Architecture

- Store principal: SQLite local
- Stockage binaire audio: fichiers sur disque, indexés en base
- Modèle de données minimal MVP: documents importés, jobs de conversion, chunks, artefacts audio, bibliothèque, événements de diagnostic
- Validation données: contraintes SQL et validation applicative à l’entrée des services
- Migration: versionnage schéma incrémental dès la première version

### Authentication and Security

- Pas d’authentification utilisateur en MVP local mono poste
- Sécurité locale orientée permissions système standards
- Aucune exposition API réseau en MVP
- Aucune transmission cloud en exécution après bootstrap

### API and Communication Patterns

- Communication interne en appels de services Python intra processus
- Contrat TTSProvider: synthèse chunk, inventaire voix, vérification santé moteur
- Gestion d’erreurs normalisée par type extraction chunk moteur export
- Signaux Qt pour communication worker vers UI

### Frontend Architecture

- UI PyQt5 avec séparation claire présentation et services applicatifs
- Thread de conversion isolé de l’UI thread
- Mise à jour progression via signaux slots
- Lecteur intégré découplé de l’orchestrateur de conversion

### Infrastructure and Deployment

- Cible unique MVP Linux Mint
- Exécution offline après téléchargement initial des modèles
- Registry local des modèles avec états installed missing invalid
- Validation intégrité au démarrage avant autorisation de conversion
- Logging JSON Lines local corrélé par correlation_id job_id chunk_index engine stage event severity timestamp

### Decision Impact Analysis

**Implementation Sequence**

1. Mettre en place le socle persistance SQLite et schéma initial
2. Implémenter le ModelRegistry et bootstrap validation intégrité
3. Définir le contrat TTSProvider et adaptateurs moteurs
4. Implémenter l’orchestrateur chunking reprise fallback
5. Connecter l’exécution threadée et signaux UI
6. Finaliser export audio, bibliothèque et lecteur intégré
7. Stabiliser observabilité JSON Lines et diagnostics utilisateur

**Cross Component Dependencies**

- L’orchestrateur dépend du schéma jobs chunks et du contrat TTSProvider
- Le fallback moteur dépend de health check et des états modèles du registry
- La reprise chunk dépend de la persistance d’état transactionnelle
- La UI dépend des signaux de progression émis par le worker de conversion
- Le diagnostic utilisateur dépend de la corrélation stricte des événements de logs

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**

9 zones de conflit potentiel entre agents AI ont été figées.

### Naming Patterns

**Database Naming Conventions:**

- Tables en `snake_case` pluriel
- Colonnes en `snake_case`
- PK standard `id`
- FK au format `<entity>_id`
- Index au format `idx_<table>_<column>`

**API Naming Conventions:**

- Contrats service internes nommés en `snake_case`
- Paramètres nommés en `snake_case`
- Événements internes au format `domain.action` minuscules

**Code Naming Conventions:**

- Modules fonctions variables en `snake_case`
- Classes en `PascalCase`
- Fichiers Python en `snake_case.py`
- Signaux Qt nommés en `snake_case`

### Structure Patterns

**Project Organization:**

- Code applicatif sous `src/`
- Tests sous `tests/` en miroir fonctionnel de `src/`
- Séparation stricte UI services domain infra adapters
- Un point d’entrée UI, un point d’entrée orchestration

**File Structure Patterns:**

- Config dans `config/`
- Schémas DB et migrations dans `migrations/`
- Logs runtime dans `runtime/logs/`
- Artefacts audio dans `runtime/library/audio/`

### Format Patterns

**API Response Formats:**

- Résultat service standard: `{ok, data, error}`
- Erreur normalisée: `{code, message, details, retryable}`

**Data Exchange Formats:**

- JSON field naming en `snake_case`
- Dates heures en ISO-8601 UTC
- Booléens stricts `true` `false`
- `null` explicite pour absence de valeur

### Communication Patterns

**Event System Patterns:**

- Convention d’événement `domain.action`
- Payload minimal commun: `correlation_id, job_id, stage, event, timestamp`
- Versionnage événement via champ `schema_version`

**State Management Patterns:**

- États job autorisés: `queued, running, paused, failed, completed`
- Transitions d’état validées côté service
- Mises à jour d’état atomiques en persistance

### Process Patterns

**Error Handling Patterns:**

- Distinction erreur technique vs erreur utilisateur
- Catégorisation erreurs extraction chunk engine export persistence
- Retry piloté par champ `retryable`

**Loading State Patterns:**

- UI liée à l’état job persistant
- Progression calculée par `processed_chunks/total_chunks`
- Aucun blocage du thread UI

### Enforcement Guidelines

**All AI Agents MUST:**

- Respecter strictement les conventions de nommage et formats définies
- Utiliser les objets normalisés de résultat erreur et événements
- Implémenter les transitions d’état job uniquement via le service d’orchestration

**Pattern Enforcement:**

- Revue PR avec checklist de conformité patterns
- Validation automatique lint type tests contractuels
- Violations consignées dans logs de CI et corrigées avant merge

### Pattern Examples

**Good Examples:**

- `conversion_job` table avec `document_id`
- événement `tts.chunk_completed`
- résultat `{ok: true, data: {...}, error: null}`

**Anti Patterns:**

- mélange `camelCase` et `snake_case`
- écriture directe d’état job depuis UI
- erreurs texte libres sans `code` ni `retryable`

## Project Structure & Boundaries

### Complete Project Directory Structure

local-audiobook/

- README.md
- pyproject.toml
- requirements.lock
- .gitignore
- .env.example
- .python-version
- docs/
  - architecture/
  - adr/
- scripts/
  - bootstrap_models.py
  - run_app.py
  - run_tests.py
- config/
  - app_config.yaml
  - logging_config.yaml
  - model_manifest.yaml
- migrations/
  - 0001_initial_schema.sql
  - 0002_job_chunk_indexes.sql
- runtime/
  - logs/
  - library/
    - audio/
    - temp/
- src/
  - app/
    - main.py
    - dependency_container.py
  - ui/
    - main_window.py
    - views/
      - import_view.py
      - conversion_view.py
      - library_view.py
      - player_view.py
    - presenters/
      - conversion_presenter.py
      - library_presenter.py
    - workers/
      - conversion_worker.py
  - domain/
    - models/
      - document.py
      - conversion_job.py
      - audio_item.py
      - model_asset.py
    - services/
      - import_service.py
      - chunking_service.py
      - tts_orchestration_service.py
      - audio_postprocess_service.py
      - library_service.py
      - player_service.py
      - model_registry_service.py
    - ports/
      - tts_provider.py
      - repository_ports.py
  - adapters/
    - extraction/
      - epub_extractor.py
      - pdf_extractor.py
      - text_extractor.py
    - tts/
      - chatterbox_provider.py
      - kokoro_provider.py
    - audio/
      - wav_builder.py
      - mp3_encoder.py
    - persistence/
      - sqlite/
        - connection.py
        - repositories/
          - document_repository.py
          - job_repository.py
          - chunk_repository.py
          - library_repository.py
    - playback/
      - qt_audio_player.py
  - infrastructure/
    - logging/
      - jsonl_logger.py
      - event_schema.py
    - settings/
      - settings_loader.py
    - events/
      - event_bus.py
      - event_types.py
  - contracts/
    - result.py
    - errors.py
- tests/
  - unit/
    - domain/
    - adapters/
    - infrastructure/
  - integration/
    - pipeline/
    - persistence/
    - ui_worker/
  - fixtures/
    - sample_epub/
    - sample_pdf/
    - sample_txt/

### Architectural Boundaries

- UI boundary: `main_window.py` pilote les vues et ne parle pas directement à SQLite ni aux moteurs TTS
- Service boundary: `tts_orchestration_service.py` orchestre chunking, fallback et progression
- Provider boundary: contrat unique `tts_provider.py` implémenté par `chatterbox_provider.py` et `kokoro_provider.py`
- Data boundary: accès DB uniquement via repositories sous `sqlite`
- Logging boundary: sortie JSONL centralisée via `jsonl_logger.py`

### Requirements to Structure Mapping

- Import and extraction FR1-FR8 vers `adapters/extraction` et `import_service.py`
- Orchestration FR9-FR18 vers `chunking_service.py`, `tts_orchestration_service.py`, `workers`
- Postprocessing FR10-FR12 vers `adapters/audio` et `audio_postprocess_service.py`
- Library FR23-FR26 vers `library_service.py` et repositories SQLite
- Player FR19-FR22 vers `player_service.py` et `qt_audio_player.py`
- Offline and observability FR27-FR30 vers `model_registry_service.py` et `infrastructure/logging`

### Integration Points

- Flux principal: import -> extraction -> chunking -> synthèse chunk -> assemblage audio -> indexation bibliothèque -> lecture
- Communication interne: services Python synchrones, exécution longue dans worker Qt dédié, signaux vers UI
- Intégrations externes: moteurs locaux Chatterbox et Kokoro, librairies extraction EPUB PDF

### File Organization Patterns

- Configuration centralisée dans `config`
- Migrations SQL versionnées dans `migrations`
- Artefacts runtime isolés dans `runtime` pour séparation code données
- Tests en miroir de modules pour limiter conflits d’agents

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**

Les décisions de persistance SQLite, orchestration TTS via contrat unique, exécution threadée Qt, chunking avec reprise et logging JSONL sont compatibles et non contradictoires pour le scope MVP.

**Pattern Consistency:**

Les conventions de nommage, formats de payload, structures d’erreur, états de job et règles de séparation des couches s’alignent avec les choix techniques et réduisent les divergences entre agents.

**Structure Alignment:**

La structure projet proposée supporte les décisions d’architecture, les frontières UI, services, adapters, persistence et logging sont explicites et cohérentes.

### Requirements Coverage Validation ✅

**Epic Feature Coverage:**

Toutes les capacités MVP issues du PRD sont mappées aux modules cibles import extraction, orchestration TTS, post-traitement audio, bibliothèque locale et lecteur intégré.

**Functional Requirements Coverage:**

Les FR import extraction conversion fallback chunking export bibliothèque lecteur offline observabilité sont couverts architecturalement.

**Non-Functional Requirements Coverage:**

Les NFR réactivité UI, robustesse pipeline long document, reprise chunk, observabilité locale et compatibilité Linux Mint ROCm sont pris en compte.

### Implementation Readiness Validation ✅

**Decision Completeness:**

Les décisions critiques sont documentées avec niveau de priorité et impacts inter-composants.

**Structure Completeness:**

Arborescence complète définie avec points d’entrée, frontières de couches, emplacement des tests, runtime, config et migrations.

**Pattern Completeness:**

Règles de cohérence définies pour nommage, formats, communication, gestion d’erreurs, états de job et enforcement.

### Gap Analysis Results

- Critique: aucun gap bloquant identifié
- Important: versions exactes des dépendances non revérifiées en ligne dans cet environnement
- Mineur: exemples additionnels de payload erreurs succès à préciser ultérieurement dans documentation ADR

### Validation Issues Addressed

Les zones de risque principales ont été traitées par décisions explicites sur fallback déterministe, reprise par chunk persistant, séparation UI worker et corrélation stricte des logs.

### Architecture Completeness Checklist

**✅ Requirements Analysis**

- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**✅ Architectural Decisions**

- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**✅ Implementation Patterns**

- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**✅ Project Structure**

- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** high

**Key Strengths:**

- Architecture modulaire claire alignée au MVP
- Règles de cohérence explicites pour éviter conflits d’agents
- Stratégie robuste de reprise et fallback
- Observabilité structurée exploitable pour diagnostic

**Areas for Future Enhancement:**

- Vérification online des versions dépendances avant gel final implementation artifacts
- Complément d’exemples de contrats événements erreurs dans ADR technique

### Implementation Handoff

**AI Agent Guidelines:**

- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries
- Refer to this document for all architectural questions

**First Implementation Priority:**

Initialiser le scaffold Python structuré puis établir persistance SQLite et contrat TTSProvider avant UI wiring complet.
