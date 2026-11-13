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
from PySide6.QtCore import (Q_ARG, QEvent, QEventLoop, QMetaObject, QObject, QPointF, QRectF, Qt,  # noqa: E402
                            QTimer, qInstallMessageHandler)
from PySide6.QtGui import QGuiApplication, QKeyEvent  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from shiboken6 import Shiboken  # noqa: E402

from app.config import load_config  # noqa: E402
from app.qt.controller import Controller  # noqa: E402
from app.qt.main import FONT_DIR, QML_DIR, load_fonts  # noqa: E402
from app.qt.translator import CatalogTranslator
from app.settings import SettingsStore  # noqa: E402

# Screen sizes documented: (width, height, file suffix)
SIZES = [(800, 480), (1024, 600), (1280, 720), (1280, 800), (720, 720), (720, 1280)]
DETAIL_SIZE = (1280, 800)          # primary display; detail views also at 720×720
SQUARE_SIZE = (720, 720)

# Annotation style: numbered badges in the side margins with leader lines ending in a dot on
# the element, legend below the screenshot. Blue callouts stay clear of the gold UI accent.
CANVAS = (255, 255, 255)
FRAME = (210, 214, 220)
CALLOUT = (37, 99, 235)        # callout color (badges, leader lines, dots)
BADGE_INK = (255, 255, 255)
TEXT = (40, 44, 52)
BADGE_R = 13
MARGIN = 64          # left/right margin for badges

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

    def __init__(self, size: tuple[int, int], theme: str = "light", lang: str = "en"):
        cfg = load_config(ROOT / "config.example.yaml")
        cfg.demo.enabled = True
        self.store = SettingsStore(Path(tempfile.mkdtemp()) / "settings.json")
        self.store.update({"hap_enabled": False, "theme": theme, "language": lang})
        self.ctl = Controller(cfg, self.store, ROOT / "config.example.yaml")
        self.translator = CatalogTranslator()
        QGuiApplication.instance().installTranslator(self.translator)
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
        QGuiApplication.instance().removeTranslator(self.translator)
        self.engine.deleteLater()
        wait(100)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / f"Jost-{name}.ttf"), size)


def _badge(d: ImageDraw.ImageDraw, x: float, y: float, number: int) -> None:
    d.ellipse((x - BADGE_R, y - BADGE_R, x + BADGE_R, y + BADGE_R), fill=CALLOUT)
    d.text((x, y), str(number), fill=BADGE_INK, font=_font("Medium", 15), anchor="mm")


def annotate(img: Image.Image, callouts: list[tuple], title: str = "") -> Image.Image:
    """Places the screenshot on a canvas with numbered badges and a legend below.

    Each callout is (number, [rects], label) or (number, [rects], label, side) with side
    "left", "right", "top" or "bottom". By default the badge goes to the screenshot edge that
    is nearest to the element, so the leader line stays short and crosses little else. The
    line ends in a dot on the element's edge. Elements scrolled out of view get no badge.
    """
    w, h = img.size
    entries = []          # [side, badge position along the edge, target x, target y, number]
    for number, rects, label, *opt in callouts:
        for r in rects:
            if r.width() <= 1 or r.height() <= 1:
                continue
            dist = {"left": r.left(), "right": w - r.right(), "top": r.top(), "bottom": h - r.bottom()}
            side = opt[0] if opt else min(dist, key=dist.get)
            cx = min(max(r.center().x(), 2), w - 2)
            cy = min(max(r.center().y(), 2), h - 2)
            tx, ty = {"left": (r.left(), cy), "right": (r.right(), cy),
                      "top": (cx, r.top()), "bottom": (cx, r.bottom())}[side]
            tx, ty = min(max(tx, 2), w - 2), min(max(ty, 2), h - 2)
            entries.append([side, ty if side in ("left", "right") else tx, tx, ty, number])

    # keep badges on each edge apart
    gap = 2 * BADGE_R + 6
    for side in ("left", "right", "top", "bottom"):
        col = sorted((e for e in entries if e[0] == side), key=lambda e: e[1])
        for prev, cur in zip(col, col[1:]):
            cur[1] = max(cur[1], prev[1] + gap)

    legend = sorted({(n, label) for n, _, label, *_ in callouts})
    title_h = 44 if title else 0
    legend_h = (24 + title_h + len(legend) * 34) if legend else (title_h + 16 if title else 0)
    top = MARGIN
    W = w + 2 * MARGIN
    H = top + h + MARGIN + legend_h + 24
    canvas = Image.new("RGB", (W, H), CANVAS)
    canvas.paste(img, (MARGIN, top))
    d = ImageDraw.Draw(canvas)
    d.rectangle((MARGIN - 1, top - 1, MARGIN + w, top + h), outline=FRAME, width=1)

    for side, pos, tx, ty, number in entries:
        px, py = MARGIN + tx, top + ty
        if side in ("left", "right"):
            bx, by = (MARGIN / 2 if side == "left" else W - MARGIN / 2), top + pos
            knee = (bx + (BADGE_R + 10) * (1 if side == "left" else -1), by)
        else:
            bx, by = MARGIN + pos, (top / 2 if side == "top" else top + h + MARGIN / 2)
            knee = (bx, by + (BADGE_R + 10) * (1 if side == "top" else -1))
        straight = abs((by - py) if side in ("left", "right") else (bx - px)) <= 1
        d.line([(bx, by), (px, py)] if straight else [(bx, by), knee, (px, py)],
               fill=CALLOUT, width=2, joint="curve")
        d.ellipse((px - 5, py - 5, px + 5, py + 5), fill=CALLOUT, outline=CANVAS, width=2)
        _badge(d, bx, by, number)

    y = top + h + MARGIN
    if title:
        d.text((MARGIN - 18, y), title, fill=TEXT, font=_font("Medium", 22), anchor="lm")
        y += title_h
    for number, label in legend:
        _badge(d, MARGIN - 18 + BADGE_R, y, number)
        d.text((MARGIN - 18 + 2 * BADGE_R + 12, y), label, fill=TEXT, font=_font("Regular", 18), anchor="lm")
        y += 34
    return canvas


