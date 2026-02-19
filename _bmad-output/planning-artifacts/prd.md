---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
inputDocuments:
  - _bmad-output/project-brief.md
documentCounts:
  briefCount: 1
  researchCount: 0
  brainstormingCount: 0
  projectDocsCount: 0
workflowType: "prd"
classification:
  projectType: desktop_app
  domain: general
  complexity: low
  projectContext: greenfield
---

# Product Requirements Document - local-audiobook

**Author:** Thibault
**Date:** 2026-02-10

## Success Criteria

### User Success

- Conversion réussie des formats EPUB, PDF, TXT, MD vers MP3 ou WAV sans cloud
- Parcours utilisateur fluide: import, choix moteur TTS, lancement conversion, écoute intégrée
- Satisfaction sur la qualité vocale FR et EN en usage réel déplacement et écoute prolongée
- Moment aha: un document personnel est converti et écoutable immédiatement en local

### Business Success

- Validation d’un produit desktop local différencié par confidentialité offline-first
- Adoption récurrente de la conversion et de l’écoute locale sur bibliothèque personnelle
- Usage équilibré des moteurs selon contexte matériel Chatterbox GPU et Kokoro CPU fallback

### Technical Success

- Pipeline stable extraction vers segmentation vers TTS vers export audio pour longs documents
- UI réactive pendant la conversion asynchrone
- Fonctionnement 100% offline après téléchargement initial des modèles
- Observabilité locale exploitable via logs pour diagnostic

### Measurable Outcomes

- Pourcentage de conversions complètes sans erreur
- Temps médian de conversion par 10k mots par moteur
- Pourcentage de sessions entièrement offline
- Pourcentage d’utilisateurs actifs lançant au moins une conversion hebdomadaire
- Répartition d’usage Chatterbox contre Kokoro

## Product Scope

### MVP - Minimum Viable Product

- Import et extraction EPUB PDF TXT MD
- Conversion TTS avec Chatterbox sur GPU et Kokoro en fallback CPU
- Sélection basique voix et langue FR EN
- Lecteur audio intégré simple lecture pause reprise navigation
- Bibliothèque locale avec métadonnées de base
- Exécution offline après setup initial

### Growth Features Post-MVP

- Mode batch multi-documents
- Recherche avancée dans la bibliothèque
- Contrôle avancé d’expressivité émotion
- Internationalisation de l’interface

### Vision Future

- Voice cloning
- Support OS additionnels Windows et macOS
- Extension du contrôle voix style émotion au niveau expert

## User Journeys

### Journey 1 Primary User Success Path Commuter Learner

- Opening Scene: lit le soir, manque de temps en journée
- Rising Action: importe un EPUB, choisit FR, Chatterbox GPU, lance conversion
- Climax: l’audio est prêt, écoute en voiture via lecteur intégré
- Resolution: transforme des trajets passifs en temps d’apprentissage

### Journey 2 Primary User Edge Case Privacy First Reader

- Opening Scene: document sensible PDF professionnel
- Rising Action: conversion locale, vérification mode offline
- Climax: erreur ponctuelle sur un chunk PDF, reprise contrôlée et log visible
- Resolution: conversion finalisée sans envoi cloud, confiance renforcée

### Journey 3 Operations User Linux Power User Developer

- Opening Scene: souhaite optimiser performance selon charge machine
- Rising Action: compare Chatterbox GPU et Kokoro CPU fallback sur TXT long
- Climax: choisit moteur selon disponibilité GPU et temps attendu
- Resolution: pipeline stable reproductible pour usage régulier

### Journey 4 Support Troubleshooting User Local Knowledge Worker

- Opening Scene: veut retrouver et rejouer rapidement un ancien rendu
- Rising Action: consulte bibliothèque locale et métadonnées de base
- Climax: identifie le bon fichier audio et reprend la lecture
- Resolution: boucle usage simple import conversion écoute réécoute

### Journey Requirements Summary

- Import robuste EPUB PDF TXT MD
- Segmentation chunking concaténation et reprise erreur
- Choix moteur TTS Chatterbox GPU et Kokoro CPU
- Sélection basique voix langue FR EN
- Lecteur intégré simple
- Bibliothèque locale avec métadonnées
- Offline après téléchargement initial

## Innovation & Novel Patterns

