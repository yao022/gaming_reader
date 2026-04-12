"""AI text filter using Claude API to extract narrative game text."""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a text filter for a video game screen reader tool designed for a visually impaired user.

The user captures their full screen while playing games. The OCR extracts ALL text visible on \
screen, including text that is NOT part of the game. Your job is to return ONLY the game's \
narrative text that the user wants to hear read aloud.

REMOVE all of the following:
- URLs, web addresses, file paths (anything with http, www, .com, .net, .png, slashes, etc.)
- Browser UI: tab titles, address bar content, bookmark bar text
- Operating system UI: taskbar text, clock/date, weather, "Buscar", Start menu, system tray
- Window controls: minimize, maximize, close button labels
- Desktop app names in taskbar (Chrome, Spotify, Discord, etc.)
- Game HUD: ammo counters, health bars, stamina, money, score, timers, minimap labels
- Button prompts: "Press A", "Press X", "Press E to interact", controller icons
- Menu labels: Options, Settings, Save, Load, Inventory, Pause, Resume, Quit
- Difficulty labels, control hints, version numbers, copyright notices
- OCR garbage: random symbols, isolated characters, nonsensical character sequences

KEEP only game narrative content:
- Notes, letters, documents found in-game
- Tutorial messages and objective descriptions
- Item descriptions
- Dialogue lines and subtitles
- Story text, journal entries, lore

ALSO:
- Clean up OCR artifacts (fix obvious misreads like 0 for O, l for I, etc.)
- Remove stray punctuation or symbols that don't belong in the text
- Preserve the original language — do NOT translate
- Return ONLY the cleaned narrative text, nothing else. No explanations, no labels, no quotes.
- If there is no narrative text at all, return exactly: [NO TEXT]
"""


class TextFilter:
    """Filters OCR text using Claude API to keep only narrative game content."""

    def __init__(self, config: Config) -> None:
        self._enabled = config.ai_filter_enabled
        self._model = config.ai_filter_model
        self._client = None

        if self._enabled:
            self._init_client()

    def _init_client(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning(
                "ANTHROPIC_API_KEY not set — AI filter disabled. "
                "Set it in .env or disable ai_filter_enabled in config.yaml"
            )
            self._enabled = False
            return

        try:
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key)
            logger.info("AI text filter ready (model: %s)", self._model)
        except Exception as e:
            logger.warning("Failed to initialize Anthropic client: %s", e)
            self._enabled = False

    def filter(self, raw_text: str) -> str:
        """Filter raw OCR text. Returns narrative text only, or raw text if filter is disabled."""
        if not raw_text.strip():
            return ""

        if not self._enabled or self._client is None:
            logger.debug("AI filter disabled, returning raw OCR text")
            return raw_text

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": raw_text}],
            )
            filtered = response.content[0].text.strip()
            if filtered == "[NO TEXT]":
                logger.info("AI filter found no narrative text")
                return ""
            logger.info("AI filter: %d chars → %d chars", len(raw_text), len(filtered))
            return filtered
        except Exception as e:
            logger.error("AI filter failed: %s — returning raw text", e)
            return raw_text


# Patterns to strip before sending text to TTS
_URL_PATTERN = re.compile(
    r"https?://\S+|www\.\S+|[a-zA-Z0-9_-]+\.(com|net|org|io|png|jpg|jpeg|gif|html)\S*",
    re.IGNORECASE,
)
# File paths like C:\foo\bar or /foo/bar/image.png
_PATH_PATTERN = re.compile(r"[A-Za-z]:\\[\w\\.-]+|/[\w/.-]{5,}")
# Symbols that TTS reads literally as words ("plus", "hashtag", "slash", "asterisk", etc.)
_SYMBOL_NOISE = re.compile(r"[#+*=%&@{}\[\]<>|\\^~`/]")
# Repeated junk like "0*0*00*" or "0 0 00 0" — numeric noise from HUD/UI
_NUMERIC_NOISE = re.compile(r"(?:\d[\s*.,;:|x×-]*){4,}")
_MULTI_SPACE = re.compile(r"  +")
_EMPTY_LINES = re.compile(r"\n\s*\n\s*\n+")


def clean_for_speech(text: str) -> str:
    """Remove URLs, stray symbols, and OCR noise so TTS reads cleanly."""
    # Strip URLs
    text = _URL_PATTERN.sub("", text)
    # Strip file paths
    text = _PATH_PATTERN.sub("", text)
    # Strip numeric noise (HUD counters, codes like 0*0*00*)
    text = _NUMERIC_NOISE.sub("", text)
    # Strip symbols that TTS reads literally ("plus", "hashtag", "slash", "asterisk")
    text = _SYMBOL_NOISE.sub("", text)
    # Collapse leftover whitespace
    text = _MULTI_SPACE.sub(" ", text)
    text = _EMPTY_LINES.sub("\n\n", text)
    return text.strip()
