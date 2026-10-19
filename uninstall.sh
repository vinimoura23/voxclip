#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
#  VoxClip — Uninstaller
# ─────────────────────────────────────────────────────────────

BOLD='\033[1m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
RED='\033[1;31m'
RESET='\033[0m'

INSTALL_DIR="$HOME/.local/share/voxclip"
BIN_LINK="$HOME/.local/bin/voxclip"
SERVICE_DST="$HOME/.config/systemd/user/voxclip.service"
HYPR_CONF="$HOME/.config/hypr/hyprland.conf"
SWAY_CONF="$HOME/.config/sway/config"
CONFIG_DIR="$HOME/.config/voxclip"
MARKER="# >>> VoxClip >>>"
MARKER_END="# <<< VoxClip <<<"

info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${RESET}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
err()   { echo -e "${RED}[ERR ]${RESET}  $*"; exit 1; }

echo -e "${BOLD}${CYAN}Desinstalando o VoxClip...${RESET}"
echo ""

# ── 1. Parar e desabilitar serviço systemd ───────────────────
if systemctl --user is-active --quiet voxclip 2>/dev/null; then
    info "Parando serviço systemd do VoxClip..."
    systemctl --user stop voxclip 2>/dev/null || true
    ok "Serviço parado."
fi

if systemctl --user is-enabled --quiet voxclip 2>/dev/null; then
    info "Desabilitando serviço systemd..."
    systemctl --user disable voxclip 2>/dev/null || true
    ok "Serviço desabilitado."
fi

if [[ -f "$SERVICE_DST" ]]; then
    info "Removendo arquivo de serviço $SERVICE_DST..."
    rm -f "$SERVICE_DST"
    systemctl --user daemon-reload 2>/dev/null || true
    ok "Arquivo de serviço removido."
fi

# ── 2. Remover executável wrapper ────────────────────────────
if [[ -f "$BIN_LINK" ]]; then
    info "Removendo executável em $BIN_LINK..."
    rm -f "$BIN_LINK"
    ok "Executável removido."
fi

# ── 3. Remover diretório de instalação ───────────────────────
if [[ -d "$INSTALL_DIR" ]]; then
    info "Removendo arquivos do programa em $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
    ok "Arquivos do programa removidos."
fi

# ── 4. Limpar atalhos no Hyprland ────────────────────────────
if [[ -f "$HYPR_CONF" ]] && grep -qF "$MARKER" "$HYPR_CONF"; then
    info "Removendo atalhos do VoxClip em $HYPR_CONF..."
    sed -i "/$MARKER/,/$MARKER_END/d" "$HYPR_CONF"
    ok "Atalhos removidos do Hyprland."

    if command -v hyprctl &>/dev/null; then
        hyprctl reload &>/dev/null && ok "Hyprland recarregado." || true
    fi
fi

# ── 5. Limpar atalhos no Sway ────────────────────────────────
if [[ -f "$SWAY_CONF" ]] && grep -qF "$MARKER" "$SWAY_CONF"; then
    info "Removendo atalhos do VoxClip em $SWAY_CONF..."
    sed -i "/$MARKER/,/$MARKER_END/d" "$SWAY_CONF"
    ok "Atalhos removidos do Sway."
fi

# ── 6. Perguntar sobre dados de configuração e histórico ─────
PURGE=${1:-}
if [[ "$PURGE" == "--purge" ]]; then
    DELETE_DATA="y"
elif [[ -t 0 && -d "$CONFIG_DIR" ]]; then
    echo ""
    read -r -p "Deseja também apagar suas configurações e histórico ($CONFIG_DIR)? [s/N]: " resp
    if [[ "$resp" =~ ^[sSyY]$ ]]; then
        DELETE_DATA="y"
    else
        DELETE_DATA="n"
    fi
else
    DELETE_DATA="n"
fi

if [[ "$DELETE_DATA" == "y" && -d "$CONFIG_DIR" ]]; then
    info "Removendo diretório de configurações $CONFIG_DIR..."
    rm -rf "$CONFIG_DIR"
    ok "Configurações e histórico removidos."
else
    if [[ -d "$CONFIG_DIR" ]]; then
        info "Configurações preservadas em: $CONFIG_DIR"
    fi
fi

echo ""
echo -e "${BOLD}${GREEN}✅ VoxClip desinstalado com sucesso!${RESET}"
echo ""
