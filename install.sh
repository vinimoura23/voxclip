#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
#  VoxClip — Universal Installer (Arch, Debian/Ubuntu, Fedora, openSUSE)
# ─────────────────────────────────────────────────────────────

BOLD='\033[1m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
RED='\033[1;31m'
RESET='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/share/voxclip"
VENV_DIR="$INSTALL_DIR/.venv"
BIN_LINK="$HOME/.local/bin/voxclip"
SERVICE_SRC="$PROJECT_DIR/contrib/voxclip.service"
SERVICE_DST="$HOME/.config/systemd/user/voxclip.service"
HYPR_CONF="$HOME/.config/hypr/hyprland.conf"
SWAY_CONF="$HOME/.config/sway/config"
MARKER="# >>> VoxClip >>>"
MARKER_END="# <<< VoxClip <<<"

info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${RESET}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
err()   { echo -e "${RED}[ERR ]${RESET}  $*"; exit 1; }

# Delegar para desinstalador se passado --uninstall
if [[ "${1:-}" == "--uninstall" ]]; then
    exec "$PROJECT_DIR/uninstall.sh" "${2:-}"
fi

echo -e "${BOLD}${CYAN}Iniciando instalação do VoxClip...${RESET}"
echo ""

# ── 1. Dependências do sistema (Detecção de Distribuição) ──────
info "Detectando gerenciador de pacotes da distribuição..."

