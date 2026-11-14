"""Starts the panel headless with demo devices and saves screenshots.

    python tools/screenshots.py OUTPUT_DIR [--size 1024x600] [--theme light|dark|both] [--lang en]

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

from PySide6.QtCore import (Q_ARG, QEventLoop, QMetaObject, QObject, QPointF, Qt, QTimer,  # noqa: E402
                            qInstallMessageHandler)
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402
from shiboken6 import Shiboken  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from app.config import load_config  # noqa: E402
from app.i18n import tr  # noqa: E402
from app.qt.controller import Controller  # noqa: E402
from app.qt.main import QML_DIR, load_fonts  # noqa: E402
from app.qt.translator import CatalogTranslator  # noqa: E402
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
    ap.add_argument("--lang", default="en")
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
    store.update({"hap_enabled": False, "language": args.lang})
    ctl = Controller(cfg, store, ROOT / "config.example.yaml")
    translator = CatalogTranslator(app)
    app.installTranslator(translator)
    engine = QQmlApplicationEngine()
    ctl.languageChanged.connect(engine.retranslate)
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
        for cat in ("light", "climate", "security"):
            ctl.selectCategory(cat)
            shot(f"{theme}-home-{cat}")
        ctl.selectCategory("")
        shot(f"{theme}-home")
        devs = {d["name"]: d["id"] for d in ctl.devices.all()}
        win.setProperty("openDevice", devs["Living Room Heating"])
        wait(300)
        shot(f"{theme}-heating")
        win.setProperty("openDevice", devs["TV Light"])
        shot(f"{theme}-light")
        win.setProperty("openDevice", devs["Weather Station"])
        shot(f"{theme}-sensor")
        win.setProperty("openDevice", devs["Living Room Blinds"])
        shot(f"{theme}-blinds")
        win.setProperty("openDevice", "")
        win.setProperty("settingsOpen", True)
        shot(f"{theme}-settings")
        page = engine.rootObjects()[0].findChild(QObject, "settingsPage")
        page.setProperty("subPage", "rooms_page")
        shot(f"{theme}-rooms")
        rooms = page.findChild(QObject, "roomsPage")
        keyboard = rooms.findChild(QObject, "textKeyboard")
        QMetaObject.invokeMethod(keyboard, "edit", Q_ARG("QVariant", tr("Rename room")),
                                 Q_ARG("QVariant", "Kitchen"), Q_ARG("QVariant", None), Q_ARG("QVariant", None))
        shot(f"{theme}-room-keyboard")
        QMetaObject.invokeMethod(keyboard, "close")
        rooms.setProperty("tab", 1)
        shot(f"{theme}-room-devices")
        editor = rooms.findChild(QObject, "deviceEditor")
        door = next(d for d in ctl.roomEditor.devices if d["kinds"])
        QMetaObject.invokeMethod(editor, "edit", Q_ARG("QVariant", door))
        shot(f"{theme}-device-editor")
        QMetaObject.invokeMethod(editor, "close")
        for name in ("virtualEditor", "groupEditor"):
            dialog = rooms.findChild(QObject, name)
            QMetaObject.invokeMethod(dialog, "edit", Q_ARG("QVariant", None))
            shot(f"{theme}-{name}")
            QMetaObject.invokeMethod(dialog, "close")
        page.setProperty("subPage", "")
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
