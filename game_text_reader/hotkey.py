"""Hotkey listener that orchestrates the capture → OCR → filter → TTS pipeline."""

from __future__ import annotations

import logging
import threading
import winsound
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .capture import ScreenCapture
    from .config import Config
    from .filter import TextFilter
    from .ocr import OCREngine
    from .tts import TTSEngine

logger = logging.getLogger(__name__)


class HotkeyListener:
    """Listens for a hotkey and runs the full text reading pipeline."""

    def __init__(
        self,
        config: Config,
        capture: ScreenCapture,
        ocr: OCREngine,
        text_filter: TextFilter,
        tts: TTSEngine,
    ) -> None:
        self._hotkey = config.hotkey
        self._sound_feedback = config.sound_feedback
        self._capture = capture
        self._ocr = ocr
        self._filter = text_filter
        self._tts = tts
        self._processing = False

    def start(self) -> None:
        """Register the hotkey and block until Ctrl+C."""
        import keyboard

        keyboard.add_hotkey(self._hotkey, self._on_hotkey)
        logger.info("Hotkey '%s' registered. Press it to capture and read game text.", self._hotkey)
        logger.info("Press Ctrl+C to quit.")

        keyboard.wait()  # blocks forever

    def _on_hotkey(self) -> None:
        """Handle hotkey press — runs pipeline in a background thread."""
        if self._processing:
            logger.debug("Already processing, ignoring hotkey press")
            return

        thread = threading.Thread(target=self._run_pipeline, daemon=True)
        thread.start()

    def _run_pipeline(self) -> None:
        """Execute the full pipeline: beep → capture → OCR → filter → TTS."""
        self._processing = True
        try:
            # Sound cue so user knows the keypress registered
            if self._sound_feedback:
                winsound.Beep(800, 150)

            logger.info("Capturing screen...")
            image = self._capture.grab()
            logger.info("Screen captured (%dx%d)", image.shape[1], image.shape[0])

            logger.info("Running OCR...")
            raw_text = self._ocr.extract(image)
            if not raw_text.strip():
                logger.info("No text detected on screen")
                if self._sound_feedback:
                    # Two short low beeps = no text found
                    winsound.Beep(400, 100)
                    winsound.Beep(400, 100)
                return

            logger.info("OCR result (%d chars): %.100s...", len(raw_text), raw_text)

            logger.info("Filtering text...")
            filtered_text = self._filter.filter(raw_text)
            if not filtered_text.strip():
                logger.info("No narrative text after filtering")
                if self._sound_feedback:
                    winsound.Beep(400, 100)
                    winsound.Beep(400, 100)
                return

            # Clean symbols/URLs that TTS would read literally
            from .filter import clean_for_speech

            cleaned_text = clean_for_speech(filtered_text)
            if not cleaned_text:
                logger.info("No text left after cleaning for speech")
                if self._sound_feedback:
                    winsound.Beep(400, 100)
                    winsound.Beep(400, 100)
                return

            logger.info("Speaking text (%d chars)...", len(cleaned_text))
            self._tts.speak(cleaned_text)

        except Exception:
            logger.exception("Pipeline error")
            if self._sound_feedback:
                # Error beep pattern
                winsound.Beep(300, 300)
        finally:
            self._processing = False
