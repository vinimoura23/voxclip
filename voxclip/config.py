"""Configuration management for VoxClip."""

import os
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


def _config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "voxclip"


def _data_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "voxclip"


def _cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "voxclip"


# Available Whisper models with metadata
WHISPER_MODELS = [
    {"id": "tiny",            "name": "Tiny",            "ram": "~100MB", "speed": "Fastest",  "accuracy": "Low"},
    {"id": "base",            "name": "Base",            "ram": "~200MB", "speed": "Very fast","accuracy": "Fair"},
    {"id": "small",           "name": "Small",           "ram": "~500MB", "speed": "Fast",     "accuracy": "Good"},
    {"id": "medium",          "name": "Medium",          "ram": "~1.5GB", "speed": "Moderate", "accuracy": "Very good"},
    {"id": "large-v3-turbo",  "name": "Large V3 Turbo",  "ram": "~2GB",   "speed": "Slower",   "accuracy": "Excellent"},
    {"id": "large-v3",        "name": "Large V3",        "ram": "~3GB",   "speed": "Slowest",  "accuracy": "Best"},
]

LANGUAGES = [
    {"id": "auto", "name": "Auto-detect"},
    {"id": "en",   "name": "English"},
    {"id": "pt",   "name": "Português"},
    {"id": "es",   "name": "Español"},
    {"id": "fr",   "name": "Français"},
    {"id": "de",   "name": "Deutsch"},
    {"id": "ja",   "name": "日本語"},
    {"id": "zh",   "name": "中文"},
]


# Modern, harmonious desktop theme palettes (Dark, Light, and Glass Violet)
THEMES = {
    "dark": {
        "name": "Modern Dark",
        "bg_color_hex": "#12131a",
        "bg_color_rgba": "rgba(18, 19, 26, 0.94)",
        "border_color_rgba": "rgba(255, 255, 255, 0.10)",
        "accent_color": "#6366f1",      # Indigo
        "accent_rgb": "99, 102, 241",
        "accent_2": "#818cf8",          # Lighter Indigo
        "accent_3": "#38bdf8",          # Sky Blue
        "bg_dark": "#0c0d12",
        "bg_light": "#1a1b24",
        "bg_hover": "#252632",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "success": "#10b981",
        "error": "#f43f5e"
    },
    "light": {
        "name": "Modern Light",
        "bg_color_hex": "#f8fafc",
        "bg_color_rgba": "rgba(248, 250, 252, 0.96)",
        "border_color_rgba": "rgba(15, 23, 42, 0.12)",
        "accent_color": "#4f46e5",      # Deep Indigo
        "accent_rgb": "79, 70, 229",
        "accent_2": "#6366f1",          # Indigo
        "accent_3": "#0284c7",          # Sky Blue
        "bg_dark": "#e2e8f0",
        "bg_light": "#ffffff",
        "bg_hover": "#f1f5f9",
        "text_primary": "#0f172a",
        "text_secondary": "#64748b",
        "success": "#059669",
        "error": "#e11d48"
    },
    "glass-violet": {
        "name": "Glass Violet",
        "bg_color_hex": "#0f0f19",
        "bg_color_rgba": "rgba(15, 15, 25, 0.92)",
        "border_color_rgba": "rgba(139, 92, 246, 0.40)",
        "accent_color": "#8b5cf6",      # Purple
        "accent_rgb": "139, 92, 246",
        "accent_2": "#a78bfa",          # Light Purple
        "accent_3": "#06b6d4",          # Cyan
        "bg_dark": "#0a0a12",
        "bg_light": "#161625",
        "bg_hover": "#202035",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "success": "#10b981",
        "error": "#f43f5e"
    }
}


def hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
    """Convert hex color to normalized RGB float tuple (0.0 to 1.0)."""
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join([c * 2 for c in hex_str])
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return r, g, b


@dataclass
class Config:
    """VoxClip configuration."""

    # UI Theme Settings
    theme: str = "dark"

    # Whisper model settings
    model_size: str = "medium"
    compute_type: str = "int8"
    language: str = "auto"  # "auto", "en", "pt"
    device: str = "cpu"  # "cpu" or "cuda"
    cpu_threads: int = 4  # Number of CPU threads (limits temperature/cores)

    # Remote server settings
    use_remote: bool = False
    remote_url: str = "http://localhost:8745"

    # Audio settings
    sample_rate: int = 16000
    channels: int = 1
    max_record_seconds: int = 120  # Max recording duration

    # VAD settings
    vad_filter: bool = True
    vad_threshold: float = 0.5

    # UI settings
    overlay_duration_done: float = 2.5  # Seconds to show result
    overlay_position: str = "top"  # "top", "center", "bottom"
    overlay_margin_top: int = 40
    overlay_x: int = -1  # -1 = center horizontally
    overlay_y: int = 40  # Pixels from top

    # Paths
    config_dir: str = field(default_factory=lambda: str(_config_dir()))
    data_dir: str = field(default_factory=lambda: str(_data_dir()))
    cache_dir: str = field(default_factory=lambda: str(_cache_dir()))

    @property
    def db_path(self) -> Path:
        return Path(self.data_dir) / "history.db"

    @property
    def config_file(self) -> Path:
        return Path(self.config_dir) / "config.json"

    @property
    def model_cache_dir(self) -> Path:
        return Path(self.cache_dir) / "models"

    def ensure_dirs(self):
        """Create all necessary directories."""
        for d in [self.config_dir, self.data_dir, self.cache_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)

    def save(self):
        """Save config to file."""
        self.ensure_dirs()
        data = asdict(self)
        # Exclude runtime-derived path fields — they are always computed from
        # XDG env vars and should not be persisted (avoids stale paths after
        # home migration or XDG reconfiguration).
        for key in ("config_dir", "data_dir", "cache_dir"):
            data.pop(key, None)
        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls) -> "Config":
        """Load config from file, or create default."""
        config = cls()
        if config.config_file.exists():
            try:
                with open(config.config_file) as f:
                    data = json.load(f)
                # Only update known fields
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
            except (json.JSONDecodeError, OSError):
                pass
        if config.theme not in THEMES:
            config.theme = "dark"
        config.ensure_dirs()
        return config
