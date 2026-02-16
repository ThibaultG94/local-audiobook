# Installation des moteurs TTS

Ce document décrit comment installer les vrais moteurs TTS (Chatterbox et Kokoro) pour remplacer les implémentations de test actuelles.

## État actuel

L'application utilise actuellement :
- **Kokoro (CPU)** : Implémentation avec `pyttsx3` pour les tests
- **Chatterbox (GPU)** : Stub qui génère du silence

## Prérequis système

### Matériel
- **GPU AMD** : RX 7900 XT (20GB VRAM) ou équivalent
- **RAM** : 32GB recommandé
- **Espace disque** : ~10GB pour PyTorch ROCm + modèles TTS

### Logiciels
- **OS** : Linux (testé sur Linux Mint/Debian 11)
- **Python** : 3.11 (IMPORTANT : pas 3.13)
- **ROCm** : Déjà installé et configuré sur le système

## Installation de Python 3.11

### Option 1 : pyenv (recommandé)

```bash
# Installer pyenv si nécessaire
curl https://pyenv.run | bash

# Installer Python 3.11
pyenv install 3.11.9
pyenv local 3.11.9

# Vérifier
python --version  # Doit afficher Python 3.11.9
```

### Option 2 : Environnement virtuel système

```bash
# Installer Python 3.11 via le gestionnaire de paquets
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# Créer un environnement virtuel
python3.11 -m venv .venv
source .venv/bin/activate
```

## Installation de PyTorch avec ROCm

PyTorch avec support ROCm est volumineux (~2.8GB). Assurez-vous d'avoir suffisamment d'espace.

```bash
# Configurer un répertoire temporaire avec plus d'espace
export TMPDIR=$HOME/tmp
mkdir -p $HOME/tmp

# Installer PyTorch ROCm 6.1
pip install --no-cache-dir torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/rocm6.1

# Vérifier l'installation
python -c "import torch; print(f'PyTorch: {torch.__version__}'); \
           print(f'ROCm available: {torch.cuda.is_available()}'); \
           print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}')"
```

**Sortie attendue :**
```
PyTorch: 2.6.0+rocm6.1
ROCm available: True
Device: AMD Radeon RX 7900 XT
```

## Installation de Chatterbox TTS

Chatterbox est un moteur TTS de Resemble AI (MIT License, ~350M paramètres).

```bash
# Installer chatterbox-tts
pip install chatterbox-tts

# Tester l'installation
python -c "from chatterbox.tts_turbo import ChatterboxTurboTTS; \
           print('Chatterbox TTS installé avec succès')"
```

### Exemple d'utilisation

```python
import torchaudio as ta
from chatterbox.tts_turbo import ChatterboxTurboTTS

# Charger le modèle (téléchargement automatique au premier lancement)
model = ChatterboxTurboTTS.from_pretrained(device="cuda")

# Générer de l'audio
text = "Hello, this is a test of Chatterbox TTS."
wav = model.generate(text)

# Sauvegarder
ta.save("test.wav", wav, model.sr)
```

**Note :** Le modèle sera téléchargé automatiquement dans `~/.cache/huggingface/` au premier lancement.

## Installation de Kokoro TTS

Kokoro est un moteur TTS léger (82M paramètres, Apache 2.0).

```bash
# Installer kokoro-tts
pip install kokoro-tts

# Tester l'installation
python -c "import kokoro; print('Kokoro TTS installé avec succès')"
```

### Exemple d'utilisation

```python
from kokoro import KokoroTTS

# Initialiser le modèle
model = KokoroTTS()

# Générer de l'audio
text = "Hello, this is a test of Kokoro TTS."
audio = model.synthesize(text)

# Sauvegarder
model.save_wav(audio, "test.wav")
```

## Intégration dans l'application

Une fois les moteurs installés, vous devez mettre à jour les adapters :

### 1. Mettre à jour `src/adapters/tts/chatterbox_provider.py`

Remplacer la méthode `_synthesize_audio()` :

