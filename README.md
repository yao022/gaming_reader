# Game Text Reader

Screen text reader for games. Press a hotkey during gameplay to capture the screen, extract text via OCR, optionally filter out HUD/menu noise with Claude AI, and hear the narrative text read aloud in Spanish (or English).

Built for accessibility — designed for players with central vision impairments who need game text read aloud, especially in fullscreen games where Windows Magnifier doesn't work.

## How it works

1. Press **F8** (configurable) while playing
2. A beep confirms the capture
3. The screen is captured (works in fullscreen games)
4. OCR extracts all visible text
5. AI filter (optional) removes HUD counters, button prompts, and menu labels — keeping only notes, letters, dialogues, item descriptions, and tutorials
6. TTS reads the filtered text aloud in Spanish

## Requirements

- Windows 10/11
- Python 3.11+
- Tesseract OCR (only if using pytesseract backend)
- Anthropic API key (only if AI filter is enabled)

## Installation

```bash
git clone https://github.com/yao022/gaming_reader.git
cd gaming_reader
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your Anthropic API key (optional):

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

## Usage

```bash
python -m game_text_reader
```

Then switch to your game and press **F8** whenever you see text you want read aloud. Press **Ctrl+C** in the terminal to quit.

## Configuration

Edit `config.yaml` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `language` | `es` | Language for OCR and TTS |
| `voice` | `es-ES-AlvaroNeural` | Edge TTS voice |
| `hotkey` | `f8` | Trigger key |
| `capture_backend` | `dxcam` | `dxcam` (faster) or `mss` (fallback) |
| `ocr_backend` | `easyocr` | `easyocr` (better with game fonts) or `pytesseract` |
| `tts_backend` | `edge-tts` | `edge-tts` (natural) or `pyttsx3` (offline) |
| `ai_filter_enabled` | `true` | Use Claude API to filter text |
| `sound_feedback` | `true` | Beep on capture |

## Sound feedback

- **Single high beep** — capture started
- **Two low beeps** — no text detected or no narrative text after filtering
- **Long low beep** — error occurred

## Tech stack

- **Screen capture**: dxcam (preferred) / mss (fallback)
- **OCR**: EasyOCR (preferred) / pytesseract (fallback)
- **AI filter**: Anthropic Claude API (Haiku)
- **TTS**: edge-tts (preferred) / pyttsx3 (offline fallback)
- **Hotkey**: keyboard library

## License

MIT
