"""Tests for OCR engine."""

from __future__ import annotations

from game_text_reader.ocr import OCREngine


def test_tesseract_lang_mapping():
    assert OCREngine._tesseract_lang("es") == "spa"
    assert OCREngine._tesseract_lang("en") == "eng"
    assert OCREngine._tesseract_lang("fr") == "fra"
    assert OCREngine._tesseract_lang("xx") == "xx"  # unknown passes through
