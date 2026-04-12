"""AI text filter using Claude API to extract narrative game text.

When the AI filter is unavailable (no credits, no API key), a local rule-based
corrector handles the most common OCR mistakes from stylized game fonts.
"""

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
   Use your knowledge of common game narratives, English, and Spanish to reconstruct the text.
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
        from pathlib import Path

        from dotenv import load_dotenv

        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(env_path, override=True)

        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            msg = (
                "ANTHROPIC_API_KEY not found — AI filter disabled. "
                "Set it in .env or disable ai_filter_enabled in config.yaml"
            )
            logger.warning(msg)
            print(f"\n[WARNING] {msg}\n")
            self._enabled = False
            return

        logger.info("ANTHROPIC_API_KEY found (%s...%s)", api_key[:10], api_key[-4:])

        try:
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key)
            logger.info("AI text filter ready (model: %s)", self._model)
            print(f"[OK] AI filter active (model: {self._model})")
        except Exception as e:
            msg = f"Failed to initialize Anthropic client: {e}"
            logger.warning(msg)
            print(f"\n[WARNING] {msg}\n")
            self._enabled = False

    def filter(self, raw_text: str) -> str:
        """Filter raw OCR text.

        If AI filter is active: send to Claude for full reconstruction + filtering.
        If AI filter is unavailable: apply local rule-based OCR correction instead.
        """
        if not raw_text.strip():
            return ""

        if not self._enabled or self._client is None:
            logger.info("AI filter unavailable — applying local OCR correction")
            return local_ocr_fix(raw_text)

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
                print(
                    "\n[WARNING] Anthropic API: insufficient credits — "
                    "go to https://console.anthropic.com/settings/billing\n"
                    "Falling back to local OCR correction.\n"
                )
                logger.warning("Anthropic credits too low — falling back to local OCR correction")
            else:
                logger.error("AI filter failed (%s) — falling back to local OCR correction", e)
            return local_ocr_fix(raw_text)


# ---------------------------------------------------------------------------
# Local rule-based OCR corrector (no API required)
# Handles common misreads from stylized / handwritten game fonts.
# ---------------------------------------------------------------------------

# Matches a sequence of at least 4 consecutive letters — real word content
_HAS_REAL_WORD = re.compile(r"[a-zA-ZáéíóúñüÁÉÍÓÚÑÜ]{4,}")

# URL / path noise
_URL_NOISE = re.compile(
    r"https?://\S+|www\.\S+|\S*(nocookie|wikia|static|revision|thelastofus)\S*"
    r"|\S*\.(com|net|org|io|png|jpg|jpeg|gif|html)\S*",
    re.IGNORECASE,
)
# Lines that are mostly a URL/path fragment after other cleaning
_URL_FRAGMENT_LINE = re.compile(
    r"^\s*\d*\s*(net|www|http|static|wiki)\b.*$",
    re.IGNORECASE,
)
_PATH_NOISE = re.compile(r"[A-Za-z]:\\[\w\\.-]+")

# OS / taskbar patterns — match common Spanish Windows taskbar text
_OS_NOISE = re.compile(
    r"\b(Buscar|Parc\.?\s*soleado|nublado|Mayorm[:\.]?\s*\w*)\b"
    r"|\d{1,2}[:/]\d{2}(:\d{2})?"   # times like 17:38, 18.06
    r"|\d{1,2}\.\d{2}\b"             # time with dot separator like 18.06
    r"|\d{1,2}/\d{2}/\d{4}"          # dates like 12/04/2026
    r"|\b\d{4}\b"                     # bare years like 2026
    r"|\d{1,2}\s*°?\s*C\b",          # temperatures like 13 C
    re.IGNORECASE,
)

# Symbols TTS reads as words
_SYMBOL_NOISE = re.compile(r"[#+*=%&@{}\[\]<>|\\^~`/]")
_MULTI_SPACE = re.compile(r"  +")


