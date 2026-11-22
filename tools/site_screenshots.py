"""Regenerates the clean (unannotated) screenshots for the project page in site/assets/screens.

    python tools/site_screenshots.py

Runs the panel headless with demo devices (same harness as tools/doc_screenshots.py)
and saves WebP files. Needs Pillow with WebP support.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import doc_screenshots as ds  # noqa: E402  (sets QT_QPA_PLATFORM=offscreen)
from PIL import Image  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

OUT = ROOT / "site" / "assets" / "screens"
CATEGORIES = ("favorites", "light", "scenes", "climate", "weather", "energy", "security")


def save(p: ds.Panel, name: str) -> None:
    p.grab().save(OUT / f"{name}.webp", "WEBP", quality=88, method=6)


def populate(p: ds.Panel) -> None:
    """Scenes, favorites and the guest Wi-Fi tile, so every menu entry has something to show."""
    room = "Living Room" if "Living Room" in p.ctl.rooms else p.ctl.rooms[0]
    p.ctl.selectRoom(room)
    rows = p.ctl.sceneDraft("")["devices"]
    p.ctl.saveScene("", "Movie night", room, {r["id"]: {"on": False} for r in rows[:2]}, True)
    p.ctl.saveScene("", "Reading", room, {r["id"]: r["attrs"] for r in rows})
    p.ctl.saveScene("", "Good morning", room, {r["id"]: r["attrs"] for r in rows[1:]})
    for name in ("Living Room Ceiling Light", "Living Room Heating", "Front Door Lock",
                 "Coffee Maker", "Living Room Blinds", "Kitchen Light"):
        p.ctl.roomEditor.saveDevice(p.device_id(name), {"favorite": True})
    p.ctl.settings.save({"wifi_ssid": "Holiday Home Guests", "wifi_password": "sunny-days-42",
                         "wifi_favorite": True})
    ds.wait(600)


def home(size, theme, prefix, lang="en", cats=CATEGORIES) -> ds.Panel:
    p = ds.Panel(size, theme=theme, lang=lang)
    populate(p)
    for c in cats:
        p.ctl.selectCategory(c)
        p.ctl.selectRoom("" if c != "scenes" else "Living Room")
        save(p, f"{prefix}-home-{c}")
    return p


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    QGuiApplication(sys.argv)
    ds.load_fonts()
    home((1280, 800), "light", "light", cats=("light",)).close()   # day/night comparison
    for theme in ("dark",):
        p = home((1280, 800), theme, theme)
        for dev, name in (("Living Room Heating", "heating"), ("TV Light", "light"),
                          ("Weather Station", "sensor"), ("Living Room Blinds", "blinds")):
            p.win.setProperty("openDevice", p.device_id(dev))
            save(p, f"{theme}-{name}")
        p.win.setProperty("openDevice", "")
        p.close()
    # Security: alarm system, PIN, smoke alarm, garage door, batteries
    p = ds.Panel((1280, 800), theme="dark")
    p.store.update({"alarm_pin": "1234"})
    aid = p.device_id("Alarm System")
    p.ctl.setAttrs(aid, {"mode": "away"})
    ds.wait(5000)       # the demo alarm system follows its target with the next poll
    p.win.setProperty("openDevice", aid)
    save(p, "dark-alarm-system")
    off = p.rect("alarmMode:off")
    p.click(off.center().x(), off.center().y())
    save(p, "dark-alarm-pin")
    p.close()

    p = ds.Panel((1280, 800), theme="dark")
    p.ctl.selectCategory("security")
    p.ctl.selectRoom("")
    smoke = p.device_id("Hall Smoke Detector")
    d = p.ctl.devices.get(smoke)
    p.ctl._on_message({"type": "device", "device": {**d, "state": {**d.get("state", {}), "triggered": True}}})
    ds.wait(600)
    save(p, "dark-smoke-alarm")
    p.close()

    p = ds.Panel((1280, 800), theme="dark")
    p.store.update({"alarm_pin": "1234"})
    p.ctl.selectCategory("security")
    p.ctl.selectRoom("")
    ds.wait(300)
    tile = p.rect(f"tile:{p.device_id('Garage Door')}")
    p.click(tile.center().x(), tile.center().y())
    save(p, "dark-garage-confirm")
    p.close()

    p = ds.Panel((1280, 800), theme="dark")
    vid = p.device_id("Garden Sprinkler")
    p.ctl.toggle(vid)
    ds.wait(600)
    p.win.setProperty("openDevice", vid)
    save(p, "dark-valve")
    p.win.setProperty("openDevice", "")
    p.win.setProperty("settingsOpen", True)
    ds.wait(300)
    row = p.rect("row:batteries_page")
    p.click(row.center().x(), row.center().y())
    save(p, "dark-batteries")
    p.close()

    # History charts, power, guest Wi-Fi, screen saver with weather
    p = ds.Panel((1280, 800), theme="dark")
    populate(p)
    p.win.setProperty("openDevice", p.device_id("Weather Station"))
    ds.wait(400)
    tab = p.rect("detailHistory")
    p.click(tab.center().x(), tab.center().y())
    ds.wait(600)
    seven = p.rect("historyRange:7")
    p.click(seven.center().x(), seven.center().y())
    ds.wait(600)
    plot = p.rect("historyPlot")
    p.click(plot.x() + plot.width() * 0.62, plot.center().y())
    save(p, "dark-history")
    p.win.setProperty("openDevice", "")
    ds.wait(200)
    p.win.setProperty("openDevice", p.device_id("Washing Machine"))
    ds.wait(500)
    tab = p.rect("detailHistory")
    p.click(tab.center().x(), tab.center().y())
    ds.wait(600)
    seven = p.rect("historyRange:7")
    p.click(seven.center().x(), seven.center().y())
    ds.wait(800)
    save(p, "dark-history-power")
    p.win.setProperty("openDevice", "")
    p.ctl.selectCategory("favorites")
    ds.wait(400)
    tile = p.rect("tile:wifi:guest")
    p.click(tile.center().x(), tile.center().y())
    ds.wait(600)
    save(p, "dark-wifi-code")
    p.key(ds.Qt.Key.Key_Escape)
    ds.wait(300)
    p.win.setProperty("idle", True)
    ds.wait(900)
    save(p, "dark-screensaver")
    p.close()

    # Dark blue theme
    home((1280, 800), "blue", "blue", cats=("light",)).close()
    for size, tag in (((720, 720), "720x720"), ((800, 480), "800x480"),
                      ((720, 1280), "720x1280"), ((1024, 600), "1024x600")):
        home(size, "dark", f"dark-{tag}", cats=("light",)).close()
    for lang in ("de", "fr", "it", "es", "pt"):
        home((1280, 800), "dark", f"dark-{lang}", lang=lang, cats=("light",)).close()
    print(f"saved to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
