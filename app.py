"""Run the desktop application: python app.py"""

import importlib.util
import sys


def main() -> int:
    if sys.version_info < (3, 10):
        print("Python 3.10 or newer is required. Python 3.12 is recommended.")
        return 1
    if importlib.util.find_spec("pypdf") is None:
        print("Install the dependency first: python -m pip install -r requirements.txt")
        return 1
    try:
        import tkinter as tk
        from library_indexer.gui import main as run_gui
    except ImportError:
        print("Tkinter is unavailable. On Ubuntu/Debian: sudo apt install python3-tk")
        print("On Windows, reinstall Python with the Tcl/Tk option enabled.")
        print("You can also use: python cli.py scan sample_books")
        return 1
    try:
        run_gui()
    except tk.TclError as error:
        print(f"Could not start the desktop interface: {error}")
        print("Use a computer with a desktop, or run: python cli.py scan sample_books")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
