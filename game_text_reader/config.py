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
    "voices": {"es": "es-ES-AlvaroNeural", "en": "en-US-GuyNeural"},
    "hotkey": "f8",
    "hotkey_local": "f9",
    "capture_backend": "dxcam",
    "ocr_backend": "winrt",
    "tts_backend": "edge-tts",
    "tts_backend_local": "pyttsx3",
    "tts_rate": 20,
    "ai_filter_enabled": True,
    "ai_filter_model": "claude-3-haiku-20240307",
    "sound_feedback": True,
    "ocr_languages": ["es", "en"],
}


@dataclass
class Config:
    language: str = "es"
    voices: dict[str, str] = field(
        default_factory=lambda: {"es": "es-ES-AlvaroNeural", "en": "en-US-GuyNeural"}
    )
    hotkey: str = "f8"
    hotkey_local: str = "f9"
    capture_backend: str = "dxcam"
    ocr_backend: str = "winrt"
    tts_backend: str = "edge-tts"
    tts_backend_local: str = "pyttsx3"
    tts_rate: int = 20
    ai_filter_enabled: bool = True
    ai_filter_model: str = "claude-3-haiku-20240307"
    sound_feedback: bool = True
    ocr_languages: list[str] = field(default_factory=lambda: ["es", "en"])


def load_config(config_path: Path | str | None = None) -> Config:
    """Load configuration from YAML file and environment variables."""
    env_path = _PROJECT_ROOT / ".env"
    loaded = load_dotenv(env_path, override=True)
    logger.info(".env path: %s (exists=%s, loaded=%s)", env_path, env_path.exists(), loaded)

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
