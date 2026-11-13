"""Starts the panel headless with demo devices and saves screenshots.

    python tools/screenshots.py OUTPUT_DIR [--size 1024x600] [--theme light|dark|both]

Prints all QML warnings; exit code 1 if there are any (used by the tests).
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

from PySide6.QtCore import QEventLoop, QPointF, Qt, QTimer, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402
from shiboken6 import Shiboken  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from app.config import load_config  # noqa: E402
from app.qt.controller import Controller  # noqa: E402
from app.qt.main import QML_DIR, load_fonts  # noqa: E402
from app.settings import SettingsStore  # noqa: E402

warnings: list[str] = []


def handler(mode, ctx, msg):  # noqa: ANN001
    if "QML" in msg or "qml" in msg or (ctx.file or "").endswith(".qml"):
        warnings.append(f"{ctx.file}:{ctx.line}: {msg}")


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--size", default="1024x600")
    ap.add_argument("--theme", default="both")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    w, h = (int(x) for x in args.size.split("x"))

    qInstallMessageHandler(handler)
    app = QGuiApplication(sys.argv)
    load_fonts()
    cfg = load_config(ROOT / "config.example.yaml")
    cfg.demo.enabled = True
    tmp = tempfile.mkdtemp()
    store = SettingsStore(Path(tmp) / "settings.json")
    store.update({"hap_enabled": False})
    ctl = Controller(cfg, store, ROOT / "config.example.yaml")
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("panel", ctl)
    engine.rootContext().setContextProperty("initialWidth", w)
    engine.rootContext().setContextProperty("initialHeight", h)
    engine.load(QML_DIR / "Main.qml")
    if not engine.rootObjects():
        print("\n".join(warnings))
        return 1
    win = Shiboken.wrapInstance(Shiboken.getCppPointer(engine.rootObjects()[0])[0], QQuickWindow)
    ctl.start()
    wait(1500)

    def shot(name: str) -> None:
        wait(400)
        win.grabWindow().save(str(out / f"{name}.png"))

    def click(x: float, y: float) -> None:
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPointF(x, y).toPoint())

    themes = ["light", "dark"] if args.theme == "both" else [args.theme]
    for theme in themes:
        store.update({"theme": theme})
        ctl.settings_saved({"theme"})
        shot(f"{theme}-home")
        devs = {d["name"]: d["id"] for d in ctl.devices.all()}
        win.setProperty("openDevice", devs["Living Room Heating"])
        wait(300)
        shot(f"{theme}-heating")
        win.setProperty("openDevice", devs["TV Light"])
        shot(f"{theme}-light")
        win.setProperty("openDevice", devs["Weather Station"])
        shot(f"{theme}-sensor")
        win.setProperty("openDevice", "")
        win.setProperty("settingsOpen", True)
        shot(f"{theme}-settings")
        win.setProperty("settingsOpen", False)
    win.setProperty("idle", True)
    wait(900)   # let the fade-in finish
    shot("screensaver")
    win.setProperty("idle", False)

    ctl.shutdown()
    if warnings:
        print("QML warnings:\n" + "\n".join(warnings))
        return 1
    print("ok, no QML warnings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