### Detected Innovation Areas

- Orchestration dual-engine offline-first: sélection intelligente entre Chatterbox GPU ROCm et Kokoro CPU fallback
- Continuité de service locale: conversion possible même sans GPU disponible ou saturé
- Positionnement privacy-first opérationnel: aucune dépendance cloud après bootstrap modèles

### Market Context & Competitive Landscape

- Les solutions TTS locales sont souvent mono-moteur ou orientées cloud
- La combinaison GPU qualité et CPU résilience dans une UI desktop unifiée est un différenciateur pragmatique
- Valeur perçue principale: fiabilité locale, confidentialité, et flexibilité perf qualité

### Validation Approach

- Tests comparatifs qualité et temps de conversion par 10k mots entre moteurs
- Scénarios de bascule contrôlée GPU vers CPU sans interruption du flux utilisateur
- Validation offline stricte: tests en mode réseau coupé après setup

### Risk Mitigation

- Risque divergence qualité vocale entre moteurs: profils voix par défaut et attentes UX explicites
- Risque complexité technique de bascule: politique de fallback déterministe et journalisée
- Risque confusion utilisateur: libellés clairs du moteur actif et recommandations contextuelles

## Desktop App Specific Requirements

### Project-Type Overview

- Application desktop Python PyQt5 orientée conversion locale de documents en audio
- Cible MVP Linux Mint uniquement
- Extensions futures Windows et macOS

### Technical Architecture Considerations

- Architecture modulaire import extraction, orchestration TTS, post-traitement audio, bibliothèque locale, lecteur intégré
- Traitement asynchrone obligatoire pour préserver la réactivité UI
- Exécution locale sans dépendance réseau après téléchargement initial des modèles

### Platform Support

- MVP Linux Mint desktop confirmé
- Hors MVP portage Windows macOS avec abstraction des différences OS

### System Integration

- Intégration OS minimale en MVP accès système de fichiers, import documents, export MP3 WAV, lecture audio locale
- Pas d’intégrations système avancées en MVP

### Update Strategy

- Pas d’auto-update en MVP
- Mécanisme de mise à jour manuel documenté

### Offline Capabilities

- Fonctionnement complet offline après setup initial
- Vérification explicite des prérequis modèles pour éviter toute dépendance réseau en exécution

### Implementation Considerations

- Sélection moteur explicite et fallback déterministe Chatterbox GPU vers Kokoro CPU
- Logs locaux structurés pour diagnostic extraction, conversion, concaténation, export
- Gestion de ressources pour longs documents et erreurs chunk avec reprise contrôlée

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

- **MVP Approach:** Problem-solving MVP centré utilité immédiate offline
- **Resource Requirements:** noyau desktop Python PyQt5, pipeline extraction TTS audio, persistance locale

### MVP Feature Set Phase 1

- **Core User Journeys Supported:** conversion individuelle fiable puis écoute locale
- **Must-Have Capabilities:**
  - import et extraction EPUB PDF TXT MD
  - conversion TTS Chatterbox GPU ROCm plus fallback Kokoro CPU
  - sélection basique voix langue FR EN
  - lecteur intégré simple lecture pause reprise navigation
  - bibliothèque locale métadonnées de base
  - offline complet après téléchargement initial

### Post-MVP Features

- **Phase 2 Post-MVP:** mode batch, recherche avancée bibliothèque, expressivité émotion avancée, internationalisation UI
- **Phase 3 Expansion:** voice cloning, support Windows macOS, optimisation avancée orchestration multi-profils

### Risk Mitigation Strategy

- **Technical Risks:** segmentation longs textes, stabilité pipeline, fallback déterministe GPU CPU, logs structurés
- **Market Risks:** valider qualité perçue et vitesse de conversion sur cas réels FR EN
- **Resource Risks:** garder un noyau MVP strict, reporter fonctionnalités non essentielles

## Functional Requirements

### Document Ingestion & Text Extraction

- FR1: User can import source files in EPUB format
- FR2: User can import source files in PDF format
- FR3: User can import source files in TXT format
- FR4: User can import source files in Markdown format
- FR5: System can extract textual content from imported EPUB files
- FR6: System can extract textual content from imported PDF files
- FR7: System can extract textual content from imported TXT and Markdown files
- FR8: System can report extraction failures with actionable error feedback

