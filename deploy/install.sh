#!/usr/bin/env bash
# Installation on Raspberry Pi OS (Bookworm or Trixie).
#
#   ./deploy/install.sh               install the app (application menu entry)
#   ./deploy/install.sh --autostart   also start in full screen when logging in to the desktop
#   ./deploy/install.sh --eglfs       full screen without desktop as a system service (e.g. Pi OS Lite)
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
MODE="${1:-}"

echo "==> Installing Smart Home Panel in $DIR (user: $USER_NAME)"

sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip \
  libegl1 libgles2 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 libfontconfig1 libdbus-1-3

[ -d "$DIR/.venv" ] || python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q --upgrade pip
"$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
"$DIR/.venv/bin/python" -c "import PySide6; print('==> PySide6', PySide6.__version__)"

if [ ! -f "$DIR/config.yaml" ]; then
  cp "$DIR/config.example.yaml" "$DIR/config.yaml"
  echo "==> Created config.yaml (rooms, scenes, schedules). Enter the connection in the app under Settings."
fi
chmod +x "$DIR/deploy/start.sh"

# Allow this user to reboot from the panel (Settings → System), also without a desktop session
sudo tee /etc/polkit-1/rules.d/50-smarthome-panel.rules >/dev/null <<EOF
polkit.addRule(function(action, subject) {
    if ((action.id == "org.freedesktop.login1.reboot" ||
         action.id == "org.freedesktop.login1.reboot-multiple-sessions") &&
        subject.user == "$USER_NAME") {
        return polkit.Result.YES;
    }
});
EOF

# Application menu entry
APPS="$HOME_DIR/.local/share/applications"
mkdir -p "$APPS"
cat > "$APPS/smarthome-panel.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Smart Home Panel
Comment=Control lights, plugs and heating
Exec=$DIR/deploy/start.sh
Terminal=false
Categories=Utility;
EOF

case "$MODE" in
  --autostart)
    # labwc (default since late 2024)
    mkdir -p "$HOME_DIR/.config/labwc"
    grep -qs "deploy/start.sh" "$HOME_DIR/.config/labwc/autostart" \
      || echo "$DIR/deploy/start.sh &" >> "$HOME_DIR/.config/labwc/autostart"
    # wayfire (older Bookworm installations)
    WF="$HOME_DIR/.config/wayfire.ini"
    if [ -f "$WF" ] && ! grep -q "deploy/start.sh" "$WF"; then
      printf '\n[autostart]\nsmarthome = %s/deploy/start.sh\n' "$DIR" >> "$WF"
    fi
    # X11-Desktop (LXDE)
    mkdir -p "$HOME_DIR/.config/autostart"
    cp "$APPS/smarthome-panel.desktop" "$HOME_DIR/.config/autostart/"
    echo "==> Autostart set up. Desktop autologin: sudo raspi-config → System Options → Boot / Auto Login"
    ;;
  --eglfs)
    sed -e "s#__USER__#$USER_NAME#g" -e "s#__DIR__#$DIR#g" \
      "$DIR/deploy/smarthome-panel-eglfs.service" | sudo tee /etc/systemd/system/smarthome-panel.service >/dev/null
    sudo systemctl daemon-reload
    sudo systemctl enable --now smarthome-panel.service
    echo "==> Service running: sudo systemctl status smarthome-panel"
    ;;
esac

chown -R "$USER_NAME": "$HOME_DIR/.local/share/applications" "$HOME_DIR/.config" 2>/dev/null || true
echo "==> Done. Start with: $DIR/deploy/start.sh  (window instead of full screen: .venv/bin/python -m app)"
