#!/usr/bin/env bash
# Rotates the screen when the desktop session starts (installed by `install.sh --rotate`).
#
#   deploy/rotate.sh 90|180|270 [OUTPUT]
#
# Wayland (labwc, wayfire): wlr-randr --transform; X11: xrandr --rotate. Without OUTPUT the first
# active output is used. The touchscreen is rotated separately by a udev rule (see install.sh),
# because the compositor does not rotate touch input with the screen.
set -u

ROTATION="${1:-0}"
OUTPUT="${2:-}"

first_wayland_output() {
  # wlr-randr lists every output as an unindented line "NAME "description"", followed by its
  # indented properties, among them "Enabled: yes"
  wlr-randr 2>/dev/null | awk '
    /^[^ \t]/ { name = $1 }
    /^[ \t]+Enabled: yes/ && name != "" { print name; exit }'
}

rotate_wayland() {
  local out="${OUTPUT:-$(first_wayland_output)}"
  [ -n "$out" ] || return 1
  wlr-randr --output "$out" --transform "$ROTATION"
}

rotate_x11() {
  local out="${OUTPUT:-$(xrandr --query | awk '/ connected/ { print $1; exit }')}"
  local dir
  case "$ROTATION" in
    90) dir=right ;; 180) dir=inverted ;; 270) dir=left ;; *) dir=normal ;;
  esac
  [ -n "$out" ] && xrandr --output "$out" --rotate "$dir"
}

apply() {
  if [ -n "${WAYLAND_DISPLAY:-}" ] && command -v wlr-randr >/dev/null; then
    rotate_wayland
  elif [ -n "${DISPLAY:-}" ] && command -v xrandr >/dev/null; then
    rotate_x11
  else
    return 1
  fi
}

# Outputs may not be ready right after login: try for up to 15 seconds.
for _ in $(seq 15); do
  apply && break
  sleep 1
done
# Pi OS restores the screen layout from its "Screen Configuration" (kanshi) shortly after login;
# apply the rotation once more afterwards so it is not reset.
sleep 4
apply
