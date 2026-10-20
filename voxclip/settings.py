"""GTK3 Settings window for VoxClip."""

import json
import logging
import threading
import urllib.request
from typing import Callable, Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib  # noqa: E402

from .config import Config, WHISPER_MODELS, LANGUAGES, THEMES, hex_to_rgb
from .icons import get_icon_image

log = logging.getLogger(__name__)


class SettingsWindow:
    """GTK3 Settings window for VoxClip."""

    def __init__(
        self, 
        on_save_callback: Optional[Callable[[], None]] = None,
        on_history_callback: Optional[Callable[[], None]] = None,
    ):
        self.on_save_callback = on_save_callback
        self.on_history_callback = on_history_callback
        self.config = Config.load()
        self._build_ui()
        self._load_css()
        self._load_values()
        self._on_backend_changed()

    def _build_ui(self):
        # Create standard window (not layer shell)
        self.window = Gtk.Window(title="VoxClip Settings")
        self.window.set_default_size(440, 560)
        self.window.set_resizable(True)
        self.window.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.window.set_keep_above(True)
        self.window.connect("destroy", self._on_cancel)

        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_name("settings-main")
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)
        self.window.add(main_box)

        # Title
        title_label = Gtk.Label()
        title_label.set_markup("<span size='large' weight='bold'>VoxClip Settings</span>")
        title_label.set_halign(Gtk.Align.START)
        main_box.pack_start(title_label, False, False, 0)

        # Scrollable container for the form options
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.NONE)
        scroll.set_min_content_height(350)

        # Grid for options
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(16)
        grid.set_margin_bottom(12)
        scroll.add(grid)
        
        main_box.pack_start(scroll, True, True, 0)

        # 1. Backend Selection
        backend_label = Gtk.Label(label="Transcription Backend:")
        backend_label.set_halign(Gtk.Align.START)
        backend_label.set_valign(Gtk.Align.CENTER)
        grid.attach(backend_label, 0, 0, 1, 1)

        self.backend_combo = Gtk.ComboBoxText()
        self.backend_combo.append("local", "Local Whisper")
        self.backend_combo.append("remote", "Remote Server (Save Battery)")
        self.backend_combo.connect("changed", self._on_backend_changed)
        grid.attach(self.backend_combo, 1, 0, 1, 1)

        # 2. Local Whisper Section Box
        self.local_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        
        local_grid = Gtk.Grid()
        local_grid.set_column_spacing(12)
        local_grid.set_row_spacing(16)
        self.local_box.pack_start(local_grid, True, True, 0)

        # Model size Selection
        model_label = Gtk.Label(label="Whisper Model:")
        model_label.set_halign(Gtk.Align.START)
        model_label.set_valign(Gtk.Align.CENTER)
        local_grid.attach(model_label, 0, 0, 1, 1)

        self.model_combo = Gtk.ComboBoxText()
        for m in WHISPER_MODELS:
            self.model_combo.append(m["id"], f"{m['name']} ({m['ram']})")
        local_grid.attach(self.model_combo, 1, 0, 1, 1)

        # Device Selection
        device_label = Gtk.Label(label="Device / Hardware:")
        device_label.set_halign(Gtk.Align.START)
        device_label.set_valign(Gtk.Align.CENTER)
        local_grid.attach(device_label, 0, 1, 1, 1)

        self.device_combo = Gtk.ComboBoxText()
        self.device_combo.append("cpu", "CPU")
        self.device_combo.append("cuda", "CUDA (NVIDIA GPU)")
        local_grid.attach(self.device_combo, 1, 1, 1, 1)

        # CPU Threads Selection (Limits cores and temperature)
        threads_label = Gtk.Label(label="CPU Cores / Threads:")
        threads_label.set_halign(Gtk.Align.START)
        threads_label.set_valign(Gtk.Align.CENTER)
        local_grid.attach(threads_label, 0, 2, 1, 1)

        self.threads_combo = Gtk.ComboBoxText()
        self.threads_combo.append("1", "1 Core (Coolest/Silent)")
        self.threads_combo.append("2", "2 Cores (Saves Battery)")
        self.threads_combo.append("4", "4 Cores (Recommended)")
        self.threads_combo.append("8", "8 Cores (High Perf)")
        local_grid.attach(self.threads_combo, 1, 2, 1, 1)

        grid.attach(self.local_box, 0, 1, 2, 1)

        # 3. Remote Server Section Box
        self.remote_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        
        remote_grid = Gtk.Grid()
        remote_grid.set_column_spacing(12)
        remote_grid.set_row_spacing(16)
        self.remote_box.pack_start(remote_grid, True, True, 0)

        # Server URL Entry
        url_label = Gtk.Label(label="Server URL:")
        url_label.set_halign(Gtk.Align.START)
        url_label.set_valign(Gtk.Align.CENTER)
        remote_grid.attach(url_label, 0, 0, 1, 1)

        self.url_entry = Gtk.Entry()
        self.url_entry.set_placeholder_text("http://192.168.1.100:8745")
        remote_grid.attach(self.url_entry, 1, 0, 1, 1)

        # Connection status label & test button
        test_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.test_button = Gtk.Button(label="Test Connection")
        self.test_button.set_name("test-button")
        self.test_button.connect("clicked", self._on_test_connection)
        test_box.pack_start(self.test_button, False, False, 0)

        self.status_label = Gtk.Label(label="")
        self.status_label.set_halign(Gtk.Align.START)
        test_box.pack_start(self.status_label, True, True, 0)
        self.remote_box.pack_start(test_box, False, False, 0)

        grid.attach(self.remote_box, 0, 2, 2, 1)

        # 4. Common Settings Section
        self.common_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        common_grid = Gtk.Grid()
        common_grid.set_column_spacing(12)
        common_grid.set_row_spacing(16)
        self.common_box.pack_start(common_grid, True, True, 0)

        # Language Selection
        lang_label = Gtk.Label(label="Speech Language:")
        lang_label.set_halign(Gtk.Align.START)
        lang_label.set_valign(Gtk.Align.CENTER)
        common_grid.attach(lang_label, 0, 0, 1, 1)

        self.lang_combo = Gtk.ComboBoxText()
        for lang in LANGUAGES:
            self.lang_combo.append(lang["id"], lang["name"])
        common_grid.attach(self.lang_combo, 1, 0, 1, 1)

        # Max Recording Limit Selection
        limit_label = Gtk.Label(label="Max Recording Limit:")
        limit_label.set_halign(Gtk.Align.START)
        limit_label.set_valign(Gtk.Align.CENTER)
        common_grid.attach(limit_label, 0, 1, 1, 1)

        self.limit_combo = Gtk.ComboBoxText()
        self.limit_combo.append("30", "30 Seconds")
        self.limit_combo.append("60", "1 Minute")
        self.limit_combo.append("120", "2 Minutes (Default)")
        self.limit_combo.append("300", "5 Minutes")
        self.limit_combo.append("600", "10 Minutes")
        self.limit_combo.append("3600", "Unlimited (1 Hour)")
        common_grid.attach(self.limit_combo, 1, 1, 1, 1)

        # Theme Selection
        theme_label = Gtk.Label(label="Application Theme:")
        theme_label.set_halign(Gtk.Align.START)
        theme_label.set_valign(Gtk.Align.CENTER)
        common_grid.attach(theme_label, 0, 2, 1, 1)

        self.theme_combo = Gtk.ComboBoxText()
        for tid, tinfo in THEMES.items():
            self.theme_combo.append(tid, tinfo["name"])
        common_grid.attach(self.theme_combo, 1, 2, 1, 1)

        grid.attach(self.common_box, 0, 3, 2, 1)

        # Action Buttons Row (Stretched across full width)
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_box.pack_end(button_box, False, False, 0)

        # Left aligned: View History Button
        self.history_btn = Gtk.Button()
        self.history_btn.set_name("history-button")
        hist_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hist_theme = THEMES.get(self.config.theme, THEMES["dark"])
        hist_btn_icon = get_icon_image("history", size=14, color=hist_theme["text_primary"])
        hist_btn_label = Gtk.Label(label="View History")
        hist_btn_box.pack_start(hist_btn_icon, False, False, 0)
        hist_btn_box.pack_start(hist_btn_label, False, False, 0)
        self.history_btn.add(hist_btn_box)
        self.history_btn.connect("clicked", self._on_history_click)
        button_box.pack_start(self.history_btn, False, False, 0)

        # Spacer pushing Cancel and Save to the far right
        spacer = Gtk.Box()
        button_box.pack_start(spacer, True, True, 0)

        # Right aligned: Cancel, Apply, and Save Buttons
        self.cancel_btn = Gtk.Button(label="Cancel")
        self.cancel_btn.set_name("cancel-button")
        self.cancel_btn.connect("clicked", self._on_cancel)
        button_box.pack_start(self.cancel_btn, False, False, 0)

        self.apply_btn = Gtk.Button(label="Apply")
        self.apply_btn.set_name("apply-button")
        self.apply_btn.connect("clicked", self._on_apply)
        button_box.pack_start(self.apply_btn, False, False, 0)

        self.save_btn = Gtk.Button(label="Save")
        self.save_btn.set_name("save-button")
        self.save_btn.connect("clicked", self._on_save)
        button_box.pack_start(self.save_btn, False, False, 0)

    def _load_values(self):
        """Loads configuration values into widgets."""
        # Backend
        backend = "remote" if self.config.use_remote else "local"
        self.backend_combo.set_active_id(backend)

        # Local settings
        self.model_combo.set_active_id(self.config.model_size)
        self.device_combo.set_active_id(self.config.device)
        self.threads_combo.set_active_id(str(self.config.cpu_threads))

        # Remote settings
        self.url_entry.set_text(self.config.remote_url)

        # Common
        self.lang_combo.set_active_id(self.config.language)
        self.limit_combo.set_active_id(str(self.config.max_record_seconds))
        self.theme_combo.set_active_id(self.config.theme)

    def _on_backend_changed(self, widget=None):
        """Shows or hides backend-specific options."""
        backend = self.backend_combo.get_active_id()
        if backend == "local":
            self.local_box.show_all()
            self.remote_box.hide()
        else:
            self.local_box.hide()
            self.remote_box.show_all()

    def _on_test_connection(self, widget):
        """Tests the remote Whisper server connection asynchronously."""
        url = self.url_entry.get_text().strip()
        if not url:
            self.status_label.set_text("URL cannot be empty")
            return

        self.status_label.set_text("Testing...")
        self.test_button.set_sensitive(False)

        def _test_thread():
            try:
                # Add ping to /health
                ping_url = f"{url.rstrip('/')}/health"
                req = urllib.request.Request(ping_url, method="GET")
                with urllib.request.urlopen(req, timeout=5.0) as response:
                    if response.status == 200:
                        GLib.idle_add(self._update_status, "Connected successfully", True)
                    else:
                        GLib.idle_add(self._update_status, f"HTTP Error {response.status}", False)
            except Exception as e:
                log.warning("Connection test to %s failed: %s", url, e)
                GLib.idle_add(self._update_status, "Connection failed", False)

        threading.Thread(target=_test_thread, daemon=True).start()

    def _update_status(self, text: str, success: bool):
        self.status_label.set_text(text)
        self.test_button.set_sensitive(True)
        theme = THEMES.get(self.config.theme, THEMES["dark"])
        color_hex = theme["success"] if success else theme["error"]
        r, g, b = hex_to_rgb(color_hex)
        self.status_label.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(r, g, b, 1.0))

    def _save_settings(self) -> bool:
        """Reads settings from widgets and saves to config file."""
        try:
            backend = self.backend_combo.get_active_id()
            if backend:
                self.config.use_remote = (backend == "remote")

            # Save Local Settings
            model_size = self.model_combo.get_active_id()
            if model_size:
                self.config.model_size = model_size

            device = self.device_combo.get_active_id()
            if device:
                self.config.device = device

            threads = self.threads_combo.get_active_id()
            if threads:
                self.config.cpu_threads = int(threads)

            # Save Remote Settings
            self.config.remote_url = self.url_entry.get_text().strip()

            # Save Common Settings
            lang = self.lang_combo.get_active_id()
            if lang:
                self.config.language = lang

            limit = self.limit_combo.get_active_id()
            if limit:
                self.config.max_record_seconds = int(limit)

            theme = self.theme_combo.get_active_id()
            if theme:
                self.config.theme = theme

            self.config.save()
            log.info("Settings saved successfully")
            return True
        except Exception as e:
            log.error("Failed to save settings: %s", e)
            return False

    def _on_save(self, widget):
        """Saves current state to configuration and closes."""
        if self._save_settings():
            if self.on_save_callback:
                self.on_save_callback()
            self.window.destroy()

    def _on_apply(self, widget):
        """Saves current state and applies the theme instantly to settings and overlay."""
        if self._save_settings():
            if self.on_save_callback:
                self.on_save_callback()
            # Hot-reload dynamic CSS stylesheet on this window immediately!
            self._load_css()

    def _on_cancel(self, widget=None):
        self.window.destroy()

    def _on_history_click(self, widget):
        """Trigger view history event, falling back to IPC if standalone."""
        if self.on_history_callback:
            self.on_history_callback()
        else:
            from .daemon import send_command
            send_command("history")
            self.window.destroy()

    def show(self):
        self.window.show_all()
        self._on_backend_changed()

    def _load_css(self):
        """Loads dynamically compiled theme stylesheet for settings window."""
        theme_name = self.config.theme if self.config.theme in THEMES else "dark"
        theme = THEMES[theme_name]

        bg_color_hex = theme["bg_color_hex"]
        border_color_rgba = theme["border_color_rgba"]
        accent_color = theme["accent_color"]
        accent_rgb = theme["accent_rgb"]
        accent_2 = theme["accent_2"]
        bg_dark = theme["bg_dark"]
        bg_light = theme["bg_light"]
        bg_hover = theme["bg_hover"]
        text_primary = theme["text_primary"]
        text_secondary = theme["text_secondary"]

        css = f"""
        #settings-main {{
            background-color: {bg_color_hex};
        }}
        window {{
            background-color: {bg_color_hex};
            border: 1px solid {border_color_rgba};
            border-radius: 12px;
        }}
        #settings-main label, grid label, window label {{
            color: {text_primary};
            font-size: 13px;
            font-weight: 500;
        }}
        /* Clean native input and combobox styling */
        combobox, combobox *, combobox button, combobox cellview, combobox box, combobox text, entry {{
            background-color: {bg_light};
            background: {bg_light};
            border-color: {border_color_rgba};
            color: {text_primary};
            box-shadow: none;
            text-shadow: none;
        }}
        combobox, entry {{
            border: 1px solid {border_color_rgba};
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 13px;
            font-weight: 400;
            min-height: 32px;
        }}
        combobox:hover, entry:hover {{
            border-color: {accent_2};
        }}
        combobox:focus, entry:focus {{
            border-color: {accent_color};
            background-color: {bg_hover};
        }}
        combobox button:hover {{
            background-color: transparent;
        }}
        /* Dropdown Menu */
        menu, comboboxwindow, comboboxbox {{
            background-color: {bg_dark};
            border: 1px solid {border_color_rgba};
            color: {text_primary};
            border-radius: 8px;
            padding: 4px;
        }}
        menuitem, cellview {{
            background-color: transparent;
            color: {text_primary};
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: 500;
        }}
        menuitem:hover, menuitem:active {{
            background-color: rgba({accent_rgb}, 0.20);
            color: {text_primary};
        }}

        /* Unified Modern Desktop Button Base (32px height, 6px radius) */
        button {{
            background-image: none;
            box-shadow: none;
            text-shadow: none;
            outline: none;
            background-color: {bg_light};
            border: 1px solid {border_color_rgba};
            border-radius: 6px;
            color: {text_primary};
            font-weight: 500;
            padding: 4px 14px;
            min-height: 32px;
            font-size: 13px;
            transition: all 120ms ease;
        }}
        button:hover {{
            background-color: {bg_hover};
            border-color: {accent_2};
        }}
        button:active {{
            background-color: {bg_dark};
        }}

        /* Primary Action: Solid Accent (Save) */
        #save-button {{
            background-color: {accent_color};
            border: 1px solid {accent_color};
            color: #ffffff;
            font-weight: 600;
        }}
        #save-button:hover {{
            background-color: {accent_2};
            border-color: {accent_2};
            color: #ffffff;
        }}
        #save-button:active {{
            background-color: {accent_color};
            opacity: 0.9;
        }}

        /* Secondary Accent (Apply) */
        #apply-button {{
            background-color: rgba({accent_rgb}, 0.12);
            border: 1px solid rgba({accent_rgb}, 0.35);
            color: {text_primary};
        }}
        #apply-button:hover {{
            background-color: rgba({accent_rgb}, 0.22);
            border-color: {accent_color};
        }}

        /* Neutral Dismiss (Cancel) */
        #cancel-button {{
            background-color: transparent;
            border: 1px solid transparent;
            color: {text_secondary};
        }}
        #cancel-button:hover {{
            background-color: {bg_hover};
            border-color: {border_color_rgba};
            color: {text_primary};
        }}

        /* Standard Secondary (View History & Test Connection) */
        #history-button, #test-button {{
            background-color: {bg_light};
            border: 1px solid {border_color_rgba};
            color: {text_primary};
        }}
        #history-button:hover, #test-button:hover {{
            background-color: {bg_hover};
            border-color: {accent_2};
        }}
        """

        if hasattr(self, "_css_provider") and self._css_provider:
            Gtk.StyleContext.remove_provider_for_screen(Gdk.Screen.get_default(), self._css_provider)

        self._css_provider = Gtk.CssProvider()
        self._css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
