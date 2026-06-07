"""Entry point. Resolves the bundled Zstd dictionary and launches the GUI."""
import os, sys


def _dict_path():
    base = getattr(sys, "_MEIPASS", None)          # set by PyInstaller at runtime
    if base:
        return os.path.join(base, "cerimal_zstd.dict")
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "assets", "cerimal_zstd.dict")


def _report_fatal():
    """Surface a startup/runtime error as a dialog + log file. Under --windowed there
    is no console, so an unhandled exception would otherwise vanish silently."""
    import traceback
    tb = traceback.format_exc()
    base = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))
    log_path = os.path.join(base, "wicked_respec_error.log")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(tb)
    except Exception:
        log_path = "(could not write log file)"
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Wicked Respec - error",
                             f"Something went wrong:\n\n{tb}\n\nSaved to: {log_path}")
        root.destroy()
    except Exception:
        pass


def _show_message(title, msg):
    """Show a message to the user (dialog if Tk is available; always prints too)."""
    print(msg)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror(title, msg)
        root.destroy()
    except Exception:
        pass


def main():
    try:
        dict_path = _dict_path()
        frozen = getattr(sys, "_MEIPASS", None) is not None
        if not frozen:
            # Running from source: the game's Zstd dictionary isn't committed, so fetch
            # it on demand. A packaged build bundles it instead, so this is skipped there.
            from src.dict_fetch import ensure_dict, manual_instructions
            if not ensure_dict(dict_path):
                _show_message("Wicked Respec - dictionary needed",
                              manual_instructions(dict_path))
                return
        with open(dict_path, "rb") as f:
            dict_bytes = f.read()
        from src.gui import run
        run(dict_bytes)
    except Exception:
        _report_fatal()
        raise


if __name__ == "__main__":
    main()
