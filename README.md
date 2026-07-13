# 🎙️ VoxClip

**Voice-to-Clipboard for Hyprland/Wayland** — Press a shortcut, speak, and your words are transcribed and copied to clipboard. Entirely local, no cloud services.

## Features

- 🎤 **One-shortcut recording** — `Super+Shift+V` to start/stop
- 🧠 **Local AI transcription** — Powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (OpenAI Whisper)
- 🌍 **Multilingual** — Optimized for English and Portuguese (auto-detection)
- 🖥️ **Native Wayland overlay** — Beautiful GTK3 overlay with waveform animation via `gtk-layer-shell`
- 📋 **Clipboard integration** — Text goes straight to `wl-copy`
- 📜 **History** — Browse and re-copy past transcriptions (`Super+Shift+H`)
- 🔒 **100% local** — Everything runs on your machine, no data leaves

## Requirements

### System packages (Arch Linux)

```bash
sudo pacman -S python python-pip python-gobject gtk3 gtk-layer-shell \
               wl-clipboard portaudio libnotify1, 2, 3, 4, 5, 6, 7, 8, 9, 10 para processar um áudio mais rápido, podemos fazer o que exatamente.
```

### Python packages

```bash
pip install --user faster-whisper sounddevice numpy
```

Or use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Installation

```bash
# Clone or copy the project
cd voxclip

# Install in development mode
pip install --user -e .
```

## Quick Start

### 1. Start the daemon

```bash
voxclip daemon
```

The first run will download the Whisper model (~1.5 GB for `medium`). Subsequent starts are instant.

### 2. Add keybindings to Hyprland

Add to `~/.config/hypr/hyprland.conf`:

```ini
# VoxClip
bind = $mainMod SHIFT, V, exec, voxclip toggle
bind = $mainMod SHIFT, H, exec, voxclip history

# Optional: blur effect on overlay
layerrule = blur, voxclip
layerrule = ignorealpha 0.3, voxclip
```

### 3. Use it!

1. Press `Super+Shift+V` → overlay appears, recording starts
2. Speak your text
3. Press `Super+Shift+V` again → transcription begins
4. Text is copied to clipboard → paste anywhere with `Ctrl+V`

### 4. (Optional) Run as a systemd service

```bash
cp contrib/voxclip.service ~/.config/systemd/user/
systemctl --user enable --now voxclip
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `voxclip daemon` | Start the daemon |
| `voxclip toggle` | Start/stop recording |
| `voxclip history` | Show transcription history |
| `voxclip status` | Check if daemon is running |
| `voxclip stop` | Stop the daemon |
| `voxclip config` | Show current configuration |
| `voxclip devices` | List audio input devices |

### Options

```bash
voxclip daemon --model large-v3-turbo  # Use a different model
voxclip daemon --language en            # Force English only
voxclip daemon --device cuda            # Use GPU (if available)
voxclip -v daemon                       # Verbose/debug logging
```

## Configuration

Config file: `~/.config/voxclip/config.json`

```json
{
  "model_size": "medium",
  "compute_type": "int8",
  "language": "auto",
  "device": "cpu",
  "sample_rate": 16000,
  "max_record_seconds": 120,
  "vad_filter": true,
  "vad_threshold": 0.5,
  "overlay_duration_done": 2.5,
  "overlay_position": "top",
  "overlay_margin_top": 40
}
```

### Model Selection Guide

| Model | RAM | Speed (CPU) | Accuracy | Recommended For |
|-------|-----|-------------|----------|-----------------|
| `tiny` | ~100MB | Fastest | Low | Testing only |
| `base` | ~200MB | Very fast | Fair | Quick & dirty |
| `small` | ~500MB | Fast | Good | Constrained hardware |
| **`medium`** | **~1.5GB** | **Moderate** | **Very good** | **Default — best for T480** |
| `large-v3-turbo` | ~2GB | Slower | Excellent | When accuracy matters most |
| `large-v3` | ~3GB | Slowest | Best | Only with GPU |

## How It Works

```
[Keyboard Shortcut] → [Unix Socket] → [Daemon]
                                         ↓
                                    [sounddevice: Record 16kHz mono]
                                         ↓
                                    [faster-whisper: Transcribe]
                                         ↓
                              [wl-copy + SQLite + Notification]
```

The daemon runs a GTK3 main loop with a `gtk-layer-shell` overlay for Wayland. Audio is captured via `sounddevice` (PortAudio) and transcribed using `faster-whisper` with CTranslate2 acceleration and int8 quantization for CPU efficiency.

## License

MIT
