#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
#  VoxClip — installer for Arch Linux + Hyprland
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
MARKER="# >>> VoxClip >>>"
MARKER_END="# <<< VoxClip <<<"

info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${RESET}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
err()   { echo -e "${RED}[ERR ]${RESET}  $*"; exit 1; }

# ── 1. System dependencies ──────────────────────────────────
info "Instalando dependências do sistema via pacman..."
PKGS=(python python-pip python-gobject gtk3 gtk-layer-shell
      wl-clipboard portaudio libnotify)

MISSING=()
for pkg in "${PKGS[@]}"; do
    pacman -Qi "$pkg" &>/dev/null || MISSING+=("$pkg")
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    info "Pacotes faltando: ${MISSING[*]}"
    sudo pacman -S --needed --noconfirm "${MISSING[@]}"
    ok "Pacotes do sistema instalados."
else
    ok "Todos os pacotes do sistema já estão instalados."
fi

# ── 2. Garantir ~/.local/bin no PATH ────────────────────────
BASH_PROFILE="$HOME/.bash_profile"
if ! grep -qF '/.local/bin' "$BASH_PROFILE" 2>/dev/null; then
    info "Adicionando ~/.local/bin ao PATH em $BASH_PROFILE..."
    # Insert after the header comments, before sourcing .bashrc
    sed -i '/\[\[ -f ~\/.bashrc \]\]/i export PATH="$HOME/.local/bin:$PATH"\n' "$BASH_PROFILE" 2>/dev/null \
        || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$BASH_PROFILE"
    ok "PATH atualizado."
else
    ok "~/.local/bin já está no PATH."
fi
# Also export for the current script session
export PATH="$HOME/.local/bin:$PATH"

# ── 3. Copiar projeto para ~/.local/share/voxclip ───────────
info "Copiando projeto para $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
rsync -a --exclude='.venv' --exclude='__pycache__' \
      --exclude='*.egg-info' "$PROJECT_DIR/" "$INSTALL_DIR/"
ok "Projeto copiado."

# ── 4. Virtual environment + dependências Python ────────────
#    --system-site-packages é necessário para acessar gi (PyGObject)
#    e gtk-layer-shell que são pacotes nativos do sistema.
info "Criando virtualenv em $VENV_DIR (com acesso a pacotes do sistema)..."
python -m venv --system-site-packages "$VENV_DIR"
source "$VENV_DIR/bin/activate"

info "Instalando dependências Python..."
pip install --upgrade pip -q
pip install -e "$INSTALL_DIR" -q
ok "Dependências Python instaladas."

deactivate

# ── 5. Wrapper script em ~/.local/bin ────────────────────────
info "Criando wrapper em $BIN_LINK..."
mkdir -p "$(dirname "$BIN_LINK")"
cat > "$BIN_LINK" << 'WRAPPER'
#!/usr/bin/env bash
source "$HOME/.local/share/voxclip/.venv/bin/activate"
exec python -m voxclip "$@"
WRAPPER
chmod +x "$BIN_LINK"
ok "Comando 'voxclip' disponível."

# ── 6. Systemd user service ─────────────────────────────────
info "Instalando serviço systemd..."
mkdir -p "$(dirname "$SERVICE_DST")"
cp "$SERVICE_SRC" "$SERVICE_DST"
systemctl --user daemon-reload
ok "Serviço instalado (voxclip.service)."

# ── 7. Keybindings no Hyprland ──────────────────────────────
VOXCLIP_BIN="$BIN_LINK"

if [[ -f "$HYPR_CONF" ]]; then
    if grep -qF "$MARKER" "$HYPR_CONF"; then
        info "Atualizando keybindings do VoxClip em hyprland.conf..."
        # Remove old block and re-add
        sed -i "/$MARKER/,/$MARKER_END/d" "$HYPR_CONF"
    fi

    info "Adicionando keybindings ao $HYPR_CONF..."
    cat >> "$HYPR_CONF" << HYPR

$MARKER
bind = SUPER SHIFT, V, exec, $VOXCLIP_BIN toggle
bind = SUPER ALT, H, exec, $VOXCLIP_BIN history
layerrule = blur on, match:namespace ^(voxclip)\$
layerrule = ignore_alpha 0.3, match:namespace ^(voxclip)\$
windowrule = float 1, match:title ^(VoxClip Settings)\$
windowrule = center 1, match:title ^(VoxClip Settings)\$
$MARKER_END
HYPR
    ok "Keybindings adicionados."

    # Reload Hyprland if running
    if command -v hyprctl &>/dev/null; then
        hyprctl reload &>/dev/null && ok "Hyprland recarregado." \
            || warn "Não foi possível recarregar o Hyprland automaticamente."
    fi
else
    warn "hyprland.conf não encontrado em $HYPR_CONF — adicione as keybindings manualmente."
fi

# ── Pronto! ──────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}✅ VoxClip instalado com sucesso!${RESET}"
echo ""
echo -e "  ${CYAN}Iniciar daemon:${RESET}       voxclip daemon"
echo -e "  ${CYAN}Iniciar via systemd:${RESET}  systemctl --user enable --now voxclip"
echo -e "  ${CYAN}Gravar/parar:${RESET}         Super+Shift+V"
echo -e "  ${CYAN}Histórico:${RESET}            Super+Alt+H"
echo -e "  ${CYAN}Settings:${RESET}             Botão ⚙ no overlay"
echo ""
echo -e "  Na primeira execução o modelo Whisper (~1.5 GB) será baixado."
echo ""
