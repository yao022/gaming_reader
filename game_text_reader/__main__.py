"""Entry point for game_text_reader: python -m game_text_reader."""

from __future__ import annotations

import logging
import sys


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("game_text_reader")

    logger.info("Game Text Reader starting...")

    from .capture import ScreenCapture
    from .config import load_config
    from .filter import TextFilter
    from .hotkey import HotkeyListener
    from .ocr import OCREngine
    from .tts import TTSEngine

    config = load_config()
    logger.info(
        "Config: language=%s, hotkey=%s, capture=%s, ocr=%s, tts=%s, ai_filter=%s",
        config.language,
        config.hotkey,
        config.capture_backend,
        config.ocr_backend,
        config.tts_backend,
        config.ai_filter_enabled,
    )

    # Verify API key is loaded if AI filter is enabled
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if config.ai_filter_enabled:
        if api_key:
            logger.info("ANTHROPIC_API_KEY loaded (%s...%s)", api_key[:10], api_key[-4:])
        else:
            logger.warning("ANTHROPIC_API_KEY is NOT set — AI filter will not work!")

    logger.info("Initializing components...")
    capture = ScreenCapture(config)
    ocr = OCREngine(config)
    text_filter = TextFilter(config)
    tts = TTSEngine(config)

    # Local mode (F9) uses a separate TTS engine — pyttsx3 by default so it's
    # offline and instant (no network download like edge-tts).
    if config.tts_backend_local != config.tts_backend:
        from dataclasses import replace as dc_replace
        local_config = dc_replace(config, tts_backend=config.tts_backend_local)
        tts_local = TTSEngine(local_config)
        logger.info("Local TTS backend: %s", config.tts_backend_local)
    else:
        tts_local = tts

    if not text_filter._enabled:
        logger.warning(
            ">>> AI FILTER IS OFF — text will NOT be filtered or reconstructed. "
            "Check your .env file and ANTHROPIC_API_KEY."
        )

    listener = HotkeyListener(config, capture, ocr, text_filter, tts, tts_local)

    try:
        listener.start()
    except KeyboardInterrupt:
        logger.info("Shutting down.")
        sys.exit(0)


if __name__ == "__main__":
    main()
