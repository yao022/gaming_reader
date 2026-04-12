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
screen, including text that is NOT part of the game. The OCR often badly mangles text, especially \
from stylized or handwritten game fonts.

Your job is to:
1. Identify the game's narrative text (notes, letters, documents, dialogue, item descriptions, \
tutorials, journal entries, objectives, story text).
2. DISCARD everything else: URLs, browser UI, taskbar text (clock, date, weather, "Buscar"), \
desktop app names, window controls, game HUD (ammo, health, score, timers), button prompts \
(Press A/X/E), menu labels, version numbers, copyright, OCR garbage (random isolated symbols, \
single characters, nonsensical sequences like "@ | * | e | @").
3. RECONSTRUCT the narrative text intelligently. The OCR makes many mistakes with stylized fonts:
   - "#" often means "t" (e.g. "#his" → "this", "#han" → "than")
   - "+" often means "t" (e.g. "+own" → "town", "+ired" → "tired")
   - "9" often means "g" (e.g. "9uts" → "guts", "9rew" → "grew")
   - "4" often means "t" (e.g. "i4" → "it")
   - "0" often means "o" (e.g. "04'" → "of")
   - "1" often means "I" (e.g. "1 doubf" → "I doubt")
   - Letters get swapped, merged, or garbled — use context to figure out the real words
   - Punctuation and spacing get mangled
   You know these are from real game text (novels, letters, notes). Use your knowledge of common \
game narratives, English, and Spanish to reconstruct what the text actually says.
4. Preserve the original language of the text — do NOT translate.
5. Return ONLY the cleaned, reconstructed narrative text. No explanations, no labels, no quotes.
6. If there is no narrative text at all, return exactly: [NO TEXT]
"""


class TextFilter:
    """Filters OCR text using Claude API to keep only narrative game content."""

    def __init__(self, config: Config) -> None:
        self._enabled = config.ai_filter_enabled
        self._model = config.ai_filter_model
        self._client = None

        if self._enabled:
            self._init_client()
        else:
            logger.warning("AI filter is disabled in config.yaml")

    def _init_client(self) -> None:
        # Try loading .env directly as a fallback in case config.py didn't load it
        from pathlib import Path

        from dotenv import load_dotenv

        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(env_path, override=True)

        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            msg = (
                "ANTHROPIC_API_KEY not found in environment or .env file — AI filter disabled. "
                "Set it in .env or disable ai_filter_enabled in config.yaml"
            )
            logger.warning(msg)
            print(f"\n[WARNING]  {msg}\n")
            self._enabled = False
            return

        logger.info("ANTHROPIC_API_KEY found (%s...%s)", api_key[:10], api_key[-4:])

        try:
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key)
            # Quick validation: this doesn't make an API call, just checks the client exists
            logger.info("AI text filter ready (model: %s)", self._model)
            print(f"[OK] AI filter active (model: {self._model})")
        except Exception as e:
            msg = f"Failed to initialize Anthropic client: {e}"
            logger.warning(msg)
            print(f"\n[WARNING]  {msg}\n")
            self._enabled = False

    def filter(self, raw_text: str) -> str:
        """Filter raw OCR text. Returns narrative text only, or raw text if filter is disabled."""
        if not raw_text.strip():
            return ""

        if not self._enabled or self._client is None:
            logger.warning(
                "AI filter is NOT running — returning raw OCR text. "
                "Check your ANTHROPIC_API_KEY in .env"
            )
            return raw_text

        try:
            logger.info("Sending %d chars to AI filter (model: %s)...", len(raw_text), self._model)
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
            err = str(e)
            if "credit balance is too low" in err:
                print("\n[WARNING] Anthropic API: insufficient credits — go to https://console.anthropic.com/settings/billing")
                logger.warning("Anthropic credits too low — AI filter skipped")
            else:
                logger.error("AI filter failed: %s — returning raw text", e)
            return raw_text


# Patterns to strip before sending text to TTS
_URL_PATTERN = re.compile(
    r"https?://\S+|www\.\S+|"
    r"\S*\.(com|net|org|io|png|jpg|jpeg|gif|html|php|asp)\S*|"
    r"\S*(nocookie|wiki|static|revision|latest)\S*",
    re.IGNORECASE,
)
# File paths like C:\foo\bar or /foo/bar/image.png
_PATH_PATTERN = re.compile(r"[A-Za-z]:\\[\w\\.-]+|/[\w/.-]{5,}")
# Symbols that TTS reads literally as words ("plus", "hashtag", "slash", "asterisk", etc.)
_SYMBOL_NOISE = re.compile(r"[#+*=%&@{}\[\]<>|\\^~`/]")
# Repeated junk like "0*0*00*" or "0 0 00 0" — numeric noise from HUD/UI
_NUMERIC_NOISE = re.compile(r"(?:\d[\s*.,;:|x×-]*){4,}")
# Lines that are just 1-2 characters (isolated OCR garbage like "X", "11", "0 =")
_SHORT_JUNK_LINE = re.compile(r"^.{1,3}$", re.MULTILINE)
# Common taskbar/OS patterns
_OS_PATTERNS = re.compile(
    r"\b(Buscar|Parc\.\s*soleado|nublado|Mayorm\.)\b|"
    r"\d{1,2}[:/]\d{2}\b|"
    r"\d{1,2}/\d{2}/\d{4}|"
    r"\d{1,2}\s*°?\s*C\b",
    re.IGNORECASE,
)
_MULTI_SPACE = re.compile(r"  +")
_EMPTY_LINES = re.compile(r"\n\s*\n\s*\n+")


def clean_for_speech(text: str) -> str:
    """Remove URLs, stray symbols, and OCR noise so TTS reads cleanly."""
    # Strip URLs and URL-like fragments
    text = _URL_PATTERN.sub("", text)
    # Strip file paths
    text = _PATH_PATTERN.sub("", text)
    # Strip OS/taskbar patterns (date, time, weather, "Buscar")
    text = _OS_PATTERNS.sub("", text)
    # Strip numeric noise (HUD counters, codes like 0*0*00*)
    text = _NUMERIC_NOISE.sub("", text)
    # Strip symbols that TTS reads literally
    text = _SYMBOL_NOISE.sub("", text)
    # Strip short garbage lines (isolated "X", "11", "0 =", "9 C", etc.)
    text = _SHORT_JUNK_LINE.sub("", text)
    # Collapse leftover whitespace
    text = _MULTI_SPACE.sub(" ", text)
    text = _EMPTY_LINES.sub("\n\n", text)
    # Remove lines that are only whitespace
    lines = [line for line in text.split("\n") if line.strip()]
    return "\n".join(lines).strip()
