#!/usr/bin/env python
"""Script de test du pipeline TTS complet."""

import sys
from pathlib import Path

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from adapters.tts.kokoro_provider import KokoroProvider
from adapters.tts.chatterbox_provider import ChatterboxProvider
from domain.services.chunking_service import ChunkingService

def test_pipeline():
    """Test le pipeline complet de conversion."""
    print("=== Test du pipeline TTS ===\n")
    
    # 1. Lire le fichier de test
    print("1. Lecture du fichier test...")
    with open("test_sample.txt", "r") as f:
        text = f.read()
    print(f"   Texte: {text[:50]}...")
    
    # 2. Chunking
    print("\n2. Découpage en chunks...")
    chunker = ChunkingService()
    chunks_result = chunker.chunk_text(text=text, max_chars=100)
    if not chunks_result.ok:
        print(f"   ❌ Erreur: {chunks_result.error.message}")
        return False
    
    chunks = chunks_result.data
    print(f"   ✓ {len(chunks)} chunks créés")
    for i, chunk in enumerate(chunks):
        print(f"     Chunk {i}: {chunk[:40]}...")
    
    # 3. Test Kokoro
    print("\n3. Test synthèse avec Kokoro...")
    kokoro = KokoroProvider(healthy=True)
    
    for i, chunk in enumerate(chunks[:2]):  # Tester seulement les 2 premiers
        result = kokoro.synthesize_chunk(
            chunk,
            correlation_id="test",
            job_id="test_job",
            chunk_index=i
        )
        if not result.ok:
            print(f"   ❌ Chunk {i} échoué: {result.error.message}")
            return False
        
        audio_size = len(result.data["audio_bytes"])
        print(f"   ✓ Chunk {i}: {audio_size} bytes audio générés")
    
    # 4. Test Chatterbox
    print("\n4. Test synthèse avec Chatterbox...")
    chatterbox = ChatterboxProvider(healthy=True)
    
    result = chatterbox.synthesize_chunk(
        chunks[0],
        correlation_id="test",
        job_id="test_job",
        chunk_index=0
    )
    if not result.ok:
        print(f"   ❌ Échec: {result.error.message}")
        return False
    
    audio_size = len(result.data["audio_bytes"])
    print(f"   ✓ {audio_size} bytes audio générés")
    
    # 5. Vérifier les voix disponibles
    print("\n5. Voix disponibles...")
    kokoro_voices = kokoro.list_voices()
    chatterbox_voices = chatterbox.list_voices()
    
    print(f"   Kokoro: {len(kokoro_voices.data)} voix")
    print(f"   Chatterbox: {len(chatterbox_voices.data)} voix")
    
    print("\n✅ Pipeline complet testé avec succès!")
    return True

if __name__ == "__main__":
    success = test_pipeline()
    sys.exit(0 if success else 1)
