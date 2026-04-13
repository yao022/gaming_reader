"""Hotkey listener that orchestrates the capture → OCR → filter → TTS pipeline.

Hotkeys:
  F7  (hotkey_stop)       — stop TTS playback immediately
  F8  (hotkey)            — full pipeline: AI filter + edge-tts (natural voice)
  F9  (hotkey_local)      — local-only: rule-based OCR + pyttsx3 (instant, robotic)
  F10 (hotkey_local_nice) — local-only: rule-based OCR + edge-tts (natural voice)
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
        tts_local: TTSEngine | None = None,
    ) -> None:
        self._hotkey = config.hotkey
        self._hotkey_local = config.hotkey_local
        self._hotkey_local_nice = config.hotkey_local_nice
        self._hotkey_stop = config.hotkey_stop
        self._sound_feedback = config.sound_feedback
        self._capture = capture
        self._ocr = ocr
        self._filter = text_filter
        self._tts = tts
        self._tts_local = tts_local if tts_local is not None else tts
        self._debug_logs = config.debug_logs
        self._processing = False

    def start(self) -> None:
        """Register hotkeys and block until Ctrl+C."""
        import keyboard

        keyboard.add_hotkey(self._hotkey_stop, self._on_hotkey_stop)
        keyboard.add_hotkey(self._hotkey, self._on_hotkey_ai)
        keyboard.add_hotkey(self._hotkey_local, self._on_hotkey_local)
        keyboard.add_hotkey(self._hotkey_local_nice, self._on_hotkey_local_nice)
        logger.info(
            "'%s' = stop  |  '%s' = AI+nice  |  '%s' = local+fast  |  '%s' = local+nice  |  Ctrl+C to quit",
            self._hotkey_stop,
            self._hotkey,
            self._hotkey_local,
            self._hotkey_local_nice,
        )
        keyboard.wait()

    def _on_hotkey_stop(self) -> None:
        """Handle F7 — stop TTS playback immediately."""
        self._tts.stop()
        self._tts_local.stop()
        if self._sound_feedback:
            winsound.Beep(500, 80)

    def _on_hotkey_ai(self) -> None:
        """Handle F8 — full pipeline with AI filter + edge-tts."""
        if self._processing:
            return
        threading.Thread(target=self._run_pipeline, args=(True, "ai"), daemon=True).start()

    def _on_hotkey_local(self) -> None:
        """Handle F9 — local OCR + pyttsx3 (instant, robotic voice)."""
        if self._processing:
            return
        threading.Thread(target=self._run_pipeline, args=(False, "local"), daemon=True).start()

    def _on_hotkey_local_nice(self) -> None:
        """Handle F10 — local OCR + edge-tts (natural voice, ~3s delay)."""
        if self._processing:
            return
        threading.Thread(target=self._run_pipeline, args=(False, "local_nice"), daemon=True).start()

    def _run_pipeline(self, use_ai: bool, mode: str = "ai") -> None:
        """Execute the pipeline: beep → capture → OCR → filter → TTS.

        mode: "ai" (F8), "local" (F9), or "local_nice" (F10)
        """
        self._processing = True
        t0 = time.perf_counter()
        try:
            if self._sound_feedback:
                beep_freq = {
                    "ai": 800,         # F8 — highest pitch
                    "local_nice": 700,  # F10 — medium pitch
                    "local": 600,       # F9 — lowest pitch
                }
                winsound.Beep(beep_freq.get(mode, 600), 150)

            logger.info("Capturing screen... (mode: %s)", mode)
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

            if self._debug_logs:
                self._write_debug_log(raw_text, filtered_text, cleaned_text)

            if not cleaned_text:
                logger.info("No narrative text after filtering/cleaning")
                if self._sound_feedback:
                    winsound.Beep(400, 100)
                    winsound.Beep(400, 100)
                return

            # F8 (ai) and F10 (local_nice) use edge-tts; F9 (local) uses pyttsx3
            tts_engine = self._tts_local if mode == "local" else self._tts
            logger.info("Starting TTS (%d chars)... total so far: %.2fs", len(cleaned_text), t4 - t0)
            tts_engine.speak(cleaned_text)
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
