# 🎙️ VoxClip

<div align="center">

**Speech-to-Text for Hyprland & Wayland**  
*Aperte um atalho, fale no microfone e cole o texto com Ctrl+V.*

[English](#english) • [Português](#português)

</div>

---

<a name="english"></a>
## 🇬🇧 English

**VoxClip** is a speech-to-text tool built for Hyprland and Wayland. The idea is dead simple: press a shortcut, speak into your microphone, and your words are instantly transcribed and copied to your clipboard — ready to paste anywhere with `Ctrl+V`.

Under the hood, it runs OpenAI's Whisper model locally on your machine (via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)), so your audio never leaves your computer. You can also offload transcription to another machine on your local network to save laptop battery.

### ✨ Key Features

- **⚡ Instant Toggle** — Trigger recording and transcription with a single keyboard shortcut (`Super+Shift+V`).
- **🧠 Local AI Transcription** — High-accuracy speech-to-text powered by `faster-whisper` (8-bit quantization on CPU or CUDA GPU).
- **🔋 Client / Server Mode** — Offload speech recognition to an external machine on your local network to save battery on laptops.
- **🖥️ Native Wayland Pill** — Compact floating HUD with real-time waveform visualization built using GTK3, Cairo, and `gtk-layer-shell`.
- **🎨 Built-in Themes** — Support for popular palettes: Glass Violet, Dracula, Nord, Gruvbox, Tokyo Night, and One Dark.
- **📜 Transcription History** — Visual history panel (`Super+Alt+H`) to search, re-copy, or delete past transcriptions.
- **⚙️ Visual Settings Panel** — GUI to switch models, languages, CPU core allocation, and themes on the fly.
- **📊 Waybar Integration** — Built-in JSON output mode (`voxclip status --waybar`) to show status and states in your status bar.
- **🔒 100% Private** — Runs entirely offline on your hardware by default.

---

### 🚀 Quick Installation (Arch, Debian/Ubuntu, Fedora, openSUSE)

The easiest way to install VoxClip is using the automated installer. It automatically detects your Linux distribution, installs required system packages, sets up the Python virtual environment, registers the systemd user service, and configures Hyprland or Sway keybindings:

```bash
git clone https://github.com/voxclip/voxclip.git
cd voxclip
chmod +x install.sh uninstall.sh
./install.sh
```

To uninstall cleanly at any time:
```bash
./uninstall.sh
# or: ./install.sh --uninstall
```

---

### 🛠️ Manual Installation

If you prefer installing manually:

#### 1. System Dependencies (Arch Linux)

```bash
sudo pacman -S --needed python python-pip python-gobject gtk3 gtk-layer-shell \
                       wl-clipboard portaudio libnotify
```

#### 2. Virtual Environment Setup

> [!IMPORTANT]
> The `--system-site-packages` flag is required so that the virtual environment can access system-level libraries such as `python-gobject` (`gi`) and `gtk-layer-shell`.

```bash
python -m venv --system-site-packages ~/.local/share/voxclip/.venv
source ~/.local/share/voxclip/.venv/bin/activate
pip install -e .
```

---

### ⌨️ Hyprland Configuration

Add the following configuration to `~/.config/hypr/hyprland.conf`:

```ini
# VoxClip Keybindings
bind = SUPER SHIFT, V, exec, voxclip toggle
bind = SUPER ALT, H, exec, voxclip history

# Layer and Window Rules
layerrule = blur on, match:namespace ^(voxclip)$
layerrule = ignore_alpha 0.3, match:namespace ^(voxclip)$
windowrule = float 1, match:title ^(VoxClip Settings)$
windowrule = center 1, match:title ^(VoxClip Settings)$
```

Reload Hyprland:
```bash
hyprctl reload
```

---

### 🖥️ CLI Commands

| Command | Description |
|---|---|
| `voxclip daemon` | Starts the background daemon (GTK main loop & IPC listener). |
| `voxclip toggle` | Toggles recording on/off (starts recording or triggers transcription). |
| `voxclip history` | Opens the transcription history overlay. |
| `voxclip settings` | Opens the graphical settings panel. |
| `voxclip serve` | Starts the standalone HTTP transcription server for remote devices. |
| `voxclip status` | Checks daemon status (`--waybar` outputs JSON for Waybar modules). |
| `voxclip devices` | Lists available audio input devices detected by PortAudio. |
| `voxclip config` | Dumps current configuration in JSON format. |
| `voxclip stop` | Gracefully shuts down the running daemon. |

---

### 🌐 Remote Server Mode (Save Laptop Battery)

You can run heavy Whisper models on a dedicated home server or desktop workstation and connect your laptop client to it:

1. **On your server/desktop:**
   ```bash
   voxclip serve --host 0.0.0.0 --port 8745 --model medium
   ```

2. **On your laptop:**
   Open the settings GUI with `voxclip settings`, select **Remote Server**, enter the server URL (e.g., `http://192.168.1.100:8745`), test the connection, and save.

---

### 🧠 Model Selection Guide

| Model | Memory (RAM/VRAM) | Speed (CPU) | Accuracy | Best Suited For |
|---|---|---|---|---|
| `tiny` | ~100 MB | Fastest | Basic | Quick tests & minimal devices |
| `base` | ~200 MB | Very fast | Good | Short commands and casual notes |
| `small` | ~500 MB | Fast | High | Balanced everyday transcription |
| **`medium`** | **~1.5 GB** | **Moderate** | **Very High** | **Default — great balance for modern multi-core CPUs** |
| `large-v3-turbo` | ~2 GB | Slower | Excellent | High precision multilingual speech |
| `large-v3` | ~3 GB | Slowest | Best in Class | Maximum accuracy (recommended with CUDA GPU) |

---
---

<a name="português"></a>
## 🇧🇷 Português

O **VoxClip** é uma ferramenta de speech-to-text (transforma fala em texto) feita sob medida para quem usa Hyprland e Wayland. A ideia é muito simples: você aperta um atalho no teclado, fala o que quiser no microfone e o texto já cai copiado na sua área de transferência, prontinho para colar onde precisar com `Ctrl+V`.

Tudo roda 100% no seu computador usando inteligência artificial (o modelo Whisper da OpenAI via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)), garantindo privacidade total sem enviar nada para servidores externos. E se quiser economizar a bateria do notebook, dá até para mandar o processamento pesado para outro computador na sua rede local.

