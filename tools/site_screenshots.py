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
CATEGORIES = ("light", "climate", "scenes", "security")


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
    for size, tag in (((720, 720), "720x720"), ((800, 480), "800x480"),
                      ((720, 1280), "720x1280"), ((1024, 600), "1024x600")):
        home(size, "dark", f"dark-{tag}", cats=("light",)).close()
    for lang in ("de", "fr", "it", "es"):
        home((1280, 800), "dark", f"dark-{lang}", lang=lang, cats=("light",)).close()
    print(f"saved to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
