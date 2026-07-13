"""VoxClip — Voice-to-Clipboard for Hyprland.

Usage:
    voxclip daemon           Start the daemon (runs GTK main loop)
    voxclip toggle           Toggle recording on/off
    voxclip history          Show transcription history
    voxclip status           Check daemon status
    voxclip stop             Stop the daemon
    voxclip config           Show current configuration
    voxclip devices          List audio input devices
"""

import argparse
import json
import logging
import sys

from . import __version__, __app_name__
from .config import Config
from .daemon import VoxClipDaemon, send_command


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet noisy loggers
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    logging.getLogger("ctranslate2").setLevel(logging.WARNING)


def cmd_daemon(args, config: Config):
    """Start the VoxClip daemon."""
    # Apply CLI overrides
    if args.model:
        config.model_size = args.model
    if args.language:
        config.language = args.language
    if args.device:
        config.device = args.device

    daemon = VoxClipDaemon(config)
    daemon.run()


def cmd_toggle(args, config: Config):
    """Send toggle command to daemon."""
    response = send_command("toggle")
    if response is None:
        print("Error: VoxClip daemon is not running.", file=sys.stderr)
        print("Start it with: voxclip daemon", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(response, indent=2))


def cmd_history(args, config: Config):
    """Send history command to daemon."""
    response = send_command("history")
    if response is None:
        print("Error: VoxClip daemon is not running.", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(response, indent=2))


def cmd_status(args, config: Config):
    """Check daemon status."""
    response = send_command("status")
    if response is None:
        if args.waybar:
            import json
            print(json.dumps({
                "text": "❌ Off",
                "tooltip": "VoxClip daemon is offline",
                "class": "offline"
            }))
            sys.exit(0)
        else:
            print("VoxClip daemon is not running.")
            sys.exit(1)

    state = response.get("state", "unknown")
    if args.waybar:
        import json
        icons = {
            "IDLE": "🎙️ Idle",
            "RECORDING": "🔴 REC",
            "TRANSCRIBING": "⏳ Transcribing",
        }
        classes = {
            "IDLE": "idle",
            "RECORDING": "recording",
            "TRANSCRIBING": "transcribing",
        }
        text = icons.get(state, "🎙️ Vox")
        cls = classes.get(state, "unknown")
        tooltip = f"VoxClip: {state}"
        print(json.dumps({
            "text": text,
            "tooltip": tooltip,
            "class": cls
        }))
    else:
        print(f"VoxClip daemon is running. State: {state}")


def cmd_stop(args, config: Config):
    """Stop the daemon."""
    response = send_command("stop")
    if response is None:
        print("VoxClip daemon is not running.")
        sys.exit(1)
    print("VoxClip daemon stopping...")


def cmd_config(args, config: Config):
    """Show current configuration."""
    from dataclasses import asdict
    print(json.dumps(asdict(config), indent=2))


def cmd_devices(args, config: Config):
    """List audio input devices."""
    from .audio import list_devices
    print(list_devices())


def cmd_serve(args, config: Config):
    """Start the remote Whisper server."""
    from .server import run_server
    # Overrides
    if args.model:
        config.model_size = args.model
    if args.device:
        config.device = args.device

    run_server(host=args.host, port=args.port)


def cmd_settings(args, config: Config):
    """Open settings window."""
    response = send_command("settings")
    if response is not None:
        print("Opened settings window in the running daemon.")
        return

    print("VoxClip daemon is not running. Opening standalone settings...")
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    from .settings import SettingsWindow

    win = SettingsWindow()
    win.show()
    win.window.connect("destroy", Gtk.main_quit)
    Gtk.main()


def main():
    parser = argparse.ArgumentParser(
        prog=__app_name__,
        description="VoxClip — Voice-to-Clipboard for Hyprland",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # daemon
    daemon_parser = subparsers.add_parser("daemon", help="Start the VoxClip daemon")
    daemon_parser.add_argument(
        "--model", type=str, default=None,
        help="Whisper model size (tiny, base, small, medium, large-v3, large-v3-turbo)",
    )
    daemon_parser.add_argument(
        "--language", type=str, default=None,
        help="Language code (en, pt, auto)",
    )
    daemon_parser.add_argument(
        "--device", type=str, default=None,
        help="Compute device (cpu, cuda)",
    )

    # toggle
    subparsers.add_parser("toggle", help="Toggle recording on/off")

    # history
    subparsers.add_parser("history", help="Show transcription history")

    # settings
    subparsers.add_parser("settings", help="Open configuration settings GUI")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start the remote Whisper HTTP server")
    serve_parser.add_argument(
        "--host", type=str, default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
    )
    serve_parser.add_argument(
        "--port", type=int, default=8745,
        help="Port to listen on (default: 8745)",
    )
    serve_parser.add_argument(
        "--model", type=str, default=None,
        help="Model size to load (default: from config)",
    )
    serve_parser.add_argument(
        "--device", type=str, default=None,
        help="Device to run inference on (cpu, cuda)",
    )

    # status
    status_parser = subparsers.add_parser("status", help="Check daemon status")
    status_parser.add_argument(
        "--waybar", action="store_true", help="Output JSON formatted for Waybar"
    )

    # stop
    subparsers.add_parser("stop", help="Stop the daemon")

    # config
    subparsers.add_parser("config", help="Show current configuration")

    # devices
    subparsers.add_parser("devices", help="List audio input devices")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    setup_logging(args.verbose)
    config = Config.load()

    commands = {
        "daemon": cmd_daemon,
        "toggle": cmd_toggle,
        "history": cmd_history,
        "settings": cmd_settings,
        "serve": cmd_serve,
        "status": cmd_status,
        "stop": cmd_stop,
        "config": cmd_config,
        "devices": cmd_devices,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args, config)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
