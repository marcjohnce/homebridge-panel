#!/usr/bin/env bash
# Installation auf Raspberry Pi OS (Bookworm oder Trixie).
#
#   ./deploy/install.sh               Programm installieren (Startmenü-Eintrag)
#   ./deploy/install.sh --autostart   zusätzlich beim Anmelden am Desktop im Vollbild starten
#   ./deploy/install.sh --eglfs       Vollbild ohne Desktop als Systemdienst (z. B. Pi OS Lite)
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
MODE="${1:-}"

echo "==> Installiere Smart Home Panel in $DIR (Benutzer: $USER_NAME)"

sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip \
  libegl1 libgles2 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 libfontconfig1 libdbus-1-3

[ -d "$DIR/.venv" ] || python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q --upgrade pip
"$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
"$DIR/.venv/bin/python" -c "import PySide6; print('==> PySide6', PySide6.__version__)"

if [ ! -f "$DIR/config.yaml" ]; then
  cp "$DIR/config.example.yaml" "$DIR/config.yaml"
  echo "==> config.yaml angelegt (Räume, Szenen, Zeitpläne). Verbindung in der App unter Einstellungen eintragen."
fi
chmod +x "$DIR/deploy/start.sh"

# Startmenü-Eintrag
APPS="$HOME_DIR/.local/share/applications"
mkdir -p "$APPS"
cat > "$APPS/smarthome-panel.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Smart Home Panel
Comment=Lichter, Steckdosen und Heizung steuern
Exec=$DIR/deploy/start.sh
Terminal=false
Categories=Utility;
EOF

case "$MODE" in
  --autostart)
    # labwc (Standard seit Ende 2024)
    mkdir -p "$HOME_DIR/.config/labwc"
    grep -qs "deploy/start.sh" "$HOME_DIR/.config/labwc/autostart" \
      || echo "$DIR/deploy/start.sh &" >> "$HOME_DIR/.config/labwc/autostart"
    # wayfire (ältere Bookworm-Installationen)
    WF="$HOME_DIR/.config/wayfire.ini"
    if [ -f "$WF" ] && ! grep -q "deploy/start.sh" "$WF"; then
      printf '\n[autostart]\nsmarthome = %s/deploy/start.sh\n' "$DIR" >> "$WF"
    fi
    # X11-Desktop (LXDE)
    mkdir -p "$HOME_DIR/.config/autostart"
    cp "$APPS/smarthome-panel.desktop" "$HOME_DIR/.config/autostart/"
    echo "==> Autostart eingerichtet. Desktop-Autologin: sudo raspi-config → System Options → Boot / Auto Login"
    ;;
  --eglfs)
    sed -e "s#__USER__#$USER_NAME#g" -e "s#__DIR__#$DIR#g" \
      "$DIR/deploy/smarthome-panel-eglfs.service" | sudo tee /etc/systemd/system/smarthome-panel.service >/dev/null
    sudo systemctl daemon-reload
    sudo systemctl enable --now smarthome-panel.service
    echo "==> Dienst läuft: sudo systemctl status smarthome-panel"
    ;;
esac

chown -R "$USER_NAME": "$HOME_DIR/.local/share/applications" "$HOME_DIR/.config" 2>/dev/null || true
echo "==> Fertig. Starten mit: $DIR/deploy/start.sh  (Fenster statt Vollbild: .venv/bin/python -m app)"
