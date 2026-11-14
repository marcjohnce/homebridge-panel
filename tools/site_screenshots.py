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
CATEGORIES = ("light", "climate", "security")


def save(p: ds.Panel, name: str) -> None:
    p.grab().save(OUT / f"{name}.webp", "WEBP", quality=88, method=6)


def home(size, theme, prefix, lang="en", cats=CATEGORIES) -> ds.Panel:
    p = ds.Panel(size, theme=theme, lang=lang)
    for c in cats:
        p.ctl.selectCategory(c)
        p.ctl.selectRoom("")
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