if command -v pacman &>/dev/null; then
    info "Distribuição baseada em Arch Linux detectada (pacman)."
    PKGS=(python python-pip python-gobject gtk3 gtk-layer-shell wl-clipboard portaudio libnotify)
    MISSING=()
    for pkg in "${PKGS[@]}"; do
        pacman -Qi "$pkg" &>/dev/null || MISSING+=("$pkg")
    done
    if [[ ${#MISSING[@]} -gt 0 ]]; then
        info "Instalando pacotes necessários: ${MISSING[*]}"
        sudo pacman -S --needed --noconfirm "${MISSING[@]}"
    fi
    ok "Dependências do sistema verificadas."

elif command -v apt-get &>/dev/null; then
    info "Distribuição baseada em Debian/Ubuntu detectada (apt)."
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3 python3-pip python3-venv python3-gi gir1.2-gtk-3.0 \
                                libgtk-layer-shell0 gir1.2-gtklayershell-0.1 wl-clipboard \
                                libportaudio2 libnotify-bin
    ok "Dependências do sistema instaladas via apt."

elif command -v dnf &>/dev/null; then
    info "Distribuição baseada em Fedora/RHEL detectada (dnf)."
    sudo dnf install -y python3 python3-pip python3-gobject gtk3 gtk-layer-shell \
                        wl-clipboard portaudio libnotify
    ok "Dependências do sistema instaladas via dnf."

elif command -v zypper &>/dev/null; then
    info "Distribuição openSUSE detectada (zypper)."
    sudo zypper --non-interactive install python3 python3-pip python3-gobject gtk3 \
                                          gtk-layer-shell wl-clipboard portaudio libnotify-tools
    ok "Dependências do sistema instaladas via zypper."

else
    warn "Gerenciador de pacotes não reconhecido automaticamente."
    warn "Certifique-se de ter instalado: python3, python-gobject, gtk3, gtk-layer-shell, wl-clipboard e portaudio."
fi

# ── 2. Garantir ~/.local/bin no PATH ────────────────────────
BASH_PROFILE="$HOME/.bash_profile"
BASHRC="$HOME/.bashrc"
ZSHRC="$HOME/.zshrc"

add_path() {
    local target="$1"
    if [[ -f "$target" ]] && ! grep -qF '/.local/bin' "$target" 2>/dev/null; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$target"
        info "Adicionado ~/.local/bin ao PATH em $target."
    fi
}

add_path "$BASH_PROFILE"
add_path "$BASHRC"
add_path "$ZSHRC"
export PATH="$HOME/.local/bin:$PATH"
ok "~/.local/bin configurado no PATH."

# ── 3. Copiar projeto para ~/.local/share/voxclip ───────────
info "Copiando arquivos do projeto para $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
if command -v rsync &>/dev/null; then
    rsync -a --exclude='.venv' --exclude='__pycache__' \
          --exclude='*.egg-info' "$PROJECT_DIR/" "$INSTALL_DIR/"
else
    cp -r "$PROJECT_DIR"/* "$INSTALL_DIR/"
fi
ok "Projeto copiado."

# ── 4. Virtual environment + dependências Python ────────────
info "Criando ambiente virtual com acesso a pacotes do sistema (--system-site-packages)..."
python3 -m venv --system-site-packages "$VENV_DIR"
source "$VENV_DIR/bin/activate"

info "Instalando dependências Python..."
pip install --upgrade pip -q
pip install -e "$INSTALL_DIR" -q
ok "Dependências Python instaladas."

deactivate

# ── 5. Wrapper script em ~/.local/bin ────────────────────────
info "Criando comando executável em $BIN_LINK..."
mkdir -p "$(dirname "$BIN_LINK")"
cat > "$BIN_LINK" << 'WRAPPER'
#!/usr/bin/env bash
source "$HOME/.local/share/voxclip/.venv/bin/activate"
exec python -m voxclip "$@"
WRAPPER
chmod +x "$BIN_LINK"
ok "Comando 'voxclip' criado com sucesso."

# ── 6. Systemd user service ─────────────────────────────────
info "Configurando serviço de usuário no systemd..."
mkdir -p "$(dirname "$SERVICE_DST")"
cp "$SERVICE_SRC" "$SERVICE_DST"
systemctl --user daemon-reload
ok "Serviço instalado (voxclip.service)."

# ── 7. Configuração de atalhos e regras de janela ───────────
CONFIGURED_WM=false

# Hyprland
if [[ -f "$HYPR_CONF" ]]; then
    if grep -qF "$MARKER" "$HYPR_CONF"; then
        sed -i "/$MARKER/,/$MARKER_END/d" "$HYPR_CONF"
    fi

    info "Adicionando atalhos e regras ao Hyprland ($HYPR_CONF)..."
    cat >> "$HYPR_CONF" << HYPR

$MARKER
bind = SUPER SHIFT, V, exec, $BIN_LINK toggle
bind = SUPER ALT, H, exec, $BIN_LINK history
layerrule = blur on, match:namespace ^(voxclip)\$
layerrule = ignore_alpha 0.3, match:namespace ^(voxclip)\$
windowrule = float 1, match:title ^(VoxClip Settings)\$
windowrule = center 1, match:title ^(VoxClip Settings)\$
$MARKER_END
HYPR
    ok "Atalhos e regras adicionados ao Hyprland."
    CONFIGURED_WM=true

    if command -v hyprctl &>/dev/null; then
        hyprctl reload &>/dev/null && ok "Hyprland recarregado com sucesso." || true
    fi
fi

# Sway
if [[ -f "$SWAY_CONF" ]]; then
    if grep -qF "$MARKER" "$SWAY_CONF"; then
        sed -i "/$MARKER/,/$MARKER_END/d" "$SWAY_CONF"
    fi

    info "Adicionando atalhos ao Sway ($SWAY_CONF)..."
    cat >> "$SWAY_CONF" << SWAY

$MARKER
bindsym Mod4+Shift+v exec $BIN_LINK toggle
bindsym Mod4+Mod1+h exec $BIN_LINK history
$MARKER_END
SWAY
    ok "Atalhos adicionados ao Sway."
    CONFIGURED_WM=true
fi

# Caso não seja Hyprland nem Sway (GNOME / KDE / etc)
if [[ "$CONFIGURED_WM" == false ]]; then
    echo ""
    warn "Compositor/Ambiente gráfico automático não detectado."
    echo -e "  Para usar o VoxClip no ${BOLD}GNOME, KDE Plasma ou outro ambiente${RESET}:"
    echo -e "  Cadastre um atalho personalizado nas configurações do sistema apontando para:"
    echo -e "    ${CYAN}Gravar/Transcrever:${RESET} $BIN_LINK toggle"
    echo -e "    ${CYAN}Histórico:${RESET}         $BIN_LINK history"
fi

# ── Conclusão ────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}🎉 VoxClip instalado com sucesso!${RESET}"
echo ""
echo -e "  ${CYAN}Iniciar daemon agora:${RESET}  voxclip daemon"
echo -e "  ${CYAN}Iniciar via systemd:${RESET}   systemctl --user enable --now voxclip"
echo -e "  ${CYAN}Atalho de gravação:${RESET}    Super+Shift+V"
echo -e "  ${CYAN}Atalho do histórico:${RESET}   Super+Alt+H"
echo -e "  ${CYAN}Configurações:${RESET}         voxclip settings (ou clique no ⚙ da pílula)"
echo -e "  ${CYAN}Para desinstalar:${RESET}      ./uninstall.sh (ou ./install.sh --uninstall)"
echo ""
echo -e "  ${YELLOW}Nota:${RESET} Na primeira gravação o modelo Whisper será baixado (~1.5 GB)."
echo ""
