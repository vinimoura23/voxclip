"""GTK3 overlay UI with gtk-layer-shell for Hyprland/Wayland."""

import logging
import math
import time
from enum import Enum, auto
from typing import Callable, Optional

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

# GtkLayerShell is optional — falls back to a regular window without it
HAS_LAYER_SHELL = False
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell  # noqa: E402
    HAS_LAYER_SHELL = True
except (ValueError, ImportError):
    GtkLayerShell = None

from gi.repository import Gtk, Gdk, GLib, Pango  # noqa: E402

log = logging.getLogger(__name__)


def hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
    """Convert hex color to normalized RGB float tuple (0.0 to 1.0) for Cairo."""
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join([c*2 for c in hex_str])
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return r, g, b


class OverlayState(Enum):
    HIDDEN = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    DONE = auto()
    HISTORY = auto()


class OverlayWindow:
    """Wayland overlay window using GTK3 + gtk-layer-shell.
    
    Provides an ultra-sleek, compact, draggable and minimalist visual feedback pill.
    """

    def __init__(
        self,
        margin_top: int = 40,
        done_duration: float = 2.5,
        on_cancel: Optional[Callable] = None,
        on_history_select: Optional[Callable[[int], None]] = None,
        on_settings_saved: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        on_history: Optional[Callable[[], None]] = None,
        on_history_from_settings: Optional[Callable] = None,
        on_history_delete: Optional[Callable[[int], None]] = None,
        on_history_clear: Optional[Callable[[], None]] = None,
    ):
        self.margin_top = margin_top
        self.done_duration = done_duration
        self.on_cancel = on_cancel
        self.on_history_select = on_history_select
        self.on_settings_saved = on_settings_saved
        self.on_stop = on_stop
        self.on_history = on_history
        self.on_history_from_settings = on_history_from_settings
        self.on_history_delete = on_history_delete
        self.on_history_clear = on_history_clear

        self._state = OverlayState.HIDDEN
        self._amplitude: float = 0.0
        self._amplitude_history: list[float] = [0.0] * 60
        self._elapsed: float = 0.0
        self._result_text: str = ""
        self._animation_tick_id: Optional[int] = None
        self._done_timeout_id: Optional[int] = None
        self._pulse_phase: float = 0.0

        # Dragging state
        self._is_dragging = False
        self._drag_start_x = 0.0
        self._drag_start_y = 0.0
        self._start_margin_left = 0
        self._start_margin_top = 0
        self._start_pos_x = 0
        self._start_pos_y = 0

        # History → Settings back-navigation
        self._from_settings: bool = False
        self._settings_window_ref = None

        # Load and cache config — refreshed only on reload_theme() to avoid
        # reading the config file from disk on every animation frame.
        from .config import Config, THEMES
        self._config = Config.load()
        self._theme = THEMES.get(self._config.theme, THEMES["glass-violet"])

        screen = Gdk.Screen.get_default()
        screen_width = screen.get_width() if screen else 1920
        
        # Center horizontally if default -1
        if self._config.overlay_x == -1:
            self._current_x = (screen_width - 410) // 2
        else:
            self._current_x = self._config.overlay_x
        self._current_y = self._config.overlay_y

        self._build_ui()
        self._load_css()

    def _build_ui(self):
        """Construct the GTK widget tree."""
        # Main window
        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.window.set_default_size(410, 54)
        self.window.set_app_paintable(True)

        # Enable RGBA visuals for transparency
        screen = self.window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.window.set_visual(visual)

        # Layer shell setup (or fallback to regular window)
        if HAS_LAYER_SHELL:
            GtkLayerShell.init_for_window(self.window)
            GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.OVERLAY)
            # Anchor left and top for exact pixel margins (draggable)
            GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.TOP, True)
            GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.BOTTOM, False)
            GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.RIGHT, False)
            GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.LEFT, self._current_x)
            GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.TOP, self._current_y)
            GtkLayerShell.set_exclusive_zone(self.window, -1)
            GtkLayerShell.set_namespace(self.window, "voxclip")
            GtkLayerShell.set_keyboard_mode(self.window, GtkLayerShell.KeyboardMode.ON_DEMAND)
            log.info("Using draggable gtk-layer-shell for Wayland overlay at (%d, %d)", self._current_x, self._current_y)
        else:
            # Fallback: regular floating window (works on X11 or without layer-shell)
            self.window.set_keep_above(True)
            self.window.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
            self.window.move(self._current_x, self._current_y)
            log.warning("gtk-layer-shell not available — using fallback draggable window mode.")

        # Drag & Key events connected directly to the window
        self.window.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.BUTTON1_MOTION_MASK
        )
        self.window.connect("key-press-event", self._on_key_press)
        self.window.connect("button-press-event", self._on_button_press)
        self.window.connect("button-release-event", self._on_button_release)
        self.window.connect("motion-notify-event", self._on_motion_notify)

        # Main container
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main_box.set_name("main-container")
        self.window.add(self.main_box)

        # --- 1. RECORDING PILL LAYOUT ---
        # Format: [🔴 mic | waveform | [Super+Shift+V] | 0:00 | ⚙️]
        self.recording_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.recording_box.set_name("recording-box")
        self.recording_box.set_valign(Gtk.Align.CENTER)

        # Mic indicator (pulsing dot)
        self.mic_drawing = Gtk.DrawingArea()
        self.mic_drawing.set_size_request(16, 16)
        self.mic_drawing.set_valign(Gtk.Align.CENTER)
        self.mic_drawing.connect("draw", self._draw_mic_indicator)
        self.recording_box.pack_start(self.mic_drawing, False, False, 4)

        # Compact Waveform (Expanded width for high visual feedback)
        self.waveform_drawing = Gtk.DrawingArea()
        self.waveform_drawing.set_size_request(160, 26)
        self.waveform_drawing.set_valign(Gtk.Align.CENTER)
        self.waveform_drawing.connect("draw", self._draw_waveform)
        self.recording_box.pack_start(self.waveform_drawing, True, True, 4)

        # Whisper Model Size Label (e.g. base, medium)
        self.model_label = Gtk.Label(label="base")
        self.model_label.set_name("model-label")
        self.model_label.set_valign(Gtk.Align.CENTER)
        self.recording_box.pack_start(self.model_label, False, False, 4)

        # Monospace Shortcut Reminder Label
        self.shortcut_label = Gtk.Label(label="Super+Shift+V")
        self.shortcut_label.set_name("shortcut-label")
        self.shortcut_label.set_valign(Gtk.Align.CENTER)
        self.recording_box.pack_start(self.shortcut_label, False, False, 4)

        # Timer label
        self.timer_label = Gtk.Label(label="0:00")
        self.timer_label.set_name("timer-label")
        self.timer_label.set_valign(Gtk.Align.CENTER)
        self.recording_box.pack_start(self.timer_label, False, False, 4)

        # Remodeled beautiful rectangular stop button
        self.rec_stop_btn = Gtk.Button()
        self.rec_stop_btn.set_name("rec-stop-button")
        self.rec_stop_btn.set_size_request(20, 20)
        
        stop_image = Gtk.Image.new_from_icon_name("media-playback-stop-symbolic", Gtk.IconSize.MENU)
        self.rec_stop_btn.add(stop_image)
        
        self.rec_stop_btn.connect("clicked", self._on_stop_click)
        self.recording_box.pack_start(self.rec_stop_btn, False, False, 4)

        # Cancel button — stops recording and discards audio (no transcription)
        self.rec_cancel_btn = Gtk.Button()
        self.rec_cancel_btn.set_name("rec-cancel-button")
        self.rec_cancel_btn.set_size_request(20, 20)
        self.rec_cancel_btn.set_tooltip_text("Cancel recording (discard audio)")

        cancel_label = Gtk.Label(label="✕")
        cancel_label.set_name("cancel-icon-label")
        self.rec_cancel_btn.add(cancel_label)

        self.rec_cancel_btn.connect("clicked", self._on_cancel_btn_click)
        self.recording_box.pack_start(self.rec_cancel_btn, False, False, 0)

        # Custom themed Settings button
        rec_settings_btn = self._create_settings_button()
        self.recording_box.pack_start(rec_settings_btn, False, False, 4)

        self.main_box.pack_start(self.recording_box, True, True, 0)

        # --- 2. TRANSCRIBING PILL LAYOUT ---
        # Format: [⟳ spinner | Transcribing... | ⚙️]
        self.transcribing_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.transcribing_box.set_name("transcribing-box")
        self.transcribing_box.set_valign(Gtk.Align.CENTER)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(20, 20)
        self.spinner.set_valign(Gtk.Align.CENTER)
        self.transcribing_box.pack_start(self.spinner, False, False, 4)

        self.transcribing_label = Gtk.Label(label="Transcribing…")
        self.transcribing_label.set_name("transcribing-label")
        self.transcribing_label.set_valign(Gtk.Align.CENTER)
        self.transcribing_box.pack_start(self.transcribing_label, True, True, 4)

        trans_settings_btn = self._create_settings_button()
        self.transcribing_box.pack_start(trans_settings_btn, False, False, 4)

        self.main_box.pack_start(self.transcribing_box, True, True, 0)

        # --- 3. DONE PILL LAYOUT ---
        # Format: [✓ icon | "Copied" | text preview | ⚙️]
        self.done_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.done_box.set_name("done-box")
        self.done_box.set_valign(Gtk.Align.CENTER)

        self.done_icon = Gtk.Label(label="✓")
        self.done_icon.set_name("done-icon")
        self.done_icon.set_valign(Gtk.Align.CENTER)
        self.done_box.pack_start(self.done_icon, False, False, 4)

        self.done_status = Gtk.Label(label="Copied")
        self.done_status.set_name("done-status")
        self.done_status.set_valign(Gtk.Align.CENTER)
        self.done_box.pack_start(self.done_status, False, False, 4)

        self.done_text = Gtk.Label()
        self.done_text.set_name("done-text")
        self.done_text.set_ellipsize(Pango.EllipsizeMode.END)
        self.done_text.set_valign(Gtk.Align.CENTER)
        self.done_box.pack_start(self.done_text, True, True, 4)

        done_settings_btn = self._create_settings_button()
        self.done_box.pack_start(done_settings_btn, False, False, 4)

        self.main_box.pack_start(self.done_box, True, True, 0)

        # --- 4. HISTORY VIEW ---
        self.history_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.history_box.set_name("history-box")

        history_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        history_title = Gtk.Label(label="📋  History")
        history_title.set_name("history-title")
        history_title.set_halign(Gtk.Align.START)
        history_header.pack_start(history_title, True, True, 0)

        hist_settings_btn = self._create_settings_button()
        history_header.pack_end(hist_settings_btn, False, False, 0)

        self.history_clear_btn = Gtk.Button(label="🗑 Clear All")
        self.history_clear_btn.set_name("history-clear-btn")
        self.history_clear_btn.connect("clicked", self._on_history_clear_click)
        history_header.pack_end(self.history_clear_btn, False, False, 0)

        self.history_box.pack_start(history_header, False, False, 4)

        # Scrollable list
        self.history_scroll = Gtk.ScrolledWindow()
        self.history_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.history_scroll.set_min_content_height(200)
        self.history_scroll.set_max_content_height(400)

        self.history_list = Gtk.ListBox()
        self.history_list.set_name("history-list")
        self.history_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.history_scroll.add(self.history_list)
        self.history_box.pack_start(self.history_scroll, True, True, 0)

        history_hint = Gtk.Label(label="Esc to go back")
        history_hint.set_name("hint-label")
        history_hint.set_margin_top(4)
        self.history_box.pack_start(history_hint, False, False, 0)

        self.main_box.pack_start(self.history_box, True, True, 0)

    def _create_settings_button(self) -> Gtk.Button:
        """Create a gear ⚙ settings button."""
        btn = Gtk.Button()
        btn.set_name("rec-settings-button")
        btn.set_size_request(20, 20)

        gear = Gtk.Label(label="⚙")
        gear.set_name("settings-gear-icon")
        btn.add(gear)

        btn.connect("clicked", self._on_settings_click)
        return btn

    def _load_css(self):
        """Load CSS styling for the overlay dynamically based on the active theme."""
        from .config import Config, THEMES
        config = Config.load()
        theme_name = config.theme if config.theme in THEMES else "glass-violet"
        theme = THEMES[theme_name]

        bg_color_rgba = theme["bg_color_rgba"]
        border_color_rgba = theme["border_color_rgba"]
        accent_color = theme["accent_color"]
        accent_rgb = theme["accent_rgb"]
        accent_2 = theme["accent_2"]
        accent_3 = theme["accent_3"]
        text_primary = theme["text_primary"]
        text_secondary = theme["text_secondary"]
        success = theme["success"]
        error = theme["error"]

        css = f"""
        #main-container {{
            background-color: {bg_color_rgba};
            border: 1px solid {border_color_rgba};
            border-radius: 27px;
            padding: 4px 12px;
        }}

        #timer-label {{
            color: {text_secondary};
            font-size: 13px;
            font-weight: 600;
            font-family: "JetBrains Mono", "Fira Code", "SF Mono", monospace;
        }}

        #shortcut-label {{
            color: rgba(255, 255, 255, 0.45);
            font-size: 10px;
            font-family: "JetBrains Mono", "Fira Code", "SF Mono", monospace;
            background-color: rgba(255, 255, 255, 0.08);
            padding: 2px 6px;
            border-radius: 5px;
        }}

        #model-label {{
            color: rgba(255, 255, 255, 0.75);
            font-size: 10px;
            font-weight: bold;
            font-family: "JetBrains Mono", "Fira Code", "SF Mono", monospace;
            background-color: rgba({accent_rgb}, 0.22);
            border: 1px solid rgba({accent_rgb}, 0.45);
            padding: 2px 6px;
            border-radius: 5px;
        }}

        #lightning-label {{
            color: #f59e0b;
            font-size: 14px;
            font-weight: bold;
            text-shadow: 0 0 6px rgba(245, 158, 11, 0.7);
        }}

        #hint-label {{
            color: {text_secondary};
            font-size: 11px;
            font-style: italic;
            opacity: 0.7;
        }}

        #transcribing-label {{
            color: {text_primary};
            font-size: 13px;
            font-weight: 500;
        }}

        #done-icon {{
            color: {success};
            font-size: 16px;
            font-weight: bold;
        }}

        #done-status {{
            color: {success};
            font-size: 12px;
            font-weight: 600;
            background: rgba({accent_rgb}, 0.15);
            padding: 2px 6px;
            border-radius: 6px;
        }}

        #done-text {{
            color: {text_primary};
            font-size: 13px;
            font-weight: 400;
        }}

        #history-title {{
            color: {text_primary};
            font-size: 15px;
            font-weight: 700;
        }}

        #history-list {{
            background-color: transparent;
        }}

        #history-list row {{
            padding: 8px 12px;
            border-radius: 8px;
            margin: 2px 0;
            background-color: rgba(255, 255, 255, 0.03);
            transition: background-color 150ms ease;
        }}

        #history-list row:hover {{
            background-color: rgba({accent_rgb}, 0.15);
        }}

        #history-list row:selected {{
            background-color: rgba({accent_rgb}, 0.25);
        }}

        .history-text {{
            color: {text_primary};
            font-size: 12px;
        }}

        .history-meta {{
            color: {text_secondary};
            font-size: 10px;
        }}

        spinner {{
            color: {accent_color};
        }}

        /* Remodeled beautiful Stop Button */
        #rec-stop-button {{
            color: {error};
            background: rgba({accent_rgb}, 0.12);
            border: 1px solid rgba({accent_rgb}, 0.45);
            border-radius: 5px;
            padding: 0px;
            margin: 0;
            min-width: 20px;
            min-height: 20px;
            transition: all 200ms ease;
            box-shadow: none;
        }}

        #rec-stop-button:hover {{
            color: #ffffff;
            background: {error};
            border-color: {error};
            box-shadow: 0 0 8px {error};
        }}

        /* Cancel button — discard recording without transcribing */
        #rec-cancel-button {{
            color: {text_secondary};
            background: transparent;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 5px;
            padding: 0px;
            margin: 0;
            min-width: 20px;
            min-height: 20px;
            transition: all 200ms ease;
            box-shadow: none;
        }}

        #rec-cancel-button:hover {{
            color: #ffffff;
            background: {error};
            border-color: {error};
            box-shadow: 0 0 8px {error};
        }}

        #cancel-icon-label {{
            font-size: 11px;
            font-weight: bold;
        }}

        /* Remodeled beautiful Settings Button matching Stop button */
        #rec-settings-button {{
            color: {accent_color};
            background: rgba({accent_rgb}, 0.12);
            border: 1px solid rgba({accent_rgb}, 0.45);
            border-radius: 5px;
            padding: 0px;
            margin: 0;
            min-width: 20px;
            min-height: 20px;
            transition: all 200ms ease;
            box-shadow: none;
        }}

        #rec-settings-button:hover {{
            color: #ffffff;
            background: {accent_color};
            border-color: {accent_color};
            box-shadow: 0 0 8px {accent_color};
        }}

        #settings-gear-icon {{
            font-size: 14px;
        }}

        /* Row action buttons (copy / delete) */
        .row-action-btn {{
            min-width: 26px;
            min-height: 26px;
            padding: 2px 5px;
            font-size: 12px;
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 5px;
            color: {text_secondary};
            transition: all 150ms ease;
            box-shadow: none;
        }}

        .row-action-btn:hover {{
            border-color: rgba({accent_rgb}, 0.4);
            background-color: rgba({accent_rgb}, 0.15);
            color: {text_primary};
        }}

        #row-delete-btn:hover {{
            border-color: rgba(244, 63, 94, 0.4);
            background-color: rgba(244, 63, 94, 0.12);
            color: {error};
        }}

        /* Clear All button in history header */
        #history-clear-btn {{
            font-size: 11px;
            color: {error};
            background-color: transparent;
            background-image: none;
            border: 1px solid rgba(244, 63, 94, 0.35);
            border-radius: 5px;
            padding: 2px 8px;
            min-height: 20px;
            box-shadow: none;
            transition: all 150ms ease;
        }}

        #history-clear-btn:hover {{
            background-color: rgba(244, 63, 94, 0.15);
            border-color: {error};
        }}
        """

        if hasattr(self, "_css_provider") and self._css_provider:
            Gtk.StyleContext.remove_provider_for_screen(Gdk.Screen.get_default(), self._css_provider)

        self._css_provider = Gtk.CssProvider()
        self._css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def reload_theme(self):
        """Reload configuration and refresh stylesheet dynamically."""
        log.info("Reloading dynamic theme stylesheet for overlay...")
        from .config import Config, THEMES
        self._config = Config.load()
        self._theme = THEMES.get(self._config.theme, THEMES["glass-violet"])
        self._load_css()
        # Immediately queue redrawing for Cairo components to update gradients
        self.mic_drawing.queue_draw()
        self.waveform_drawing.queue_draw()

    # --- Size Constraint Enforcements ---
    def _enforce_size(self, width: int, height: int):
        """Forces the GTK Window and main container layout to be exactly width x height."""
        self.window.set_size_request(width, height)
        self.main_box.set_size_request(width, height)
        self.window.resize(width, height)

    # --- State management ---

    @property
    def state(self) -> OverlayState:
        return self._state

    def show_recording(self):
        """Show the recording overlay."""
        self._state = OverlayState.RECORDING
        self._amplitude = 0.0
        self._amplitude_history = [0.0] * 60
        self._elapsed = 0.0
        self._pulse_phase = 0.0

        # Load active config to get model size or remote status
        if self._config.use_remote:
            self.model_label.set_text("REMOTE")
        else:
            self.model_label.set_text(self._config.model_size.upper())

        self.recording_box.show_all()
        self.transcribing_box.hide()
        self.done_box.hide()
        self.history_box.hide()

        # Enforce premium compact window layout strictly
        self._enforce_size(410, 54)
        self.window.show_all()
        # window.show_all() reveals ALL children — re-hide the inactive boxes
        self.transcribing_box.hide()
        self.done_box.hide()
        self.history_box.hide()

        self._start_animation()

    def show_transcribing(self):
        """Show the transcribing state."""
        self._state = OverlayState.TRANSCRIBING
        self._stop_animation()

        self.recording_box.hide()
        self.transcribing_box.show_all()
        self.done_box.hide()
        self.history_box.hide()
        
        self._enforce_size(410, 54)
        self.spinner.start()

    def show_done(self, text: str, language: str = "", auto_hide: bool = True):
        """Show the transcription result."""
        self._state = OverlayState.DONE
        self._result_text = text
        self.spinner.stop()

        self.recording_box.hide()
        self.transcribing_box.hide()
        self.done_box.show_all()
        self.history_box.hide()

        display_text = text if len(text) <= 45 else text[:42] + "..."
        lang_tag = f"{language.upper()}" if language else "Copied"
        
        self.done_text.set_text(f'"{display_text}"')
        self.done_status.set_text(lang_tag)

        self._enforce_size(420, 54)

        if auto_hide:
            if self._done_timeout_id:
                GLib.source_remove(self._done_timeout_id)
            self._done_timeout_id = GLib.timeout_add(
                int(self.done_duration * 1000), self._on_done_timeout
            )

    def show_error(self, message: str):
        """Show an error state."""
        self._state = OverlayState.DONE
        self.spinner.stop()

        self.recording_box.hide()
        self.transcribing_box.hide()
        self.done_box.show_all()
        self.history_box.hide()

        self.done_icon.set_text("✗")
        self.done_icon.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.95, 0.25, 0.38, 1.0))
        self.done_status.set_text("Error")
        self.done_status.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.95, 0.25, 0.38, 1.0))
        self.done_text.set_text(message)

        self._enforce_size(420, 54)

        if self._done_timeout_id:
            GLib.source_remove(self._done_timeout_id)
        self._done_timeout_id = GLib.timeout_add(4000, self._on_done_timeout)

    def show_history(self, entries, from_settings: bool = False, settings_window_ref=None):
        """Show the history browser.
        
        Args:
            entries: List of history entries to display.
            from_settings: If True, pressing Esc will go back to the settings window
                           instead of closing the overlay.
            settings_window_ref: The SettingsWindow instance to reopen on Esc.
        """
        self._state = OverlayState.HISTORY
        self._from_settings = from_settings
        self._settings_window_ref = settings_window_ref

        self.recording_box.hide()
        self.transcribing_box.hide()
        self.done_box.hide()
        self.history_box.show_all()

        # Clear existing rows
        for child in self.history_list.get_children():
            self.history_list.remove(child)

        if not entries:
            empty_label = Gtk.Label(label="No transcriptions yet")
            empty_label.set_name("hint-label")
            empty_label.set_margin_top(20)
            empty_label.set_margin_bottom(20)
            row = Gtk.ListBoxRow()
            row.set_activatable(False)
            row.add(empty_label)
            self.history_list.add(row)
        else:
            for entry in entries:
                row = self._create_history_row(entry)
                self.history_list.add(row)

        self._enforce_size(520, min(120 + len(entries) * 55, 500))
        self.window.show_all()
        # window.show_all() reveals ALL children — re-hide the inactive boxes
        self.recording_box.hide()
        self.transcribing_box.hide()
        self.done_box.hide()

    def hide(self):
        """Hide the overlay."""
        self._state = OverlayState.HIDDEN
        self._stop_animation()
        if self._done_timeout_id:
            GLib.source_remove(self._done_timeout_id)
            self._done_timeout_id = None
        self.spinner.stop()
        
        # Reset done elements style
        self.done_icon.set_text("✓")
        self.done_icon.override_color(Gtk.StateFlags.NORMAL, None)
        self.done_status.override_color(Gtk.StateFlags.NORMAL, None)
        self.window.hide()

    def update_amplitude(self, amplitude: float):
        """Update the current audio amplitude (called from audio thread via GLib.idle_add)."""
        self._amplitude = min(amplitude * 12.0, 1.0)  # Amplify and clamp
        self._amplitude_history.append(self._amplitude)
        if len(self._amplitude_history) > 60:
            self._amplitude_history.pop(0)

    def update_elapsed(self, seconds: float):
        """Update the recording timer."""
        self._elapsed = seconds
        mins = int(seconds) // 60
        secs = int(seconds) % 60
        self.timer_label.set_text(f"{mins}:{secs:02d}")

    # --- Drawing ---

    def _draw_mic_indicator(self, widget, cr):
        """Draw the pulsing microphone indicator using dynamic theme colors."""
        theme = self._theme
        accent_color = theme["accent_color"]
        r_acc, g_acc, b_acc = hex_to_rgb(accent_color)

        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 2

        # Pulse effect
        pulse = 0.6 + 0.4 * math.sin(self._pulse_phase)
        outer_radius = radius + 3 * pulse

        # Outer glow using active theme accent color
        cr.set_source_rgba(r_acc, g_acc, b_acc, 0.25 * pulse)
        cr.arc(cx, cy, outer_radius, 0, 2 * math.pi)
        cr.fill()

        # Main circle
        cr.set_source_rgba(0.95, 0.25, 0.25, 0.8 + 0.2 * pulse)
        cr.arc(cx, cy, radius * 0.7, 0, 2 * math.pi)
        cr.fill()

        # Inner dot
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.9)
        cr.arc(cx, cy, radius * 0.25, 0, 2 * math.pi)
        cr.fill()

    def _draw_waveform(self, widget, cr):
        """Draw the audio waveform visualization with beautiful theme gradients."""
        theme = self._theme
        accent_1 = theme["accent_color"]
        accent_3 = theme["accent_3"]
        r1, g1, b1 = hex_to_rgb(accent_1)
        r3, g3, b3 = hex_to_rgb(accent_3)

        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        mid_y = h / 2
        num_bars = min(len(self._amplitude_history), 32)

        if num_bars == 0:
            return

        bar_width = max(2, (w - 4) / num_bars - 2)
        gap = 2
        total_width = num_bars * (bar_width + gap) - gap
        start_x = (w - total_width) / 2

        # Get the last N amplitude values
        amplitudes = self._amplitude_history[-num_bars:]

        for i, amp in enumerate(amplitudes):
            x = start_x + i * (bar_width + gap)
            bar_height = max(3, amp * (h - 4))

            # Dynamic gradient color from accent_1 to accent_3 based on position
            t = i / max(num_bars - 1, 1)
            r = r1 * (1 - t) + r3 * t
            g = g1 * (1 - t) + g3 * t
            b = b1 * (1 - t) + b3 * t
            alpha = 0.5 + 0.5 * amp

            cr.set_source_rgba(r, g, b, alpha)

            # Draw rounded bar
            radius = bar_width / 2
            bar_y = mid_y - bar_height / 2
            cr.move_to(x + radius, bar_y)
            cr.line_to(x + bar_width - radius, bar_y)
            cr.arc(x + bar_width - radius, bar_y + radius, radius, -math.pi / 2, 0)
            cr.line_to(x + bar_width, bar_y + bar_height - radius)
            cr.arc(x + bar_width - radius, bar_y + bar_height - radius, radius, 0, math.pi / 2)
            cr.line_to(x + radius, bar_y + bar_height)
            cr.arc(x + radius, bar_y + bar_height - radius, radius, math.pi / 2, math.pi)
            cr.line_to(x, bar_y + radius)
            cr.arc(x + radius, bar_y + radius, radius, math.pi, 3 * math.pi / 2)
            cr.close_path()
            cr.fill()

    # --- Animation ---

    def _start_animation(self):
        """Start the animation tick for recording state."""
        if self._animation_tick_id is None:
            self._animation_tick_id = GLib.timeout_add(33, self._on_animation_tick)  # ~30fps

    def _stop_animation(self):
        """Stop the animation tick."""
        if self._animation_tick_id is not None:
            GLib.source_remove(self._animation_tick_id)
            self._animation_tick_id = None

    def _on_animation_tick(self) -> bool:
        """Called ~30fps to update animations."""
        if self._state != OverlayState.RECORDING:
            self._animation_tick_id = None
            return False

        self._pulse_phase += 0.12
        self.mic_drawing.queue_draw()
        self.waveform_drawing.queue_draw()
        return True

    # --- History helpers ---

    def _create_history_row(self, entry) -> Gtk.ListBoxRow:
        """Create a history list row with copy and delete action buttons."""
        row = Gtk.ListBoxRow()
        row.entry_id = entry.id
        row.set_activatable(False)

        # Outer: content on the left, action buttons on the right
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        main_box.set_margin_start(4)
        main_box.set_margin_end(4)

        # Content: text + metadata
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        text_label = Gtk.Label(label=entry.preview)
        text_label.set_halign(Gtk.Align.START)
        text_label.set_ellipsize(Pango.EllipsizeMode.END)
        text_label.get_style_context().add_class("history-text")
        content_box.pack_start(text_label, False, False, 0)

        meta_parts = [entry.created_at]
        if entry.language:
            meta_parts.append(entry.language.upper())
        if entry.duration_seconds > 0:
            meta_parts.append(f"{entry.duration_seconds:.1f}s")

        meta_label = Gtk.Label(label=" · ".join(meta_parts))
        meta_label.set_halign(Gtk.Align.START)
        meta_label.get_style_context().add_class("history-meta")
        content_box.pack_start(meta_label, False, False, 0)

        main_box.pack_start(content_box, True, True, 0)

        # Action buttons (copy + delete)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_box.set_valign(Gtk.Align.CENTER)

        copy_btn = Gtk.Button(label="⧉")
        copy_btn.set_name("row-copy-btn")
        copy_btn.set_tooltip_text("Copy to clipboard")
        copy_btn.get_style_context().add_class("row-action-btn")
        eid = entry.id  # capture for lambda
        copy_btn.connect("clicked", lambda _b, i=eid: self._on_row_copy(i))
        btn_box.pack_start(copy_btn, False, False, 0)

        del_btn = Gtk.Button(label="🗑")
        del_btn.set_name("row-delete-btn")
        del_btn.set_tooltip_text("Delete entry")
        del_btn.get_style_context().add_class("row-action-btn")
        del_btn.connect("clicked", lambda _b, i=eid: self._on_row_delete(i))
        btn_box.pack_start(del_btn, False, False, 0)

        main_box.pack_end(btn_box, False, False, 0)

        row.add(main_box)
        return row

    def _on_row_copy(self, entry_id: int):
        """Copy a history entry to clipboard."""
        if self.on_history_select:
            self.on_history_select(entry_id)

    def _on_row_delete(self, entry_id: int):
        """Delete a history entry and refresh the list."""
        if self.on_history_delete:
            self.on_history_delete(entry_id)

    def _on_history_clear_click(self, widget):
        """Clear all history entries."""
        if self.on_history_clear:
            self.on_history_clear()

    def _on_history_row_activated(self, listbox, row):
        """Handle clicking a history entry (kept for compatibility)."""
        if hasattr(row, "entry_id") and self.on_history_select:
            self.on_history_select(row.entry_id)

    # --- Event handlers ---

    def _on_key_press(self, widget, event):
        """Handle key press events."""
        if event.keyval == Gdk.KEY_Escape:
            if self._state == OverlayState.RECORDING and self.on_cancel:
                self.on_cancel()
            elif self._state == OverlayState.HISTORY:
                if self._from_settings and self._settings_window_ref is not None:
                    # Go back to settings window instead of closing entirely
                    self.hide()
                    try:
                        self._settings_window_ref.show()
                    except Exception:
                        pass
                    self._from_settings = False
                    self._settings_window_ref = None
                else:
                    self.hide()
            elif self._state == OverlayState.DONE:
                self.hide()
            return True
        return False

    def _on_button_press(self, widget, event):
        """Start dragging window on left-click, grabbing the seat pointer to prevent cursor escape."""
        if event.button == 1:
            self._is_dragging = True
            # Grab the pointer via Gdk.Seat so the cursor stays confined to our window
            # during the drag — this is the correct Wayland/X11 approach in GTK3.
            try:
                seat = Gdk.Display.get_default().get_default_seat()
                pointer = seat.get_pointer()
                _, start_x, start_y = pointer.get_position()
                self._drag_start_x = start_x
                self._drag_start_y = start_y
                # Perform a seat grab to capture all pointer events during drag
                gdk_window = self.window.get_window()
                if gdk_window is not None:
                    seat.grab(
                        gdk_window,
                        Gdk.SeatCapabilities.POINTER,
                        False,   # owner_events: False keeps events local
                        None,    # cursor (None = keep current)
                        event,
                        None, None,
                    )
            except Exception:
                # Fallback to standard event coordinates if seat grab fails
                self._drag_start_x = event.x_root
                self._drag_start_y = event.y_root

            if HAS_LAYER_SHELL:
                self._start_margin_left = self._current_x
                self._start_margin_top = self._current_y
            else:
                self._start_pos_x, self._start_pos_y = self.window.get_position()
            return True
        return False

    def _on_button_release(self, widget, event):
        """Stop dragging, release the seat grab, and save new position to config."""
        if event.button == 1 and self._is_dragging:
            self._is_dragging = False
            # Release the seat pointer grab so normal cursor behaviour resumes
            try:
                seat = Gdk.Display.get_default().get_default_seat()
                seat.ungrab()
            except Exception:
                pass
            # Save coordinates to config
            from .config import Config
            config = Config.load()
            config.overlay_x = self._current_x
            config.overlay_y = self._current_y
            config.save()
            log.info("Saved dragging position: (%d, %d)", self._current_x, self._current_y)
            return True
        return False

    def _on_motion_notify(self, widget, event):
        """Move the window as it gets dragged using global seat pointer (buttery smooth)."""
        if self._is_dragging:
            try:
                seat = Gdk.Display.get_default().get_default_seat()
                pointer = seat.get_pointer()
                _, cur_x, cur_y = pointer.get_position()
                dx = cur_x - self._drag_start_x
                dy = cur_y - self._drag_start_y
            except Exception:
                dx = event.x_root - self._drag_start_x
                dy = event.y_root - self._drag_start_y

            if HAS_LAYER_SHELL:
                new_x = max(0, self._start_margin_left + int(dx))
                new_y = max(0, self._start_margin_top + int(dy))
                self._current_x = new_x
                self._current_y = new_y
                GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.LEFT, new_x)
                GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.TOP, new_y)
                # Avoid self.window.queue_resize() inside motion notify to prevent CPU spikes and drag lag
            else:
                new_x = max(0, self._start_pos_x + int(dx))
                new_y = max(0, self._start_pos_y + int(dy))
                self._current_x = new_x
                self._current_y = new_y
                self.window.move(new_x, new_y)
            return True
        return False

    def _on_stop_click(self, widget):
        """Handle Stop button clicked (finish and transcribe)."""
        if self.on_stop:
            self.on_stop()

    def _on_cancel_btn_click(self, widget):
        """Handle Cancel button clicked (discard audio, no transcription)."""
        if self.on_cancel:
            self.on_cancel()

    def _on_settings_click(self, widget):
        """Opens the Settings Window (singleton — reuses existing window).

        If recording is active when ⚙ is clicked, the recorder keeps running in
        the background (the pill is just hidden). Closing settings without saving
        (Cancel / X / Apply then close) restores the pill and the recording
        continues from where it left off. Clicking Save cancels the recording
        because the configuration (e.g. model) may have changed.
        """
        was_recording = (self._state == OverlayState.RECORDING)

        # If we're in history and came from a settings window, just go back to it
        # instead of opening a new one — this prevents duplicate windows.
        if self._settings_window_ref is not None:
            try:
                self.hide()
                self._settings_window_ref.show()
                self._from_settings = False
                self._settings_window_ref = None
                return
            except Exception:
                self._settings_window_ref = None

        # If a settings window is already open, just focus it
        if hasattr(self, "_settings_window") and self._settings_window is not None:
            try:
                if self._settings_window.window.get_visible():
                    self._settings_window.window.present()
                    return
            except Exception:
                self._settings_window = None

        if was_recording:
            # Keep the recorder running — just hide the pill so the normal GTK
            # settings window (below the overlay layer) is actually visible.
            self.window.hide()
        else:
            if self.on_cancel:
                self.on_cancel()

        from .settings import SettingsWindow

        # Mutable flag: True only when the user explicitly clicks Save
        # (not Cancel / X / Apply-then-close).
        _save_clicked = [False]

        def _on_save():
            _save_clicked[0] = True
            if was_recording and self.on_cancel:
                # Cancel the ongoing recording; config may have changed
                self.on_cancel()
            if self.on_settings_saved:
                self.on_settings_saved()

        def _on_history():
            # Hide (not destroy) so ESC from history can bring it back.
            settings_win = self._settings_window
            self._settings_window.window.hide()
            if self.on_history_from_settings:
                self.on_history_from_settings(settings_win)
            elif self.on_history:
                self.on_history()
            else:
                from .daemon import send_command
                send_command("history")

        self._settings_window = SettingsWindow(
            on_save_callback=_on_save,
            on_history_callback=_on_history,
        )

        def _on_settings_closed(_win):
            """Called when the settings window is destroyed for any reason."""
            if was_recording and not _save_clicked[0]:
                # User dismissed settings without saving — restore the recording pill.
                # The recorder has been running all along; just make it visible again.
                self.window.show()

        self._settings_window.window.connect("destroy", _on_settings_closed)
        self._settings_window.show()

    def _on_done_timeout(self) -> bool:
        """Auto-hide after showing result."""
        self._done_timeout_id = None
        self.hide()
        return False
