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
    assert pump_until(lambda: len(model.all()) == 29)
    assert ctl.statusOk and ctl.statusText == "Connected"
    assert "Kitchen" in ctl.rooms and ctl.indoorTemp != ""

    ctl.selectRoom("Kitchen")
    assert model.rowCount() == 1 and ctl.currentRoom == "Kitchen"
    coffee = model.data(model.index(0), list(model.roleNames())[model.ROLES.index("deviceId")])
    ctl.toggle(coffee)
    assert pump_until(lambda: ctl.device(coffee)["state"]["on"] is True)
    ctl.selectRoom("")
    assert model.rowCount() == 11 and ctl.category == "light"     # lights, plugs, TV, speaker, valve, blinds
    ctl.selectCategory("climate")
    ctl.selectRoom("")                     # all rooms
    assert model.rowCount() == 9 and "Kitchen" not in ctl.rooms     # incl. air purifier and humidifier
    ctl.selectCategory("security")
    ctl.selectRoom("")                     # all rooms
    assert model.rowCount() == 9 and ctl.securityCount == 1       # the bedroom window is open
    assert [ctl.devices.get(r)["name"] for r in model._rows[:2]] == ["Alarm System", "Bedroom Window"]   # then alerts
    ctl.selectCategory("")
    ctl.selectRoom("")                     # all rooms
    assert model.rowCount() == 29

    errors = []
    ctl.toast.connect(errors.append)
    ctl.setAttrs(coffee, {"brightness": 50})
    assert pump_until(lambda: errors) and "does not support" in errors[0]
    ctl.shutdown()


def test_settings_reconnect_and_test_connection(qapp, tmp_path, hap_server):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)

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
    assert pump_until(lambda: len(ctl.devices.all()) == 30 and ctl.statusOk)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29 and ctl.outdoorTemp != "")
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    ed = ctl.roomEditor
    coffee = next(d["id"] for d in ctl.devices.all() if d["name"] == "Coffee Maker")

    assert ed.addRoom("Office") == "" and ed.addRoom("office") != ""
    assert "Office" not in ctl.rooms                       # empty rooms are not on the home screen
    assert ed.assign(coffee, "Office") == ""
    assert "Office" in ctl.rooms and "Kitchen" not in ctl.rooms
    assert ed.renameRoom("Office", "Büro") == "" and ctl.device(coffee)["room"] == "Büro"
    ed.moveRoom("Büro", -99)
    ed.finishMoves()                                       # leaving the page: saved and shown
    assert ctl.rooms[0] == "Büro"
    assert ed.deleteRoom("Büro") == "" and ctl.device(coffee)["room"] == "General"
    assert next(r for r in ed.rooms if r["name"] == "General")["isDefault"]
    ctl.shutdown()

    saved = json.loads((tmp_path / "settings.json").read_text())["rooms"]
    assert "Büro" not in saved["order"] and saved["devices"][coffee] == "General"
    ctl2 = Controller(AppConfig.model_validate({"demo": {"enabled": True}}), SettingsStore(tmp_path / "settings.json"))
    ctl2.start()
    assert pump_until(lambda: len(ctl2.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)

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

    # moving a room: the row changes places at once, saved when the tab is left
    first = ctl.roomEditor.rooms[0]["name"]
    row = item("room:" + first).parentItem()
    tap("roomDown:" + first)
    assert pump_until(lambda: row.property("index") == 1)
    assert item("room:" + first).parentItem() is row                  # moved, not built again
    assert ctl.roomEditor.rooms[0]["name"] == first and ctl.rooms[0] == first     # not yet everywhere

    # tapping the same arrow again moves the same device further (the list follows it)
    tap("tab:devices")
    assert pump_until(lambda: ctl.roomEditor.rooms[1]["name"] == first)    # the tab change finished the move
    ed = ctl.roomEditor
    room = max(ctl.rooms, key=lambda r: sum(d["room"] == r for d in ed.devices))
    target = [d["id"] for d in ed.devices if d["room"] == room][1]
    flick = item("roomsFlick")
    down = item("deviceDown:" + target)
    flick.setProperty("contentY", down.mapToItem(flick.property("contentItem"), QPointF(0, 0)).y() - 200)
    pump_until(lambda: False, timeout=0.3)
    down = item("deviceDown:" + target)
    spot = down.mapToScene(QPointF(down.width() / 2, down.height() / 2)).toPoint()
    row = item("device:" + target).parentItem()          # the delegate: moved, not built again
    neighbour = item("device:" + [d["id"] for d in ed.devices if d["room"] == room][2]).parentItem()
    y0 = row.y()
    busy = win.findChild(QObject, "busyPopup")
    assert pump_until(lambda: not busy.property("visible"))     # "Loading devices …" is gone
    stored = lambda: SettingsStore(tmp_path / "settings.json").rooms.get("device_order", {}).get(room)   # noqa: E731
    before = stored()
    for expected in (2, 3, 4):
        y = row.y()
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, spot)
        assert pump_until(lambda: row.property("index") == expected)
        assert pump_until(lambda: row.y() > y)              # placed on the next frame (a person is slower)
        ed.notify()                                         # a device update meanwhile changes nothing here                                      # a device update meanwhile changes nothing here
    assert item("device:" + target).parentItem() is row and row.y() > y0
    assert neighbour.property("index") == 1 and neighbour.y() < y0 + 1      # moved up into its place
    assert stored() == before                           # not saved after every move …
    tap("tab:rooms")                                     # … but when the tab or the page is left
    assert [d["id"] for d in ed.devices if d["room"] == room].index(target) == 4
    assert stored().index(target) == 4
    ctl.shutdown()
    win.close()
    qapp.removeTranslator(translator)
    engine.deleteLater()          # before the controller it refers to is collected
    pump_until(lambda: False, timeout=0.3)


