#!/usr/bin/env bash
# Startet das Smart Home Panel im Vollbild (für Autostart und Desktop-Verknüpfung).
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR" || exit 1
export SMARTHOME_CONFIG="${SMARTHOME_CONFIG:-$DIR/config.yaml}"
exec "$DIR/.venv/bin/python" -m app --fullscreen --hide-cursor "$@"
