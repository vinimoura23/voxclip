"""VoxClip — Voice-to-Clipboard for Hyprland/Wayland."""

import os

__version__ = "0.1.0"
__app_name__ = "voxclip"

# Use XDG_RUNTIME_DIR (mode 0700, user-private) instead of /tmp
# so other processes on the system cannot connect to the IPC socket.
SOCKET_PATH = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
    "voxclip.sock",
)
