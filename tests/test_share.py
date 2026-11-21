"""Sharing the settings between panels over MQTT: what is shared, what stays, save and load."""
import asyncio
import json
import socket
import threading
import time

import pytest

from app import share
from app.config import AppConfig, MqttConfig
from app.qt.controller import Controller
from app.settings import SettingsStore

from test_qt import pump_until, qapp  # noqa: F401 – the Qt application fixture

KITCHEN = {
    "theme": "dark", "language": "de", "idle_seconds": 60, "upside_down": True, "alarm_pin": "1234",
    "wifi_ssid": "Guests", "wifi_password": "secret", "wifi_favorite": True, "hap_host": "10.0.0.5",
    "hap_pin": "111-22-333", "mqtt_enabled": True, "mqtt_host": "broker-a", "mqtt_password": "pw",
    "panel_name": "Kitchen", "show_general": False,
    "rooms": {"order": ["Kitchen", "Hall"], "devices": {"demo:coffee": "Kitchen"}, "names": {"demo:coffee": "Espresso"},
              "favorites": ["demo:coffee"], "hidden": ["demo:fan"]},
    "groups": [{"id": "g1", "name": "All lights", "room": "Hall", "members": []}],
    "switch_groups": [], "virtual": [{"id": "pressure", "name": "Pressure", "topic": "boiler/p"}],
}


def test_shared_part_leaves_out_local_settings_and_secrets():
    part = share.shared_part(KITCHEN)
    assert part["rooms"]["names"] == {"demo:coffee": "Espresso"} and "favorites" not in part["rooms"]
    assert part["hap_host"] == "10.0.0.5" and part["wifi_ssid"] == "Guests" and part["show_general"] is False
    assert len(part["groups"]) == 1 and len(part["virtual"]) == 1
    for local in ("theme", "language", "idle_seconds", "upside_down", "alarm_pin", "wifi_password", "wifi_favorite",
                  "hap_pin", "mqtt_enabled", "mqtt_host", "mqtt_password", "panel_name"):
        assert local not in part, local


def test_merge_keeps_the_own_favorites_and_settings():
    hall = {"theme": "light", "alarm_pin": "9999", "hap_pin": "031-45-154", "mqtt_host": "broker-b",
            "rooms": {"order": ["Hall"], "favorites": ["demo:alarm"]}, "groups": [], "panel_name": "Hall"}
    merged = share.merge(hall, share.shared_part(KITCHEN))
    assert merged["rooms"]["order"] == ["Kitchen", "Hall"] and merged["rooms"]["favorites"] == ["demo:alarm"]
    assert merged["groups"] == KITCHEN["groups"] and merged["hap_host"] == "10.0.0.5"
    assert (merged["theme"], merged["alarm_pin"], merged["hap_pin"], merged["mqtt_host"], merged["panel_name"]) == \
        ("light", "9999", "031-45-154", "broker-b", "Hall")


@pytest.fixture
def broker():
    """A real MQTT broker (amqtt) on a free port."""
    amqtt_broker = pytest.importorskip("amqtt.broker")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    loop = asyncio.new_event_loop()
    started = threading.Event()

    def run():
        asyncio.set_event_loop(loop)
        b = amqtt_broker.Broker({"listeners": {"default": {"type": "tcp", "bind": f"127.0.0.1:{port}"}},
                                 "sys_interval": 0, "auth": {"allow-anonymous": True, "plugins": ["auth_anonymous"]},
                                 "topic-check": {"enabled": False}}, loop=loop)
        loop.run_until_complete(b.start())
        started.set()
        loop.run_forever()
    threading.Thread(target=run, daemon=True).start()
    assert started.wait(10)
    yield port
    loop.call_soon_threadsafe(loop.stop)


def test_save_and_load_on_a_broker(broker):
    cfg = MqttConfig(host="127.0.0.1", port=broker, timeout=3)
    assert share.load(cfg, wait=0.5) is None                     # nothing saved yet
    share.save(cfg, share.payload(KITCHEN, "Kitchen", "1.2.3"))
    data = share.load(cfg)
    assert data["panel"] == "Kitchen" and data["version"] == "1.2.3" and data["saved"]
    assert data["settings"] == share.shared_part(KITCHEN)
    assert "secret" not in json.dumps(data) and "1234" not in json.dumps(data)
    with pytest.raises(share.ShareError):
        share.load(MqttConfig(host="127.0.0.1", port=1, timeout=1))


