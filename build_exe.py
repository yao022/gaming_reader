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

    # Create a template .env file
    env_template = BUILD_DIR / ".env.example"
    env_template.write_text(
        "# Paste your Anthropic API key here and rename this file to .env\n"
        "ANTHROPIC_API_KEY=sk-ant-api03-YOUR-KEY-HERE\n",
        encoding="utf-8",
    )

    print(f"\n{'=' * 60}")
    print(f"BUILD COMPLETE!")
    print(f"{'=' * 60}")
    print(f"\nOutput folder: {BUILD_DIR}")
    print(f"\nTo use on your gaming PC:")
    print(f"  1. Copy the entire 'GameTextReader' folder to your gaming PC")
    print(f"  2. Rename .env.example to .env and paste your API key")
    print(f"  3. (Optional) Edit config.yaml to change settings")
    print(f"  4. Run GameTextReader.exe")
    print(f"  5. Press F8 (AI mode) or F9 (local mode) while gaming!")


if __name__ == "__main__":
    main()
