"""Tests der Qt-Schicht ohne Bildschirm (offscreen)."""
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from app.config import AppConfig  # noqa: E402
from app.qt.controller import Controller  # noqa: E402
from app.settings import SettingsStore  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
U = lambda s: f"{int(s, 16):08X}-0000-1000-8000-0026BB765291"  # noqa: E731


@pytest.fixture(scope="module")
def qapp():
    return QGuiApplication.instance() or QGuiApplication([])


def pump_until(cond, timeout=6.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


class FakeHap(BaseHTTPRequestHandler):
    """Minimaler HAP-Server wie Homebridge im Insecure-Modus."""
    pin = "123-45-678"
    lamp_on = False

    def log_message(self, *a):
        pass

    def _send(self, code, body=None):
        data = json.dumps(body).encode() if body is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/hap+json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.headers.get("Authorization") != self.pin:
            return self._send(470, {"status": -70401})
        self._send(200, {"accessories": [{"aid": 2, "services": [
            {"iid": 1, "type": U("3E"), "characteristics": [{"iid": 2, "type": U("23"), "value": "Flurlicht", "perms": ["pr"]}]},
            {"iid": 9, "type": U("43"), "characteristics": [
                {"iid": 10, "type": U("25"), "value": FakeHap.lamp_on, "perms": ["pr", "pw"]}]}]}]})

    def do_PUT(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeHap.lamp_on = body["characteristics"][0]["value"]
        self._send(204)


@pytest.fixture(scope="module")
def hap_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeHap)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


def make_controller(tmp_path, **settings):
    store = SettingsStore(tmp_path / "settings.json")
    store.update({"hap_enabled": False, **settings})
    cfg = AppConfig.model_validate({"demo": {"enabled": True},
                                    "devices": {"Kaffeemaschine": {"room": "Küche"}}})
    return Controller(cfg, store)


def test_controller_demo_model_and_commands(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    model = ctl.devices
    assert pump_until(lambda: model.rowCount() == 8)
    assert ctl.statusOk and ctl.statusText == "Verbunden"
    assert "Küche" in ctl.rooms and ctl.indoorTemp != ""

    ctl.selectRoom("Küche")
    assert model.rowCount() == 1 and ctl.currentRoom == "Küche"
    coffee = model.data(model.index(0), list(model.roleNames())[model.ROLES.index("deviceId")])
    ctl.toggle(coffee)
    assert pump_until(lambda: ctl.device(coffee)["state"]["on"] is True)
    ctl.selectRoom("")
    assert model.rowCount() == 8

    errors = []
    ctl.toast.connect(errors.append)
    ctl.setAttrs(coffee, {"brightness": 50})
    assert pump_until(lambda: errors) and "unterstützt" in errors[0]
    ctl.shutdown()


def test_settings_reconnect_and_test_connection(qapp, tmp_path, hap_server):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: ctl.devices.rowCount() == 8)

    results = []
    ctl.settings.testFinished.connect(lambda ok, msg: results.append((ok, msg)))
    ctl.settings.testConnection("127.0.0.1", hap_server, "11111111")
    assert pump_until(lambda: results) and results[-1][0] is False and "PIN" in results[-1][1]
    ctl.settings.testConnection("127.0.0.1", float(hap_server), "12345678")
    assert pump_until(lambda: len(results) == 2) and results[-1] == (True, "Verbunden: 1 steuerbare Geräte gefunden")
    ctl.settings.testConnection("", hap_server, "123-45-678")
    assert pump_until(lambda: len(results) == 3) and results[-1][0] is False

    assert ctl.settings.save({"hap_port": 0}) == {"hap_port": "Erlaubt sind 1 bis 65535"}
    assert ctl.settings.save({"hap_enabled": True, "hap_host": "127.0.0.1",
                              "hap_port": hap_server, "hap_pin": "12345678"}) == {}
    lamp = "homebridge:2.9"
    assert pump_until(lambda: ctl.device(lamp).get("name") == "Flurlicht")
    assert pump_until(lambda: ctl.devices.rowCount() == 9 and ctl.statusOk)
    ctl.toggle(lamp)
    assert pump_until(lambda: FakeHap.lamp_on is True)
    assert json.loads((tmp_path / "settings.json").read_text())["hap_pin"] == "123-45-678"
    ctl.shutdown()


def test_theme_setting(qapp, tmp_path):
    ctl = make_controller(tmp_path, theme="dark", idle_seconds=300)
    assert ctl.theme == "dark" and ctl.idleSeconds == 300
    seen = []
    ctl.themeChanged.connect(lambda: seen.append(ctl.theme))
    ctl.settings.save({"theme": "light"})
    assert ctl.theme == "light" and seen == ["light"]
    ctl.shutdown()


def test_qml_loads_without_warnings(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "screenshots.py"), str(tmp_path), "--theme", "dark"],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "dark-einstellungen.png").stat().st_size > 10_000
