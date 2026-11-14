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
from app.qt.format import category  # noqa: E402
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
    assert pump_until(lambda: len(model.all()) == 23)
    assert ctl.statusOk and ctl.statusText == "Connected"
    assert "Kitchen" in ctl.rooms and ctl.indoorTemp != ""

    ctl.selectRoom("Kitchen")
    assert model.rowCount() == 1 and ctl.currentRoom == "Kitchen"
    coffee = model.data(model.index(0), list(model.roleNames())[model.ROLES.index("deviceId")])
    ctl.toggle(coffee)
    assert pump_until(lambda: ctl.device(coffee)["state"]["on"] is True)
    ctl.selectRoom("")
    assert model.rowCount() == 9 and ctl.category == "light"      # lights, plugs, valve, blinds
    ctl.selectCategory("climate")
    ctl.selectRoom("")                     # all rooms
    assert model.rowCount() == 7 and "Kitchen" not in ctl.rooms
    ctl.selectCategory("security")
    ctl.selectRoom("")                     # all rooms
    assert model.rowCount() == 7 and ctl.securityCount == 1       # the bedroom window is open
    assert [ctl.devices.get(r)["name"] for r in model._rows[:2]] == ["Alarm System", "Bedroom Window"]   # then alerts
    ctl.selectCategory("")
    ctl.selectRoom("")                     # all rooms
    assert model.rowCount() == 23

    errors = []
    ctl.toast.connect(errors.append)
    ctl.setAttrs(coffee, {"brightness": 50})
    assert pump_until(lambda: errors) and "does not support" in errors[0]
    ctl.shutdown()


def test_settings_reconnect_and_test_connection(qapp, tmp_path, hap_server):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)

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
    assert pump_until(lambda: len(ctl.devices.all()) == 24 and ctl.statusOk)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 23 and ctl.outdoorTemp != "")
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
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
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
    assert pump_until(lambda: len(ctl2.devices.all()) == 23)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 23)

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
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
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


def test_room_marks(qapp, tmp_path):
    """Red dot under Security (no motion yet), accent dot under Lights, none under Climate."""
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ctl.selectCategory("security")
    window = next(d for d in ctl.devices.all() if d["name"] == "Bedroom Window")   # open
    assert ctl.roomMarks == {window["room"]: "alert"}
    ctl._on_message({"type": "device", "device": {**window, "state": {"triggered": False}}})
    assert ctl.roomMarks == {}
    motion = {**{k: v for k, v in window.items() if k != "baseKind"}, "state": {"triggered": True}, "meta": {**window.get("meta", {}), "security": "motion"}}
    ctl._on_message({"type": "device", "device": motion})
    assert ctl.securityCount == 0 and ctl.roomMarks == {}       # motion: only while armed
    alarm = next(d for d in ctl.devices.all() if d["type"] == "alarm")
    ctl.setAttrs(alarm["id"], {"mode": "away"})
    assert pump_until(lambda: ctl.device(alarm["id"])["state"].get("armed"))
    assert pump_until(lambda: ctl.securityCount == 1 and ctl.roomMarks == {window["room"]: "alert"})
    ctl.selectCategory("light")
    lit = {d["room"] for d in ctl.devices.all() if d["type"] != "blind" and d["state"].get("on")
           and d["room"] in ctl.rooms}
    assert lit and set(ctl.roomMarks) >= lit and set(ctl.roomMarks.values()) == {"on"}
    ctl.selectCategory("climate")
    assert ctl.roomMarks == {}
    ctl.shutdown()


