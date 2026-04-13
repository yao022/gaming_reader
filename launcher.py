"""Standalone launcher for PyInstaller .exe builds."""
import sys
import os

# When frozen, suppress verbose logging — only show warnings and errors
if getattr(sys, "frozen", False):
    os.environ.setdefault("PYINSTALLER_FROZEN", "1")

from game_text_reader.__main__ import main

if __name__ == "__main__":
    main()
