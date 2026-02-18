"""Integration test for TTS adapters with real synthesis."""

import io
import wave

from src.adapters.tts.kokoro_provider import KokoroProvider
from src.adapters.tts.chatterbox_provider import ChatterboxProvider


def _validate_wav_format(audio_bytes: bytes, expected_sample_rate: int) -> dict:
    """Validate WAV format and extract audio properties.
    
    Returns:
        dict with keys: valid, channels, sample_width, framerate, num_frames
    """
    try:
        buf = io.BytesIO(audio_bytes)
        with wave.open(buf, "rb") as wf:
            return {
                "valid": True,
                "channels": wf.getnchannels(),
                "sample_width": wf.getsampwidth(),
                "framerate": wf.getframerate(),
                "num_frames": wf.getnframes(),
            }
    except Exception as e:
        return {"valid": False, "error": str(e)}


def test_kokoro_provider_health_check():
    """Test Kokoro provider health check."""
    provider = KokoroProvider(healthy=True)
    result = provider.health_check()
    
    assert result.ok
    assert result.data["engine"] == "kokoro_cpu"
    assert result.data["available"] is True


def test_kokoro_provider_list_voices():
    """Test Kokoro provider voice listing."""
    provider = KokoroProvider(healthy=True)
    result = provider.list_voices()
    
    assert result.ok
    assert len(result.data) > 0
    assert result.data[0]["engine"] == "kokoro_cpu"


def test_kokoro_provider_synthesize():
    """Test Kokoro provider synthesis."""
    provider = KokoroProvider(healthy=True)
    result = provider.synthesize_chunk(
        "Hello world",
        correlation_id="test",
        job_id="test_job",
        chunk_index=0
    )
    
    assert result.ok
    assert len(result.data["audio_bytes"]) > 0
    assert result.data["metadata"]["engine"] == "kokoro_cpu"
    assert result.data["metadata"]["content_type"] == "audio/wav"
    assert result.data["metadata"]["sample_rate_hz"] == 24000
    
    # Validate WAV format
    wav_info = _validate_wav_format(result.data["audio_bytes"], 24000)
    assert wav_info["valid"], f"Invalid WAV format: {wav_info.get('error')}"
    assert wav_info["channels"] == 1, "Expected mono audio"
    assert wav_info["sample_width"] == 2, "Expected 16-bit audio"
    assert wav_info["framerate"] == 24000, "Sample rate mismatch"
    assert wav_info["num_frames"] > 0, "Audio contains no frames"


def test_chatterbox_provider_health_check():
    """Test Chatterbox provider health check."""
    provider = ChatterboxProvider(healthy=True)
    result = provider.health_check()
    
    assert result.ok
    assert result.data["engine"] == "chatterbox_gpu"
    assert result.data["available"] is True


def test_chatterbox_provider_list_voices():
    """Test Chatterbox provider voice listing."""
    provider = ChatterboxProvider(healthy=True)
    result = provider.list_voices()
    
    assert result.ok
    assert len(result.data) > 0
    assert result.data[0]["engine"] == "chatterbox_gpu"


def test_chatterbox_provider_synthesize():
    """Test Chatterbox provider synthesis."""
    provider = ChatterboxProvider(healthy=True)
    result = provider.synthesize_chunk(
        "Hello world",
        correlation_id="test",
        job_id="test_job",
        chunk_index=0
    )
    
    assert result.ok
    assert len(result.data["audio_bytes"]) > 0
    assert result.data["metadata"]["engine"] == "chatterbox_gpu"
    assert result.data["metadata"]["content_type"] == "audio/wav"
    assert result.data["metadata"]["sample_rate_hz"] == 24000
    
    # Validate WAV format
    wav_info = _validate_wav_format(result.data["audio_bytes"], 24000)
    assert wav_info["valid"], f"Invalid WAV format: {wav_info.get('error')}"
    assert wav_info["channels"] == 1, "Expected mono audio"
    assert wav_info["sample_width"] == 2, "Expected 16-bit audio"
    assert wav_info["framerate"] == 24000, "Sample rate mismatch"
    assert wav_info["num_frames"] > 0, "Audio contains no frames"


def test_kokoro_synthesize_validates_empty_text():
    """Test that Kokoro validates empty text input."""
    provider = KokoroProvider(healthy=True)
    result = provider.synthesize_chunk(
        "",
        correlation_id="test",
        job_id="test_job",
        chunk_index=0
    )
    
    assert not result.ok
    assert result.error.code == "tts_input_invalid"


def test_kokoro_synthesize_validates_voice():
    """Test that Kokoro validates voice input."""
    provider = KokoroProvider(healthy=True)
    result = provider.synthesize_chunk(
        "Hello",
        voice="invalid_voice",
        correlation_id="test",
        job_id="test_job",
        chunk_index=0
    )
    
    assert not result.ok
    assert result.error.code == "tts_voice_invalid"
