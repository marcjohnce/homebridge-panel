"""Generates the annotated screenshots used in docs/user-interface.md.

    python tools/doc_screenshots.py [OUTPUT_DIR]      (default: docs/images)

The panel runs headless with demo devices. Callouts are placed from the real
positions of named QML items (objectName), so the images stay correct after
layout changes – just run the script again.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PySide6.QtCore import QEvent, QEventLoop, QObject, QPointF, QRectF, Qt, QTimer, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QGuiApplication, QKeyEvent  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from shiboken6 import Shiboken  # noqa: E402

from app.config import load_config  # noqa: E402
from app.qt.controller import Controller  # noqa: E402
from app.qt.main import FONT_DIR, QML_DIR, load_fonts  # noqa: E402
from app.settings import SettingsStore  # noqa: E402

# Screen sizes documented: (width, height, file suffix)
SIZES = [(800, 480), (1024, 600), (1280, 720), (1280, 800), (720, 1280)]
DETAIL_SIZE = (1024, 600)

CALLOUT = (37, 99, 235)          # blue: clearly separate from the gold UI accent
BADGE_R = 13

warnings: list[str] = []


def on_message(mode, ctx, msg):  # noqa: ANN001
    if (ctx.file or "").endswith(".qml") or "qml" in msg.lower():
        warnings.append(f"{ctx.file}:{ctx.line}: {msg}")


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


class Panel:
    """A headless panel window with demo devices."""

    def __init__(self, size: tuple[int, int], theme: str = "light"):
        cfg = load_config(ROOT / "config.example.yaml")
        cfg.demo.enabled = True
        self.store = SettingsStore(Path(tempfile.mkdtemp()) / "settings.json")
        self.store.update({"hap_enabled": False, "theme": theme})
        self.ctl = Controller(cfg, self.store, ROOT / "config.example.yaml")
        self.engine = QQmlApplicationEngine()
        ctx = self.engine.rootContext()
        ctx.setContextProperty("panel", self.ctl)
        ctx.setContextProperty("initialWidth", size[0])
        ctx.setContextProperty("initialHeight", size[1])
        self.engine.load(QML_DIR / "Main.qml")
        if not self.engine.rootObjects():
            raise SystemExit("QML failed to load:\n" + "\n".join(warnings))
        self.win = Shiboken.wrapInstance(Shiboken.getCppPointer(self.engine.rootObjects()[0])[0], QQuickWindow)
        self.ctl.start()
        wait(1500)

    def device_id(self, name: str) -> str:
        return next(d["id"] for d in self.ctl.devices.all() if d["name"] == name)

    def item(self, name: str) -> QQuickItem:
        """Finds a visible item by objectName in the visual tree (incl. delegates and popups)."""
        root = self.win.contentItem()
        while root.parentItem() is not None:
            root = root.parentItem()
        stack = [root]
        while stack:
            it = stack.pop()
            if it.objectName() == name and it.isVisible():
                return it
            stack.extend(it.childItems())
        obj = self.win.findChild(QObject, name)
        if obj is None:
            raise SystemExit(f"QML item not found: {name}")
        return Shiboken.wrapInstance(Shiboken.getCppPointer(obj)[0], QQuickItem)

    def rect(self, name: str) -> QRectF:
        """Visible scene rectangle of an item (clipped by clipping ancestors)."""
        it = self.item(name)
        w = it.width()
        h = it.height()
        if name == "roomTabs":  # horizontal list: only the part covered by tabs
            w = min(w, it.property("contentWidth"))
        if name == "scenes":    # scrollable list: only the part covered by scenes
            h = min(h, it.property("contentHeight"))
        r = QRectF(it.mapToScene(QPointF(0, 0)), it.mapToScene(QPointF(w, h)))
        p = it.parentItem()
        while p is not None:
            if p.clip():
                r = r.intersected(QRectF(p.mapToScene(QPointF(0, 0)), p.mapToScene(QPointF(p.width(), p.height()))))
            p = p.parentItem()
        return r

    def click(self, x: float, y: float) -> None:
        QTest.mouseClick(self.win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPointF(x, y).toPoint())

    def key(self, k: Qt.Key, text: str = "") -> None:
        for t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QGuiApplication.sendEvent(self.win, QKeyEvent(t, k, Qt.KeyboardModifier.NoModifier, text))

    def grab(self) -> Image.Image:
        wait(500)
        img = self.win.grabWindow()
        tmp = Path(tempfile.mkdtemp()) / "shot.png"
        img.save(str(tmp))
        return Image.open(tmp).convert("RGB")

    def close(self) -> None:
        self.ctl.shutdown()
        self.win.close()
        self.engine.deleteLater()
        wait(100)


def annotate(img: Image.Image, callouts: list[tuple]) -> Image.Image:
    """Draws a box around each rectangle and a numbered badge.

    Each callout is (number, [rects]) or (number, [rects], "left"); "left" puts the
    badge outside the box on its left side (if there is room) so it covers no text.
    """
    img = img.copy()
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(FONT_DIR / "Jost-Medium.ttf"), 16)
    W, H = img.size
    badges: list[tuple[float, float]] = []
    for number, rects, *opt in callouts:
        for r in rects:
            x0, y0 = max(2, r.left() - 4), max(2, r.top() - 4)
            x1, y1 = min(W - 3, r.right() + 4), min(H - 3, r.bottom() + 4)
            d.rounded_rectangle((x0, y0, x1, y1), radius=8, outline=CALLOUT, width=2)
            if opt and opt[0] == "left" and x0 - 2 * BADGE_R - 6 >= 0:
                bx, by = x0 - BADGE_R - 4, y0 + min(y1 - y0, 44) / 2
            else:
                bx = min(max(BADGE_R + 2, x0), W - BADGE_R - 2)
                by = min(max(BADGE_R + 2, y0), H - BADGE_R - 2)
            while any(abs(bx - ox) < 2 * BADGE_R + 2 and abs(by - oy) < 2 * BADGE_R + 2 for ox, oy in badges):
                bx += 2 * BADGE_R + 4
            badges.append((bx, by))
            d.ellipse((bx - BADGE_R, by - BADGE_R, bx + BADGE_R, by + BADGE_R), fill=CALLOUT, outline="white", width=2)
            d.text((bx, by - 1), str(number), fill="white", font=font, anchor="mm")
    return img


def save(img: Image.Image, out: Path, name: str) -> None:
    path = out / f"{name}.png"
    img.save(path, optimize=True)
    print(f"  {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")


def home_callouts(p: Panel) -> list[tuple[int, list[QRectF]]]:
    lamp = p.device_id("Living Room Ceiling Light")
    heating = p.device_id("Living Room Heating")
    return [
        (1, [p.rect("clock").united(p.rect("date"))]),
        (2, [p.rect("climate")]),
        (3, [p.rect("scenes")]),
        (4, [p.rect("statusDot").united(p.rect("statusText"))]),
        (5, [p.rect("settingsButton")]),
        (6, [p.rect("roomTabs")]),
        (7, [p.rect(f"tile:{lamp}")]),
        (8, [p.rect(f"more:{lamp}")]),
        (9, [p.rect(f"tile:{heating}")]),
    ]


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "images"
    out.mkdir(parents=True, exist_ok=True)
    qInstallMessageHandler(on_message)
    app = QGuiApplication(sys.argv)  # noqa: F841
    load_fonts()

    # Home screen at every supported size
    for w, h in SIZES:
        p = Panel((w, h))
        p.win.setProperty("idle", False)
        save(annotate(p.grab(), home_callouts(p)), out, f"home-{w}x{h}")
        p.close()

    # Detail views, settings and keypad at the reference size
    p = Panel(DETAIL_SIZE)
    p.win.setProperty("openDevice", p.device_id("Living Room Heating"))
    save(annotate(p.grab(), [
        (1, [p.rect("backButton")]),
        (2, [p.rect("headerNote")], "left"),
        (3, [p.rect("dial")]),
        (4, [p.rect("minusButton"), p.rect("plusButton")]),
        (5, [p.rect("modes")], "left"),
    ]), out, "heating")

    tv = p.device_id("TV Light")
    p.ctl.setAttrs(tv, {"on": True, "brightness": 60, "hue": 200, "saturation": 70})
    wait(800)
    p.win.setProperty("openDevice", tv)
    save(annotate(p.grab(), [
        (1, [p.rect("brightnessBar")]),
        (2, [p.rect("colorWheel")]),
        (3, [p.rect("powerButton")]),
    ]), out, "light")

    kitchen = p.device_id("Kitchen Light")
    p.ctl.setAttrs(kitchen, {"on": True, "brightness": 80, "color_temp": 330})
    wait(800)
    p.win.setProperty("openDevice", kitchen)
    save(annotate(p.grab(), [
        (1, [p.rect("brightnessBar")]),
        (4, [p.rect("colorTemp")]),
        (3, [p.rect("powerButton")]),
    ]), out, "light-white-tone")

    p.win.setProperty("openDevice", "")
    p.win.setProperty("settingsOpen", True)
    wait(300)
    p.item("settingsFlick").setProperty("contentY", 0)
    save(annotate(p.grab(), [
        (1, [p.rect("section:display")], "left"),
        (2, [p.rect("section:homebridge")], "left"),
        (3, [p.rect("testButton")]),
        (4, [p.rect("applyButton")]),
    ]), out, "settings")

    p.item("settingsFlick").setProperty("contentY", 200)
    wait(300)
    pin_row = p.rect("row:hap_pin")
    p.click(pin_row.right() - 60, pin_row.center().y())
    wait(400)
    for digit in "12345":
        p.key(getattr(Qt.Key, f"Key_{digit}"), digit)
    save(annotate(p.grab(), [
        (1, [p.rect("keypadDisplay")], "left"),
        (2, [p.rect("keypadHint")], "left"),
        (3, [p.rect("keypadKeys")], "left"),
        (4, [p.rect("keypadDone")]),
    ]), out, "keypad")
    p.key(Qt.Key.Key_Escape)
    p.win.setProperty("settingsOpen", False)

    p.win.setProperty("idle", True)
    save(p.grab(), out, "screensaver")
    p.close()

    # Dark theme
    p = Panel(DETAIL_SIZE, theme="dark")
    save(p.grab(), out, "home-dark")
    p.win.setProperty("openDevice", p.device_id("Living Room Heating"))
    save(p.grab(), out, "heating-dark")
    p.close()

    if warnings:
        print("QML warnings:\n" + "\n".join(warnings))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