def save(img: Image.Image, out: Path, name: str) -> None:
    path = out / f"{name}.png"
    img.save(path, optimize=True)
    print(f"  {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")


def home_callouts(p: Panel, top_layout: bool) -> list[tuple]:
    lamp = p.device_id("Living Room Ceiling Light")
    status = p.rect("statusDot") if top_layout else p.rect("statusDot").united(p.rect("statusText"))
    out = [(1, [p.rect("clock")], "Clock" if top_layout else "Clock and date")]
    if not top_layout:
        out.append((2, [p.rect("climate")], "Indoor and outdoor temperature"))
    out += [
        (3, [p.rect("categoryMenu")], "Menu: lights, climate, scenes, security", *(["top"] if top_layout else ["left"])),
        (4, [status], "Connection status"),
        (5, [p.rect("settingsButton")], "Settings"),
        (6, [p.rect("roomTabs")], "Rooms; “All” comes last", *([] if top_layout else ["top"])),
        (7, [p.rect(f"tile:{lamp}")], "Device that is on (tap to switch)"),
        (8, [p.rect(f"more:{lamp}")], "Open controls"),
    ]
    return [(i, *c[1:]) for i, c in enumerate(out, 1)]


def menu_views(p: Panel, out: Path, size: str, suffix: str = "") -> None:
    """Climate, scenes and security as chosen in the menu."""
    p.win.setProperty("openDevice", "")
    p.ctl.selectCategory("climate")
    save(annotate(p.grab(), [
        (1, [p.rect("category:climate")], "Climate", "left" if not suffix else "top"),
        (2, [p.rect(f"tile:{p.device_id('Living Room Heating')}")], "Heating tile"),
        (3, [p.rect(f"tile:{p.device_id('Weather Station')}")], "Sensor tile"),
    ], f"Climate – {size}"), out, f"home-climate{suffix}")
    p.ctl.selectCategory("scenes")
    save(annotate(p.grab(), [
        (1, [p.rect("category:scenes")], "Scenes", "left" if not suffix else "top"),
        (2, [p.rect("scene:movie")], "Scene of a room (tap to run)"),
        (3, [p.rect("scene:all-off")], "Scene for the whole house"),
    ], f"Scenes – {size}"), out, f"home-scenes{suffix}")
    p.ctl.selectCategory("security")
    save(annotate(p.grab(), [
        (1, [p.rect("category:security")], "Security with number of alerts", "left" if not suffix else "top"),
        (2, [p.rect(f"tile:{p.device_id('Bedroom Window')}")], "Open window (shown first)"),
        (3, [p.rect(f"tile:{p.device_id('Terrace Glass Break')}")], "Glass break sensor"),
    ], f"Security – {size}"), out, f"home-security{suffix}")
    leak = p.device_id("Washing Machine Leak")
    d = p.ctl.devices.get(leak)
    p.ctl._on_message({"type": "device", "device": {**d, "state": {"triggered": True}}})
    wait(300)
    save(annotate(p.grab(), [
        (1, [p.rect(f"tile:{leak}")], "Alarm: leak or glass break"),
    ], f"Alarm – {size}"), out, f"home-alarm{suffix}")
    p.ctl._on_message({"type": "device", "device": {**d, "state": {"triggered": False}}})
    p.ctl.selectCategory("light")


