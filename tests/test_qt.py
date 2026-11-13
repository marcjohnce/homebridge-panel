"""Tests of the Qt layer without a screen (offscreen)."""
import gc
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


@pytest.fixture(autouse=True)
def collect_in_main_thread():
    """Free the Qt objects of a test here, not later from a background thread (which crashes Qt)."""
    yield
    gc.collect()


def pump_until(cond, timeout=6.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


class FakeHap(BaseHTTPRequestHandler):
    """Minimal HAP server, like Homebridge in insecure mode."""
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
            {"iid": 1, "type": U("3E"), "characteristics": [{"iid": 2, "type": U("23"), "value": "Hall Light", "perms": ["pr"]}]},
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
    store.update({"hap_enabled": False, "language": "en", **settings})
    cfg = AppConfig.model_validate({"demo": {"enabled": True},
                                    "devices": {"Coffee Maker": {"room": "Kitchen"}}})
    return Controller(cfg, store)


def test_controller_demo_model_and_commands(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    model = ctl.devices
    assert pump_until(lambda: len(model.all()) == 17)
    assert ctl.statusOk and ctl.statusText == "Connected"
    assert "Kitchen" in ctl.rooms and ctl.indoorTemp != ""

    ctl.selectRoom("Kitchen")
    assert model.rowCount() == 1 and ctl.currentRoom == "Kitchen"
    coffee = model.data(model.index(0), list(model.roleNames())[model.ROLES.index("deviceId")])
    ctl.toggle(coffee)
    assert pump_until(lambda: ctl.device(coffee)["state"]["on"] is True)
    ctl.selectRoom("")
    assert model.rowCount() == 7 and ctl.category == "light"      # lights, plugs, blinds
    ctl.selectCategory("climate")
    assert model.rowCount() == 6 and "Kitchen" not in ctl.rooms
    ctl.selectCategory("security")
    assert model.rowCount() == 4 and ctl.securityCount == 1       # the bedroom window is open
    assert ctl.devices.get(model._rows[0])["name"] == "Bedroom Window"     # alerts first
    ctl.selectCategory("")
    assert model.rowCount() == 17

    errors = []
    ctl.toast.connect(errors.append)
    ctl.setAttrs(coffee, {"brightness": 50})
    assert pump_until(lambda: errors) and "does not support" in errors[0]
    ctl.shutdown()


def test_settings_reconnect_and_test_connection(qapp, tmp_path, hap_server):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 17)

    results = []
    ctl.settings.testFinished.connect(lambda ok, msg: results.append((ok, msg)))
    ctl.settings.testConnection("127.0.0.1", hap_server, "11111111")
    assert pump_until(lambda: results) and results[-1][0] is False and "PIN" in results[-1][1]
    ctl.settings.testConnection("127.0.0.1", float(hap_server), "12345678")
    assert pump_until(lambda: len(results) == 2) and results[-1] == (True, "Connected: found 1 controllable devices")
    ctl.settings.testConnection("", hap_server, "123-45-678")
    assert pump_until(lambda: len(results) == 3) and results[-1][0] is False

    assert ctl.settings.save({"hap_port": 0}) == {"hap_port": "Allowed range is 1 to 65535"}
    assert ctl.settings.save({"hap_enabled": True, "hap_host": "127.0.0.1",
                              "hap_port": hap_server, "hap_pin": "12345678"}) == {}
    lamp = "homebridge:2.9"
    assert pump_until(lambda: ctl.device(lamp).get("name") == "Hall Light")
    assert pump_until(lambda: len(ctl.devices.all()) == 18 and ctl.statusOk)
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


@pytest.mark.parametrize("size", ["1024x600", "1280x800", "720x720"])
def test_qml_loads_without_warnings(tmp_path, size):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "screenshots.py"), str(tmp_path),
                        "--theme", "dark", "--size", size], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "dark-settings.png").stat().st_size > 10_000


