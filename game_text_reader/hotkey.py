"""Hotkey listener that orchestrates the capture → OCR → filter → TTS pipeline.

Two hotkeys are registered:
  F8 (hotkey)       — full pipeline: AI filter (with local fallback)
  F9 (hotkey_local) — local-only: skips AI, uses rule-based OCR corrector
"""

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
    """Listens for hotkeys and runs the full text reading pipeline."""

    def __init__(
        self,
        config: Config,
        capture: ScreenCapture,
        ocr: OCREngine,
        text_filter: TextFilter,
        tts: TTSEngine,
    ) -> None:
        self._hotkey = config.hotkey
        self._hotkey_local = config.hotkey_local
        self._sound_feedback = config.sound_feedback
        self._capture = capture
        self._ocr = ocr
        self._filter = text_filter
        self._tts = tts
        self._processing = False

    def start(self) -> None:
        """Register hotkeys and block until Ctrl+C."""
        import keyboard

        keyboard.add_hotkey(self._hotkey, self._on_hotkey_ai)
        keyboard.add_hotkey(self._hotkey_local, self._on_hotkey_local)
        logger.info(
            "'%s' = AI filter  |  '%s' = local only  |  Ctrl+C to quit",
            self._hotkey,
            self._hotkey_local,
        )
        keyboard.wait()

    def _on_hotkey_ai(self) -> None:
        """Handle F8 — full pipeline with AI filter."""
        if self._processing:
            return
        threading.Thread(target=self._run_pipeline, args=(True,), daemon=True).start()

    def _on_hotkey_local(self) -> None:
        """Handle F9 — local-only, no AI call."""
        if self._processing:
            return
        threading.Thread(target=self._run_pipeline, args=(False,), daemon=True).start()

    def _run_pipeline(self, use_ai: bool) -> None:
        """Execute the pipeline: beep → capture → OCR → filter → TTS."""
        self._processing = True
        t0 = time.perf_counter()
        try:
            if self._sound_feedback:
                # Different beep pitch for AI vs local so you can tell them apart
                winsound.Beep(800 if use_ai else 600, 150)

            logger.info("Capturing screen... (mode: %s)", "AI" if use_ai else "local")
            image = self._capture.grab()
            t1 = time.perf_counter()
            logger.info("Captured (%dx%d) in %.2fs", image.shape[1], image.shape[0], t1 - t0)

            logger.info("Running OCR...")
            raw_text = self._ocr.extract(image)
            t2 = time.perf_counter()
            logger.info("OCR done in %.2fs (%d chars)", t2 - t1, len(raw_text))
            if not raw_text.strip():
                logger.info("No text detected")
                if self._sound_feedback:
                    winsound.Beep(400, 100)
                    winsound.Beep(400, 100)
                return

            logger.info("Filtering... (use_ai=%s)", use_ai)
            if use_ai:
                filtered_text = self._filter.filter(raw_text)
            else:
                from .filter import local_ocr_fix
                filtered_text = local_ocr_fix(raw_text)
            t3 = time.perf_counter()
            logger.info("Filter done in %.2fs (%d chars)", t3 - t2, len(filtered_text))

            from .filter import clean_for_speech
            cleaned_text = clean_for_speech(filtered_text) if filtered_text.strip() else ""
            t4 = time.perf_counter()
            logger.info("Clean done in %.2fs (%d chars)", t4 - t3, len(cleaned_text))

            self._write_debug_log(raw_text, filtered_text, cleaned_text)

            if not cleaned_text:
                logger.info("No narrative text after filtering/cleaning")
                if self._sound_feedback:
                    winsound.Beep(400, 100)
                    winsound.Beep(400, 100)
                return

            logger.info("Starting TTS (%d chars)... total so far: %.2fs", len(cleaned_text), t4 - t0)
            self._tts.speak(cleaned_text)
            logger.info("TTS dispatched (total pipeline: %.2fs)", time.perf_counter() - t0)

        except Exception:
            logger.exception("Pipeline error")
            if self._sound_feedback:
                winsound.Beep(300, 300)
        finally:
            self._processing = False

    @staticmethod
    def _write_debug_log(raw_ocr: str, filtered: str, cleaned: str) -> None:
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
        logger.info("Debug log: %s", log_path)