def detail_views(p: Panel, out: Path, suffix: str, size: str) -> None:
    p.win.setProperty("openDevice", p.device_id("Living Room Heating"))
    save(annotate(p.grab(), [
        (1, [p.rect("backButton")], "Back to the room"),
        (2, [p.rect("headerNote")], "Status"),
        (3, [p.rect("dial")], "Dial: drag to set the target temperature", "top"),
        (4, [p.rect("minusButton"), p.rect("plusButton")], "Cooler / warmer"),
        (5, [p.rect("modes")], "Mode"),
    ], f"Thermostat – {size}"), out, f"heating{suffix}")

    tv = p.device_id("TV Light")
    p.ctl.setAttrs(tv, {"on": True, "brightness": 60, "hue": 200, "saturation": 70})
    wait(800)
    p.win.setProperty("openDevice", tv)
    save(annotate(p.grab(), [
        (1, [p.rect("brightnessBar")], "Brightness", "left"),
        (2, [p.rect("colorWheel")], "Color wheel", "right"),
        (3, [p.rect("powerButton")], "Power", "bottom"),
    ], f"Color light – {size}"), out, f"light{suffix}")

    kitchen = p.device_id("Kitchen Light")
    p.ctl.setAttrs(kitchen, {"on": True, "brightness": 80, "color_temp": 330})
    wait(800)
    p.win.setProperty("openDevice", kitchen)
    save(annotate(p.grab(), [
        (1, [p.rect("brightnessBar")], "Brightness", "left"),
        (4, [p.rect("colorTemp")], "White tone", "right"),
        (3, [p.rect("powerButton")], "Power", "bottom"),
    ], f"White light – {size}"), out, f"light-white-tone{suffix}")

    p.win.setProperty("openDevice", p.device_id("Weather Station"))
    save(annotate(p.grab(), [
        (1, [p.rect("headerNote")], "Outdoor sensor"),
        (2, [p.rect("reading:temp")], "Temperature", "bottom"),
        (3, [p.rect("reading:humidity")], "Humidity", "bottom"),
        (4, [p.rect("reading:pressure")], "Air pressure", "bottom"),
    ], f"Weather station – {size}"), out, f"sensor{suffix}")
    p.win.setProperty("openDevice", p.device_id("Hall Light Sensor"))
    save(annotate(p.grab(), [(5, [p.rect("reading:lux")], "Light level")], f"Light sensor – {size}"),
         out, f"sensor-light{suffix}")

    p.win.setProperty("openDevice", p.device_id("Living Room Blinds"))
    save(annotate(p.grab(), [
        (1, [p.rect("blindVisual")], "Blind: drag to set the position", "left"),
        (2, [p.rect("blindPosition")], "Position", "right"),
        (3, [p.rect("openButton").united(p.rect("closeButton"))], "Open, stop, close", "right"),
        (4, [p.rect("tiltSlider")], "Slat angle", "right"),
    ], f"Blinds – {size}"), out, f"blinds{suffix}")
    p.win.setProperty("openDevice", "")


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
        save(annotate(p.grab(), home_callouts(p, w / h < 1.4), f"Home screen – {w} × {h}"), out, f"home-{w}x{h}")
        p.close()

    # Detail views at the primary size (1280×800) and at 720×720
    square = Panel(SQUARE_SIZE)
    detail_views(square, out, "-720x720", "720 × 720")
    menu_views(square, out, "720 × 720", "-720x720")
    square.close()
    p = Panel(DETAIL_SIZE)
    detail_views(p, out, "", "1280 × 800")
    menu_views(p, out, "1280 × 800")

    # Settings, keypad and screen saver at the primary size

    p.win.setProperty("openDevice", "")
    p.win.setProperty("settingsOpen", True)
    wait(300)
    p.item("settingsFlick").setProperty("contentY", 0)
    save(annotate(p.grab(), [
        (1, [p.rect("section:display")], "Display settings (saved immediately)", "left"),
        (2, [p.rect("section:rooms")], "Rooms and devices", "left"),
        (3, [p.rect("section:homebridge")], "Homebridge connection", "left"),
        (4, [p.rect("testButton")], "Test connection", "bottom"),
        (5, [p.rect("applyButton")], "Apply", "bottom"),
    ], "Settings"), out, "settings")

    rooms_row = p.rect("row:rooms_page")
    p.click(rooms_row.center().x(), rooms_row.center().y())
    wait(400)
    rooms_flick = p.item("roomsFlick")
    rooms_flick.setProperty("contentY", max(0, rooms_flick.property("contentHeight") - rooms_flick.height()))
    save(annotate(p.grab(), [
        (1, [p.rect("tab:rooms"), p.rect("tab:devices")], "Rooms / Devices", "top"),
        (2, [p.rect("room:Hall")], "Room with number of devices", "left"),
        (3, [p.rect("rename:Kitchen")], "Move up/down, rename, delete", "right"),
        (4, [p.rect("addRoom")], "Add room", "bottom"),
    ], "Rooms and devices"), out, "rooms")
    rename = p.rect("rename:Kitchen")
    p.click(rename.center().x(), rename.center().y())
    wait(400)
    save(annotate(p.grab(), [
        (1, [p.rect("keyboardInput")], "Name (first key replaces it)", "left"),
        (2, [p.rect("keyboardKeys")], "Keys in the panel language; ?123 for digits and accents", "left"),
        (3, [p.rect("keyboardDone")], "Done", "bottom"),
    ], "Keyboard for names"), out, "keyboard")
    p.key(Qt.Key.Key_Escape)
    wait(300)
    devices_tab = p.rect("tab:devices")
    p.click(devices_tab.center().x(), devices_tab.center().y())
    wait(400)
    door = next(d for d in p.ctl.roomEditor.devices if d["name"] == "Terrace Door")
    QMetaObject.invokeMethod(p.engine.rootObjects()[0].findChild(QObject, "deviceEditor"), "edit", Q_ARG("QVariant", door))
    wait(400)
    save(annotate(p.grab(), [
        (1, [p.rect("deviceName")], "Display name (tap to change)", "left"),
        (2, [p.rect("kindChoices")], "Kind: window, door or glass break", "left"),
        (3, [p.rect("roomChoices")], "Room; “New room …” creates one", "left"),
        (4, [p.rect("deviceSave")], "Save", "bottom"),
    ], "Edit device"), out, "device-editor")
    p.key(Qt.Key.Key_Escape)
    wait(300)
    p.win.setProperty("settingsOpen", False)
    wait(300)
    p.win.setProperty("settingsOpen", True)
    wait(300)

    p.item("settingsFlick").setProperty("contentY", 350)
    wait(300)
    pin_row = p.rect("row:hap_pin")
    p.click(pin_row.right() - 60, pin_row.center().y())
    wait(400)
    for digit in "12345":
        p.key(getattr(Qt.Key, f"Key_{digit}"), digit)
    save(annotate(p.grab(), [
        (1, [p.rect("keypadDisplay")], "Entry (first key replaces the old value)", "left"),
        (2, [p.rect("keypadHint")], "Format hint or error", "left"),
        (3, [p.rect("keypadKeys")], "Keys", "left"),
        (4, [p.rect("keypadDone")], "Done", "bottom"),
    ], "Keypad"), out, "keypad")
    p.key(Qt.Key.Key_Escape)
    wait(300)

    flick = p.item("settingsFlick")
    flick.setProperty("contentY", max(0, flick.property("contentHeight") - flick.height()))
    wait(300)
    save(annotate(p.grab(), [
        (1, [p.rect("section:system")], "System", "left"),
        (2, [p.rect("action:restart_app")], "Restart app", "right"),
        (3, [p.rect("action:reboot")], "Restart Raspberry Pi", "right"),
    ], "Settings: System"), out, "settings-system")

    reboot = p.rect("action:reboot")
    p.click(reboot.center().x(), reboot.center().y())
    wait(400)
    save(annotate(p.grab(), [
        (1, [p.rect("confirmCancel")], "Cancel", "bottom"),
        (2, [p.rect("confirmOk")], "Restart", "bottom"),
    ], "Confirmation"), out, "confirm-restart")
    p.key(Qt.Key.Key_Escape)
    p.win.setProperty("settingsOpen", False)

    p.win.setProperty("idle", True)
    wait(900)   # let the fade-in finish
    save(annotate(p.grab(), [], "Screen saver"), out, "screensaver")
    p.close()

    # Dark theme
    p = Panel(DETAIL_SIZE, theme="dark")
    save(annotate(p.grab(), [], "Home screen, dark"), out, "home-dark")
    p.win.setProperty("openDevice", p.device_id("Living Room Heating"))
    save(annotate(p.grab(), [], "Thermostat, dark"), out, "heating-dark")
    p.close()

    # Another language
    p = Panel(DETAIL_SIZE, lang="de")
    save(annotate(p.grab(), [], "Home screen in German"), out, "home-de")
    p.win.setProperty("settingsOpen", True)
    wait(300)
    save(annotate(p.grab(), [(1, [p.rect("row:language")], "Language", "left")], "Settings in German"),
         out, "settings-de")
    p.close()

    if warnings:
        print("QML warnings:\n" + "\n".join(warnings))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