def test_security_alarm_and_open_since(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    g = next(d for d in ctl.devices.all() if d["type"] == "garage")
    assert category(g) == "security" and ctl.device(g["id"])["stateText"] == "Closed" and g["icon"] == "garage"
    asked = []
    ctl.confirmRequested.connect(asked.append)
    ctl.toggle(g["id"])                                     # a tap only asks
    assert asked == [g["id"]] and ctl.device(g["id"])["state"]["door"] == "closed"
    toasts = []
    ctl.toast.connect(toasts.append)
    ctl.setAttrs(g["id"], {"on": True})                     # opening needs the PIN
    assert toasts == ["Enter the PIN to open"]
    assert ctl.openClose(g["id"], True, "1111") == "Wrong PIN"
    assert ctl.openClose(g["id"], True, "2468") == ""
    assert pump_until(lambda: ctl.device(g["id"])["state"]["door"] == "open", 15)
    assert ctl.securityCount == 2 and ctl.device(g["id"])["stateText"] == "Open"   # an open door alerts
    ctl.selectCategory("security")
    assert ctl.roomMarks.get(g["room"]) == "alert"
    assert ctl.openClose(g["id"], False, "") == ""         # closing needs no PIN
    assert pump_until(lambda: ctl.device(g["id"])["state"]["door"] == "closed", 15)
    ctl.shutdown()


def test_television(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    tv = next(d for d in ctl.devices.all() if d["type"] == "tv")
    assert tv["icon"] == "tv" and ctl.device(tv["id"])["stateText"] == "Off"
    assert [i["name"] for i in tv["meta"]["inputs"]] == ["HDMI 1", "HDMI 2", "Netflix"]
    ctl.toggle(tv["id"])
    assert pump_until(lambda: ctl.device(tv["id"])["stateText"] == "On – HDMI 1")
    ctl.setAttrs(tv["id"], {"input": 3})
    assert pump_until(lambda: ctl.device(tv["id"])["stateText"] == "On – Netflix")
    ctl.setAttrs(tv["id"], {"mute": True})
    assert pump_until(lambda: ctl.device(tv["id"])["state"]["mute"] is True)
    ctl.setAttrs(tv["id"], {"remote": "select"})        # write-only keys: no error
    ctl.setAttrs(tv["id"], {"volume_step": 1})
    ctl.shutdown()


def test_more_device_classes(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    by = {d["name"]: d["id"] for d in ctl.devices.all()}
    sky, spk, pur, hum = by["Skylight"], by["Kitchen Speaker"], by["Bedroom Air Purifier"], by["Bedroom Humidifier"]
    assert ctl.device(sky)["icon"] == "window" and ctl.device(sky)["stateText"] == "Closed"
    asked = []
    ctl.detailRequested.connect(asked.append)
    ctl.toggle(sky)                                        # a motorized window: open the controls, not the window
    assert asked == [sky]
    ctl.setAttrs(sky, {"position": 40})
    assert pump_until(lambda: ctl.device(sky)["state"]["position"] == 40, 12)
    assert ctl.securityCount == 2                          # open: an alert like an open window
    ctl.roomEditor.saveDevice(sky, {"quiet": True})
    assert ctl.securityCount == 1
    ctl.toggle(spk)
    assert pump_until(lambda: ctl.device(spk)["stateText"] == "Playing, 35%")
    ctl.setAttrs(pur, {"auto": False, "speed": 70})
    assert pump_until(lambda: ctl.device(pur)["stateText"] == "Purifying, 70%")
    assert ctl.device(hum)["stateText"] == "Humidifying, now 38%"
    ctl.setAttrs(hum, {"humidify_target": 30})
    assert pump_until(lambda: ctl.device(hum)["stateText"] == "Idle, now 38%")
    ctl.shutdown()


def test_door_lock(qapp, tmp_path):
    ctl = make_controller(tmp_path, alarm_pin="2468")
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    lock = next(d for d in ctl.devices.all() if d["type"] == "lock")
    assert category(lock) == "security" and lock["icon"] == "lock" and ctl.device(lock["id"])["stateText"] == "Locked"
    asked = []
    ctl.confirmRequested.connect(asked.append)
    ctl.toggle(lock["id"])                                  # a tap only asks
    assert asked == [lock["id"]]
    toasts = []
    ctl.toast.connect(toasts.append)
    ctl.setAttrs(lock["id"], {"on": True})                  # unlocking needs the PIN
    assert toasts == ["Enter the PIN to unlock"]
    assert ctl.openClose(lock["id"], True, "1111") == "Wrong PIN"
    assert ctl.openClose(lock["id"], True, "2468") == ""
    assert pump_until(lambda: ctl.device(lock["id"])["state"]["lock"] == "unlocked", 12)
    assert ctl.device(lock["id"])["stateText"] == "Unlocked" and ctl.securityCount == 2   # unlocked: an alert
    assert pump_until(lambda: ctl.device(lock["id"])["icon"] == "lockOpen")
    assert ctl.openClose(lock["id"], False, "") == ""       # locking needs no PIN
    assert pump_until(lambda: ctl.device(lock["id"])["state"]["lock"] == "locked", 12)
    ctl.shutdown()


def test_room_marks_follow_switching(qapp, tmp_path):
    """The dot and the "n on" summary follow a light at once, not only after a room change."""
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    ed = ctl.roomEditor
    washer = next(d for d in ed.devices if d["name"] == "Washing Machine")
    assert washer["kind"] == "plug" and [k["value"] for k in washer["kinds"]][:2] == ["switch", "plug"]
    assert ed.saveDevice(washer["id"], {"kind": "washer"}) == ""
    d = ctl.device(washer["id"])
    assert d["icon"] == "washer" and d["stateText"] == "Running, 384 W"      # its plug measures power

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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    ed = ctl.roomEditor
    washer = next(d for d in ed.devices if d["name"] == "Washing Machine")
    assert washer["kind"] == "washer" and washer["area"] == "climate" and washer["icon"] == "washer"
    assert ed.saveDevice(washer["id"], {"area": ""}) == ""             # automatic despite config.yaml
    assert ed._layout.areas[washer["id"]] == "auto" and ctl.device(washer["id"])["meta"].get("area") is None
    coffee = next(d for d in ed.devices if d["name"] == "Coffee Maker")
    assert ed.saveDevice(coffee["id"], {"kind": "washer"}) == ""
    assert ctl.device(coffee["id"])["icon"] == "coffee"                # an icon from config.yaml stays
    ctl.shutdown()


def test_lamp_kind_changes_icon(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    ed = ctl.roomEditor
    lamp = next(d for d in ed.devices if d["name"] == "Kitchen Light")
    assert lamp["kind"] == "bulb" and [k["value"] for k in lamp["kinds"]] == ["bulb", "ceiling", "pendant", "chandelier", "spot", "wall", "table", "desk", "floorlamp", "globe", "tube", "strip"]
    assert lamp["icon"] == "light"
    assert ed.saveDevice(lamp["id"], {"kind": "wall"}) == ""
    assert ctl.device(lamp["id"])["icon"] == "wall" and ctl.device(lamp["id"])["meta"]["lamp"] == "wall"
    assert ed.saveDevice(lamp["id"], {"kind": "bulb"}) == ""
    assert ctl.device(lamp["id"])["icon"] == "light" and lamp["id"] not in ed._layout.kinds
    ctl.shutdown()


def test_manual_device_order_per_room(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    ed = ctl.roomEditor
    room = lambda: [d["name"] for d in ed.devices if d["room"] == "General" and d["type"] == "light"]   # noqa: E731
    before = room()
    last = next(d for d in ed.devices if d["name"] == before[-1])
    ed.moveDevice(last["id"], -99)
    ed.finishMoves()
    assert room()[0] == before[-1]
    ctl.selectCategory("light")
    ctl.selectRoom("")                     # all rooms
    ctl.selectRoom("General")
    model = ctl.devices
    first = model.data(model.index(0), list(model.roleNames())[model.ROLES.index("name")])
    assert first == before[-1]                                          # the tiles follow the order
    assert ed.renameRoom("General", "House") == "" and "House" in ed._layout.device_order

    # under "All": alphabetically by the name shown, whatever the room or the manual order
    ctl.selectRoom("")
    role = lambda r: list(model.roleNames())[model.ROLES.index(r)]   # noqa: E731
    shown = [model.data(model.index(i), role("shortName")) for i in range(model.rowCount())]
    assert shown == sorted(shown, key=str.casefold) and len(shown) > 5    # as the tiles read
    assert ed.saveDevice(last["id"], {"name": "Aaa first lamp"}) == ""        # the display name counts
    assert model.data(model.index(0), role("name")) == "Aaa first lamp"
    ctl.shutdown()


def test_light_group(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    ed = ctl.roomEditor
    assert ed.saveVirtual({"name": "Pressure", "topic": ""}) != ""
    assert ed.saveVirtual({"name": "Water pressure", "topic": "boiler/pressure", "unit": "bar", "decimals": 1,
                           "room": "Kitchen", "icon": "none"}) == ""
    assert pump_until(lambda: ctl.mqtt_backend() is not None and ctl.mqtt_backend().devices
                      and ctl.mqtt_backend()._client is not None, timeout=10)   # started, not only created
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    assert ctl.currentRoom == ctl.rooms[0]                  # at start
    ctl.selectRoom("")
    assert ctl.currentRoom == ""
    ctl.selectCategory("security")
    assert ctl.currentRoom == ctl.rooms[0] != ""            # not "All"
    ctl.shutdown()


def test_favorites_start_page(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    assert ctl.category == "light"                      # no favorites yet
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    ed = ctl.roomEditor
    ids = [d["id"] for d in ctl.devices.all() if d["type"] in ("light", "thermostat", "lock")][:3]
    for i in reversed(ids):                             # added at the end: reverse order
        assert ed.saveDevice(i, {"favorite": True}) == ""
    assert [d["id"] for d in ed.favorites] == ids[::-1]
    ed.moveFavorite(ids[0], -99)                        # back to the front
    ed.finishMoves()
    assert [d["id"] for d in ed.favorites] == [ids[0], ids[2], ids[1]]

    ctl.selectCategory("favorites")
    assert ctl.rooms == [] and ctl.currentRoom == ""    # no room tabs, every room
    assert ctl.devices._rows == [ids[0], ids[2], ids[1]]
    assert ctl.roomMarks == {}

    assert ed.saveDevice(ids[2], {"hidden": True}) == ""      # hidden: not on the home screen
    assert ctl.devices._rows == [ids[0], ids[1]] and len(ed.favorites) == 3
    ctl.selectCategory("light")
    ctl.selectStart()
    assert ctl.category == "favorites"
    assert ed.saveDevice(ids[0], {"favorite": False}) == ""
    assert ctl.devices._rows == [ids[1]]
    assert ed.saveDevice(ids[0], {"favorite": True}) == ""
    ed.moveFavorite(ids[0], -99)
    ed.save_moves()                                     # a few seconds after the last move
    stored = SettingsStore(tmp_path / "settings.json").rooms["favorites"]
    assert stored == [ids[0], ids[2], ids[1]]
    ctl.shutdown()

    again = make_controller(tmp_path)                   # starts with the favorites
    assert again.category == "favorites"
    again.shutdown()


class FakeUpdater:
    supported = True

    def __init__(self):
        self.installed_tags, self.fail = [], ""

    def installed(self):
        return "0.0.2"

    def check(self):
        from app.updater import UpdateCheck
        return UpdateCheck("0.0.2", "v0.0.3", True)

    def install(self, tag):
        from app.updater import UpdateError
        if self.fail:
            raise UpdateError(self.fail)
        self.installed_tags.append(tag)


def test_software_update(qapp, tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.update({"hap_enabled": False, "language": "en"})
    up = FakeUpdater()
    ctl = Controller(AppConfig.model_validate({"demo": {"enabled": True}}), store, updater=up)
    calls, messages = [], []
    ctl._exec = lambda path, argv: calls.append(argv)
    ctl.restarting.connect(messages.append)
    assert ctl.version == "0.0.2" and ctl.updateInfo["state"] == "idle"
    assert "update" not in store.values
    ctl.installUpdate()                                     # nothing found yet: ignored
    assert ctl.updateInfo["state"] == "idle"
    ctl.checkUpdate()
    assert pump_until(lambda: ctl.updateInfo["state"] == "available")
    info = ctl.updateInfo
    assert info["install"] and info["latest"] == "0.0.3"
    assert info["text"] == "Version 0.0.3 is available (installed: 0.0.2)"

    up.fail = "the app folder has local changes"
    ctl.installUpdate()
    assert pump_until(lambda: ctl.updateInfo["text"].startswith("Update failed"))
    assert ctl.updateInfo["install"] and not calls          # can be tried again

    up.fail = ""
    ctl.installUpdate()
    assert pump_until(lambda: calls)
    assert up.installed_tags == ["v0.0.3"] and messages == ["Update installed. Restarting the app …"]
    ctl.shutdown()


def test_groups_and_virtual_devices_as_favorites(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.store.update({"mqtt_enabled": True, "mqtt_host": "127.0.0.1", "mqtt_port": 1})
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    ed = ctl.roomEditor
    lights = [d["id"] for d in ed.lights if d["room"] == "General"][:2]
    switches = [d["id"] for d in ed.switches if d["name"] in ("TV Plug", "Washing Machine")]
    assert ed.saveGroup({"name": "Both", "room": "General", "members": lights, "favorite": True}) == ""
    assert ed.saveSwitchGroup({"name": "Pick", "room": "General", "members": switches, "favorite": True}) == ""
    assert ed.saveVirtual({"name": "Water pressure", "topic": "boiler/pressure", "room": "Kitchen",
                           "favorite": True}) == ""
    group = "group:" + ctl.store.groups[0]["id"]
    choice = "choice:" + ctl.store.switch_groups[0]["id"]
    virtual = "mqtt:" + ctl.store.virtual[0]["id"]
    assert pump_until(lambda: ctl.mqtt_backend() is not None and ctl.mqtt_backend().devices
                      and ctl.mqtt_backend()._client is not None, timeout=10)   # started, not only created
    backend = ctl.mqtt_backend()
    backend._client.loop_stop()                   # no broker here: pretend it answered
    backend._connected.set()
    backend.receive("boiler/pressure", "1.6")
    assert pump_until(lambda: ctl.device(virtual) != {}, timeout=8)
    assert [d["id"] for d in ed.favorites] == [group, choice, virtual]
    assert all(d["favorite"] for d in ed.devices if d["id"] in (group, choice, virtual))
    ctl.selectCategory("favorites")
    assert ctl.devices._rows == [group, choice, virtual]

    # saving without the flag keeps it; switching it off or deleting removes the favorite
    assert ed.saveGroup({"id": ctl.store.groups[0]["id"], "name": "Both", "room": "General", "members": lights}) == ""
    assert ed.saveSwitchGroup({"id": ctl.store.switch_groups[0]["id"], "name": "Pick", "room": "General",
                               "members": switches, "favorite": False}) == ""
    ed.deleteVirtual(ctl.store.virtual[0]["id"])
    assert ed._layout.favorites == [group]
    assert SettingsStore(tmp_path / "settings.json").rooms["favorites"] == [group]
    ctl.shutdown()


def test_device_history(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    with_history = sorted(d["name"] for d in ctl.devices.all() if d["meta"].get("history"))
    assert with_history == ["Living Room Climate", "Living Room Heating", "Washing Machine", "Weather Station"]
    got = []
    ctl.historyLoaded.connect(lambda dev_id, days, result: got.append((dev_id, days, result)))
    ctl.loadHistory("demo:weather-station", 1)
    assert pump_until(lambda: got)
    dev_id, days, result = got[0]
    assert (dev_id, days, result["error"]) == ("demo:weather-station", 1, "")
    assert result["kinds"] == ["temperature", "humidity", "pressure"]
    for kind, (lo, hi) in {"temperature": (-10, 20), "humidity": (40, 100), "pressure": (980, 1040)}.items():
        ser = result["series"][kind]
        assert 140 <= len(ser["points"]) <= 145 and lo < ser["min"] < ser["max"] < hi, kind
        assert result["since"] <= ser["points"][0]["t"] <= ser["points"][-1]["t"] <= result["until"]
    ctl.loadHistory("demo:weather-station", 30)
    assert pump_until(lambda: len(got) == 2)
    assert all(len(s["points"]) <= 240 for s in got[1][2]["series"].values())    # averaged for the chart
    assert (tmp_path / "history.json").exists()             # kept for the next start
    ctl.loadHistory("demo:living-climate", 7)               # no barometer: its 0 hPa are not offered
    ctl.loadHistory("demo:heating-living", 7)
    ctl.loadHistory("demo:coffee", 1)                       # no history: empty, no error
    assert pump_until(lambda: len(got) == 5)
    kinds = {d: r["kinds"] for d, _, r in got[2:]}
    assert kinds == {"demo:living-climate": ["temperature", "humidity"], "demo:heating-living": ["temperature"],
                     "demo:coffee": []}
    assert got[4][2]["series"] == {} and got[4][2]["error"] == ""
    # a plug that measures power: its power history and the consumption in the period
    washer = ctl.device("demo:washer")
    assert washer["stateText"] == "On, 384 W" and washer["meta"]["history"]       # a plain plug here
    assert ctl.devices.role_value(ctl._model.get("demo:washer"), "hasDetail")       # detail view with History
    ctl.loadHistory("demo:washer", 7)
    assert pump_until(lambda: len(got) == 6)
    power = got[5][2]
    assert power["kinds"] == ["power"] and power["series"]["power"]["max"] == 2050.0
    assert 2 < power["series"]["power"]["energy"] < 5                  # kWh in a week of washes
    ctl.shutdown()


def test_history_chart_switches_between_quantities(qapp, tmp_path):
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from shiboken6 import Shiboken
    from app.qt.main import QML_DIR

    ctl = make_controller(tmp_path)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("panel", ctl)
    engine.rootContext().setContextProperty("initialWidth", 1024)
    engine.rootContext().setContextProperty("initialHeight", 600)
    engine.load(QML_DIR / "Main.qml")
    win = Shiboken.wrapInstance(Shiboken.getCppPointer(engine.rootObjects()[0])[0], QQuickWindow)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)

    def find(name, item=None):
        for child in (item or win.contentItem()).childItems():
            if child.objectName() == name and child.isVisible():
                return child
            if (hit := find(name, child)) is not None:
                return hit
        return None

    def tap(name):
        assert pump_until(lambda: find(name) is not None), name
        # the buttons move once the history arrived (one or two lines): tap where they end up
        where = lambda: find(name).mapToScene(QPointF(find(name).width() / 2, find(name).height() / 2))   # noqa: E731
        last = None
        while (now := where()) != last:
            last = now
            pump_until(lambda: False, timeout=0.15)
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, last.toPoint())

    def range_text():
        assert pump_until(lambda: find("historyRange") is not None)
        return find("historyRange").property("text")

    win.setProperty("openDevice", "demo:weather-station")
    tap("detailHistory")
    assert "°C" in range_text()
    tap("historyKind:humidity")
    assert pump_until(lambda: range_text().endswith("%"))
    tap("historyRange:7")
    tap("historyKind:pressure")
    assert pump_until(lambda: range_text().endswith("hPa"))
    win.setProperty("openDevice", "")
    pump_until(lambda: False, timeout=0.2)
    win.setProperty("openDevice", "demo:heating-living")     # temperature only: no choice
    tap("detailHistory")
    assert "°C" in range_text() and find("historyKind:temperature") is None
    ctl.shutdown()
    win.close()
    engine.deleteLater()
    pump_until(lambda: False, timeout=0.3)


def test_upside_down(qapp, tmp_path):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from shiboken6 import Shiboken
    from app.qt.main import QML_DIR

    ctl = make_controller(tmp_path)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("panel", ctl)
    engine.rootContext().setContextProperty("initialWidth", 1024)
    engine.rootContext().setContextProperty("initialHeight", 600)
    engine.load(QML_DIR / "Main.qml")
    win = Shiboken.wrapInstance(Shiboken.getCppPointer(engine.rootObjects()[0])[0], QQuickWindow)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)

    def find(name, item=None):
        for child in (item or win.contentItem()).childItems():
            if child.objectName() == name and child.isVisible():
                return child
            if (hit := find(name, child)) is not None:
                return hit
        return None

    def center(name):
        it = find(name)
        return it.mapToScene(QPointF(it.width() / 2, it.height() / 2))

    # the menu settles once the devices are there: measure when it no longer moves
    last = None
    while (before := center("category:climate")) != last:
        last = before
        pump_until(lambda: False, timeout=0.2)
    assert win.contentItem().property("rotation") == 0
    assert ctl.settings.save({"upside_down": True}) == {}
    assert pump_until(lambda: win.contentItem().property("rotation") == 180)

    def mirrored():
        after = center("category:climate")
        return abs(after.x() - (1024 - before.x())) < 1 and abs(after.y() - (600 - before.y())) < 1
    assert pump_until(mirrored)
    after = center("category:climate")
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, after.toPoint())
    assert pump_until(lambda: ctl.category == "climate")              # the tap reaches the turned item
    assert ctl.settings.save({"upside_down": False}) == {}
    pump_until(lambda: False, timeout=0.3)
    assert win.contentItem().property("rotation") == 0
    ctl.shutdown()
    win.close()
    engine.deleteLater()
    pump_until(lambda: False, timeout=0.3)


def test_busy_feedback_while_opening_and_saving(qapp, tmp_path):
    """Pages and saving run through Busy.run: the popup opens first, the work follows a frame
    later, then the popup closes again; taps are blocked meanwhile."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from shiboken6 import Shiboken
    from app.qt.main import QML_DIR

    ctl = make_controller(tmp_path)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("panel", ctl)
    engine.rootContext().setContextProperty("initialWidth", 1024)
    engine.rootContext().setContextProperty("initialHeight", 600)
    engine.load(QML_DIR / "Main.qml")
    win = Shiboken.wrapInstance(Shiboken.getCppPointer(engine.rootObjects()[0])[0], QQuickWindow)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    popup = win.findChild(QObject, "busyPopup")

    def find(name, item=None):
        for child in (item or win.contentItem()).childItems():
            if child.objectName() == name and child.isVisible():
                return child
            if (hit := find(name, child)) is not None:
                return hit
        return None

    def tap(name):
        assert pump_until(lambda: find(name) is not None), name
        assert pump_until(lambda: not popup.property("visible"))    # a closing popup still takes taps
        it = find(name)
        p = it.mapToScene(QPointF(it.width() / 2, it.height() / 2)).toPoint()
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)

    tap("settingsButton")
    assert popup.property("opened") and not win.property("settingsOpen")   # feedback first …
    assert pump_until(lambda: win.property("settingsOpen") and not popup.property("opened"))   # … then the page
    row, flick = find("row:rooms_page"), find("settingsFlick")
    flick.setProperty("contentY", row.mapToItem(flick.property("contentItem"), QPointF(0, 0)).y() - 100)
    pump_until(lambda: False, timeout=0.2)
    tap("row:rooms_page")
    assert pump_until(lambda: find("roomsPage") is not None and not popup.property("opened"))
    tap("tab:devices")
    assert popup.property("opened")
    assert pump_until(lambda: find("device:demo:coffee") is not None and not popup.property("opened"))
    ctl.shutdown()
    win.close()
    engine.deleteLater()
    pump_until(lambda: False, timeout=0.3)


def test_display_off_after_screen_saver(qapp, tmp_path):
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from shiboken6 import Shiboken
    from app.display_power import DisplayPower
    from app.qt.main import QML_DIR

    class FakePower(DisplayPower):
        def __init__(self):
            super().__init__(tmp_path / "none", env={})
            self.calls = []

        def set(self, on):
            self.calls.append(on)
            self.is_on = on
            return True

    store = SettingsStore(tmp_path / "settings.json")
    store.update({"hap_enabled": False, "language": "en", "idle_seconds": 60, "display_off": 300})
    power = FakePower()
    ctl = Controller(AppConfig.model_validate({"demo": {"enabled": True}}), store, display_power=power)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("panel", ctl)
    engine.rootContext().setContextProperty("initialWidth", 1024)
    engine.rootContext().setContextProperty("initialHeight", 600)
    engine.load(QML_DIR / "Main.qml")
    win = Shiboken.wrapInstance(Shiboken.getCppPointer(engine.rootObjects()[0])[0], QQuickWindow)
    timer = win.findChild(QObject, "displayOffTimer")
    assert ctl.displayOffSeconds == 300 and not timer.property("running")
    win.setProperty("idle", True)                                  # screen saver
    assert timer.property("running") and timer.property("interval") == 300_000
    timer.setProperty("interval", 50)                              # don't wait five minutes
    assert pump_until(lambda: power.calls == [False])              # display off
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPointF(500, 300).toPoint())
    assert pump_until(lambda: power.calls == [False, True])        # a touch: on again, screen saver over
    assert not win.property("idle") and not timer.property("running")
    win.setProperty("idle", True)
    timer.setProperty("interval", 50)
    assert pump_until(lambda: power.calls == [False, True, False])
    ctl.securityAlarm.emit("Water detected")                       # an alarm switches it on as well
    assert pump_until(lambda: power.calls == [False, True, False, True])
    assert ctl.settings.save({"display_off": 0}) == {} and ctl.displayOffSeconds == 0
    win.setProperty("idle", True)
    assert not timer.property("running")                           # never
    ctl.shutdown()
    win.close()
    engine.deleteLater()
    pump_until(lambda: False, timeout=0.3)


def test_touch_that_wakes_the_display_switches_nothing(qapp, tmp_path):
    """With the display off, the touch that wakes the panel – and further taps while the display
    is still lighting up – must not reach the tiles underneath."""
    import time as _time
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from shiboken6 import Shiboken
    from app.display_power import DisplayPower
    from app.qt.main import QML_DIR

    class SlowPower(DisplayPower):                       # a display that takes a while to light up
        def __init__(self):
            super().__init__(tmp_path / "none", env={})
            self.calls = []

        def set(self, on):
            _time.sleep(0.4)
            self.calls.append(on)
            self.is_on = on
            return True

    store = SettingsStore(tmp_path / "settings.json")
    store.update({"hap_enabled": False, "language": "en", "idle_seconds": 60, "display_off": 300})
    power = SlowPower()
    ctl = Controller(AppConfig.model_validate({"demo": {"enabled": True}}), store, display_power=power)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("panel", ctl)
    engine.rootContext().setContextProperty("initialWidth", 1024)
    engine.rootContext().setContextProperty("initialHeight", 600)
    engine.load(QML_DIR / "Main.qml")
    win = Shiboken.wrapInstance(Shiboken.getCppPointer(engine.rootObjects()[0])[0], QQuickWindow)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    ctl.selectCategory("light")
    ctl.selectRoom("")

    def find(name, item=None):
        for child in (item or win.contentItem()).childItems():
            if child.objectName() == name and child.isVisible():
                return child
            if (hit := find(name, child)) is not None:
                return hit
        return None

    light = next(d["id"] for d in ctl.devices.all() if d["type"] == "light" and d["reachable"])
    assert pump_until(lambda: find("tile:" + light) is not None)
    tile = find("tile:" + light)
    spot = tile.mapToScene(QPointF(tile.width() / 2, tile.height() / 2)).toPoint()
    was_on = ctl.device(light)["state"]["on"]

    def tap():
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, spot)

    timer = win.findChild(QObject, "displayOffTimer")
    win.setProperty("idle", True)
    timer.setProperty("interval", 50)
    assert pump_until(lambda: power.calls == [False])              # display off
    tap()                                                           # wakes the panel …
    assert not win.property("idle") and win.property("shielded")
    for _ in range(3):                                              # … taps in the dark go nowhere
        pump_until(lambda: False, timeout=0.15)
        tap()
    assert pump_until(lambda: power.calls == [False, True])
    assert win.property("shielded")                                 # one more second after it is lit
    pump_until(lambda: False, timeout=0.5)
    assert ctl.device(light)["state"]["on"] == was_on               # nothing switched
    assert pump_until(lambda: not win.property("shielded"), timeout=3)
    tap()                                                           # now the tile works again
    assert pump_until(lambda: ctl.device(light)["state"]["on"] != was_on)

    # the screen saver alone (display still on): only a short moment
    win.setProperty("idle", True)
    tap()
    assert win.property("shielded")
    assert pump_until(lambda: not win.property("shielded"), timeout=1)
    ctl.shutdown()
    win.close()
    engine.deleteLater()
    pump_until(lambda: False, timeout=0.3)


def test_arming_away_warns_about_open_windows(qapp, tmp_path):
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from shiboken6 import Shiboken
    from app.qt.main import QML_DIR

    ctl = make_controller(tmp_path)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("panel", ctl)
    engine.rootContext().setContextProperty("initialWidth", 1024)
    engine.rootContext().setContextProperty("initialHeight", 600)
    engine.load(QML_DIR / "Main.qml")
    win = Shiboken.wrapInstance(Shiboken.getCppPointer(engine.rootObjects()[0])[0], QQuickWindow)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    assert [o["id"] for o in ctl.openBeforeArming()] == ["demo:bedroom-window"]       # a window is open
    assert ctl.openBeforeArming()[0]["state"] == "Open"

    def find(name, item=None):
        root = item or win.contentItem()
        while item is None and root.parentItem() is not None:      # popups live in the overlay
            root = root.parentItem()
        for child in root.childItems():
            if child.objectName() == name and child.isVisible():
                return child
            if (hit := find(name, child)) is not None:
                return hit
        return None

    def tap(name):
        assert pump_until(lambda: find(name) is not None), name
        it = find(name)
        p = it.mapToScene(QPointF(it.width() / 2, it.height() / 2)).toPoint()
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)

    warning = lambda: win.findChild(QObject, "openWarning")      # noqa: E731
    mode = lambda: ctl.device("demo:alarm")["state"]["target"]     # noqa: E731
    win.setProperty("openDevice", "demo:alarm")
    tap("alarmMode:away")
    assert pump_until(lambda: warning().property("opened"))        # warned, not armed
    assert find("open:demo:bedroom-window") is not None and mode() == "off"
    tap("openWarningCancel")
    assert pump_until(lambda: not warning().property("visible"))
    pump_until(lambda: False, timeout=0.3)
    assert mode() == "off"
    tap("alarmMode:away")
    assert pump_until(lambda: warning().property("opened"))
    tap("armAnyway")                                                # armed anyway
    assert pump_until(lambda: mode() == "away")

    tap("alarmMode:night")                                          # other modes: no warning
    assert pump_until(lambda: mode() == "night") and not warning().property("visible")
    # nothing open (the window set to "No alerts"): "Away" arms at once
    assert ctl.roomEditor.saveDevice("demo:bedroom-window", {"quiet": True}) == ""
    assert ctl.openBeforeArming() == []
    tap("alarmMode:away")
    assert pump_until(lambda: mode() == "away") and not warning().property("visible")
    ctl.shutdown()
    win.close()
    engine.deleteLater()
    pump_until(lambda: False, timeout=0.3)


def test_new_lights_get_a_lamp_kind_from_their_name(qapp, tmp_path):
    from app.models import guess_lamp
    assert [guess_lamp(n) for n in ("Wandleuchte Flur", "Deckenspot Bad", "Schreibtischlampe", "Tischlampe",
                                    "Lámpara de techo", "Licht Flur")] == ["wall", "spot", "desk", "table", "ceiling", None]
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    # the first start: every device counts as known, nothing changes
    assert ctl._model.layout.seen and "demo:living-ceiling" in ctl._model.layout.seen
    assert ctl._model.layout.kinds == {}

    def light(dev_id, name, lamp="bulb"):
        ctl._on_message({"type": "device", "device": {
            "id": dev_id, "name": name, "type": "light", "backend": "demo", "room": "General", "icon": "light",
            "state": {"on": False}, "capabilities": ["on"], "reachable": True, "order": 100,
            "meta": {"lamp": lamp, "kinds": ["bulb", "ceiling", "wall", "spot"]}}})

    light("demo:new-wall", "Wandleuchte Flur")                    # new: kind from the name
    assert ctl.device("demo:new-wall")["meta"]["lamp"] == "wall" and ctl.device("demo:new-wall")["icon"] == "wall"
    light("demo:new-plain", "Licht Keller")                        # nothing in the name: a bulb
    assert ctl.device("demo:new-plain")["meta"]["lamp"] == "bulb"
    light("demo:new-config", "Deckenlampe", lamp="spot")           # kind from config.yaml: kept
    assert ctl.device("demo:new-config")["meta"]["lamp"] == "spot"
    # changed on the panel afterwards: stays as chosen, also when the device reports again
    assert ctl.roomEditor.saveDevice("demo:new-wall", {"kind": "ceiling"}) == ""
    light("demo:new-wall", "Wandleuchte Flur")
    assert ctl.device("demo:new-wall")["meta"]["lamp"] == "ceiling"
    stored = SettingsStore(tmp_path / "settings.json").rooms
    assert {"demo:new-wall", "demo:new-plain"} <= set(stored["seen"])
    ctl.shutdown()
    again = make_controller(tmp_path)                                # known after a restart
    assert "demo:new-wall" in again._model.layout.seen
    again.shutdown()


def test_wifi_tile_in_the_favorites(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    assert ctl.wifiCode()["error"].startswith("Enter the guest Wi-Fi")
    assert ctl.settings.save({"wifi_favorite": True}) == {}
    assert ctl._model.get("wifi:guest") is None                    # no network yet: no tile
    assert ctl.settings.save({"wifi_ssid": "Guests", "wifi_password": "welcome"}) == {}
    ctl.selectCategory("favorites")
    assert ctl.devices._rows == ["wifi:guest"]                     # the only favorite
    tile = ctl._model.get("wifi:guest")
    assert tile["name"] == "Wi-Fi QR code" and tile["icon"] == "wifi"
    assert ctl.devices.role_value(tile, "stateText") == "Guests"
    # not a device: not counted, in no room, not among the devices of the room settings …
    assert len(ctl.devices.all()) == 29 and "" not in ctl.rooms
    assert all(d["id"] != "wifi:guest" for d in ctl.roomEditor.devices)
    # … but listed with the favorites there, to be moved
    assert ctl.roomEditor.saveDevice("demo:coffee", {"favorite": True}) == ""
    assert [d["id"] for d in ctl.roomEditor.favorites] == ["wifi:guest", "demo:coffee"]
    assert ctl.roomEditor.favorites[0]["panelTile"] is True
    ctl.roomEditor.moveFavorite("wifi:guest", 1)
    ctl.roomEditor.finishMoves()
    assert [d["id"] for d in ctl.roomEditor.favorites] == ["demo:coffee", "wifi:guest"]
    assert ctl.devices._rows == ["demo:coffee", "wifi:guest"]
    assert ctl.roomEditor.saveDevice("demo:coffee", {"favorite": False}) == ""
    asked = []
    ctl.wifiRequested.connect(lambda: asked.append(True))
    ctl.toggle("wifi:guest")
    assert asked == [True]
    code = ctl.wifiCode()
    assert (code["error"], code["ssid"], code["password"]) == ("", "Guests", "welcome")
    assert code["image"].startswith("data:image/png;base64,")
    assert "wifi:guest" in SettingsStore(tmp_path / "settings.json").rooms["favorites"]
    assert ctl.settings.save({"wifi_favorite": False}) == {}
    assert ctl._model.get("wifi:guest") is None and ctl.devices.rowCount() == 0
    assert "wifi:guest" not in SettingsStore(tmp_path / "settings.json").rooms["favorites"]
    ctl.shutdown()


def test_wifi_settings_entered_on_the_panel(qapp, tmp_path):
    """Text entries of a section that saves at once (Wi-Fi for guests) are saved when the
    keyboard closes, not kept for "Apply"; then the tile appears."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
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
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    busy = win.findChild(QObject, "busyPopup")

    def find(name, item=None):
        for child in (item or win.contentItem()).childItems():
            if child.objectName() == name and child.isVisible():
                return child
            if (hit := find(name, child)) is not None:
                return hit
        return None

    def tap(name, fx=0.5):
        assert pump_until(lambda: find(name) is not None), name
        assert pump_until(lambda: not busy.property("visible"))
        it = find(name)
        p = it.mapToScene(QPointF(it.width() * fx, it.height() / 2)).toPoint()
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)

    def scroll_to(name):
        assert pump_until(lambda: not busy.property("visible"))
        pump_until(lambda: False, timeout=0.2)          # the page is rebuilt after saving
        row, flick = find(name), find("settingsFlick")
        flick.setProperty("contentY", row.mapToItem(flick.property("contentItem"), QPointF(0, 0)).y() - 100)
        pump_until(lambda: False, timeout=0.2)

    tap("settingsButton")
    assert pump_until(lambda: find("row:wifi_ssid") is not None)
    for key, text in (("wifi_ssid", "gast"), ("wifi_password", "abc")):
        scroll_to(f"row:{key}")
        tap(f"row:{key}", 0.95)
        for ch in text:
            tap("key:" + ch)
        tap("keyboardDone")
        assert pump_until(lambda: ctl.store.get(key) == text), key
    scroll_to("row:wifi_favorite")
    tap("row:wifi_favorite", 0.97)
    assert pump_until(lambda: ctl._model.get("wifi:guest") is not None)
    assert ctl.wifiCode()["ssid"] == "gast"
    ctl.shutdown()
    win.close()
    engine.deleteLater()
    pump_until(lambda: False, timeout=0.3)


def test_wifi_dialog_from_the_tile(qapp, tmp_path):
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from shiboken6 import Shiboken
    from app.qt.main import QML_DIR

    ctl = make_controller(tmp_path)
    assert ctl.settings.save({"wifi_ssid": "Guests", "wifi_password": "welcome", "wifi_favorite": True}) == {}
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("panel", ctl)
    engine.rootContext().setContextProperty("initialWidth", 1024)
    engine.rootContext().setContextProperty("initialHeight", 600)
    engine.load(QML_DIR / "Main.qml")
    win = Shiboken.wrapInstance(Shiboken.getCppPointer(engine.rootObjects()[0])[0], QQuickWindow)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    ctl.selectCategory("favorites")
    dialog = win.findChild(QObject, "wifiDialog")

    def find(name, item=None):
        for child in (item or win.contentItem()).childItems():
            if child.objectName() == name and child.isVisible():
                return child
            if (hit := find(name, child)) is not None:
                return hit
        return None

    def tap(name):
        assert pump_until(lambda: find(name) is not None), name
        it = find(name)
        p = it.mapToScene(QPointF(it.width() / 2, it.height() / 2)).toPoint()
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)

    def popup_item(name):
        return find(name, dialog.property("contentItem"))

    tap("tile:wifi:guest")
    assert pump_until(lambda: dialog.property("opened"))               # no PIN
    assert popup_item("wifiSsid").property("text") == "Guests"
    assert popup_item("wifiPassword").property("text") == "welcome"
    assert pump_until(lambda: popup_item("wifiQr").property("implicitWidth") > 20)     # the PNG is decoded
    tap("wifiClose")
    assert pump_until(lambda: not dialog.property("visible"))
    ctl.shutdown()
    win.close()
    engine.deleteLater()
    pump_until(lambda: False, timeout=0.3)


def test_backup_and_restore_in_the_settings(qapp, tmp_path):
    ctl = make_controller(tmp_path)
    calls, messages = [], []
    ctl._exec = lambda path, argv: calls.append(argv)
    ctl.restarting.connect(messages.append)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    s = ctl.settings
    assert s.backups == []
    assert ctl.roomEditor.saveDevice("demo:coffee", {"favorite": True, "name": "Espresso"}) == ""
    assert s.createBackup() == ""
    [b] = s.backups
    assert b["favorites"] == 1 and "1 favorite" in b["text"] and s.backupFolder.endswith("backups")

    assert ctl.roomEditor.saveDevice("demo:coffee", {"favorite": False, "name": ""}) == ""
    assert s.save({"theme": "dark"}) == {}
    assert s.restoreBackup("../settings.json").startswith("Restore failed")
    assert s.restoreBackup(b["name"]) == ""
    assert pump_until(lambda: calls)                                # restarts to load them
    assert messages == ["Settings restored. Restarting the app …"]
    restored = SettingsStore(tmp_path / "settings.json")
    assert restored.rooms["favorites"] == ["demo:coffee"] and restored.rooms["names"]["demo:coffee"] == "Espresso"
    assert restored.get("theme") != "dark"
    s.deleteBackup(b["name"])
    assert s.backups == []
