"""Clipboard management via wl-copy (Wayland)."""

import subprocess
import shutil
import logging

log = logging.getLogger(__name__)


def copy_to_clipboard(text: str) -> bool:
    """Copy text to Wayland clipboard using wl-copy.
    
    Returns True on success, False on failure.
    """
    wl_copy = shutil.which("wl-copy")
    if not wl_copy:
        log.error("wl-copy not found. Install wl-clipboard: sudo pacman -S wl-clipboard")
        return False

    try:
        proc = subprocess.run(
            [wl_copy, "--", text],
            timeout=5,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            log.error("wl-copy failed: %s", proc.stderr)
            return False
        log.info("Text copied to clipboard (%d chars)", len(text))
        return True
    except subprocess.TimeoutExpired:
        log.error("wl-copy timed out")
        return False
    except OSError as e:
        log.error("Failed to run wl-copy: %s", e)
        return False


def notify(title: str, body: str, urgency: str = "normal", timeout_ms: int = 3000) -> None:
    """Send a desktop notification via notify-send."""
    notify_send = shutil.which("notify-send")
    if not notify_send:
        log.warning("notify-send not found, skipping notification")
        return

    try:
        subprocess.run(
            [
                notify_send,
                "--urgency", urgency,
                "--expire-time", str(timeout_ms),
                "--app-name", "VoxClip",
                title,
                body,
            ],
            timeout=5,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        log.warning("notify-send failed: %s", e)
