stepsCompleted: [1, 2, 3]
inputDocuments: []
date: 2026-02-10
author: Thibault

---

# Product Brief: Local Audiobook Converter

<!-- Content will be appended sequentially through collaborative workflow steps -->

## Executive Summary

L'application "Local Audiobook Converter" est une solution de conversion locale de documents textuels (ebooks, PDF, TXT, Markdown) en fichiers audio. L'objectif est de permettre aux utilisateurs d'écouter leurs livres et documents quand ils ne peuvent pas lire, notamment en voiture, en marchant, etc. L'application fonctionne entièrement en local sur la machine de l'utilisateur, sans nécessiter de service cloud, respectant ainsi la confidentialité et l'autonomie de l'utilisateur.

## Core Vision

### Problem Statement

Les utilisateurs ont besoin de pouvoir écouter leurs documents et livres numériques lorsqu'ils ne peuvent pas lire, par exemple pendant les déplacements ou lors d'activités physiques. Cependant, les solutions existantes sont souvent soit trop complexes, soit nécessitent une connexion internet, soit ne supportent pas tous les formats de documents.

### Problem Impact

- Les utilisateurs perdent l'opportunité d'écouter leurs documents pendant les déplacements
- Les solutions actuelles manquent souvent de flexibilité dans le choix des voix et des paramètres
- L'utilisation de services cloud pose des problèmes de confidentialité pour certains utilisateurs
- Le manque de support pour différents formats de documents limite l'accessibilité

### Why Existing Solutions Fall Short

- La plupart des solutions actuelles nécessitent une connexion internet
- Elles ne supportent pas tous les formats de documents textuels
- Elles manquent souvent de personnalisation des voix et des paramètres audio
- Elles ne permettent pas une conversion entièrement locale sans transmission de données

### Proposed Solution

Une application de conversion locale qui permet de convertir des documents textuels (EPUB, PDF, TXT, Markdown) en fichiers audio avec plusieurs choix de voix, qualité et langues. L'application dispose d'une interface simple et intuitive, permettant de gérer une bibliothèque locale de fichiers audio générés.

### Key Differentiators

- Conversion entièrement locale sans besoin de service cloud
- Support de plusieurs formats de documents textuels
- Choix multiple de voix (homme, femme, qualité, langue)
- Interface graphique simple et intuitive
- Gestion de bibliothèque locale
- Respect total de la vie privée de l'utilisateur

## Target Users

### Primary Users

- **Commuter Learner** : utilisateur qui écoute ebooks et documents pendant les déplacements voiture, marche et transports, avec un objectif de transformer du temps passif en temps d'apprentissage.
- **Privacy-First Reader** : utilisateur qui refuse les solutions cloud et SaaS, et qui veut une conversion 100% locale sans transfert de données vers des services tiers.

### Secondary Users

- **Linux Power User / Developer** : utilisateur technique Linux qui souhaite un contrôle fin des modèles TTS, de la qualité, du traitement batch et des performances locales.
- **Local Knowledge Worker** : utilisateur qui convertit des documents personnels ou professionnels sensibles en audio, en restant entièrement hors cloud.

### User Journey

- **Discovery** : l'utilisateur recherche une alternative locale aux solutions TTS cloud.
- **Onboarding** : installation desktop, téléchargement initial des modèles, configuration de la langue, de la voix et des paramètres.
- **Core Usage** : import EPUB/PDF/TXT/Markdown, choix voix et vitesse, lancement de conversion, classement du résultat dans la bibliothèque locale.
- **Success Moment** : écoute fluide en déplacement avec qualité vocale satisfaisante, tout en conservant la confidentialité des données.
- **Long-term** : usage récurrent sur plusieurs documents, recours au mode batch, organisation continue de la bibliothèque audio.

## Functional Requirements