### Conversion Orchestration

- FR9: User can start a document-to-audio conversion from extracted text
- FR10: User can select output format as MP3 or WAV
- FR11: System can segment long texts into conversion chunks
- FR12: System can process chunks and assemble a final continuous audio file
- FR13: System can continue conversion by switching to fallback engine when primary engine is unavailable
- FR14: System can preserve conversion state and logs when a chunk fails

### Voice & Language Controls

- FR15: User can select TTS engine between Chatterbox and Kokoro
- FR16: User can select a voice profile available for the chosen engine
- FR17: User can select language for synthesis with FR and EN available in MVP
- FR18: User can adjust basic speech rate for output generation

### Playback Experience

- FR19: User can play generated audio inside the application
- FR20: User can pause and resume playback
- FR21: User can seek to a specific playback position
- FR22: User can view playback progress and current time

### Local Library Management

- FR23: System can store generated audio files in a local library
- FR24: System can persist basic metadata for each generated audiobook
- FR25: User can browse locally stored audiobooks in the library view
- FR26: User can reopen a selected library item for playback

### Offline Operation & Local Observability

- FR27: System can operate without internet access after model bootstrap is completed
- FR28: System can inform user when required local model assets are missing
- FR29: System can record local logs for extraction, conversion, fallback, and export events
- FR30: User can access diagnostic information for failed conversions

### Future Capability Placeholders Post-MVP

- FR31: User can launch batch conversion jobs across multiple documents
- FR32: User can search library items with advanced filters
- FR33: User can use advanced expressivity and emotion controls
- FR34: User can use voice cloning from a reference sample
- FR35: User can run the application on additional desktop operating systems

### Chapter-Aware Conversion and UX Improvements (Epic 7)

- NR1: System can detect native chapters from imported EPUB files using TOC/spine structure
- NR2: System can propose page-based segmentation for PDF files and word-count-based segmentation for TXT/MD files when no chapter structure is detected
- NR3: System can convert selected chapters or sections sequentially, producing one audio file per chapter in the output folder
- NR4: Conversion view displays the imported filename and file size after successful import
- NR5: User can select a custom output destination folder for converted audio files
- NR6: User can set a custom base name for output audio files (pre-filled from source filename)
- NR7: User can view and select individual chapters/sections to convert, with all chapters selected by default
- NR8: Speech rate slider defaults to 1.0 (normal speed) on first launch and when no persisted value exists
- NR9: Import functionality is integrated directly into the Conversion tab; the Import tab is removed
- NR10: Library tab displays converted audio files from a configurable output folder
- NR11: Library tab displays metadata per item: title, format, file size, conversion date, source filename
- NR12: Library tab includes an integrated audio player with Play/Pause, seek bar, elapsed time, and total duration
- NR13: User can configure the Library folder via a folder selection dialog; selection is persisted across sessions
- NR14: User can preview the selected TTS voice with a short editable French text sample directly in the Conversion view, without saving to library

## Non-Functional Requirements

### Performance

- NFR1: UI interactions non bloquantes pendant conversion et lecture
- NFR2: Traitement stable des longs documents via chunking sans arrêt du pipeline
- NFR3: Temps de conversion mesurable par 10k mots et traçable par moteur

### Reliability

- NFR4: Reprise contrôlée sur erreur de chunk avec conservation d’état
- NFR5: Génération audio finale cohérente sans corruption de concaténation
- NFR6: Journalisation locale suffisante pour diagnostiquer extraction conversion export

### Security & Privacy

- NFR7: Aucune transmission de contenu texte ou audio vers des services tiers en exécution
- NFR8: Stockage local des artefacts avec permissions système standard
- NFR9: Fonctionnement offline complet après bootstrap modèles

### Compatibility

- NFR10: MVP compatible Linux Mint avec GPU AMD RX 7900 XT via ROCm
- NFR11: Fallback CPU opérationnel via Kokoro quand Chatterbox GPU indisponible
- NFR12: Support des formats entrée EPUB PDF TXT MD et sortie MP3 WAV

### Maintainability & Observability

- NFR13: Architecture modulaire séparant extraction orchestration TTS post-traitement bibliothèque
- NFR14: Logs structurés corrélables par document et étape pipeline
- NFR15: Configuration claire des moteurs voix langues sans modifier le code applicatif
