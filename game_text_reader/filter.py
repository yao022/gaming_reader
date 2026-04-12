"""AI text filter using Claude API to extract narrative game text."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a text filter for a video game screen reader tool designed for a visually impaired user.

You will receive raw OCR text extracted from a game screenshot. Your job is to:
1. KEEP only narrative content: notes, letters, documents, tutorial messages, item descriptions, \
dialogue lines, story text, journal entries, objective descriptions.
2. REMOVE irrelevant UI text: HUD counters (ammo, health, time), button prompts \
(Press A, Press X, Press E), menu labels (Options, Settings, Save, Load, Inventory), \
difficulty labels, control hints, version numbers, copyright notices.
3. Clean up OCR artifacts (fix obvious misreads, remove garbage characters).
4. Preserve the original language of the text — do NOT translate.
5. Return ONLY the cleaned narrative text, nothing else. No explanations, no labels.
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
