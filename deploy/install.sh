#!/usr/bin/env bash
# Installation on Raspberry Pi OS (Bookworm or Trixie).
#
#   ./deploy/install.sh               install the app (application menu entry)
#   ./deploy/install.sh --autostart   also start in full screen when logging in to the desktop
#   ./deploy/install.sh --eglfs       full screen without desktop as a system service (e.g. Pi OS Lite)
#
# Screen in portrait (desktop only, also later via deploy/set-rotation.sh); for upside down
# rather use Settings → Display → Upside down in the panel (much faster):
#   ./deploy/install.sh --autostart --rotate 90                    portrait (90 or 270, clockwise)
#   ./deploy/install.sh --autostart --rotate 270 --output HDMI-A-1 on a specific output
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-${USER:-$(id -un)}}"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
MODE=""
ROTATE=""
ROTATE_OPTS=()     # --output / --touch for deploy/set-rotation.sh
while [ $# -gt 0 ]; do
  case "$1" in
    --autostart|--eglfs) MODE="$1" ;;
    --rotate) ROTATE="${2:-}"; shift ;;
    --output|--touch) ROTATE_OPTS+=("$1" "${2:-}"); shift ;;
    -h|--help) awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (see --help)" >&2; exit 1 ;;
  esac
  shift
done
if [ ${#ROTATE_OPTS[@]} -gt 0 ] && [ -z "$ROTATE" ]; then
  echo "--output and --touch belong to --rotate" >&2
  exit 1
fi
if [ -n "$ROTATE" ]; then
  if [ "$MODE" = --eglfs ]; then
    echo "--rotate needs the desktop (--autostart); see README → Rotating the screen" >&2
    exit 1
  fi
  case "$ROTATE" in
    0|90|180|270) ;;
    *) echo "--rotate must be 0, 90, 180 or 270" >&2; exit 1 ;;
  esac
fi

echo "==> Installing Smart Home Panel in $DIR (user: $USER_NAME)"

sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip \
  libegl1 libgles2 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 libfontconfig1 libdbus-1-3
# switching the display off (Settings → Display → Display off after): wlopm on Wayland
sudo apt-get install -y -qq wlopm 2>/dev/null || true

[ -d "$DIR/.venv" ] || python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q --upgrade pip
"$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
"$DIR/.venv/bin/python" -c "import PySide6; print('==> PySide6', PySide6.__version__)"

if [ ! -f "$DIR/config.yaml" ]; then
  cp "$DIR/config.example.yaml" "$DIR/config.yaml"
  echo "==> Created config.yaml (rooms and devices). Enter the connection in the app under Settings."
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

# Allow this user to switch the display's backlight off and on (Display off after)
sudo tee /etc/udev/rules.d/99-smarthome-panel-backlight.rules >/dev/null <<'EOF'
SUBSYSTEM=="backlight", ACTION=="add", RUN+="/bin/chgrp video /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power", RUN+="/bin/chmod g+w /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"
EOF
sudo usermod -aG video "$USER_NAME"
sudo udevadm control --reload-rules 2>/dev/null || true
sudo udevadm trigger --subsystem-match=backlight --action=add 2>/dev/null || true

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

if [ -n "$ROTATE" ]; then
  chmod +x "$DIR/deploy/set-rotation.sh"
  "$DIR/deploy/set-rotation.sh" "$ROTATE" "${ROTATE_OPTS[@]}"
fi

chown -R "$USER_NAME": "$HOME_DIR/.local/share/applications" "$HOME_DIR/.config" 2>/dev/null || true
echo "==> Done. Start with: $DIR/deploy/start.sh  (window instead of full screen: .venv/bin/python -m app)"
