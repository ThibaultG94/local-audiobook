# Rapport de Passe 2 - Implémentation TTS Local

> **Note historique:** Ce document décrit une phase d'exploration technique antérieure au projet. Les décisions et contraintes mentionnées ici ont évolué. Pour la configuration actuelle, consulter [`README.md`](README.md) et [`INSTALLATION.md`](INSTALLATION.md).

## Contexte historique

Ce rapport documente une phase d'exploration technique réalisée avant la finalisation de l'architecture actuelle. Les informations ci-dessous sont conservées à titre de référence historique uniquement.

### Stack technique explorée (historique)

**Moteurs TTS évalués:**

- Chatterbox TTS (GPU AMD via ROCm)
- Kokoro TTS (CPU fallback)

**Contraintes techniques rencontrées:**

- Compatibilité versions Python
- Dépendances PyTorch et ROCm
- Gestion de l'espace disque pour les modèles

### Décisions finales

**Stack retenue (voir documentation actuelle):**

- Python 3.12
- ROCm 7.2
- PyTorch 2.9.1
- Chatterbox (GPU) + Kokoro ONNX (CPU fallback)

Pour les instructions d'installation actuelles et à jour, consulter:

- [`README.md`](README.md) - Vue d'ensemble et quick start
- [`INSTALLATION.md`](INSTALLATION.md) - Installation complète avec ROCm 7.2

---

**Ce document est conservé uniquement pour référence historique et ne doit pas être utilisé comme guide d'installation.**
