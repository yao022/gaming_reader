"""Tests for TTS language detection and voice selection."""

from __future__ import annotations

from game_text_reader.config import Config
from game_text_reader.tts import TTSEngine, detect_language


def test_detect_language_spanish():
    assert detect_language("Esta es una nota encontrada en la habitación.") == "es"


def test_detect_language_english():
    assert detect_language("You found a mysterious letter on the desk.") == "en"


def test_detect_language_fallback_on_empty():
    # Very short or ambiguous text should fall back to default
    result = detect_language("", default="es")
    assert result == "es"


def test_voice_for_lang():
    config = Config(
        tts_backend="pyttsx3",  # avoid import checks
        voices={"es": "es-ES-AlvaroNeural", "en": "en-US-GuyNeural"},
    )
    engine = TTSEngine(config)
    assert engine._voice_for_lang("es") == "es-ES-AlvaroNeural"
    assert engine._voice_for_lang("en") == "en-US-GuyNeural"
    # Unknown language falls back to default language voice
    assert engine._voice_for_lang("fr") == "es-ES-AlvaroNeural"