def local_ocr_fix(text: str) -> str:
    """Apply rule-based corrections to OCR output from stylized game fonts.

    Removes garbage lines, URLs, OS chrome, and fixes common character
    substitutions so the text is speakable without the AI filter.
    """
    lines_out = []
    for line in text.splitlines():
        stripped = line.strip()
        # Drop lines with no real word content (no run of 4+ letters)
        if not _HAS_REAL_WORD.search(stripped):
            continue
        # Drop URL lines
        stripped = _URL_NOISE.sub("", stripped).strip()
        if not stripped:
            continue
        # Drop URL fragment lines (e.g. "20 net", "25 static...")
        if _URL_FRAGMENT_LINE.match(stripped):
            continue
        # Drop OS/taskbar lines (date, time, weather, "Buscar", "Mayorm")
        stripped = _OS_NOISE.sub("", stripped).strip()
        if not stripped:
            continue
        # Drop lines that became too short after cleaning (e.g. "C 4)")
        if len(stripped) <= 5:
            continue
        lines_out.append(stripped)

    text = "\n".join(lines_out)

    # Underscores → spaces first so word-boundary rules work on the result
    text = text.replace("_", " ")

    # Fix common OCR character substitutions in game fonts
    # Special cases for # first (before generic rule)
    text = re.sub(r"#his\b", "this", text, flags=re.IGNORECASE)
    text = re.sub(r"#han\b", "than", text, flags=re.IGNORECASE)
    # # before any letter → t  (e.g. #his → this, #own → town)
    text = re.sub(r"#([a-zA-Z])", r"t\1", text)

    # + before a capital → "too " + word  (e.g. +Scared → too scared)
    text = re.sub(r"\+([A-Z][a-z])", lambda m: "too " + m.group(1).lower(), text)
    # standalone + (space+space) → "to"
    text = re.sub(r"(?<=\s)\+(?=\s)", "to", text)
    # + before a lowercase letter → t  (e.g. +own → town, +ired → tired)
    text = re.sub(r"\+([a-z])", r"t\1", text)

    # 9 at the start of a word → g  (e.g. 9uts → guts, 9rew → grew)
    text = re.sub(r"\b9([a-zA-Z])", r"g\1", text)
    # gnw → grew  (9nw → gnw after above rule)
    text = re.sub(r"\bgnw\b", "grew", text, flags=re.IGNORECASE)

    # Standalone 1 → I
    text = re.sub(r"(?<!\w)1(?!\w)", "I", text)
    # i4 / I4 → it
    text = re.sub(r"\bi4\b", "it", text, flags=re.IGNORECASE)
    # 04' / 04 → of
    text = re.sub(r"\b04['']?\b", "of", text)
    # 90/ → got  (e.g. "9uess 90/" → "guess got")
    text = re.sub(r"\b90[/\\]?\b", "got", text)
    # ñown → town  (ñ is OCR misread of t in some fonts)
    text = re.sub(r"\bñown\b", "town", text, flags=re.IGNORECASE)
    # of' → of  (leftover apostrophe from 04' fix)
    text = re.sub(r"\bof['']", "of", text)
    # Stray leading digit followed by You/were/were (e.g. "4 You were")
    text = re.sub(r"(?<!\w)\d\s+(?=You\b|were\b|the\b)", "", text)

    # Word-specific f→t / garble fixes
    text = re.sub(r"\bdoubf\b", "doubt", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwanf\b", "want", text, flags=re.IGNORECASE)
    text = re.sub(r"\blef\b", "let", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthaf\b", "that", text, flags=re.IGNORECASE)
    text = re.sub(r"righ[})\]t]?\b", "right", text, flags=re.IGNORECASE)
    text = re.sub(r"\brigh\b", "right", text, flags=re.IGNORECASE)
    text = re.sub(r"\bBul\b", "But", text)
    text = re.sub(r"\btis\b", "this", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmoreu\b", "more", text, flags=re.IGNORECASE)
    text = re.sub(r"\bStuplc\b", "stupid", text, flags=re.IGNORECASE)

    # Cood → Good
    text = re.sub(r"\bCood\b", "Good", text)
    # ShiHy / Sh1 → shitty
    text = re.sub(r"\bShiHy\b", "shitty", text, flags=re.IGNORECASE)
    text = re.sub(r"\bSh1\b", "shit", text, flags=re.IGNORECASE)
    # Yov → You
    text = re.sub(r"\bYov\b", "You", text)
    # aHitide / aHitude → attitude
    text = re.sub(r"\baH[it]+[iu]?de\b", "attitude", text, flags=re.IGNORECASE)
    text = re.sub(r"aHitide", "attitude", text, flags=re.IGNORECASE)
    # anolher → another, beller → better
    text = re.sub(r"\banolher\b", "another", text, flags=re.IGNORECASE)
    text = re.sub(r"\bbeller\b", "better", text, flags=re.IGNORECASE)
    # Yhis/Hown/Hhis/Hhan — capital Y/H misreads
    text = re.sub(r"\bYhis\b", "this", text)
    text = re.sub(r"\bHown\b", "town", text)
    text = re.sub(r"\bHhis\b", "this", text)
    text = re.sub(r"\bHhan\b", "than", text)
    # Jef → yet
    text = re.sub(r"\bJef\b", "yet", text)

    # Remove remaining stray symbols
    text = _SYMBOL_NOISE.sub("", text)
    text = _MULTI_SPACE.sub(" ", text)

    # Remove lines that are now empty or just whitespace
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Final speech cleaner (always runs, after AI filter or local fix)
# ---------------------------------------------------------------------------

_FINAL_URL = re.compile(r"\S*(nocookie|wikia|thelastofus|revision)\S*", re.IGNORECASE)
_FINAL_SYMBOLS = re.compile(r"[#+*=%&@{}\[\]<>|\\^~`/]")
_FINAL_SHORT_LINES = re.compile(r"^.{1,4}$", re.MULTILINE)
_FINAL_SPACES = re.compile(r"  +")
_FINAL_EMPTY = re.compile(r"\n\s*\n\s*\n+")


def clean_for_speech(text: str) -> str:
    """Final pass: strip any remaining URLs, symbols, and short junk lines."""
    text = _FINAL_URL.sub("", text)
    text = _FINAL_SYMBOLS.sub("", text)
    text = _FINAL_SHORT_LINES.sub("", text)
    text = _FINAL_SPACES.sub(" ", text)
    text = _FINAL_EMPTY.sub("\n\n", text)
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines).strip()
