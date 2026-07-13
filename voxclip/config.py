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


# Famous developer & system theme palettes
THEMES = {
    "glass-violet": {
        "name": "Glass Violet (Default)",
        "bg_color_hex": "#0f0f19",
        "bg_color_rgba": "rgba(10, 10, 18, 0.86)",
        "border_color_rgba": "rgba(139, 92, 246, 0.5)",
        "accent_color": "#8b5cf6",      # Purple
        "accent_rgb": "139, 92, 246",
        "accent_2": "#3b82f6",          # Blue
        "accent_3": "#06b6d4",          # Cyan
        "bg_dark": "#131322",
        "bg_light": "#161625",
        "bg_hover": "#1c1c30",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "success": "#10b981",
        "error": "#f43f5e"
    },
    "dracula": {
        "name": "Dracula",
        "bg_color_hex": "#282a36",
        "bg_color_rgba": "rgba(40, 42, 54, 0.90)",
        "border_color_rgba": "rgba(189, 147, 249, 0.6)",
        "accent_color": "#bd93f9",      # Purple
        "accent_rgb": "189, 147, 249",
        "accent_2": "#ff79c6",          # Pink
        "accent_3": "#8be9fd",          # Cyan
        "bg_dark": "#1e1f29",
        "bg_light": "#21222c",
        "bg_hover": "#44475a",
        "text_primary": "#f8f8f2",
        "text_secondary": "#6272a4",
        "success": "#50fa7b",
        "error": "#ff5555"
    },
    "nord": {
        "name": "Nord",
        "bg_color_hex": "#2e3440",
        "bg_color_rgba": "rgba(46, 52, 64, 0.92)",
        "border_color_rgba": "rgba(136, 192, 208, 0.6)",
        "accent_color": "#88c0d0",      # Frost Cyan
        "accent_rgb": "136, 192, 208",
        "accent_2": "#81a1c1",          # Frost Blue
        "accent_3": "#8fbcbb",          # Frost Green
        "bg_dark": "#242933",
        "bg_light": "#3b4252",
        "bg_hover": "#434c5e",
        "text_primary": "#eceff4",
        "text_secondary": "#4c566a",
        "success": "#a3be8c",
        "error": "#bf616a"
    },
    "gruvbox": {
        "name": "Gruvbox",
        "bg_color_hex": "#282828",
        "bg_color_rgba": "rgba(40, 40, 40, 0.92)",
        "border_color_rgba": "rgba(254, 128, 25, 0.6)",
        "accent_color": "#fe8019",      # Orange
        "accent_rgb": "254, 128, 25",
        "accent_2": "#fabd2f",          # Yellow
        "accent_3": "#b8bb26",          # Green
        "bg_dark": "#1d2021",
        "bg_light": "#3c3836",
        "bg_hover": "#504945",
        "text_primary": "#ebdbb2",
        "text_secondary": "#a89984",
        "success": "#b8bb26",
        "error": "#fb4934"
    },
    "tokyo-night": {
        "name": "Tokyo Night",
        "bg_color_hex": "#1a1b26",
        "bg_color_rgba": "rgba(26, 27, 38, 0.90)",
        "border_color_rgba": "rgba(122, 162, 247, 0.6)",
        "accent_color": "#7aa2f7",      # Blue
        "accent_rgb": "122, 162, 247",
        "accent_2": "#bb9af3",          # Purple
        "accent_3": "#7dcfff",          # Cyan
        "bg_dark": "#16161e",
        "bg_light": "#24283b",
        "bg_hover": "#2f3549",
        "text_primary": "#c0caf5",
        "text_secondary": "#565f89",
        "success": "#9ece6a",
        "error": "#f7768e"
    },
    "one-dark": {
        "name": "One Dark",
        "bg_color_hex": "#21252b",
        "bg_color_rgba": "rgba(33, 37, 43, 0.92)",
        "border_color_rgba": "rgba(97, 175, 239, 0.6)",
        "accent_color": "#61afef",      # Blue
        "accent_rgb": "97, 175, 239",
        "accent_2": "#c678dd",          # Purple
        "accent_3": "#98c379",          # Green
        "bg_dark": "#1e2227",
        "bg_light": "#282c34",
        "bg_hover": "#353b45",
        "text_primary": "#abb2bf",
        "text_secondary": "#5c6370",
        "success": "#98c379",
        "error": "#e06c75"
    }
}


@dataclass
class Config:
    """VoxClip configuration."""

    # UI Theme Settings
    theme: str = "glass-violet"

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
        config.ensure_dirs()
        return config