def test_two_panels_share_over_mqtt(qapp, tmp_path, broker):
    def panel(name, values):
        store = SettingsStore(tmp_path / name / "settings.json")
        store.update({"hap_enabled": False, "language": "en", "mqtt_enabled": True, "mqtt_host": "127.0.0.1",
                      "mqtt_port": broker, "panel_name": name, **values})
        return Controller(AppConfig.model_validate({"demo": {"enabled": True}}), store)

    kitchen = panel("Kitchen", {"theme": "dark", "alarm_pin": "1234"})
    kitchen.start()
    assert pump_until(lambda: len(kitchen.devices.all()) == 29)
    assert kitchen.roomEditor.addRoom("Office") == "" and kitchen.roomEditor.assign("demo:coffee", "Office") == ""
    assert kitchen.roomEditor.saveDevice("demo:coffee", {"name": "Espresso", "favorite": True}) == ""
    s = kitchen.settings
    assert s.sharingAvailable and s.sharedInfo() == {"error": "", "empty": True}
    assert s.saveShared() == ""
    info = s.sharedInfo()
    assert info["panel"] == "Kitchen" and info["saved"] and "2 rooms" in info["text"] and "favorite" not in info["text"]
    kitchen.shutdown()

    hall = panel("Hall", {"theme": "light", "alarm_pin": "9999"})
    hall.store.rooms = {"favorites": ["demo:alarm"]}
    hall.store.save()
    restarts = []
    hall._exec = lambda path, argv: restarts.append(argv)
    assert hall.settings.loadShared() == ""
    assert pump_until(lambda: restarts)                          # restarts to load them
    loaded = SettingsStore(tmp_path / "Hall" / "settings.json")
    assert loaded.rooms["devices"]["demo:coffee"] == "Office" and loaded.rooms["names"]["demo:coffee"] == "Espresso"
    assert loaded.rooms["favorites"] == ["demo:alarm"]           # its own favorites
    assert (loaded.get("theme"), loaded.get("alarm_pin"), loaded.get("panel_name")) == ("light", "9999", "Hall")
    assert len(hall.settings.backups) == 1                       # the settings before loading


def test_sharing_needs_mqtt(qapp, tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.update({"hap_enabled": False, "language": "en"})
    ctl = Controller(AppConfig.model_validate({"demo": {"enabled": True}}), store)
    assert not ctl.settings.sharingAvailable
    assert ctl.settings.sharedInfo()["error"].startswith("MQTT broker: Set up the MQTT broker")
    assert ctl.settings.saveShared().startswith("Saving to MQTT failed")
    ctl.shutdown()


def test_share_buttons_on_the_backups_page(qapp, tmp_path, broker):
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from shiboken6 import Shiboken
    from app.qt.main import QML_DIR

    store = SettingsStore(tmp_path / "settings.json")
    store.update({"hap_enabled": False, "language": "en", "mqtt_enabled": True, "mqtt_host": "127.0.0.1",
                  "mqtt_port": broker, "panel_name": "Kitchen"})
    ctl = Controller(AppConfig.model_validate({"demo": {"enabled": True}}), store)
    restarts = []
    ctl._exec = lambda path, argv: restarts.append(argv)
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
        root = item or win.contentItem()
        while item is None and root.parentItem() is not None:      # dialogs live in the overlay
            root = root.parentItem()
        for child in root.childItems():
            if child.objectName() == name and child.isVisible():
                return child
            if (hit := find(name, child)) is not None:
                return hit
        return None

    def tap(name):
        assert pump_until(lambda: find(name) is not None), name
        assert pump_until(lambda: not busy.property("visible"))
        it = find(name)
        p = it.mapToScene(QPointF(it.width() / 2, it.height() / 2)).toPoint()
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)

    win.setProperty("settingsOpen", True)
    assert pump_until(lambda: win.findChild(QObject, "settingsPage") is not None)
    win.findChild(QObject, "settingsPage").setProperty("subPage", "backups_page")
    tap("shareSave")                                             # nothing on the broker: saved at once
    assert pump_until(lambda: "Saved on the MQTT broker" in find("backupMessage").property("text"), timeout=8)
    def question():
        field = win.findChild(QObject, "backupConfirm").property("field")
        return field.toVariant().get("confirm", "") if field is not None else ""

    tap("shareSave")                                             # now it asks before overwriting
    assert pump_until(lambda: question().startswith("Overwrite the settings Kitchen saved on"), timeout=8)
    tap("confirmCancel")
    tap("shareLoad")
    confirm = win.findChild(QObject, "backupConfirm")
    assert pump_until(lambda: confirm.property("opened") and question().startswith("Load the settings Kitchen saved on"),
                      timeout=8)
    tap("confirmOk")
    assert pump_until(lambda: restarts, timeout=8)               # loaded, the app restarts
    win.close()
    engine.deleteLater()
    pump_until(lambda: False, timeout=0.3)