### ✨ Principais Recursos

- **⚡ Gravação com um Atalho** — Inicie e finalize a captura com uma única combinação de teclas (`Super+Shift+V`).
- **🧠 Transcrição por IA Local** — Reconhecimento de voz rápido e preciso com `faster-whisper` (quantização int8 para CPU ou aceleração via CUDA/GPU).
- **🔋 Modo Cliente / Servidor** — Processe o áudio em outra máquina na sua rede local para economizar a bateria de notebooks.
- **🖥️ Interface Nativa Wayland** — Pílula visual compacta com forma de onda em tempo real desenvolvida em GTK3, Cairo e `gtk-layer-shell`.
- **🎨 Temas Integrados** — Paletas populares disponíveis: Glass Violet, Dracula, Nord, Gruvbox, Tokyo Night e One Dark.
- **📜 Histórico de Transcrições** — Painel visual acessível via `Super+Alt+H` para consultar, copiar novamente ou limpar transcrições anteriores.
- **⚙️ Painel Gráfico de Configurações** — Ajuste modelos Whisper, idioma, número de núcleos de CPU e temas em tempo de execução.
- **📊 Módulo para Waybar** — Modo de saída JSON (`voxclip status --waybar`) pronto para ser consumido na sua barra de status.
- **🔒 Privacidade Total** — Processamento 100% local e privado por padrão, sem envio de áudio para nuvens públicas.

---

### 🚀 Instalação Rápida (Arch, Debian/Ubuntu, Fedora, openSUSE)

A maneira mais prática de instalar o VoxClip é utilizando o instalador automático. Ele detecta automaticamente sua distribuição Linux, instala os pacotes do sistema necessários, configura o ambiente virtual Python, o serviço systemd de usuário e os atalhos no Hyprland ou Sway:

