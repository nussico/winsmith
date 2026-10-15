"""Start the GUI: `winsmith`, `python -m winsmith`, `python main.py` or the built Winsmith.exe."""
import faulthandler
import sys


def run():
    if sys.stderr:  # print a traceback on hard crashes (no-op in a windowed build without stderr)
        faulthandler.enable()
    try:
        import PySide6  # noqa: F401
    except ImportError:
        sys.exit("Winsmith needs PySide6. Install it with:  python -m pip install PySide6-Essentials")
    from .ui.app import main
    main()


if __name__ == "__main__":
    run()