- **FR-001 Import multi-formats** : l'application doit importer des fichiers EPUB, PDF, TXT et Markdown.
- **FR-002 Extraction de texte** : l'application doit extraire le contenu via `ebooklib` pour EPUB, `PyPDF2` pour PDF et parsing natif pour TXT/Markdown.
- **FR-003 Conversion document vers audio** : l'utilisateur doit pouvoir convertir un document en MP3 ou WAV.
- **FR-004 Sélection moteur TTS** : l'utilisateur doit pouvoir choisir entre Chatterbox TTS et Kokoro.
- **FR-005 Sélection voix et langue** : l'utilisateur doit pouvoir sélectionner voix homme/femme, qualité et langue, avec support FR/EN minimum.
- **FR-006 Voice cloning optionnel** : l'utilisateur doit pouvoir fournir un échantillon audio court pour cloner une voix.
- **FR-007 Contrôle de rendu vocal** : l'utilisateur doit pouvoir ajuster vitesse, expressivité et paramètres de qualité.
- **FR-008 Traitement des longs textes** : le système doit segmenter automatiquement par phrases, convertir par chunks, puis concaténer proprement.
- **FR-009 Mode batch** : l'utilisateur doit pouvoir lancer des conversions sur plusieurs documents.
- **FR-010 Bibliothèque locale** : l'application doit stocker, indexer et organiser les audios générés avec métadonnées.
- **FR-011 Recherche locale** : l'utilisateur doit pouvoir rechercher dans sa bibliothèque par titre, auteur, tags et format.
- **FR-012 Lecteur intégré** : l'application doit fournir lecture, pause, reprise et navigation temporelle.
- **FR-013 Fonctionnement offline** : après installation initiale et téléchargement des modèles, l'application doit fonctionner sans connexion Internet.

## Non-Functional Requirements

- **NFR-001 Performance conversion** : conversion stable de longs documents sans crash ni blocage de l'interface.
- **NFR-002 Réactivité UI** : l'interface reste utilisable pendant la conversion via traitement asynchrone.
- **NFR-003 Qualité audio** : rendu vocal naturel, intelligible et adapté à l'écoute longue durée.
- **NFR-004 Fiabilité pipeline** : reprise contrôlée en cas d'erreur chunk avec journalisation exploitable.
- **NFR-005 Confidentialité** : aucune transmission de texte ou d'audio à des services tiers.
- **NFR-006 Sécurité locale** : stockage local avec permissions système standard et sans exposition réseau non requise.
- **NFR-007 Compatibilité OS** : MVP ciblé Linux Mint desktop.
- **NFR-008 Compatibilité hardware** : support GPU AMD RX 7900 XT via ROCm et fallback CPU via Kokoro.
- **NFR-009 Maintenabilité** : architecture modulaire séparant extraction, TTS, post-traitement audio et bibliothèque.
- **NFR-010 Observabilité locale** : logs clairs pour diagnostic des erreurs et suivi des performances.

## Technical Constraints

- **Desktop only MVP** : pas de version web ni mobile.
- **Stack interface** : Python + PyQt5.
- **TTS principal** : Chatterbox TTS (Resemble AI, licence MIT, ~0.5B paramètres, support ROCm natif, multilingue v2 23 langues, voice cloning, contrôle d'émotion).
- **TTS alternatif** : Kokoro (82M paramètres, Apache 2.0, rapide et exécutable sur CPU).
- **Extraction texte** : `ebooklib` pour EPUB, `PyPDF2` pour PDF, parsing natif TXT/Markdown.
- **Hardware cible** : AMD RX 7900 XT 20GB VRAM, 32GB RAM, Linux Mint.
- **Mémoire modèle** : prévoir ~6GB VRAM minimum pour Chatterbox.
- **Offline après setup** : aucune connexion Internet requise après téléchargement initial des modèles.
- **Langue MVP** : interface en anglais uniquement.
- **Décision technique validée** : Chatterbox TTS (GPU) et Kokoro ONNX (CPU fallback) retenus comme moteurs TTS.

## Success Metrics

### User Success Metrics

- Taux de conversions réussies de document vers audio.
- Temps moyen de conversion perçu comme acceptable par les utilisateurs cibles.
- Taux d'usage hebdomadaire du lecteur intégré et de la bibliothèque locale.
- Adoption du mode batch sur des usages multi-documents.

### Business Objectives

- Valider une solution locale premium sans cloud pour usages personnels et techniques.
- Démontrer une qualité vocale supérieure aux alternatives open-source usuelles.
- Réduire la friction de conversion multi-formats via un flux desktop unifié.

### Key Performance Indicators

- **KPI-001** : pourcentage de conversions complètes sans erreur.
- **KPI-002** : temps médian de conversion par 10 000 mots pour chaque moteur TTS.
- **KPI-003** : pourcentage d'utilisateurs actifs hebdomadaires lançant au moins une conversion.
- **KPI-004** : pourcentage d'utilisateurs actifs exploitant bibliothèque et recherche locale.
- **KPI-005** : répartition d'usage Chatterbox vs Kokoro selon contexte matériel.
- **KPI-006** : taux de sessions entièrement offline sans dépendance réseau.
