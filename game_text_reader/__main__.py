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

    logger.info("Initializing components...")
    capture = ScreenCapture(config)
    ocr = OCREngine(config)
    text_filter = TextFilter(config)
    tts = TTSEngine(config)

    listener = HotkeyListener(config, capture, ocr, text_filter, tts)

    try:
        listener.start()
    except KeyboardInterrupt:
        logger.info("Shutting down.")
        sys.exit(0)


if __name__ == "__main__":
    main()