def test_restart_app_action(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.restart_argv = ["/usr/bin/python3", "-m", "app", "--fullscreen"]
    calls, messages = [], []
    ctl._exec = lambda path, argv: calls.append((path, argv))
    ctl.restarting.connect(messages.append)
    ctl.start()
    ctl.settings.runAction("restart_app")
    assert pump_until(lambda: calls)
    assert calls == [("/usr/bin/python3", ["/usr/bin/python3", "-m", "app", "--fullscreen"])]
    assert messages == ["Restarting the app …"]
    ctl.shutdown()


def test_reboot_action(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    toasts, messages = [], []
    ctl.toast.connect(toasts.append)
    ctl.restarting.connect(messages.append)
    ctl.reboot_command = ["true"]
    ctl.settings.runAction("reboot")
    assert pump_until(lambda: messages) and messages == ["Restarting the Raspberry Pi …"]
    time.sleep(0.5)
    QCoreApplication.processEvents()
    assert toasts == []

    ctl.reboot_command = ["sh", "-c", "echo 'Access denied' >&2; exit 1"]
    ctl.settings.runAction("reboot")
    assert pump_until(lambda: toasts)
    assert toasts[0].startswith("Restart not allowed") and "Access denied" in toasts[0]
    assert messages[-1] == ""       # overlay hidden again
    ctl.settings.runAction("nonsense")
    assert pump_until(lambda: len(toasts) == 2) and "Unknown action" in toasts[1]
    ctl.shutdown()


def test_indoor_and_outdoor_temperature(qapp, tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.update({"hap_enabled": False})
    cfg = AppConfig.model_validate({"demo": {"enabled": True},
                                    "devices": {"Weather Station": {"outdoor": True}}})
    ctl = Controller(cfg, store)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 17 and ctl.outdoorTemp != "")
    devs = ctl.devices.all()
    outdoor = [d["state"]["current_temp"] for d in devs if d.get("meta", {}).get("outdoor")]
    indoor = [d["state"]["current_temp"] for d in devs
              if d["state"].get("current_temp") is not None and not d.get("meta", {}).get("outdoor")]
    assert len(outdoor) == 1 and len(indoor) == 3        # weather station / 2 thermostats + climate sensor
    assert abs(float(ctl.outdoorTemp) - outdoor[0]) < 0.06
    assert abs(float(ctl.indoorTemp) - sum(indoor) / len(indoor)) < 0.06
    ws = next(d for d in devs if d["name"] == "Weather Station")
    assert ctl.device(ws["id"])["stateText"].count(",") == 2      # temperature, humidity, pressure
    ctl.shutdown()


def test_blind_detail_drag_sets_position(qapp, tmp_path):
    """Tapping the drawn blind at 3/4 of its height closes it to about 25% open."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow
    from PySide6.QtTest import QTest
    from shiboken6 import Shiboken
    from app.qt.main import QML_DIR

    ctl = make_controller(tmp_path)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("panel", ctl)
    engine.rootContext().setContextProperty("initialWidth", 1280)
    engine.rootContext().setContextProperty("initialHeight", 800)
    engine.load(QML_DIR / "Main.qml")
    win = Shiboken.wrapInstance(Shiboken.getCppPointer(engine.rootObjects()[0])[0], QQuickWindow)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 17)
    blind = next(d["id"] for d in ctl.devices.all() if d["name"] == "Living Room Blinds")
    win.setProperty("openDevice", blind)
    assert pump_until(lambda: win.findChild(QObject, "blindVisual") is not None)
    pump_until(lambda: False, timeout=0.5)

    obj = win.findChild(QObject, "blindVisual")
    vis = Shiboken.wrapInstance(Shiboken.getCppPointer(obj)[0], QQuickItem)
    p = vis.mapToScene(QPointF(vis.width() / 2, vis.height() * 0.75))
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p.toPoint())
    assert pump_until(lambda: ctl.device(blind)["state"]["target"] != 60, timeout=4)
    assert 20 <= ctl.device(blind)["state"]["target"] <= 30
    assert pump_until(lambda: ctl.device(blind)["state"]["moving"] == "stopped"
                      and ctl.device(blind)["state"]["position"] == ctl.device(blind)["state"]["target"], timeout=8)
    ctl.shutdown()
    win.close()


def test_room_editor_changes_rooms_and_persists(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 17)
    ed = ctl.roomEditor
    coffee = next(d["id"] for d in ctl.devices.all() if d["name"] == "Coffee Maker")

    assert ed.addRoom("Office") == "" and ed.addRoom("office") != ""
    assert "Office" not in ctl.rooms                       # empty rooms are not on the home screen
    assert ed.assign(coffee, "Office") == ""
    assert "Office" in ctl.rooms and "Kitchen" not in ctl.rooms
    assert ed.renameRoom("Office", "Büro") == "" and ctl.device(coffee)["room"] == "Büro"
    ed.moveRoom("Büro", -99)
    assert ctl.rooms[0] == "Büro"
    assert ed.deleteRoom("Büro") == "" and ctl.device(coffee)["room"] == "General"
    assert next(r for r in ed.rooms if r["name"] == "General")["isDefault"]
    ctl.shutdown()

    saved = json.loads((tmp_path / "settings.json").read_text())["rooms"]
    assert "Büro" not in saved["order"] and saved["devices"][coffee] == "General"
    ctl2 = Controller(AppConfig.model_validate({"demo": {"enabled": True}}), SettingsStore(tmp_path / "settings.json"))
    ctl2.start()
    assert pump_until(lambda: len(ctl2.devices.all()) == 17)
    assert ctl2.device(coffee)["room"] == "General"
    ctl2.shutdown()


def test_rooms_page_rename_with_keyboard(qapp, tmp_path):
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow
    from PySide6.QtTest import QTest
    from shiboken6 import Shiboken
    from app.qt.main import QML_DIR
    from app.qt.translator import CatalogTranslator

    ctl = make_controller(tmp_path)
    translator = CatalogTranslator()
    qapp.installTranslator(translator)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("panel", ctl)
    engine.rootContext().setContextProperty("initialWidth", 720)
    engine.rootContext().setContextProperty("initialHeight", 720)
    engine.load(QML_DIR / "Main.qml")
    win = Shiboken.wrapInstance(Shiboken.getCppPointer(engine.rootObjects()[0])[0], QQuickWindow)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 17)

    def find(name, root=None):
        # Repeater delegates are not QObject children, so walk the visual item tree
        for child in (root or win.contentItem()).childItems():
            if child.objectName() == name and child.isVisible():
                return child
            if (hit := find(name, child)) is not None:
                return hit
        for popup in ([] if root else win.contentItem().findChildren(QQuickItem)):
            if popup.objectName() == name and popup.isVisible():
                return popup
        return None

    def item(name):
        assert pump_until(lambda: find(name) is not None), name
        pump_until(lambda: False, timeout=0.3)
        return find(name)

    def tap(name):
        it = item(name)
        p = it.mapToScene(QPointF(it.width() / 2, it.height() / 2))
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p.toPoint())

    win.setProperty("settingsOpen", True)
    tap("row:rooms_page")
    assert item("roomsPage")
    tap("rename:Kitchen")
    assert pump_until(lambda: item("keyboardInput").property("text") == "Kitchen")
    tap("key:backspace")                                   # clears the selected name
    for k in ("k", "o", "c", "h", "space", "a", "r", "e", "a"):
        tap("key:" + k)
    assert item("keyboardInput").property("text") == "Koch area"
    tap("keyboardDone")
    assert pump_until(lambda: "Koch area" in ctl.rooms)
    assert item("headerTitle").property("text") != ""                    # qsTr falls back to English
    ctl.shutdown()
    win.close()
    qapp.removeTranslator(translator)
    engine.deleteLater()          # before the controller it refers to is collected
    pump_until(lambda: False, timeout=0.3)


def test_security_alarm_and_open_since(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 17)
    alarms = []
    ctl.securityAlarm.connect(alarms.append)
    leak = next(d for d in ctl.devices.all() if d["name"] == "Washing Machine Leak")
    ctl._on_message({"type": "device", "device": {**leak, "state": {"triggered": True}}})
    assert alarms == ["Water detected: General, Washing Machine Leak"] and ctl.securityCount == 2
    ctl._on_message({"type": "device", "device": {**leak, "state": {"triggered": True}}})
    assert len(alarms) == 1                                         # only new alarms
    assert ctl.summary["security"] == "2 alerts" and ctl.summary["light"] != ""

    window = next(d for d in ctl.devices.all() if d["name"] == "Bedroom Window")
    ctl._since[window["id"]] -= 25 * 60
    ctl._on_message({"type": "device", "device": {k: v for k, v in window.items() if k != "since"}})
    assert ctl.device(window["id"])["stateText"] == "Open for 25 min"
    ctl.shutdown()


def test_device_editor_name_kind_room_and_hide_general(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 17)
    ed = ctl.roomEditor
    door = next(d for d in ed.devices if d["name"] == "Terrace Door")
    assert [k["value"] for k in door["kinds"]] == ["window", "door", "contact", "glassbreak"]
    assert ed.addRoom("Terrace") == ""
    assert ed.saveDevice(door["id"], "Garden door", "window", "Terrace") == ""
    d = ctl.device(door["id"])
    assert d["name"] == "Garden door" and d["room"] == "Terrace" and d["icon"] == "window"
    assert d["meta"]["security"] == "window" and d["baseName"] == "Terrace Door"
    assert ed.saveDevice(door["id"], "x" * 41, "door", "Terrace") != ""
    assert ed.saveDevice(door["id"], "", "door", "Terrace") == ""       # back to the original name
    assert ctl.device(door["id"])["name"] == "Terrace Door" and ctl.device(door["id"])["icon"] == "door"
    assert ed.saveDevice(door["id"], "", "contact", "Terrace") == ""    # the default kind of contact sensors
    assert ctl.device(door["id"])["icon"] == "contact" and door["id"] not in ed._layout.kinds

    assert "General" in ctl.rooms
    ctl.settings.save({"show_general": False})
    assert "General" not in ctl.rooms
    ctl.shutdown()
    saved = json.loads((tmp_path / "settings.json").read_text())
    assert saved["rooms"]["devices"][door["id"]] == "Terrace" and door["id"] not in saved["rooms"]["names"]


def test_hidden_device_only_in_settings(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 17)
    ed = ctl.roomEditor
    fan = next(d for d in ed.devices if d["name"] == "Fan")
    assert ed.addRoom("Attic") == "" and ed.saveDevice(fan["id"], "", "", "Attic", False) == ""
    ctl.selectCategory("climate")
    rows = ctl.devices.rowCount()
    assert "Attic" in ctl.rooms
    assert ed.saveDevice(fan["id"], "", "", "Attic", True) == ""
    assert ctl.devices.rowCount() == rows - 1 and "Attic" not in ctl.rooms     # its only device is hidden
    assert fan["id"] not in ctl.devices._rows
    assert next(d for d in ed.devices if d["id"] == fan["id"])["hidden"] is True     # still in the settings

    leak = next(d for d in ctl.devices.all() if d["name"] == "Washing Machine Leak")
    assert ed.saveDevice(leak["id"], "", "", leak["room"], True) == ""
    alarms = []
    ctl.securityAlarm.connect(alarms.append)
    ctl._on_message({"type": "device", "device": {k: v for k, v in leak.items() if k not in ("hidden",)}
                     | {"state": {"triggered": True}}})
    assert alarms == [] and ctl.securityCount == 1                  # hidden sensors raise no alarm
    ctl.shutdown()
    assert sorted(json.loads((tmp_path / "settings.json").read_text())["rooms"]["hidden"]) == sorted([fan["id"], leak["id"]])
