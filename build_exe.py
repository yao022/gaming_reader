"""Build standalone GameTextReader.exe using PyInstaller.

Usage:
    pip install pyinstaller
    python build_exe.py

Output: dist/GameTextReader/ containing the .exe and all dependencies.
Copy the entire folder to your gaming PC, add config.yaml and .env next to the .exe.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD_DIR = DIST / "GameTextReader"


def main() -> None:
    print("=== Building GameTextReader.exe ===\n")

    # Ensure PyInstaller is installed
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # PyInstaller command
    # NOTE: We exclude easyocr/torch/scipy/opencv/pandas since the .exe uses
    # Windows OCR (winrt) which is built into Windows — no need for heavy ML libs.
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "GameTextReader",
        "--noconfirm",
        "--console",  # Keep console window for status messages
        # Hidden imports that PyInstaller can't detect automatically
        "--hidden-import", "winsdk.windows.media.ocr",
        "--hidden-import", "winsdk.windows.graphics.imaging",
        "--hidden-import", "winsdk.windows.storage.streams",
        "--hidden-import", "winsdk.windows.globalization",
        "--hidden-import", "pyttsx3.drivers",
        "--hidden-import", "pyttsx3.drivers.sapi5",
        "--hidden-import", "comtypes",
        "--hidden-import", "comtypes.client",
        "--hidden-import", "comtypes.stream",
        "--hidden-import", "langdetect",
        "--hidden-import", "yaml",
        "--hidden-import", "dotenv",
        "--hidden-import", "edge_tts",
        "--hidden-import", "aiohttp",
        "--hidden-import", "certifi",
        "--hidden-import", "anthropic",
        "--hidden-import", "httpx",
        "--hidden-import", "dxcam",
        "--hidden-import", "PIL",
        "--hidden-import", "numpy",
        # Collect all submodules for packages that have many
        "--collect-all", "winsdk",
        "--collect-all", "edge_tts",
        "--collect-all", "langdetect",
        "--collect-all", "dxcam",
        "--collect-all", "anthropic",
        "--collect-all", "pyttsx3",
        # Exclude heavy ML libraries not needed for winrt OCR backend
        "--exclude-module", "torch",
        "--exclude-module", "torchvision",
        "--exclude-module", "easyocr",
        "--exclude-module", "scipy",
        "--exclude-module", "pandas",
        "--exclude-module", "cv2",
        "--exclude-module", "opencv",
        "--exclude-module", "sklearn",
        "--exclude-module", "skimage",
        "--exclude-module", "matplotlib",
        "--exclude-module", "tensorboard",
        "--exclude-module", "tensorflow",
        "--exclude-module", "pyarrow",
        "--exclude-module", "sqlalchemy",
        "--exclude-module", "tkinter",
        "--exclude-module", "shapely",
        "--exclude-module", "pytesseract",
        # Entry point
        str(ROOT / "launcher.py"),
    ]

    print("Running PyInstaller...")
    print(f"  Command: {' '.join(cmd[:10])}...\n")
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode != 0:
        print("\n[ERROR] PyInstaller failed!")
        sys.exit(1)

    # Copy release config alongside the exe
    release_config = ROOT / "config.release.yaml"
    dest_config = BUILD_DIR / "config.yaml"
    if release_config.exists():
        shutil.copy2(release_config, dest_config)
        print(f"\nCopied config.yaml to {dest_config}")

    # Create env.example (no leading dot — visible in Windows Explorer)
    env_example = BUILD_DIR / "env.example"
    env_example.write_text(
        "# 1. Paste your Anthropic API key below\n"
        "# 2. Save this file as .env  (rename: remove the word 'example')\n"
        "ANTHROPIC_API_KEY=sk-ant-api03-YOUR-KEY-HERE\n",
        encoding="utf-8",
    )

    # Create a visible README
    readme = BUILD_DIR / "README.txt"
    readme.write_text(
        "Game Text Reader\n"
        "================\n\n"
        "SETUP (first time only):\n"
        "  1. Rename 'env.example' to '.env'\n"
        "     (In Windows Explorer: View → Show hidden items if you can't see it)\n"
        "  2. Open .env with Notepad and paste your Anthropic API key:\n"
        "        ANTHROPIC_API_KEY=sk-ant-api03-YOUR-KEY-HERE\n"
        "  3. (Optional) Edit config.yaml to change settings\n\n"
        "HOW TO RUN:\n"
        "  Double-click GameTextReader.exe\n"
        "  OR right-click → Run as administrator (if hotkeys don't work)\n\n"
        "HOTKEYS (while the app is running):\n"
        "  F7  — Stop reading immediately\n"
        "  F8  — Capture + AI filter + natural voice (~3s)\n"
        "  F9  — Capture + local filter + fast voice (~0.5s)\n"
        "  F10 — Capture + local filter + natural voice (~3s)\n"
        "  Ctrl+C in the console window — Quit\n\n"
        "NOTES:\n"
        "  - F8 requires internet + Anthropic API key (costs fractions of a cent per use)\n"
        "  - F9/F10 work offline, no API key needed\n"
        "  - If hotkeys don't work in fullscreen games, run as administrator\n",
        encoding="utf-8",
    )

    print(f"\n{'=' * 60}")
    print(f"BUILD COMPLETE!")
    print(f"{'=' * 60}")
    print(f"\nOutput folder: {BUILD_DIR}")
    print(f"\nTo use on your gaming PC:")
    print(f"  1. Copy the entire 'GameTextReader' folder to your gaming PC")
    print(f"  2. Rename env.example to .env and paste your API key")
    print(f"  3. Run GameTextReader.exe (as admin if hotkeys don't respond)")
    print(f"  4. Press F8/F9/F10 while gaming, F7 to stop!")


if __name__ == "__main__":
    main()
