#!/usr/bin/env python3
"""Interactive visual preview for VoxClip UI (Themes, Buttons & Icons).

Run directly without affecting the background daemon:
    ~/.local/share/voxclip/.venv/bin/python preview.py [dark|light|glass-violet]
"""

import sys
import os

# Auto-reexec inside the VoxClip virtualenv if system python is missing dependencies like cairo
VENV_PYTHON = os.path.expanduser("~/.local/share/voxclip/.venv/bin/python")
if os.path.exists(VENV_PYTHON) and sys.executable != VENV_PYTHON:
    try:
        import cairo
    except ImportError:
        os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from voxclip.config import Config, THEMES
from voxclip.settings import SettingsWindow
from voxclip.overlay import OverlayWindow, OverlayState
from voxclip.history import HistoryEntry


def main():
    target_theme = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in THEMES else "dark"
    print(f"Opening VoxClip visual preview with theme: '{target_theme}' (Available: {list(THEMES.keys())})")

    # Create dummy config with selected theme
    config = Config.load()
    config.theme = target_theme

    # 1. Open Settings Window
    win = SettingsWindow()
    win.config = config
    win._load_css()
    win._load_values()
    win.window.set_title(f"VoxClip Preview — Settings [{THEMES[target_theme]['name']}]")
    win.window.connect("destroy", Gtk.main_quit)
    win.window.show_all()

    # 2. Open Overlay Window in DONE state to showcase pill & icons
    overlay = OverlayWindow()
    overlay._theme = THEMES[target_theme]
    overlay._load_css()
    overlay.show_done("This is a preview of the new VoxClip design!", "EN", auto_hide=False)

    print("Preview windows opened. Close the Settings window to exit.")
    Gtk.main()


if __name__ == "__main__":
    main()
