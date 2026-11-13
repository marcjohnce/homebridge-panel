"""Startpunkt der Qt-Anwendung."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QML_DIR = ROOT / "qml"
FONT_DIR = ROOT / "assets" / "fonts"


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="smarthome-panel", description="Smart Home Panel (Qt)")
    p.add_argument("--config", help="Pfad zur config.yaml (Räume, Szenen, Zeitpläne)")
    p.add_argument("--settings", help="Pfad zur settings.json (Standard: ~/.config/smarthome-panel/)")
    p.add_argument("--fullscreen", action="store_true", help="Im Vollbild starten (Wandpanel)")
    p.add_argument("--hide-cursor", action="store_true", help="Mauszeiger ausblenden (Touchscreen)")
    p.add_argument("--demo", action="store_true", help="Simulierte Geräte zusätzlich anzeigen")
    p.add_argument("--size", default="1024x600", help="Fenstergröße ohne Vollbild, z. B. 800x480")
    return p.parse_known_args(argv)[0]


def load_fonts() -> None:
    from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
    for ttf in sorted(FONT_DIR.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(ttf))
    font = QFont("Jost")
    font.setPixelSize(16)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    QGuiApplication.setFont(font)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    args = parse_args(argv[1:])
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QCursor, QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    from ..config import config_path, load_config
    from ..settings import SettingsStore
    from .controller import ActivityFilter, Controller

    app = QGuiApplication(argv)
    app.setApplicationName("Smart Home Panel")
    app.setOrganizationName("smarthome-panel")
    load_fonts()
    if args.hide_cursor:
        app.setOverrideCursor(QCursor(Qt.CursorShape.BlankCursor))

    cfg_file = config_path(args.config)
    cfg = load_config(cfg_file, required=False)
    if args.demo:
        cfg.demo.enabled = True
    store = SettingsStore(args.settings)
    controller = Controller(cfg, store, cfg_file.resolve() if cfg_file.exists() else None,
                            fullscreen=args.fullscreen)
    app.installEventFilter(ActivityFilter(controller))

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("panel", controller)
    w, _, h = args.size.partition("x")
    engine.rootContext().setContextProperty("initialWidth", int(w or 1024))
    engine.rootContext().setContextProperty("initialHeight", int(h or 600))
    engine.load(QML_DIR / "Main.qml")
    if not engine.rootObjects():
        logging.error("Oberfläche konnte nicht geladen werden")
        controller.shutdown()
        return 1

    controller.start()
    rc = app.exec()
    controller.shutdown()
    return rc


if __name__ == "__main__":
    sys.exit(main())