```bash
git clone https://github.com/voxclip/voxclip.git
cd voxclip
chmod +x install.sh uninstall.sh
./install.sh
```

Para desinstalar de forma limpa a qualquer momento:
```bash
./uninstall.sh
# ou: ./install.sh --uninstall
```

---

### 🛠️ Instalação Manual

Se preferir instalar manualmente passo a passo:

#### 1. Dependências do Sistema (Arch Linux)

```bash
sudo pacman -S --needed python python-pip python-gobject gtk3 gtk-layer-shell \
                       wl-clipboard portaudio libnotify
```

#### 2. Configuração do Ambiente Virtual

> [!IMPORTANT]
> O parâmetro `--system-site-packages` é essencial para que o ambiente virtual acesse bibliotecas do sistema como `python-gobject` (`gi`) e `gtk-layer-shell`.

```bash
python -m venv --system-site-packages ~/.local/share/voxclip/.venv
source ~/.local/share/voxclip/.venv/bin/activate
pip install -e .
```

---

### ⌨️ Configuração no Hyprland

Adicione o seguinte trecho ao seu arquivo `~/.config/hypr/hyprland.conf`:

```ini
# Atalhos do VoxClip
bind = SUPER SHIFT, V, exec, voxclip toggle
bind = SUPER ALT, H, exec, voxclip history

# Regras de Camada (Layer) e Janela
layerrule = blur on, match:namespace ^(voxclip)$
layerrule = ignore_alpha 0.3, match:namespace ^(voxclip)$
windowrule = float 1, match:title ^(VoxClip Settings)$
windowrule = center 1, match:title ^(VoxClip Settings)$
```

Recarregue as configurações do Hyprland:
```bash
hyprctl reload
```

---

### 🖥️ Comandos da CLI

| Comando | Descrição |
|---|---|
| `voxclip daemon` | Inicia o daemon em segundo plano (loop GTK e socket IPC). |
| `voxclip toggle` | Alterna a gravação (inicia a captura ou encerra e transcreve). |
| `voxclip history` | Abre o painel com o histórico de transcrições recentes. |
| `voxclip settings` | Abre a janela visual de configurações. |
| `voxclip serve` | Inicia o servidor HTTP para transcrição remota em rede local. |
| `voxclip status` | Consulta o status do daemon (`--waybar` exporta JSON formatado). |
| `voxclip devices` | Lista os microfones e dispositivos de áudio disponíveis. |
| `voxclip config` | Exibe as configurações atuais em formato JSON. |
| `voxclip stop` | Encerra o daemon em execução de forma segura. |

---

### 🌐 Modo Servidor Remoto (Economia de Bateria)

Você pode executar o modelo Whisper em um computador de mesa potente ou servidor doméstico e enviar o áudio gravado do notebook:

1. **No servidor / desktop:**
   ```bash
   voxclip serve --host 0.0.0.0 --port 8745 --model medium
   ```

2. **No notebook:**
   Abra as configurações com `voxclip settings`, selecione **Remote Server**, insira a URL (ex: `http://192.168.1.100:8745`), clique em testar conexão e salve.

---

### 🧠 Guia de Escolha de Modelos

| Modelo | Memória (RAM/VRAM) | Velocidade (CPU) | Precisão | Recomendação |
|---|---|---|---|---|
| `tiny` | ~100 MB | Extremamente rápido | Básica | Testes rápidos e dispositivos com pouca memória |
| `base` | ~200 MB | Muito rápido | Boa | Comandos curtos e ditados simples |
| `small` | ~500 MB | Rápido | Ótima | Excelente equilíbrio para o dia a dia |
| **`medium`** | **~1.5 GB** | **Moderada** | **Muito Alta** | **Padrão recomendado para a maioria das CPUs modernas** |
| `large-v3-turbo` | ~2 GB | Moderada/Lenta | Excelente | Alta precisão multilíngue |
| `large-v3` | ~3 GB | Lenta | Máxima | Precisão absoluta (recomendado com aceleração CUDA) |

---

## 📄 License

Distribuído sob a licença [MIT](LICENSE).
