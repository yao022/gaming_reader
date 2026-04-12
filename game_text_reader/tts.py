"""Text-to-speech using edge-tts (preferred) or pyttsx3 (offline fallback).

Detects the language of the text and selects the matching voice so that
Spanish text is read by a Spanish speaker and English text by an English one.
"""

from __future__ import annotations

import asyncio
import ctypes
import logging
import os
import tempfile
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)


def detect_language(text: str, default: str = "es") -> str:
    """Detect the language of *text*, returning an ISO 639-1 code (e.g. 'es', 'en').

    Falls back to *default* when detection is uncertain or the library is missing.
    """
    try:
        from langdetect import LangDetectException, detect

        lang = detect(text)
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
        self._voices = dict(config.voices)
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
        if lang in self._voices:
            return self._voices[lang]
        return self._voices.get(self._default_lang, next(iter(self._voices.values())))

    def speak(self, text: str) -> None:
        """Speak text in a background thread (non-blocking), auto-detecting language."""
        if not text.strip():
            return

        lang = detect_language(text, default=self._default_lang)
        voice = self._voice_for_lang(lang)
        logger.info("TTS: lang='%s', voice='%s'", lang, voice)

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

            async def _stream() -> bytes:
                """Collect all audio bytes from edge-tts."""
                communicate = edge_tts.Communicate(text, voice)
                buf = bytearray()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        buf.extend(chunk["data"])
                return bytes(buf)

            t0 = time.perf_counter()
            audio_bytes = asyncio.run(_stream())
            t1 = time.perf_counter()
            if not audio_bytes:
                raise RuntimeError("edge-tts returned no audio")
            logger.info("edge-tts download: %.2fs (%d bytes)", t1 - t0, len(audio_bytes))

            # Try fast ffplay pipe first (starts playing immediately, no temp file)
            if not _play_mp3_ffplay_pipe(audio_bytes):
                # Fall back to MCI (writes temp file, then plays)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
                t2 = time.perf_counter()
                logger.info("edge-tts playback start (MCI): %.2fs after download", t2 - t1)
                _play_mp3_mci(tmp_path)
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        except Exception as e:
            logger.error("edge-tts failed: %s — trying pyttsx3 fallback", e)
            self._speak_pyttsx3(text, lang)

    def _speak_pyttsx3(self, text: str, lang: str) -> None:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            lang_keywords = {"es": "spanish", "en": "english", "fr": "french", "de": "german"}
            keyword = lang_keywords.get(lang, lang)
            selected_voice = None
            for v in voices:
                if keyword in v.name.lower() or f"-{lang}-" in v.id.lower() or v.id.lower().endswith(f"_{lang}_"):
                    engine.setProperty("voice", v.id)
                    selected_voice = v.name
                    break
            if selected_voice:
                logger.info("pyttsx3 voice selected: %s", selected_voice)
            else:
                available = [v.name for v in voices]
                logger.warning(
                    "pyttsx3: no voice found for lang='%s'. "
                    "Available voices: %s. "
                    "Install English voice: Settings → Time & Language → Speech → Add voices.",
                    lang, available,
                )
            engine.setProperty("rate", 170)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            logger.error("pyttsx3 TTS failed: %s", e)


def _play_mp3_ffplay_pipe(audio_bytes: bytes) -> bool:
    """Stream mp3 bytes to ffplay via stdin — playback starts with first chunk.

    Returns True if ffplay is available and playback succeeded, False otherwise.
    """
    import subprocess

    try:
        proc = subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", "pipe:0"],
            input=audio_bytes,
            capture_output=True,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        return proc.returncode == 0
    except FileNotFoundError:
        return False  # ffplay not installed
    except Exception as e:
        logger.warning("ffplay pipe failed: %s", e)
        return False


def _play_mp3_mci(path: str) -> None:
    """Play an mp3 file using Windows MCI (winmm.dll) — no PowerShell needed."""
    try:
        winmm = ctypes.windll.winmm  # type: ignore[attr-defined]
        alias = "gtr_audio"
        winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, None)
        winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
        winmm.mciSendStringW(f"close {alias}", None, 0, None)
    except Exception as e:
        logger.warning("MCI playback failed (%s)", e)
        logger.error("No working audio player — install ffmpeg for best performance")
