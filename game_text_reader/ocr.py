"""OCR text extraction from screen captures.

Backends (in order of preference):
  winrt      — Windows.Media.Ocr, built into Windows 10/11, hardware-accelerated
               via DirectX (works on AMD/Intel integrated graphics). ~0.1-0.3s.
  easyocr    — Deep-learning OCR, accurate but slow on CPU (~3s). GPU needed.
  pytesseract — Traditional OCR, faster than easyocr on CPU. Fallback.

Images are downscaled before OCR to reduce inference time without losing
accuracy (game text is large, so downscaling has minimal effect).
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)

# Max width fed to OCR. Game text is large enough that downscaling doesn't
# hurt recognition quality but cuts inference time significantly.
_MAX_OCR_WIDTH = 960


def _downscale(image: np.ndarray) -> np.ndarray:
    """Downscale image to _MAX_OCR_WIDTH if wider, preserving aspect ratio."""
    h, w = image.shape[:2]
    if w <= _MAX_OCR_WIDTH:
        return image
    scale = _MAX_OCR_WIDTH / w
    new_w, new_h = int(w * scale), int(h * scale)
    from PIL import Image

    pil = Image.fromarray(image).resize((new_w, new_h), Image.LANCZOS)
    result = np.asarray(pil)
    logger.debug("Downscaled %dx%d → %dx%d for OCR", w, h, new_w, new_h)
    return result


class OCREngine:
    """Extracts text from a screen capture image."""

    def __init__(self, config: Config) -> None:
        self._backend = config.ocr_backend
        self._languages = config.ocr_languages
        self._easyocr_reader = None
        self._init_backend()

    def _init_backend(self) -> None:
        if self._backend == "winrt":
            try:
                from winsdk.windows.media.ocr import OcrEngine  # noqa: F401

                logger.info("Using Windows OCR (winrt) backend — hardware accelerated")
            except ImportError:
                logger.warning(
                    "winsdk not installed — falling back to easyocr. "
                    "Install with: pip install winsdk"
                )
                self._backend = "easyocr"

        if self._backend == "easyocr":
            try:
                import easyocr

                logger.info(
                    "Initializing EasyOCR (this may take a few seconds on first run)..."
                )
                self._easyocr_reader = easyocr.Reader(
                    self._languages, gpu=True, verbose=False
                )
                logger.info("EasyOCR ready (languages: %s)", self._languages)
            except Exception:
                logger.warning("EasyOCR unavailable, falling back to pytesseract")
                self._backend = "pytesseract"

        if self._backend == "pytesseract":
            logger.info("Using pytesseract OCR backend")

    def extract(self, image: np.ndarray) -> str:
        """Extract text from an RGB numpy array image. Returns concatenated text."""
        image = _downscale(image)
        if self._backend == "winrt":
            return self._extract_winrt(image)
        if self._backend == "easyocr" and self._easyocr_reader is not None:
            return self._extract_easyocr(image)
        return self._extract_pytesseract(image)

    # ------------------------------------------------------------------
    # Windows OCR (winrt) — fastest, hardware-accelerated
    # ------------------------------------------------------------------

    def _extract_winrt(self, image: np.ndarray) -> str:
        """Use Windows.Media.Ocr for fast hardware-accelerated OCR.

        Runs the Windows Runtime OCR engine which leverages DirectX and works
        on AMD/Intel integrated graphics without any extra drivers.
        """
        try:
            text = asyncio.run(self._winrt_ocr_async(image))
            logger.info("Windows OCR extracted %d chars", len(text))
            return text
        except Exception as e:
            logger.error("Windows OCR failed (%s) — falling back to pytesseract", e)
            return self._extract_pytesseract(image)

    async def _winrt_ocr_async(self, image: np.ndarray) -> str:
        from winsdk.windows.globalization import Language
        from winsdk.windows.graphics.imaging import BitmapDecoder
        from winsdk.windows.media.ocr import OcrEngine
        from winsdk.windows.storage.streams import (
            DataWriter,
            InMemoryRandomAccessStream,
        )

        # Encode image as PNG in memory — BitmapDecoder understands PNG
        from PIL import Image as PilImage

        pil = PilImage.fromarray(image)
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        # Write PNG bytes into a Windows IRandomAccessStream
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(png_bytes)
        await writer.store_async()
        writer.detach_stream()
        stream.seek(0)

        # Decode PNG → SoftwareBitmap
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()

        # Run OCR for each configured language and collect results
        lines: list[str] = []
        seen: set[str] = set()

        for lang_code in self._languages:
            lang = Language(lang_code)
            if OcrEngine.is_language_supported(lang):
                engine = OcrEngine.try_create_from_language(lang)
            else:
                engine = OcrEngine.try_create_from_user_profile_languages()

            if engine is None:
                continue

            result = await engine.recognize_async(bitmap)
            for line in result.lines:
                txt = line.text.strip()
                if txt and txt not in seen:
                    seen.add(txt)
                    lines.append(txt)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # EasyOCR
    # ------------------------------------------------------------------

    def _extract_easyocr(self, image: np.ndarray) -> str:
        results = self._easyocr_reader.readtext(image, detail=0, paragraph=True)
        text = "\n".join(results)
        logger.info("EasyOCR extracted %d chars", len(text))
        return text

    # ------------------------------------------------------------------
    # pytesseract
    # ------------------------------------------------------------------

    def _extract_pytesseract(self, image: np.ndarray) -> str:
        import pytesseract
        from PIL import Image

        pil_image = Image.fromarray(image)
        lang_str = "+".join(self._tesseract_lang(lang) for lang in self._languages)
        text = pytesseract.image_to_string(pil_image, lang=lang_str)
        logger.info("pytesseract extracted %d chars", len(text))
        return text.strip()

    @staticmethod
    def _tesseract_lang(iso_code: str) -> str:
        """Map ISO 639-1 codes to Tesseract language codes."""
        mapping = {
            "es": "spa",
            "en": "eng",
            "fr": "fra",
            "de": "deu",
            "pt": "por",
            "it": "ita",
        }
        return mapping.get(iso_code, iso_code)
