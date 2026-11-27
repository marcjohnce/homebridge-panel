"""Screenshots of the web setup for the documentation, with the demo devices.

    QT_QPA_PLATFORM=offscreen python tools/web_screenshots.py OUTPUT_DIR [--chrome /usr/bin/google-chrome]

Needs Playwright (pip install playwright) and a Chrome or Chromium. Fails on JavaScript errors.
"""
from __future__ import annotations

import argparse
import socket
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from app.config import AppConfig  # noqa: E402
from app.qt.controller import Controller  # noqa: E402
from app.settings import SettingsStore  # noqa: E402


def shots(base: str, code: str, out: Path, chrome: str, errors: list[str]) -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chrome or None)
        page = browser.new_page(viewport={"width": 1280, "height": 860}, color_scheme="light")
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base)
        page.wait_for_selector("#code")
        page.screenshot(path=str(out / "web-pair.png"))
        page.fill("#code", code)
        page.get_by_role("button").first.click()
        page.wait_for_selector("nav")
        page.screenshot(path=str(out / "web-settings.png"))
        tabs = page.locator("nav button")
        for i, name in ((2, "web-devices"), (3, "web-virtual"), (4, "web-scenes")):
            tabs.nth(i).click()
            page.wait_for_timeout(300)
            if name == "web-devices":
                page.locator("main .row button").first.click()
            elif name == "web-virtual":
                page.locator("main .btns button").first.click()
            else:
                page.locator("main .btns button").last.click()
            page.wait_for_timeout(300)
            page.screenshot(path=str(out / f"{name}.png"))
        phone = browser.new_page(viewport={"width": 390, "height": 844}, color_scheme="dark",
                                 extra_http_headers={})
        phone.context.add_cookies(page.context.cookies())
        phone.on("pageerror", lambda e: errors.append(str(e)))
        phone.goto(base)
        phone.wait_for_selector("nav")
        phone.locator("nav button").nth(1).click()
        phone.wait_for_timeout(300)
        phone.screenshot(path=str(out / "web-phone.png"))
        browser.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--chrome", default="")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    app = QGuiApplication(sys.argv)  # noqa: F841
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    store = SettingsStore(Path(tempfile.mkdtemp()) / "settings.json")
    store.update({"hap_enabled": False, "language": "en", "web_enabled": True, "web_port": port,
                  "panel_name": "Kitchen"})
    ctl = Controller(AppConfig.model_validate({"demo": {"enabled": True}}), store)
    ctl.start()
    code = ctl.web.newCode()["code"].replace(" ", "")
    errors: list[str] = []
    done = threading.Event()
    failure: list[BaseException] = []

    def run() -> None:
        try:
            shots(f"http://127.0.0.1:{port}/", code, out, args.chrome, errors)
        except BaseException as e:  # noqa: BLE001
            failure.append(e)
        done.set()
    QTimer.singleShot(1500, lambda: threading.Thread(target=run, daemon=True).start())
    timer = QTimer(interval=100, timeout=lambda: app.quit() if done.is_set() else None)
    timer.start()
    app.exec()
    ctl.shutdown()
    if failure:
        raise failure[0]
    if errors:
        print("JavaScript errors:", *errors, sep="\n  ")
        return 1
    print("Saved to", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
