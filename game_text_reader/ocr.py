"""OCR text extraction using EasyOCR (preferred) or pytesseract (fallback).

Images are downscaled before OCR to reduce inference time — a 1080p image
passed to EasyOCR on CPU takes 5-8 seconds; at 1280px wide it takes ~2s.
"""

from __future__ import annotations

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
        if self._backend == "easyocr" and self._easyocr_reader is not None:
            return self._extract_easyocr(image)
        return self._extract_pytesseract(image)

    def _extract_easyocr(self, image: np.ndarray) -> str:
        results = self._easyocr_reader.readtext(image, detail=0, paragraph=True)
        text = "\n".join(results)
        logger.info("EasyOCR extracted %d chars", len(text))
        return text

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
            "es": "spa", "en": "eng", "fr": "fra",
            "de": "deu", "pt": "por", "it": "ita",
        }
        return mapping.get(iso_code, iso_code)
