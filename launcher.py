"""Standalone launcher for PyInstaller .exe builds."""
import sys
import os

# When frozen, suppress verbose logging — only show warnings and errors
if getattr(sys, "frozen", False):
    os.environ.setdefault("PYINSTALLER_FROZEN", "1")


def _main():
    from game_text_reader.__main__ import main
    main()


if __name__ == "__main__":
    try:
        _main()
    except Exception as e:
        print("\n" + "=" * 60)
        print("ERROR — Game Text Reader crashed on startup:")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 60)
        print("Common fixes:")
        print("  1. Make sure .env file exists next to the .exe with:")
        print("     ANTHROPIC_API_KEY=sk-ant-...")
        print("  2. Run as Administrator (right-click → Run as administrator)")
        print("  3. Check that config.yaml is next to the .exe")
        print("=" * 60)
        input("\nPress Enter to close...")
        sys.exit(1)
