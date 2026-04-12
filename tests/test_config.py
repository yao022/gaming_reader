"""Tests for configuration loading."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from game_text_reader.config import Config, load_config


def test_default_config():
    cfg = Config()
    assert cfg.language == "es"
    assert cfg.voices == {"es": "es-ES-AlvaroNeural", "en": "en-US-GuyNeural"}
    assert cfg.hotkey == "f8"
    assert cfg.capture_backend == "dxcam"
    assert cfg.ocr_backend == "easyocr"
    assert cfg.tts_backend == "edge-tts"
    assert cfg.ai_filter_enabled is True
    assert cfg.sound_feedback is True
    assert cfg.ocr_languages == ["es", "en"]


def test_load_config_from_yaml():
    data = {
        "language": "en",
        "hotkey": "f9",
        "voices": {"es": "es-MX-DaliaNeural", "en": "en-US-JennyNeural"},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        f.flush()
        cfg = load_config(f.name)

    assert cfg.language == "en"
    assert cfg.hotkey == "f9"
    assert cfg.voices["en"] == "en-US-JennyNeural"
    # Defaults should still apply for unset keys
    assert cfg.capture_backend == "dxcam"


def test_load_config_missing_file():
    cfg = load_config("/nonexistent/path/config.yaml")
    assert cfg.language == "es"  # should fall back to defaults
