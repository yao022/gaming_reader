"""Configuration loading from config.yaml and .env files."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"

_DEFAULTS = {
    "language": "es",
    "voice": "es-ES-AlvaroNeural",
    "hotkey": "f8",
    "capture_backend": "dxcam",
    "ocr_backend": "easyocr",
    "tts_backend": "edge-tts",
    "ai_filter_enabled": True,
    "ai_filter_model": "claude-haiku-4-5-20251001",
    "sound_feedback": True,
    "ocr_languages": ["es", "en"],
}


@dataclass
class Config:
    language: str = "es"
    voice: str = "es-ES-AlvaroNeural"
    hotkey: str = "f8"
    capture_backend: str = "dxcam"
    ocr_backend: str = "easyocr"
    tts_backend: str = "edge-tts"
    ai_filter_enabled: bool = True
    ai_filter_model: str = "claude-haiku-4-5-20251001"
    sound_feedback: bool = True
    ocr_languages: list[str] = field(default_factory=lambda: ["es", "en"])


def load_config(config_path: Path | str | None = None) -> Config:
    """Load configuration from YAML file and environment variables."""
    load_dotenv(_PROJECT_ROOT / ".env")

    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH

    raw: dict = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        logger.info("Loaded config from %s", path)
    else:
        logger.warning("Config file not found at %s, using defaults", path)

    merged = {**_DEFAULTS, **raw}
    return Config(**{k: v for k, v in merged.items() if k in Config.__dataclass_fields__})
