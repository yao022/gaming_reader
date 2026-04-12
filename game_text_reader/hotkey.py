"""Hotkey listener that orchestrates the capture → OCR → filter → TTS pipeline."""

from __future__ import annotations

import logging
import threading
import time
import winsound
from pathlib import Path
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

            logger.info("OCR result (%d chars)", len(raw_text))

            logger.info("Filtering text...")
            filtered_text = self._filter.filter(raw_text)

            # Clean symbols/URLs that TTS would read literally
            from .filter import clean_for_speech

            cleaned_text = clean_for_speech(filtered_text) if filtered_text.strip() else ""

            # Write debug log so we can inspect what each stage produced
            self._write_debug_log(raw_text, filtered_text, cleaned_text)

            if not cleaned_text:
                logger.info("No narrative text after filtering/cleaning")
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

    @staticmethod
    def _write_debug_log(raw_ocr: str, filtered: str, cleaned: str) -> None:
        """Write the full text at each pipeline stage to a debug log file."""
        log_dir = Path(__file__).resolve().parent.parent / "debug_logs"
        log_dir.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"capture_{timestamp}.txt"
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("STAGE 1: RAW OCR OUTPUT\n")
            f.write("=" * 60 + "\n")
            f.write(raw_ocr)
            f.write("\n\n")
            f.write("=" * 60 + "\n")
            f.write("STAGE 2: AFTER AI FILTER\n")
            f.write("=" * 60 + "\n")
            f.write(filtered)
            f.write("\n\n")
            f.write("=" * 60 + "\n")
            f.write("STAGE 3: AFTER CLEAN FOR SPEECH (sent to TTS)\n")
            f.write("=" * 60 + "\n")
            f.write(cleaned)
            f.write("\n")
        logger.info("Debug log written to %s", log_path)
