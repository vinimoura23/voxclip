"""Clipboard management with multi-platform fallbacks (Wayland, X11, generic)."""

import subprocess
import shutil
import logging

log = logging.getLogger(__name__)


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using wl-copy (Wayland), xclip/xsel (X11), or Python fallback.
    
    Returns True on success, False on failure.
    """
    # 1. Native Wayland via wl-copy
    wl_copy = shutil.which("wl-copy")
    if wl_copy:
        try:
            proc = subprocess.run(
                [wl_copy, "--", text],
                timeout=5,
                capture_output=True,
                text=True,
            )
            if proc.returncode == 0:
                log.info("Text copied to clipboard via wl-copy (%d chars)", len(text))
                return True
            log.warning("wl-copy returned exit code %d: %s", proc.returncode, proc.stderr)
        except Exception as e:
            log.warning("wl-copy execution failed: %s", e)

    # 2. X11 via xclip
    xclip = shutil.which("xclip")
    if xclip:
        try:
            proc = subprocess.run(
                [xclip, "-selection", "clipboard"],
                input=text,
                timeout=5,
                capture_output=True,
                text=True,
            )
            if proc.returncode == 0:
                log.info("Text copied to clipboard via xclip (%d chars)", len(text))
                return True
        except Exception as e:
            log.warning("xclip execution failed: %s", e)

    # 3. X11 via xsel
    xsel = shutil.which("xsel")
    if xsel:
        try:
            proc = subprocess.run(
                [xsel, "--clipboard", "--input"],
                input=text,
                timeout=5,
                capture_output=True,
                text=True,
            )
            if proc.returncode == 0:
                log.info("Text copied to clipboard via xsel (%d chars)", len(text))
                return True
        except Exception as e:
            log.warning("xsel execution failed: %s", e)

    # 4. Cross-platform / Pyperclip fallback
    try:
        import pyperclip
        pyperclip.copy(text)
        log.info("Text copied to clipboard via pyperclip (%d chars)", len(text))
        return True
    except Exception:
        pass

    log.error("Could not copy to clipboard: no clipboard utility found. Install wl-clipboard or xclip.")
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
