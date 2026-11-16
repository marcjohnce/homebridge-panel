#!/usr/bin/env bash
# Rotates screen and touchscreen of the desktop session (labwc, wayfire or X11), e.g. for a
# display mounted upside down (180) or in portrait (90 or 270, clockwise). Takes effect after a reboot.
#
#   ./deploy/set-rotation.sh 180                     rotate by 180°
#   ./deploy/set-rotation.sh 90 --output HDMI-A-1    only this output (default: the first active one)
#   ./deploy/set-rotation.sh 90 --touch 270          touch rotated differently (if touches land mirrored)
#   ./deploy/set-rotation.sh 0                       back to normal
#
# Also run by `install.sh --rotate …`. Not for `install.sh --eglfs` (no desktop): see README.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-${USER:-$(id -un)}}"
HOME_DIR="${PANEL_HOME:-$(getent passwd "$USER_NAME" | cut -d: -f6)}"
RULES_DIR="${PANEL_UDEV_DIR:-/etc/udev/rules.d}"          # overridable for tests
RULE="$RULES_DIR/99-smarthome-panel-touch.rules"
SUDO="${PANEL_SUDO-sudo}"

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  "") usage >&2; exit 1 ;;
esac
ROTATION="$1"
shift
OUTPUT=""
TOUCH=""
while [ $# -gt 0 ]; do
  case "$1" in
    --output) OUTPUT="${2:-}"; shift ;;
    --touch) TOUCH="${2:-}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
  shift
done
TOUCH="${TOUCH:-$ROTATION}"
for v in "$ROTATION" "$TOUCH"; do
  case "$v" in
    0|90|180|270) ;;
    *) echo "Rotation must be 0, 90, 180 or 270 (got \"$v\")" >&2; usage >&2; exit 1 ;;
  esac
done
if ! [[ "$OUTPUT" =~ ^[A-Za-z0-9_-]*$ ]]; then
  echo "Invalid output name: $OUTPUT" >&2
  exit 1
fi

LINE="$DIR/deploy/rotate.sh $ROTATION${OUTPUT:+ $OUTPUT}"

# ---------- screen: run deploy/rotate.sh when the desktop session starts ----------
LABWC="$HOME_DIR/.config/labwc/autostart"
mkdir -p "$(dirname "$LABWC")"
touch "$LABWC"
sed -i '/deploy\/rotate\.sh/d' "$LABWC"
[ "$ROTATION" = 0 ] || echo "$LINE &" >> "$LABWC"

WF="$HOME_DIR/.config/wayfire.ini"
if [ -f "$WF" ]; then
  sed -i '/^smarthome_rotate *=/d' "$WF"
  if [ "$ROTATION" != 0 ]; then
    if grep -q '^\[autostart\]' "$WF"; then
      sed -i "/^\[autostart\]/a smarthome_rotate = $LINE" "$WF"
    else
      printf '\n[autostart]\nsmarthome_rotate = %s\n' "$LINE" >> "$WF"
    fi
  fi
fi

X11="$HOME_DIR/.config/autostart/smarthome-panel-rotate.desktop"
rm -f "$X11"
if [ "$ROTATION" != 0 ]; then
  mkdir -p "$(dirname "$X11")"
  printf '[Desktop Entry]\nType=Application\nName=Smart Home Panel: rotate screen\nExec=%s\nNoDisplay=true\n' \
    "$LINE" > "$X11"
fi
chmod +x "$DIR/deploy/rotate.sh"

if [ "$ROTATION" != 0 ] && [ -z "${PANEL_SUDO+x}" ] && ! command -v wlr-randr >/dev/null; then
  $SUDO apt-get install -y -qq wlr-randr || echo "==> Could not install wlr-randr (needed on Wayland)"
fi

# ---------- touchscreen: libinput calibration matrix (clockwise) ----------
case "$TOUCH" in
  90) MATRIX="0 -1 1 1 0 0" ;;
  180) MATRIX="-1 0 1 0 -1 1" ;;
  270) MATRIX="0 1 0 -1 0 1" ;;
  *) MATRIX="" ;;
esac
if [ -n "$MATRIX" ]; then
  printf '# Smart Home Panel: touchscreen rotated by %s° (deploy/set-rotation.sh)\nSUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_TOUCHSCREEN}=="1", ENV{LIBINPUT_CALIBRATION_MATRIX}="%s"\n' \
    "$TOUCH" "$MATRIX" | $SUDO tee "$RULE" >/dev/null
else
  $SUDO rm -f "$RULE"
fi
if [ -z "${PANEL_UDEV_DIR:-}" ]; then
  $SUDO udevadm control --reload-rules 2>/dev/null || true
fi

chown -R "$USER_NAME": "$HOME_DIR/.config" 2>/dev/null || true
if [ "$ROTATION" = 0 ] && [ "$TOUCH" = 0 ]; then
  echo "==> Rotation removed (screen and touch). Reboot to apply: sudo reboot"
elif [ "$ROTATION" = 0 ]; then
  echo "==> Screen left as it is, touch rotated by $TOUCH°. Reboot to apply: sudo reboot"
else
  echo "==> Screen rotated by $ROTATION°${OUTPUT:+ on $OUTPUT}, touch by $TOUCH°. Reboot to apply: sudo reboot"
  case "$TOUCH" in
    90|270) echo "    Touches land mirrored? Run again with --touch $(( (TOUCH + 180) % 360 ))." ;;
  esac
fi