```python
def _synthesize_audio(self, text: str, voice: str) -> bytes:
    """Synthesize audio using Chatterbox engine."""
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    import torchaudio as ta
    from io import BytesIO
    
    if not hasattr(self, '_model'):
        self._model = ChatterboxTurboTTS.from_pretrained(device="cuda")
    
    # Générer l'audio
    wav = self._model.generate(text)
    
    # Convertir en bytes WAV
    buffer = BytesIO()
    ta.save(buffer, wav, self._model.sr, format="wav")
    return buffer.getvalue()
```

### 2. Mettre à jour `src/adapters/tts/kokoro_provider.py`

Remplacer l'implémentation pyttsx3 par Kokoro :

```python
def _synthesize_audio(self, text: str, voice: str) -> bytes:
    """Synthesize audio using Kokoro engine."""
    from kokoro import KokoroTTS
    from io import BytesIO
    
    if not hasattr(self, '_model'):
        self._model = KokoroTTS()
    
    # Générer l'audio
    audio = self._model.synthesize(text, voice=voice)
    
    # Convertir en bytes WAV
    buffer = BytesIO()
    self._model.save_wav(audio, buffer)
    return buffer.getvalue()
```

### 3. Mettre à jour `config/model_manifest.yaml`

Après installation, calculer les vrais hash des modèles :

```bash
# Trouver les fichiers modèles
find ~/.cache/huggingface -name "*.bin" -o -name "*.safetensors" | head -5

# Calculer le SHA256
sha256sum /path/to/model/file
```

Mettre à jour le manifest avec les vrais chemins, hash et tailles.

## Vérification de l'installation

### Test complet du pipeline

```bash
# Démarrer l'application
python -m src.app.main

# Dans l'interface :
# 1. Vérifier que readiness = "ready"
# 2. Importer un fichier TXT de test
# 3. Configurer : Kokoro CPU, voix par défaut, EN, WAV
# 4. Lancer la conversion
# 5. Vérifier l'audio généré dans runtime/library/audio/
```

### Tests unitaires

```bash
# Exécuter les tests
pytest tests/

# Tests spécifiques TTS
pytest tests/integration/test_tts_provider_events_schema.py -v
```

## Dépannage

### Erreur : "No module named 'torch.sparse'"

PyTorch n'est pas correctement installé. Désinstaller et réinstaller :

```bash
pip uninstall torch torchvision torchaudio
export TMPDIR=$HOME/tmp
pip install --no-cache-dir torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/rocm6.1
```

### Erreur : "OSError: [Errno 28] No space left on device"

Le répertoire temporaire `/tmp` est plein. Utiliser `TMPDIR` :

```bash
export TMPDIR=$HOME/tmp
mkdir -p $HOME/tmp
# Réessayer l'installation
```

### Erreur : "AttributeError: module 'pkgutil' has no attribute 'ImpImporter'"

Vous utilisez Python 3.13 qui n'est pas compatible. Passer à Python 3.11.

### GPU non détecté

Vérifier ROCm :

```bash
rocm-smi
python -c "import torch; print(torch.cuda.is_available())"
```

Si `False`, vérifier l'installation de ROCm et les variables d'environnement.

## Ressources

- **Chatterbox TTS** : https://github.com/resemble-ai/chatterbox
- **Kokoro TTS** : https://github.com/nazdridoy/kokoro-tts
- **PyTorch ROCm** : https://pytorch.org/get-started/locally/
- **ROCm Documentation** : https://rocm.docs.amd.com/

## Notes importantes

1. **Watermarking** : Chatterbox inclut un watermark imperceptible (Perth) dans tous les audios générés
2. **Licence** : Chatterbox (MIT), Kokoro (Apache 2.0) - 100% open source
3. **Offline** : Une fois installés, les modèles fonctionnent 100% en local
4. **Performance** : Chatterbox GPU ~2-3x plus rapide que Kokoro CPU
5. **Qualité** : Chatterbox offre une meilleure qualité mais nécessite plus de ressources