def test_batteries(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    names = [b["name"] for b in ctl.batteries]
    # demo: leak sensor 4 % (and reported low), bathroom heating 7 %, window only "not low", door 62 %
    assert names[:2] == ["Washing Machine Leak", "Bathroom Heating"] and ctl.lowBatteryCount == 2
    assert [b["low"] for b in ctl.batteries] == [True, True, False, False, False]
    heating = next(d for d in ctl.devices.all() if d["name"] == "Bathroom Heating")
    assert ctl.device(heating["id"])["batteryLow"] and ctl.device(heating["id"])["batteryText"] == "Battery 7 %"
    door = next(d for d in ctl.devices.all() if d["name"] == "Terrace Door")
    assert not ctl.device(door["id"])["batteryLow"]
    ctl.shutdown()


def test_alarm_system(qapp, tmp_path):
    ctl = make_controller(tmp_path, alarm_pin="2468")
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    alarm = next(d for d in ctl.devices.all() if d["type"] == "alarm")
    gid = alarm["id"]
    assert ctl.device(gid)["stateText"] == "Disarmed" and alarm["meta"]["modes"] == ["stay", "away", "night", "off"]
    assert category(alarm) == "security" and ctl.alarmPinSet
    ctl.setAttrs(gid, {"mode": "night"})
    assert pump_until(lambda: ctl.device(gid)["stateText"] == "Armed – Night")
    assert ctl.devices.role_value(ctl.device(gid), "isOn") is True             # armed: highlighted
    toasts = []
    ctl.toast.connect(toasts.append)
    ctl.setAttrs(gid, {"mode": "off"})                                           # needs the PIN
    assert toasts == ["Enter the PIN to disarm"]
    assert ctl.disarm(gid, "1111") == "Wrong PIN"
    assert ctl.disarm(gid, "2468") == ""
    assert pump_until(lambda: ctl.device(gid)["stateText"] == "Disarmed")

    # triggered: an alarm like a leak (red tile, wakes the panel, message)
    alarms = []
    ctl.securityAlarm.connect(alarms.append)
    d = ctl.device(gid)
    ctl._on_message({"type": "device", "device": {**{k: v for k, v in d.items() if k not in ("shortName", "stateText")},
                                                  "state": {**d["state"], "triggered": True, "armed": True}}})
    assert alarms and alarms[0].startswith("Alarm triggered!") and ctl.securityCount >= 1
    ctl.shutdown()


def test_quiet_security_sensor(qapp, tmp_path):
    """A sensor with "Security alerts" off is only shown: no alert, no red dot; alarms stay alarms."""
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ctl.selectCategory("security")
    window = next(d for d in ctl.roomEditor.devices if d["name"] == "Bedroom Window")
    assert window["canQuiet"] and ctl.securityCount == 1
    assert ctl.roomEditor.saveDevice(window["id"], {"quiet": True}) == ""
    assert ctl.securityCount == 0 and ctl.roomMarks == {} and ctl.device(window["id"])["quiet"]
    assert next(d for d in ctl.roomEditor.devices if d["id"] == window["id"])["quiet"]
    leak = next(d for d in ctl.devices.all() if d["name"] == "Washing Machine Leak")
    assert ctl.roomEditor.saveDevice(leak["id"], {"quiet": True}) == ""
    d = ctl.device(leak["id"])
    ctl._on_message({"type": "device", "device": {**{k: v for k, v in d.items() if k not in ("shortName", "stateText")},
                                                  "state": {**d["state"], "triggered": True}}})
    assert ctl.securityCount == 1                                   # a leak still is an alarm
    ctl.roomEditor.saveDevice(window["id"], {"quiet": False})
    assert ctl.securityCount == 2
    ctl.shutdown()


def test_presence_sensor(qapp, tmp_path):
    """Occupancy sensors: kind "presence", quiet by default; alerts can be switched on (while armed)."""
    from app.backends.hap import HapBackend
    from app.hap_types import snapshot_to_state
    U = "{:08X}-0000-1000-8000-0026BB765291".format
    data = {"accessories": [{"aid": 3, "services": [
        {"iid": 10, "type": U(0x86), "characteristics": [{"iid": 11, "type": U(0x71), "value": 1, "perms": ["pr"]}]}]}]}
    (snap,) = HapBackend.parse_accessories(data)
    assert snapshot_to_state(snap)[3] == {"security": "presence", "kinds": ["presence", "motion", "glassbreak"]}

    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ctl._on_message({"type": "device", "device": {
        "id": "demo:presence", "name": "Office Presence", "type": "security", "backend": "demo", "room": "Office",
        "icon": "presence", "state": {"triggered": True}, "capabilities": [], "reachable": True,
        "meta": {"security": "presence", "kinds": ["presence", "motion", "glassbreak"]}}})
    d = ctl.device("demo:presence")
    assert d["quiet"] and d["stateText"] == "Present" and d["icon"] == "presence"
    alarm = next(x for x in ctl.devices.all() if x["type"] == "alarm")
    ctl.setAttrs(alarm["id"], {"mode": "away"})
    assert pump_until(lambda: ctl.device(alarm["id"])["state"].get("armed"))
    assert ctl.securityCount == 1                                   # armed: only the open window
    assert ctl.roomEditor.saveDevice("demo:presence", {"quiet": False}) == ""
    assert ctl.securityCount == 2 and ctl.store.rooms["quiet"] == {"demo:presence": False}
    assert ctl.roomEditor.saveDevice("demo:presence", {"quiet": True}) == ""
    assert ctl.securityCount == 1 and "demo:presence" not in ctl.store.rooms.get("quiet", {})
    ctl.shutdown()


def test_valve(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    v = next(d for d in ctl.devices.all() if d["type"] == "valve")
    assert v["icon"] == "sprinkler" and ctl.device(v["id"])["stateText"] == "Closed"
    ctl.setAttrs(v["id"], {"duration": 300})
    assert pump_until(lambda: ctl.device(v["id"])["state"]["duration"] == 300)
    ctl.toggle(v["id"])
    assert pump_until(lambda: ctl.device(v["id"])["stateText"].startswith("Running, 5 min left"))
    ctl.setAttrs(v["id"], {"duration": 1800})       # a new run time applies to the next run
    assert pump_until(lambda: ctl.device(v["id"])["state"]["duration"] == 1800)
    assert ctl.device(v["id"])["stateText"] == "Running, 5 min left"
    ctl.toggle(v["id"])
    assert pump_until(lambda: ctl.device(v["id"])["stateText"] == "Closed")
    ctl.shutdown()


def test_garage_door(qapp, tmp_path):
    ctl = make_controller(tmp_path, alarm_pin="2468")
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    g = next(d for d in ctl.devices.all() if d["type"] == "garage")
    assert category(g) == "security" and ctl.device(g["id"])["stateText"] == "Closed" and g["icon"] == "garage"
    asked = []
    ctl.garageRequested.connect(asked.append)
    ctl.toggle(g["id"])                                     # a tap only asks
    assert asked == [g["id"]] and ctl.device(g["id"])["state"]["door"] == "closed"
    toasts = []
    ctl.toast.connect(toasts.append)
    ctl.setAttrs(g["id"], {"on": True})                     # opening needs the PIN
    assert toasts == ["Enter the PIN to open"]
    assert ctl.garageDoor(g["id"], True, "1111") == "Wrong PIN"
    assert ctl.garageDoor(g["id"], True, "2468") == ""
    assert pump_until(lambda: ctl.device(g["id"])["state"]["door"] == "open", 15)
    assert ctl.securityCount == 2 and ctl.device(g["id"])["stateText"] == "Open"   # an open door alerts
    ctl.selectCategory("security")
    assert ctl.roomMarks.get(g["room"]) == "alert"
    assert ctl.garageDoor(g["id"], False, "") == ""         # closing needs no PIN
    assert pump_until(lambda: ctl.device(g["id"])["state"]["door"] == "closed", 15)
    ctl.shutdown()


def test_room_marks_follow_switching(qapp, tmp_path):
    """The dot and the "n on" summary follow a light at once, not only after a room change."""
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ctl.selectCategory("light")
    kitchen = next(d for d in ctl.devices.all() if d["room"] == "Kitchen" and d["type"] != "blind")
    if kitchen["state"].get("on"):
        ctl.toggle(kitchen["id"])
        assert pump_until(lambda: "Kitchen" not in ctl.roomMarks)
    changes = []
    ctl.summaryChanged.connect(lambda: changes.append(dict(ctl.roomMarks)))
    on_before = ctl.summary["light"]
    ctl.toggle(kitchen["id"])
    assert pump_until(lambda: any(c.get("Kitchen") == "on" for c in changes))
    assert ctl.summary["light"] != on_before
    ctl.toggle(kitchen["id"])
    assert pump_until(lambda: "Kitchen" not in changes[-1])
    ctl.shutdown()


def test_device_editor_name_kind_room_and_hide_general(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ed = ctl.roomEditor
    door = next(d for d in ed.devices if d["name"] == "Terrace Door")
    assert [k["value"] for k in door["kinds"]] == ["window", "door", "contact", "glassbreak"]
    assert ed.addRoom("Terrace") == ""
    assert ed.saveDevice(door["id"], {"name": "Garden door", "kind": "window", "room": "Terrace"}) == ""
    d = ctl.device(door["id"])
    assert d["name"] == "Garden door" and d["room"] == "Terrace" and d["icon"] == "window"
    assert d["meta"]["security"] == "window" and d["baseName"] == "Terrace Door"
    assert ed.saveDevice(door["id"], {"name": "x" * 41, "kind": "door", "room": "Terrace"}) != ""
    assert ed.saveDevice(door["id"], {"name": "", "kind": "door", "room": "Terrace"}) == ""       # back to the original name
    assert ctl.device(door["id"])["name"] == "Terrace Door" and ctl.device(door["id"])["icon"] == "door"
    assert ed.saveDevice(door["id"], {"name": "", "kind": "contact", "room": "Terrace"}) == ""    # the default kind of contact sensors
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
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ed = ctl.roomEditor
    fan = next(d for d in ed.devices if d["name"] == "Fan")
    assert ed.addRoom("Attic") == "" and ed.saveDevice(fan["id"], {"name": "", "kind": "", "room": "Attic", "hidden": False}) == ""
    ctl.selectCategory("climate")
    ctl.selectRoom("")                     # all rooms
    rows = ctl.devices.rowCount()
    assert "Attic" in ctl.rooms
    assert ed.saveDevice(fan["id"], {"name": "", "kind": "", "room": "Attic", "hidden": True}) == ""
    assert ctl.devices.rowCount() == rows - 1 and "Attic" not in ctl.rooms     # its only device is hidden
    assert fan["id"] not in ctl.devices._rows
    assert next(d for d in ed.devices if d["id"] == fan["id"])["hidden"] is True     # still in the settings

    leak = next(d for d in ctl.devices.all() if d["name"] == "Washing Machine Leak")
    assert ed.saveDevice(leak["id"], {"name": "", "kind": "", "room": leak["room"], "hidden": True}) == ""
    alarms = []
    ctl.securityAlarm.connect(alarms.append)
    ctl._on_message({"type": "device", "device": {k: v for k, v in leak.items() if k not in ("hidden",)}
                     | {"state": {"triggered": True}}})
    assert alarms == [] and ctl.securityCount == 1                  # hidden sensors raise no alarm
    ctl.shutdown()
    assert sorted(json.loads((tmp_path / "settings.json").read_text())["rooms"]["hidden"]) == sorted([fan["id"], leak["id"]])


def test_outdoor_sensor_set_on_the_panel(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ed = ctl.roomEditor
    ws = next(d for d in ed.devices if d["name"] == "Weather Station")
    heating = next(d for d in ed.devices if d["name"] == "Living Room Heating")
    assert ws["canOutdoor"] and not ws["outdoor"] and not heating["canOutdoor"]
    assert ctl.outdoorTemp == ""                                   # nothing marked outdoor in this config
    assert ed.saveDevice(ws["id"], {"name": "", "kind": "", "room": ws["room"], "hidden": False, "outdoor": True}) == ""
    assert ctl.outdoorTemp != "" and next(d for d in ed.devices if d["id"] == ws["id"])["outdoor"]
    assert ed.saveDevice(ws["id"], {"name": "", "kind": "", "room": ws["room"], "hidden": False, "outdoor": False}) == ""
    assert ctl.outdoorTemp == "" and ws["id"] not in ed._layout.outdoor     # back to config.yaml
    ctl.shutdown()


def test_appliance_kind_and_menu_area(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ed = ctl.roomEditor
    washer = next(d for d in ed.devices if d["name"] == "Washing Machine")
    assert washer["kind"] == "plug" and [k["value"] for k in washer["kinds"]][:2] == ["switch", "plug"]
    assert ed.saveDevice(washer["id"], {"kind": "washer"}) == ""
    d = ctl.device(washer["id"])
    assert d["icon"] == "washer" and d["stateText"] == "Running"

    ctl.selectCategory("climate")
    ctl.selectRoom("")                     # all rooms
    climate = ctl.devices.rowCount()
    assert ed.saveDevice(washer["id"], {"kind": "fan"}) == ""          # a switched fan belongs to Climate
    assert ctl.devices.rowCount() == climate + 1 and ctl.device(washer["id"])["icon"] == "fan"
    assert ed.saveDevice(washer["id"], {"area": "security"}) == ""     # moved by hand
    assert ctl.devices.rowCount() == climate
    ctl.selectCategory("security")
    ctl.selectRoom("")                     # all rooms
    assert washer["id"] in ctl.devices._rows
    assert ed.saveDevice(washer["id"], {"area": "", "kind": "plug"}) == ""
    assert washer["id"] not in ed._layout.kinds and washer["id"] not in ed._layout.areas
    assert ed.saveDevice(washer["id"], {"area": "nonsense"}) != ""
    ctl.shutdown()


def test_appliance_from_config_and_back_to_automatic(qapp, tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.update({"hap_enabled": False, "language": "en"})
    cfg = AppConfig.model_validate({"demo": {"enabled": True}, "devices": {
        "Washing Machine": {"appliance": "washer", "area": "climate"}, "Coffee Maker": {"icon": "coffee"}}})
    ctl = Controller(cfg, store)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ed = ctl.roomEditor
    washer = next(d for d in ed.devices if d["name"] == "Washing Machine")
    assert washer["kind"] == "washer" and washer["area"] == "climate" and washer["icon"] == "washer"
    assert ed.saveDevice(washer["id"], {"area": ""}) == ""             # automatic despite config.yaml
    assert ed._layout.areas[washer["id"]] == "auto" and ctl.device(washer["id"])["meta"].get("area") is None
    coffee = next(d for d in ed.devices if d["name"] == "Coffee Maker")
    assert ed.saveDevice(coffee["id"], {"kind": "tv"}) == ""
    assert ctl.device(coffee["id"])["icon"] == "coffee"                # an icon from config.yaml stays
    ctl.shutdown()


def test_lamp_kind_changes_icon(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ed = ctl.roomEditor
    lamp = next(d for d in ed.devices if d["name"] == "Kitchen Light")
    assert lamp["kind"] == "bulb" and [k["value"] for k in lamp["kinds"]] == ["bulb", "ceiling", "spot", "wall", "table"]
    assert lamp["icon"] == "light"
    assert ed.saveDevice(lamp["id"], {"kind": "wall"}) == ""
    assert ctl.device(lamp["id"])["icon"] == "wall" and ctl.device(lamp["id"])["meta"]["lamp"] == "wall"
    assert ed.saveDevice(lamp["id"], {"kind": "bulb"}) == ""
    assert ctl.device(lamp["id"])["icon"] == "light" and lamp["id"] not in ed._layout.kinds
    ctl.shutdown()


def test_manual_device_order_per_room(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ed = ctl.roomEditor
    room = lambda: [d["name"] for d in ed.devices if d["room"] == "General" and d["type"] == "light"]   # noqa: E731
    before = room()
    last = next(d for d in ed.devices if d["name"] == before[-1])
    ed.moveDevice(last["id"], -99)
    assert room()[0] == before[-1]
    ctl.selectCategory("light")
    ctl.selectRoom("")                     # all rooms
    ctl.selectRoom("General")
    model = ctl.devices
    first = model.data(model.index(0), list(model.roleNames())[model.ROLES.index("name")])
    assert first == before[-1]                                          # the tiles follow the order
    assert ed.renameRoom("General", "House") == "" and "House" in ed._layout.device_order
    ctl.shutdown()


def test_light_group(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ed = ctl.roomEditor
    lights = [d for d in ed.lights if d["room"] == "General"][:2]
    ids = [d["id"] for d in lights]
    assert ed.saveGroup({"name": "", "room": "General", "members": ids}) != ""
    assert ed.saveGroup({"name": "Both", "room": "Kitchen", "members": ids}) != ""     # one room only
    assert ed.saveGroup({"name": "Both", "room": "General", "members": ids, "hide": True}) == ""
    group = next(d for d in ctl.devices.all() if d.get("meta", {}).get("group"))
    assert group["state"]["count"] == 2 and all(ctl.device(i)["grouped"] for i in ids)
    ctl.selectCategory("light")
    ctl.selectRoom("")                     # all rooms
    assert group["id"] in ctl.devices._rows and not set(ids) & set(ctl.devices._rows)

    ctl.toggle(group["id"])                                             # on if any was off …
    target = not group["state"]["on"]
    assert pump_until(lambda: all(ctl.device(i)["state"]["on"] is target for i in ids))
    assert pump_until(lambda: ctl.device(group["id"])["state"]["on"] is target)
    gid = next(g["id"] for g in ctl.store.groups)
    ed.deleteGroup(gid)
    assert not any(d.get("meta", {}).get("group") for d in ctl.devices.all())
    assert not any(ctl.device(i)["grouped"] for i in ids)
    ctl.shutdown()


def test_switch_group(qapp, tmp_path):
    """Only one switch on at a time; tapping steps to the next one (then "all off" if allowed)."""
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ed = ctl.roomEditor
    ids = [d["id"] for d in ed.switches if d["name"] in ("TV Plug", "Washing Machine")]
    assert len(ids) == 2
    assert ed.saveSwitchGroup({"name": "Pick", "room": "General", "members": ids[:1]}) != ""   # at least two
    assert ed.saveSwitchGroup({"name": "Pick", "room": "Kitchen", "members": ids}) != ""       # one room only
    assert ed.saveSwitchGroup({"name": "Pick", "room": "General", "members": ids, "area": "climate"}) == ""
    gid = "choice:" + ctl.store.switch_groups[0]["id"]
    g = ctl.device(gid)
    assert g["meta"]["choice"] and [o["id"] for o in g["meta"]["options"]] == ids
    assert all(ctl.device(i)["grouped"] for i in ids) and category(g) == "climate"
    assert next(d for d in ed.devices if d["id"] == gid)["switchGroup"]["name"] == "Pick"

    def state():
        return [bool(ctl.device(i)["state"].get("on")) for i in ids]

    ctl.setAttrs(gid, {"select": ids[0]})
    assert pump_until(lambda: state() == [True, False])
    assert pump_until(lambda: ctl.device(gid)["stateText"] == ctl.device(gid)["meta"]["options"][0]["name"])
    assert ctl.device(gid)["state"]["on"] is True                      # highlighted: "all off" allowed
    ctl.toggle(gid)                                                     # next switch
    assert pump_until(lambda: state() == [False, True])
    ctl.toggle(gid)                                                     # after the last: all off
    assert pump_until(lambda: state() == [False, False])
    assert pump_until(lambda: ctl.device(gid)["stateText"] == "Off")
    ctl.toggle(gid)                                                     # from off: the first
    assert pump_until(lambda: state() == [True, False])

    # without "all off": never highlighted, the last steps back to the first
    gid_raw = ctl.store.switch_groups[0]["id"]
    assert ed.saveSwitchGroup({"id": gid_raw, "name": "Pick", "room": "General", "members": ids,
                               "allowOff": False}) == ""
    assert ctl.device(gid)["state"]["on"] is False and ctl.device(gid)["stateText"] != "Off"
    ctl.setAttrs(gid, {"on": False})                                    # ignored
    ctl.toggle(gid)
    assert pump_until(lambda: state() == [False, True])
    ctl.toggle(gid)
    assert pump_until(lambda: state() == [True, False])
    ed.deleteSwitchGroup(gid_raw)
    assert ctl.device(gid) == {} and not any(ctl.device(i)["grouped"] for i in ids)
    ctl.shutdown()


def test_virtual_device_over_mqtt(qapp, tmp_path):
    from app.backends.mqtt import MqttBackend
    ctl = make_controller(tmp_path)
    ctl.store.update({"mqtt_enabled": True, "mqtt_host": "127.0.0.1", "mqtt_port": 1})   # nothing listens there
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ed = ctl.roomEditor
    assert ed.saveVirtual({"name": "Pressure", "topic": ""}) != ""
    assert ed.saveVirtual({"name": "Water pressure", "topic": "boiler/pressure", "unit": "bar", "decimals": 1,
                           "room": "Kitchen", "icon": "none"}) == ""
    assert pump_until(lambda: ctl.mqtt_backend() is not None and ctl.mqtt_backend().devices, timeout=10)
    backend = ctl.mqtt_backend()
    assert isinstance(backend, MqttBackend) and not backend.connected
    backend._client.loop_stop()                   # no broker here: stop retrying, pretend it answered
    backend._connected.set()
    backend.receive("boiler/pressure", "1.62")
    dev_id = "mqtt:" + ctl.store.virtual[0]["id"]
    assert pump_until(lambda: ctl.device(dev_id).get("stateText") == "1.6 bar", timeout=8)
    d = ctl.device(dev_id)
    assert d["room"] == "Kitchen" and d["icon"] == "none" and d["type"] == "value"
    assert "Received" in ed.lastValue(dev_id)
    ctl.selectCategory("climate")
    ctl.selectRoom("")                     # all rooms
    assert dev_id in ctl.devices._rows
    ctl.shutdown()


def test_light_group_color_and_white_tone(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    ed = ctl.roomEditor
    by_name = {d["name"]: d["id"] for d in ed.lights}
    strip, ceiling, kitchen = by_name["LED Strip"], by_name["Living Room Ceiling Light"], by_name["Kitchen Light"]

    def group(name):
        return next(d for d in ctl.devices.all() if d["name"] == name)

    assert ed.saveGroup({"name": "Color", "room": "General", "members": [strip]}) == ""
    assert ed.saveGroup({"name": "White", "room": "General", "members": [kitchen]}) == ""
    assert ed.saveGroup({"name": "Mixed", "room": "General", "members": [strip, ceiling], "hide": False}) == ""
    assert "color" in group("Color")["capabilities"] and "hue" in group("Color")["state"]
    white = group("White")
    assert "color_temp" in white["capabilities"] and white["meta"]["min_mired"] == 140
    assert not {"color", "color_temp"} & set(group("Mixed")["capabilities"])     # only what all lights can do

    ctl.setAttrs(group("Color")["id"], {"on": True, "hue": 200, "saturation": 60})
    assert pump_until(lambda: ctl.device(strip)["state"]["hue"] == 200)
    ctl.setAttrs(white["id"], {"on": True, "color_temp": 250})
    assert pump_until(lambda: ctl.device(kitchen)["state"]["color_temp"] == 250)
    assert pump_until(lambda: group("White")["state"]["color_temp"] == 250)
    ctl.shutdown()


def test_menu_switch_selects_first_room(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 23)
    assert ctl.currentRoom == ctl.rooms[0]                  # at start
    ctl.selectRoom("")
    assert ctl.currentRoom == ""
    ctl.selectCategory("security")
    assert ctl.currentRoom == ctl.rooms[0] != ""            # not "All"
    ctl.shutdown()
