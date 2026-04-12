"""Text-to-speech using edge-tts (preferred) or pyttsx3 (offline fallback).

Detects the language of the text and selects the matching voice so that
Spanish text is read by a Spanish speaker and English text by an English one.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)


def detect_language(text: str, default: str = "es") -> str:
    """Detect the language of *text*, returning an ISO 639-1 code (e.g. 'es', 'en').

    Falls back to *default* when detection is uncertain or the library is missing.
    """
    try:
        from langdetect import detect, LangDetectException

        lang = detect(text)
        # langdetect may return regional variants like 'es' or 'en'
        lang = lang.split("-")[0]
        logger.debug("Detected language: %s", lang)
        return lang
    except LangDetectException:
        logger.debug("Language detection uncertain, using default '%s'", default)
        return default
    except ImportError:
        logger.warning("langdetect not installed — defaulting to '%s'", default)
        return default


class TTSEngine:
    """Non-blocking text-to-speech engine with automatic language detection."""

    def __init__(self, config: Config) -> None:
        self._backend = config.tts_backend
        self._voices = dict(config.voices)  # e.g. {"es": "es-ES-AlvaroNeural", "en": "en-US-GuyNeural"}
        self._default_lang = config.language
        self._lock = threading.Lock()
        self._current_thread: threading.Thread | None = None
        self._init_backend()

    def _init_backend(self) -> None:
        if self._backend == "edge-tts":
            try:
                import edge_tts  # noqa: F401

                logger.info("Using edge-tts backend (voices: %s)", self._voices)
            except ImportError:
                logger.warning("edge-tts unavailable, falling back to pyttsx3")
                self._backend = "pyttsx3"

        if self._backend == "pyttsx3":
            logger.info("Using pyttsx3 TTS backend")

    def _voice_for_lang(self, lang: str) -> str:
        """Return the configured voice for a language, falling back to the default language voice."""
        if lang in self._voices:
            return self._voices[lang]
        return self._voices.get(self._default_lang, next(iter(self._voices.values())))

    def speak(self, text: str) -> None:
        """Speak the given text in a background thread (non-blocking).

        Automatically detects the language and picks the matching voice.
        """
        if not text.strip():
            return

        lang = detect_language(text, default=self._default_lang)
        voice = self._voice_for_lang(lang)
        logger.info("TTS: detected lang='%s', using voice='%s'", lang, voice)

        thread = threading.Thread(
            target=self._speak_blocking, args=(text, voice, lang), daemon=True
        )
        self._current_thread = thread
        thread.start()

    def _speak_blocking(self, text: str, voice: str, lang: str) -> None:
        with self._lock:
            if self._backend == "edge-tts":
                self._speak_edge_tts(text, voice, lang)
            else:
                self._speak_pyttsx3(text, lang)

    def _speak_edge_tts(self, text: str, voice: str, lang: str) -> None:
        try:
            import edge_tts

            async def _generate_and_play() -> None:
                communicate = edge_tts.Communicate(text, voice)
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
            self._speak_pyttsx3(text, lang)

    def _speak_pyttsx3(self, text: str, lang: str) -> None:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            # Try to find a voice matching the detected language
            lang_keywords = {"es": "spanish", "en": "english", "fr": "french", "de": "german"}
            keyword = lang_keywords.get(lang, lang)
            for v in voices:
                if keyword in v.name.lower() or lang in v.id.lower():
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

        ps_script = (
            f'Add-Type -AssemblyName presentationCore; '
            f'$p = New-Object System.Windows.Media.MediaPlayer; '
            f'$p.Open("{path}"); '
            f'$p.Play(); '
            f'Start-Sleep -Milliseconds 500; '
            f'while ($p.Position -lt $p.NaturalDuration.TimeSpan) '
            f'{{ Start-Sleep -Milliseconds 100 }}; '
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
            try:
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                    check=False,
                    capture_output=True,
                )
            except FileNotFoundError:
                logger.error("No audio player available to play TTS output")
