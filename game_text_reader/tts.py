"""Text-to-speech using edge-tts (preferred) or pyttsx3 (offline fallback)."""

from __future__ import annotations

import asyncio
import io
import logging
import tempfile
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)


class TTSEngine:
    """Non-blocking text-to-speech engine."""

    def __init__(self, config: Config) -> None:
        self._backend = config.tts_backend
        self._voice = config.voice
        self._pyttsx3_engine = None
        self._lock = threading.Lock()
        self._current_thread: threading.Thread | None = None
        self._init_backend()

    def _init_backend(self) -> None:
        if self._backend == "edge-tts":
            try:
                import edge_tts  # noqa: F401

                logger.info("Using edge-tts backend (voice: %s)", self._voice)
            except ImportError:
                logger.warning("edge-tts unavailable, falling back to pyttsx3")
                self._backend = "pyttsx3"

        if self._backend == "pyttsx3":
            try:
                import pyttsx3

                self._pyttsx3_engine = pyttsx3.init()
                voices = self._pyttsx3_engine.getProperty("voices")
                # Try to find a Spanish voice
                for v in voices:
                    if "spanish" in v.name.lower() or "es" in v.id.lower():
                        self._pyttsx3_engine.setProperty("voice", v.id)
                        break
                self._pyttsx3_engine.setProperty("rate", 170)
                logger.info("Using pyttsx3 TTS backend")
            except Exception as e:
                logger.error("pyttsx3 init failed: %s", e)

    def speak(self, text: str) -> None:
        """Speak the given text in a background thread (non-blocking)."""
        if not text.strip():
            return

        thread = threading.Thread(target=self._speak_blocking, args=(text,), daemon=True)
        self._current_thread = thread
        thread.start()

    def _speak_blocking(self, text: str) -> None:
        with self._lock:
            if self._backend == "edge-tts":
                self._speak_edge_tts(text)
            else:
                self._speak_pyttsx3(text)

    def _speak_edge_tts(self, text: str) -> None:
        try:
            import edge_tts

            async def _generate_and_play() -> None:
                communicate = edge_tts.Communicate(text, self._voice)
                # Write to a temp file and play with the built-in Windows player
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tmp_path = tmp.name

                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        with open(tmp_path, "ab") as f:
                            f.write(chunk["data"])

                self._play_audio_file(tmp_path)

                import os

                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

            asyncio.run(_generate_and_play())
        except Exception as e:
            logger.error("edge-tts failed: %s — trying pyttsx3 fallback", e)
            self._speak_pyttsx3(text)

    def _speak_pyttsx3(self, text: str) -> None:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            for v in voices:
                if "spanish" in v.name.lower() or "es" in v.id.lower():
                    engine.setProperty("voice", v.id)
                    break
            engine.setProperty("rate", 170)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            logger.error("pyttsx3 TTS failed: %s", e)

    @staticmethod
    def _play_audio_file(path: str) -> None:
        """Play an mp3 file on Windows."""
        import subprocess

        # Use PowerShell with Windows Media Player COM object for mp3 support
        ps_script = (
            f'Add-Type -AssemblyName presentationCore; '
            f'$p = New-Object System.Windows.Media.MediaPlayer; '
            f'$p.Open("{path}"); '
            f'$p.Play(); '
            f'Start-Sleep -Milliseconds 500; '
            f'while ($p.Position -lt $p.NaturalDuration.TimeSpan) {{ Start-Sleep -Milliseconds 100 }}; '
            f'$p.Close()'
        )
        try:
            subprocess.run(
                ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                check=False,
                capture_output=True,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
        except Exception:
            # Fallback: ffplay
            try:
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                    check=False,
                    capture_output=True,
                )
            except FileNotFoundError:
                logger.error("No audio player available to play TTS output")
