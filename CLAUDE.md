# Game Text Reader

Screen text reader for games. Captures screen on hotkey, OCRs text, optionally filters with Claude API, and reads aloud via TTS.

## Architecture

- `game_text_reader/config.py` — loads config.yaml + .env
- `game_text_reader/capture.py` — screen capture (dxcam preferred, mss fallback)
- `game_text_reader/ocr.py` — text extraction (easyocr preferred, pytesseract fallback)
- `game_text_reader/filter.py` — Claude API to keep only narrative text
- `game_text_reader/tts.py` — text-to-speech (edge-tts preferred, pyttsx3 fallback)
- `game_text_reader/hotkey.py` — hotkey listener orchestrating the pipeline
- `game_text_reader/__main__.py` — entry point

## Commands

- Run: `python -m game_text_reader`
- Tests: `pytest`
- Lint: `ruff check .`
- Format: `ruff format .`

## Key design decisions

- EasyOCR reader is initialized once at startup (slow to load ~2-5s)
- TTS playback is non-blocking (runs in a background thread)
- AI filter is optional (toggle `ai_filter_enabled` in config.yaml)
- Sound beep on capture so user knows keypress registered
- Windows only (dxcam, keyboard library require it)
- Default language: Spanish
