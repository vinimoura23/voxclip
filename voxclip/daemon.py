"""VoxClip daemon — manages recording, transcription, overlay, and IPC."""

import json
import logging
import os
import signal
import socket
import threading
from enum import Enum, auto
from typing import Optional

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib  # noqa: E402

from . import SOCKET_PATH
from .audio import AudioRecorder
from .clipboard import copy_to_clipboard, notify
from .config import Config
from .history import HistoryManager
from .overlay import OverlayWindow
from .transcriber import WhisperTranscriber

log = logging.getLogger(__name__)


class DaemonState(Enum):
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()


class VoxClipDaemon:
    """Main daemon that orchestrates all VoxClip components.
    
    Runs a GTK main loop and listens on a Unix socket for commands
    from the CLI (triggered by keyboard shortcuts).
    """

    def __init__(self, config: Config):
        self.config = config
        self._state = DaemonState.IDLE
        self._running = False

        # Components
        self.history = HistoryManager(config.db_path)
        self._init_transcriber()
        self.recorder: Optional[AudioRecorder] = None
        self.overlay: Optional[OverlayWindow] = None

        # Socket server
        self._socket: Optional[socket.socket] = None
        self._socket_thread: Optional[threading.Thread] = None

        # Timer for elapsed display
        self._elapsed_timer_id: Optional[int] = None

    def _init_transcriber(self):
        """Initialize or reload the transcriber based on config."""
        if hasattr(self, "transcriber") and self.transcriber:
            log.info("Unloading existing transcriber model...")
            self.transcriber.unload_model()

        if self.config.use_remote:
            from .remote_transcriber import RemoteTranscriber
            log.info("Using RemoteTranscriber at %s", self.config.remote_url)
            self.transcriber = RemoteTranscriber(
                remote_url=self.config.remote_url,
                model_size=self.config.model_size,
                device=self.config.device,
                compute_type=self.config.compute_type,
                language=self.config.language,
                vad_filter=self.config.vad_filter,
                vad_threshold=self.config.vad_threshold,
                cpu_threads=self.config.cpu_threads,
            )
        else:
            from .transcriber import WhisperTranscriber
            log.info("Using WhisperTranscriber (local) model size=%s (cpu_threads=%d)", 
                     self.config.model_size, self.config.cpu_threads)
            self.transcriber = WhisperTranscriber(
                model_size=self.config.model_size,
                device=self.config.device,
                compute_type=self.config.compute_type,
                language=self.config.language if self.config.language != "auto" else None,
                vad_filter=self.config.vad_filter,
                vad_threshold=self.config.vad_threshold,
                cache_dir=str(self.config.model_cache_dir),
                cpu_threads=self.config.cpu_threads,
            )

    def run(self):
        """Start the daemon (blocking — runs GTK main loop)."""
        log.info("VoxClip daemon starting...")
        self._running = True

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        # Create overlay (must be on GTK thread)
        self.overlay = OverlayWindow(
            margin_top=self.config.overlay_margin_top,
            done_duration=self.config.overlay_duration_done,
            on_cancel=self._cancel_recording,
            on_history_select=self._on_history_select,
            on_settings_saved=self._reload_config,
            on_stop=self._stop_recording,
            on_history=self._show_history,
            on_history_from_settings=self._show_history_from_settings,
        )

        # Initialize system tray status icon if supported
        self.tray_icon = None
        try:
            from gi.repository import Gtk
            self.tray_icon = Gtk.StatusIcon()
            self.tray_icon.set_from_icon_name("audio-input-microphone")
            self.tray_icon.set_tooltip_text("VoxClip — Idle")
            self.tray_icon.set_visible(True)
            self.tray_icon.connect("activate", lambda icon: GLib.idle_add(self._handle_toggle))
            log.info("Initialized system tray status icon successfully")
        except Exception as e:
            log.warning("Could not initialize Gtk.StatusIcon tray indicator: %s", e)

        # Start socket server in background thread
        self._start_socket_server()

        # Pre-load model in background thread if local backend is selected
        if not self.config.use_remote:
            log.info("Pre-loading Whisper model in background...")
            threading.Thread(target=self._preload_model, daemon=True).start()

        log.info("VoxClip daemon ready. Waiting for commands on %s", SOCKET_PATH)
        notify("VoxClip", "Daemon started. Use your shortcut to record.", timeout_ms=2000)

        # Run GTK main loop
        from gi.repository import Gtk
        Gtk.main()

    def stop(self):
        """Stop the daemon gracefully."""
        log.info("VoxClip daemon stopping...")
        self._running = False

        # Cancel any active recording
        if self._state == DaemonState.RECORDING and self.recorder:
            self.recorder.cancel()

        # Stop socket server
        self._stop_socket_server()

        # Unload model
        self.transcriber.unload_model()

        # Quit GTK
        from gi.repository import Gtk
        GLib.idle_add(Gtk.main_quit)

    # --- Command handling ---

    def handle_command(self, command: str) -> dict:
        """Handle a command from the socket client.
        
        Returns a response dict.
        """
        cmd = command.strip().lower()
        log.info("Received command: %s (state=%s)", cmd, self._state.name)

        if cmd == "toggle":
            return self._handle_toggle()
        elif cmd == "history":
            return self._handle_history()
        elif cmd == "settings":
            GLib.idle_add(self._show_settings)
            return {"status": "ok", "message": "Settings window shown"}
        elif cmd == "reload-config":
            GLib.idle_add(self._reload_config)
            return {"status": "ok", "message": "Config reload initiated"}
        elif cmd == "status":
            return {"status": "ok", "state": self._state.name}
        elif cmd == "stop":
            GLib.idle_add(self.stop)
            return {"status": "ok", "message": "Daemon stopping"}
        elif cmd == "hide":
            GLib.idle_add(self.overlay.hide)
            return {"status": "ok"}
        else:
            return {"status": "error", "message": f"Unknown command: {cmd}"}

    def _handle_toggle(self) -> dict:
        """Toggle recording on/off."""
        if self._state == DaemonState.IDLE:
            GLib.idle_add(self._start_recording)
            return {"status": "ok", "action": "recording_started"}
        elif self._state == DaemonState.RECORDING:
            GLib.idle_add(self._stop_recording)
            return {"status": "ok", "action": "recording_stopped"}
        elif self._state == DaemonState.TRANSCRIBING:
            return {"status": "busy", "message": "Transcription in progress"}
        return {"status": "error", "message": "Unknown state"}

    def _handle_history(self) -> dict:
        """Show history overlay."""
        if self._state != DaemonState.IDLE:
            return {"status": "busy", "message": "Cannot show history while recording"}
        GLib.idle_add(lambda: self._show_history(False, None))
        return {"status": "ok", "action": "history_shown"}

    # --- Recording flow ---

    def _start_recording(self):
        """Start recording audio (runs on GTK thread)."""
        if self._state != DaemonState.IDLE:
            return

        log.info("Starting recording...")
        self._state = DaemonState.RECORDING
        self._update_tray()

        # Create recorder with amplitude callback
        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            max_seconds=self.config.max_record_seconds,
            on_amplitude=self._on_amplitude,
        )

        try:
            self.recorder.start()
        except RuntimeError as e:
            log.error("Failed to start recording: %s", e)
            self._state = DaemonState.IDLE
            self._update_tray()
            self.overlay.show_error(str(e))
            return

        # Show overlay
        self.overlay.show_recording()

        # Start elapsed timer
        self._elapsed_timer_id = GLib.timeout_add(100, self._update_elapsed)

    def _stop_recording(self):
        """Stop recording and start transcription (runs on GTK thread)."""
        if self._state != DaemonState.RECORDING or not self.recorder:
            return

        log.info("Stopping recording...")

        # Stop elapsed timer
        if self._elapsed_timer_id:
            GLib.source_remove(self._elapsed_timer_id)
            self._elapsed_timer_id = None

        # Get audio data
        audio = self.recorder.stop()
        self.recorder = None

        if audio is None or len(audio) < self.config.sample_rate * 0.3:
            log.warning("Recording too short, ignoring")
            self._state = DaemonState.IDLE
            self._update_tray()
            self.overlay.show_error("Recording too short (min 0.3s)")
            return

        # Switch to transcribing state
        self._state = DaemonState.TRANSCRIBING
        self._update_tray()
        self.overlay.show_transcribing()

        # Transcribe in background thread
        threading.Thread(
            target=self._do_transcription,
            args=(audio,),
            daemon=True,
        ).start()

    def _cancel_recording(self):
        """Cancel the current recording (called from overlay Escape key)."""
        if self._state == DaemonState.RECORDING and self.recorder:
            log.info("Recording cancelled by user")
            if self._elapsed_timer_id:
                GLib.source_remove(self._elapsed_timer_id)
                self._elapsed_timer_id = None
            self.recorder.cancel()
            self.recorder = None
            self._state = DaemonState.IDLE
            self._update_tray()
            self.overlay.hide()

    def _do_transcription(self, audio):
        """Run transcription in background thread, then update UI on GTK thread."""
        try:
            result = self.transcriber.transcribe(audio, self.config.sample_rate)

            if result.is_empty:
                GLib.idle_add(self._on_transcription_empty)
                return

            # Copy to clipboard
            copy_to_clipboard(result.text)

            # Save to history
            self.history.add(
                text=result.text,
                language=result.language,
                confidence=result.language_probability,
                duration_seconds=result.duration_seconds,
            )

            # Update UI on GTK thread
            GLib.idle_add(
                self._on_transcription_done,
                result.text,
                result.language,
                result.transcription_time,
            )

        except Exception as e:
            log.error("Transcription failed: %s", e, exc_info=True)
            GLib.idle_add(self._on_transcription_error, str(e))

    def _on_transcription_done(self, text: str, language: str, time_taken: float):
        """Handle successful transcription (GTK thread)."""
        self._state = DaemonState.IDLE
        self._update_tray()
        self.overlay.show_done(text, language)
        notify(
            "VoxClip ✓",
            f"{text[:100]}{'...' if len(text) > 100 else ''}",
            timeout_ms=3000,
        )
        log.info("Transcription complete: %s (%.1fs)", text[:50], time_taken)

    def _on_transcription_empty(self):
        """Handle empty transcription (GTK thread)."""
        self._state = DaemonState.IDLE
        self._update_tray()
        self.overlay.show_error("No speech detected")

    def _on_transcription_error(self, error_msg: str):
        """Handle transcription error (GTK thread)."""
        self._state = DaemonState.IDLE
        self._update_tray()
        self.overlay.show_error(f"Transcription failed: {error_msg}")
        notify("VoxClip ✗", f"Error: {error_msg}", urgency="critical")

    # --- Callbacks ---

    def _on_amplitude(self, rms: float):
        """Called from audio thread with current RMS amplitude."""
        GLib.idle_add(self.overlay.update_amplitude, rms)

    def _update_elapsed(self) -> bool:
        """Update elapsed time display (GTK timer callback)."""
        if self._state != DaemonState.RECORDING or not self.recorder:
            return False
        self.overlay.update_elapsed(self.recorder.elapsed_seconds)
        return True

    def _show_history(self, from_settings: bool = False, settings_window_ref=None):
        """Show history overlay (GTK thread)."""
        entries = self.history.get_recent(30)
        self.overlay.show_history(
            entries,
            from_settings=from_settings,
            settings_window_ref=settings_window_ref,
        )

    def _show_history_from_settings(self, settings_window_ref=None):
        """Show history overlay with back-navigation to a settings window (GTK thread)."""
        entries = self.history.get_recent(30)
        self.overlay.show_history(
            entries,
            from_settings=True,
            settings_window_ref=settings_window_ref,
        )

    def _on_history_select(self, entry_id: int):
        """Handle selecting a history entry."""
        entry = self.history.get_by_id(entry_id)
        if entry:
            copy_to_clipboard(entry.text)
            self.overlay.show_done(entry.text, entry.language)
            notify("VoxClip", f"Copied from history: {entry.preview}", timeout_ms=2000)

    def _show_settings(self):
        """Show the settings window on GTK thread."""
        if self._state == DaemonState.RECORDING:
            self._cancel_recording()

        from .settings import SettingsWindow
        
        def _on_save():
            self._reload_config()

        def _on_history():
            # Close settings window and open history overlay, keeping a reference
            # so that pressing Esc in the history view can reopen settings.
            settings_win = self._settings_win
            self._settings_win.window.hide()
            self._show_history(from_settings=True, settings_window_ref=settings_win)

        self._settings_win = SettingsWindow(
            on_save_callback=_on_save,
            on_history_callback=_on_history
        )
        self._settings_win.show()

    def _reload_config(self):
        """Reload configuration from file and re-initialize transcriber."""
        log.info("Reloading config file...")
        self.config = Config.load()
        self._init_transcriber()

        if self.overlay:
            self.overlay.reload_theme()

        if not self.config.use_remote:
            log.info("Pre-loading Whisper model in background after reload...")
            threading.Thread(target=self._preload_model, daemon=True).start()
        else:
            notify("VoxClip", "Switched to remote transcription server!", timeout_ms=2000)

    def _update_tray(self):
        """Update system tray icon according to current state."""
        if not hasattr(self, "tray_icon") or not self.tray_icon:
            return
        try:
            if self._state == DaemonState.IDLE:
                self.tray_icon.set_from_icon_name("audio-input-microphone")
                self.tray_icon.set_tooltip_text("VoxClip — Idle")
            elif self._state == DaemonState.RECORDING:
                self.tray_icon.set_from_icon_name("media-record")
                self.tray_icon.set_tooltip_text("VoxClip — Recording...")
            elif self._state == DaemonState.TRANSCRIBING:
                self.tray_icon.set_from_icon_name("document-properties")
                self.tray_icon.set_tooltip_text("VoxClip — Transcribing...")
        except Exception as e:
            log.debug("Failed to update system tray icon: %s", e)

    # --- Model preloading ---

    def _preload_model(self):
        """Pre-load the Whisper model in a background thread."""
        try:
            self.transcriber.load_model()
            GLib.idle_add(
                lambda: notify("VoxClip", "Model loaded and ready!", timeout_ms=2000)
            )
        except Exception as e:
            log.error("Failed to pre-load model: %s", e, exc_info=True)
            GLib.idle_add(
                lambda: notify("VoxClip ✗", f"Model load failed: {e}", urgency="critical")
            )

    # --- Socket server ---

    def _start_socket_server(self):
        """Start the Unix socket server for IPC."""
        # Clean up stale socket
        if os.path.exists(SOCKET_PATH):
            try:
                os.unlink(SOCKET_PATH)
            except OSError:
                pass

        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.bind(SOCKET_PATH)
        self._socket.listen(5)
        self._socket.settimeout(1.0)

        self._socket_thread = threading.Thread(
            target=self._socket_loop, daemon=True, name="voxclip-socket"
        )
        self._socket_thread.start()
        log.info("Socket server listening on %s", SOCKET_PATH)

    def _stop_socket_server(self):
        """Stop the socket server."""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        if os.path.exists(SOCKET_PATH):
            try:
                os.unlink(SOCKET_PATH)
            except OSError:
                pass

    def _socket_loop(self):
        """Socket server loop (runs in background thread)."""
        while self._running:
            try:
                conn, _ = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                data = conn.recv(1024).decode("utf-8").strip()
                if data:
                    response = self.handle_command(data)
                    conn.sendall(json.dumps(response).encode("utf-8"))
            except Exception as e:
                log.warning("Socket handler error: %s", e)
                try:
                    conn.sendall(json.dumps({"status": "error", "message": str(e)}).encode())
                except OSError:
                    pass
            finally:
                conn.close()

    # --- Signal handling ---

    def _handle_signal(self, signum, frame):
        """Handle SIGTERM/SIGINT."""
        log.info("Received signal %d, shutting down...", signum)
        GLib.idle_add(self.stop)


def send_command(command: str) -> Optional[dict]:
    """Send a command to the running daemon via Unix socket.
    
    Returns the response dict, or None if the daemon is not running.
    """
    if not os.path.exists(SOCKET_PATH):
        return None

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect(SOCKET_PATH)
        sock.sendall(command.encode("utf-8"))
        response = sock.recv(4096).decode("utf-8")
        sock.close()
        return json.loads(response)
    except (socket.error, json.JSONDecodeError, OSError) as e:
        log.debug("Failed to send command '%s': %s", command, e)
        return None
