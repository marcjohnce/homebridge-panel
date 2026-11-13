#!/usr/bin/env bash
# Starts the Smart Home Panel in full screen (for autostart and the desktop shortcut).
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR" || exit 1
export SMARTHOME_CONFIG="${SMARTHOME_CONFIG:-$DIR/config.yaml}"
exec "$DIR/.venv/bin/python" -m app --fullscreen --hide-cursor "$@"
