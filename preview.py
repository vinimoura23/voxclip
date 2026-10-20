#!/usr/bin/env python3
"""Interactive Visual Preview & Design Studio for VoxClip.

Allows exploring every screen and state of VoxClip (Recording, Transcribing,
Done, History, Settings) across all available themes (Dark, Light, Glass Violet)
live, without touching the background daemon.
"""

import os
import sys
import math

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
from voxclip.icons import get_icon_image, get_icon_pixbuf


SAMPLE_HISTORY = [
    HistoryEntry(
        id=1,
        text="A inteligência artificial transcreveu este áudio com precisão.",
        language="pt",
        confidence=0.98,
        duration_seconds=3.4,
        created_at="2026-10-20 09:05:12"
    ),
    HistoryEntry(
        id=2,
        text="Fast Whisper model running smoothly on CPU int8.",
        language="en",
        confidence=0.95,
        duration_seconds=2.8,
        created_at="2026-10-20 08:58:30"
    ),
    HistoryEntry(
        id=3,
        text="Atalho Super+Shift+V configurado com sucesso no Hyprland.",
        language="pt",
        confidence=0.99,
        duration_seconds=4.1,
        created_at="2026-10-20 08:30:00"
    ),
]


class PreviewController:
    """Interactive control hub to switch between all VoxClip screens and themes."""

    def __init__(self, initial_theme: str = "dark"):
        self.current_theme_id = initial_theme if initial_theme in THEMES else "dark"
        self.config = Config.load()
        self.config.theme = self.current_theme_id

        # 1. Initialize Overlay Window
        self.overlay = OverlayWindow()
        self._apply_theme_to_overlay()

        # Connect overlay callbacks for preview interactivity
        self.overlay.on_settings_click = self.show_settings_screen
        self.overlay.on_history_clear = self._on_history_clear
        self.overlay.on_history_delete = self._on_history_delete
        self.overlay.on_history_select = self._on_history_select

        # 2. Initialize Settings Window
        self.settings_win = None

        # 3. Simulated recording timer & waveform animation
        self._sim_elapsed = 0.0
        self._sim_timer_id = None

        # 4. Create floating Control Panel to easily click through screens
        self._build_control_panel()

        # Start by showing the Done pill
        self.show_done_screen()

    def _build_control_panel(self):
        """Builds a floating switcher toolbar to navigate all screens."""
        self.ctrl_win = Gtk.Window(title="VoxClip Preview Studio")
        self.ctrl_win.set_default_size(360, 280)
        self.ctrl_win.set_position(Gtk.WindowPosition.CENTER)
        self.ctrl_win.set_keep_above(True)
        self.ctrl_win.connect("destroy", Gtk.main_quit)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        self.ctrl_win.add(box)

        # Header
        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>VoxClip Preview Studio</span>")
        title.set_halign(Gtk.Align.START)
        box.pack_start(title, False, False, 0)

        subtitle = Gtk.Label(label="Clique para visualizar cada tela e estado da interface:")
        subtitle.set_halign(Gtk.Align.START)
        box.pack_start(subtitle, False, False, 0)

        # Theme Selector Row
        theme_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        theme_label = Gtk.Label(label="Tema:")
        theme_label.set_halign(Gtk.Align.START)
        theme_box.pack_start(theme_label, False, False, 0)

        self.theme_combo = Gtk.ComboBoxText()
        for tid, tinfo in THEMES.items():
            self.theme_combo.append(tid, tinfo["name"])
        self.theme_combo.set_active_id(self.current_theme_id)
        self.theme_combo.connect("changed", self._on_theme_combo_changed)
        theme_box.pack_start(self.theme_combo, True, True, 0)
        box.pack_start(theme_box, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(sep, False, False, 4)

        # Screen buttons grid
        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(8)
        box.pack_start(grid, True, True, 0)

        btn_rec = Gtk.Button(label="1. Gravando (Recording)")
        btn_rec.connect("clicked", lambda _: self.show_recording_screen())
        grid.attach(btn_rec, 0, 0, 1, 1)

        btn_trans = Gtk.Button(label="2. Transcrevendo (Spinner)")
        btn_trans.connect("clicked", lambda _: self.show_transcribing_screen())
        grid.attach(btn_trans, 1, 0, 1, 1)

        btn_done = Gtk.Button(label="3. Concluído (Done / Result)")
        btn_done.connect("clicked", lambda _: self.show_done_screen())
        grid.attach(btn_done, 0, 1, 1, 1)

        btn_hist = Gtk.Button(label="4. Histórico (History)")
        btn_hist.connect("clicked", lambda _: self.show_history_screen())
        grid.attach(btn_hist, 1, 1, 1, 1)

        btn_settings = Gtk.Button(label="5. Configurações (Settings)")
        btn_settings.connect("clicked", lambda _: self.show_settings_screen())
        grid.attach(btn_settings, 0, 2, 2, 1)

        self.ctrl_win.show_all()

    def _apply_theme_to_overlay(self):
        theme = THEMES[self.current_theme_id]
        self.overlay._theme = theme
        self.overlay._config.theme = self.current_theme_id
        self.overlay.reload_theme()

        # Refresh currently visible screen
        if self.overlay._state == OverlayState.DONE:
            self.show_done_screen()
        elif self.overlay._state == OverlayState.HISTORY:
            self.show_history_screen()

    def _on_theme_combo_changed(self, combo):
        tid = combo.get_active_id()
        if tid and tid in THEMES:
            self.current_theme_id = tid
            self.config.theme = tid
            self._apply_theme_to_overlay()
            if self.settings_win and self.settings_win.window.get_visible():
                self.settings_win.config.theme = tid
                self.settings_win.theme_combo.set_active_id(tid)
                self.settings_win._load_css()

    def _stop_sim_timer(self):
        if self._sim_timer_id:
            GLib.source_remove(self._sim_timer_id)
            self._sim_timer_id = None

    # --- Screen Switchers ---

    def show_recording_screen(self):
        """Simulates the active Recording pill with pulsing mic and live waveform."""
        self._stop_sim_timer()
        self.overlay.show_recording()
        self._sim_elapsed = 0.0

        def _sim_step():
            self._sim_elapsed += 0.05
            self.overlay.update_elapsed(self._sim_elapsed)
            # Simulate natural voice sound wave variations
            amp = 0.2 + 0.6 * abs(math.sin(self._sim_elapsed * 3.5) * math.cos(self._sim_elapsed * 1.8))
            self.overlay.update_amplitude(amp)
            return True

        self._sim_timer_id = GLib.timeout_add(50, _sim_step)

    def show_transcribing_screen(self):
        """Shows the Transcribing state with spinner and label."""
        self._stop_sim_timer()
        self.overlay.show_transcribing()

    def show_done_screen(self):
        """Shows the Done state with check icon, text preview, and copied tag."""
        self._stop_sim_timer()
        sample_text = "Esta é uma prévia da nova interface do VoxClip com botões modernos!"
        self.overlay.show_done(sample_text, "PT", auto_hide=False)

    def show_history_screen(self):
        """Shows the History browser with sample entries, copy and delete buttons."""
        self._stop_sim_timer()
        self.overlay.show_history(SAMPLE_HISTORY)

    def show_settings_screen(self):
        """Opens or presents the Settings window."""
        if not self.settings_win or not self.settings_win.window:
            self.settings_win = SettingsWindow(
                on_save_callback=self._on_settings_save,
                on_history_callback=self.show_history_screen,
            )
            self.settings_win.config.theme = self.current_theme_id
            self.settings_win.theme_combo.set_active_id(self.current_theme_id)
            self.settings_win._load_css()

        self.settings_win.show()
        self.settings_win.window.present()

    def _on_settings_save(self):
        saved_theme = self.settings_win.config.theme
        if saved_theme in THEMES:
            self.current_theme_id = saved_theme
            self.theme_combo.set_active_id(saved_theme)
            self._apply_theme_to_overlay()

    def _on_history_clear(self):
        self.overlay.show_history([])

    def _on_history_delete(self, entry_id):
        global SAMPLE_HISTORY
        SAMPLE_HISTORY = [e for e in SAMPLE_HISTORY if e.id != entry_id]
        self.overlay.show_history(SAMPLE_HISTORY)

    def _on_history_select(self, entry_id):
        entry = next((e for e in SAMPLE_HISTORY if e.id == entry_id), None)
        if entry:
            self.overlay.show_done(entry.text, entry.language, auto_hide=False)


def main():
    initial_theme = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in THEMES else "dark"
    app = PreviewController(initial_theme=initial_theme)
    Gtk.main()


if __name__ == "__main__":
    main()
