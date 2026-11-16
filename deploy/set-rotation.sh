#!/usr/bin/env bash
# Rotates screen and touchscreen of the desktop session, e.g. for a display mounted upside down
# (180) or in portrait (90 or 270, clockwise). Takes effect after a reboot.
#
#   ./deploy/set-rotation.sh 180                     rotate by 180°
#   ./deploy/set-rotation.sh 90 --output HDMI-A-1    only this output (default: the first connected one)
#   ./deploy/set-rotation.sh 0                       back to normal
#   ./deploy/set-rotation.sh 180 --touch 0           force a touch rotation (only if touches are still off)
#
# labwc (Pi OS Bookworm/Trixie): the touchscreen is assigned to the screen, like "Screen
# Configuration → Touchscreen" does; the desktop then rotates touch input together with the screen.
# X11 and wayfire: the touch is rotated by a udev rule (libinput calibration matrix).
# Also run by `install.sh --rotate …`. Not for `install.sh --eglfs` (no desktop): see README.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-${USER:-$(id -un)}}"
HOME_DIR="${PANEL_HOME:-$(getent passwd "$USER_NAME" | cut -d: -f6)}"
# overridable for tests
RULES_DIR="${PANEL_UDEV_DIR:-/etc/udev/rules.d}"
SYS_INPUT="${PANEL_SYS_INPUT:-/sys/class/input}"
SYS_DRM="${PANEL_SYS_DRM:-/sys/class/drm}"
LABWC_SYSTEM="${PANEL_LABWC_SYSTEM:-/etc/xdg/labwc/rc.xml}"
SUDO="${PANEL_SUDO-sudo}"
RULE="$RULES_DIR/99-smarthome-panel-touch.rules"
LABWC_RC="$HOME_DIR/.config/labwc/rc.xml"
MARK="<!-- smarthome-panel -->"

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
for v in "$ROTATION" "${TOUCH:-0}"; do
  case "$v" in
    0|90|180|270) ;;
    *) echo "Rotation must be 0, 90, 180 or 270 (got \"$v\")" >&2; usage >&2; exit 1 ;;
  esac
done
if ! [[ "$OUTPUT" =~ ^[A-Za-z0-9_-]*$ ]]; then
  echo "Invalid output name: $OUTPUT" >&2
  exit 1
fi

# Names of the touchscreens, one per line
touchscreens() {
  local ev
  for ev in "$SYS_INPUT"/event*; do
    [ -e "$ev/device/name" ] || continue
    if udevadm info -q property -p "$ev" 2>/dev/null | grep -qx 'ID_INPUT_TOUCHSCREEN=1'; then
      cat "$ev/device/name"
    fi
  done
}

# First connected display output, e.g. "DSI-1" from /sys/class/drm/card1-DSI-1
first_output() {
  local d
  for d in "$SYS_DRM"/card*-*; do
    [ "$(cat "$d/status" 2>/dev/null)" = connected ] || continue
    basename "$d" | sed 's/^card[0-9]*-//'
    return
  done
}

# Is this touchscreen assigned to an output in the user's or the system's labwc configuration?
touch_mapped() {
  grep -hsF "deviceName=\"$1\"" "$LABWC_RC" "$LABWC_SYSTEM" | grep -q 'mapToOutput='
}

xml_escape() { sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g' <<<"$1"; }

# ---------- screen: run deploy/rotate.sh when the desktop session starts ----------
LINE="$DIR/deploy/rotate.sh $ROTATION${OUTPUT:+ $OUTPUT}"

LABWC_AUTOSTART="$HOME_DIR/.config/labwc/autostart"
mkdir -p "$(dirname "$LABWC_AUTOSTART")"
touch "$LABWC_AUTOSTART"
sed -i '/deploy\/rotate\.sh/d' "$LABWC_AUTOSTART"
[ "$ROTATION" = 0 ] || echo "$LINE &" >> "$LABWC_AUTOSTART"

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

# ---------- touchscreen ----------
TOUCH_NOTE=""
if [ -f "$LABWC_SYSTEM" ] || [ -f "$LABWC_RC" ] || command -v labwc >/dev/null; then
  # labwc: assign every touchscreen to the screen (entries of an earlier run are replaced)
  if [ -f "$LABWC_RC" ]; then
    sed -i "\#$MARK#d" "$LABWC_RC"
  fi
  OUT="${OUTPUT:-$(first_output)}"
  ADDED=()
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    if touch_mapped "$name"; then
      TOUCH_NOTE="touch follows the screen (\"$name\" is assigned to a screen)"
    elif [ -n "$OUT" ]; then
      ADDED+=("  <touch deviceName=\"$(xml_escape "$name")\" mapToOutput=\"$OUT\" mouseEmulation=\"yes\"/> $MARK")
      TOUCH_NOTE="touch follows the screen (\"$name\" assigned to $OUT)"
    else
      TOUCH_NOTE="no connected screen found for \"$name\": assign it in Screen Configuration → Touchscreen"
    fi
  done < <(touchscreens)
  if [ ${#ADDED[@]} -gt 0 ]; then
    mkdir -p "$(dirname "$LABWC_RC")"
    [ -f "$LABWC_RC" ] || printf '<?xml version="1.0"?>\n<labwc_config>\n</labwc_config>\n' > "$LABWC_RC"
    printf '%s\n' "${ADDED[@]}" > "$LABWC_RC.add"
    # insert before the closing tag
    awk -v add="$LABWC_RC.add" '/<\/labwc_config>/ { while ((getline l < add) > 0) print l } { print }' \
      "$LABWC_RC" > "$LABWC_RC.new"
    mv "$LABWC_RC.new" "$LABWC_RC"
    rm -f "$LABWC_RC.add"
  fi
  [ -n "$TOUCH_NOTE" ] || TOUCH_NOTE="no touchscreen found"
  MATRIX_ROTATION="${TOUCH:-0}"            # rotated by the desktop, no extra rotation
else
  MATRIX_ROTATION="${TOUCH:-$ROTATION}"    # X11, wayfire: rotate the touch input itself
fi

case "$MATRIX_ROTATION" in
  90) MATRIX="0 -1 1 1 0 0" ;;
  180) MATRIX="-1 0 1 0 -1 1" ;;
  270) MATRIX="0 1 0 -1 0 1" ;;
  *) MATRIX="" ;;
esac
if [ -n "$MATRIX" ]; then
  printf '# Smart Home Panel: touchscreen rotated by %s° (deploy/set-rotation.sh)\nSUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_TOUCHSCREEN}=="1", ENV{LIBINPUT_CALIBRATION_MATRIX}="%s"\n' \
    "$MATRIX_ROTATION" "$MATRIX" | $SUDO tee "$RULE" >/dev/null
  TOUCH_NOTE="touch rotated by $MATRIX_ROTATION° (udev rule)"
else
  $SUDO rm -f "$RULE"
fi
if [ -z "${PANEL_UDEV_DIR:-}" ]; then
  $SUDO udevadm control --reload-rules 2>/dev/null || true
fi

chown -R "$USER_NAME": "$HOME_DIR/.config" 2>/dev/null || true
if [ "$ROTATION" = 0 ]; then
  echo "==> Screen not rotated; $TOUCH_NOTE. Reboot to apply: sudo reboot"
else
  echo "==> Screen rotated by $ROTATION°${OUTPUT:+ on $OUTPUT}; $TOUCH_NOTE. Reboot to apply: sudo reboot"
fi
