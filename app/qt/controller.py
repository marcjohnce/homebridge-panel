"""Bridge between device management (asyncio, own thread) and the QML UI."""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from PySide6.QtCore import (QAbstractListModel, QByteArray, QCollator, QEvent, QLocale, QModelIndex, QObject, Qt,
                            QTimer, Property, Signal, Slot)

from .. import __version__, i18n
from ..i18n import tr
from ..backends import BackendError, HapBackend, create_backends
from ..config import AppConfig, HapBackendConfig, MqttConfig, VirtualDevice
from ..manager import DeviceManager, DeviceNotFound
from ..backends.mqtt import MqttBackend, test_connection as test_mqtt
from ..rooms import BUILTIN_DEFAULT, RoomLayout
from ..scheduler import Scheduler
from ..updater import UpdateError, Updater
from ..eve_history import DeviceHistory, bucket, energy_kwh
from ..backup import BackupError, Backups
from ..display_power import DisplayPower
from ..settings import ACTIONS, SettingsStore, apply_to_config, validate
from ..models import AREAS, KIND_ICONS, KIND_KEYS, QUIET_KINDS
from ..wifi import Wifi, qr_image
from . import format as fmt
from .format import (air_warning, alert_level, battery_low, battery_text, category, fmt_temp, has_detail,
                     short_name, state_text)

log = logging.getLogger(__name__)
ALL_ROOMS = ""
FAVORITES = "favorites"
WIFI_TILE = "wifi:guest"            # tile of the panel itself: shows the guest Wi-Fi as a QR code            # first menu entry: favorite devices of every room
NIGHT_FROM, NIGHT_TO = 19, 7


# light attribute -> capability a group member needs for it
GROUP_ATTR_CAPS = {"hue": "color", "saturation": "color", "color_temp": "color_temp", "brightness": "brightness"}


def _emit_safely(signal: Any, *args: Any) -> None:
    """Emits from a background callback; the receiver may be gone after a shutdown."""
    try:
        signal.emit(*args)
    except RuntimeError:
        pass



def _is_on_light(d: dict[str, Any]) -> bool:
    """A light, switch or plug of the Lights menu that is on (blinds, TVs and speakers do not count)."""
    return (category(d) == "light" and d["type"] in ("light", "switch", "plug") and d["reachable"]
            and bool(d.get("state", {}).get("on")))

class AsyncRunner:
    """Dedicated asyncio loop in a background thread so the UI never blocks."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name="smarthome-io", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro) -> concurrent.futures.Future:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)


class DeviceModel(QAbstractListModel):
    """Devices of the selected menu area and room (or all rooms) for the tile grid."""

    ROLES = ("deviceId", "name", "shortName", "room", "type", "icon", "isOn", "reachable", "heating",
             "stateText", "hasDetail", "targetTemp", "minTemp", "maxTemp", "modeOff", "alertLevel", "warning",
             "batteryLow")
    # order inside a room: per menu area
    RANK = {"light": 0, "switch": 1, "plug": 1, "tv": 1, "valve": 1, "blind": 2, "thermostat": 0, "sensor": 1, "fan": 2}

    def __init__(self, parent: QObject | None = None, layout: RoomLayout | None = None):
        super().__init__(parent)
        self.layout = layout or RoomLayout()
        self.grouped: set[str] = set()      # lights shown only through their light group
        self._all: dict[str, dict[str, Any]] = {}
        self._rows: list[str] = []
        self._room = ALL_ROOMS
        self._room_auto = True        # follow the first room until one is chosen
        self._category = "light"     # "" = every device (tests, tools)
        self._ids = {Qt.ItemDataRole.UserRole + 1 + i: n for i, n in enumerate(self.ROLES)}

    def roleNames(self) -> dict[int, QByteArray]:
        return {k: QByteArray(v.encode()) for k, v in self._ids.items()}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._rows) or role not in self._ids:
            return None
        return self.role_value(self._all[self._rows[index.row()]], self._ids[role])

    @staticmethod
    def role_value(d: dict[str, Any], role: str) -> Any:
        s, m = d.get("state", {}), d.get("meta", {})
        match role:
            case "deviceId": return d["id"]
            case "name": return d["name"]
            case "shortName": return short_name(d["name"], d["room"])
            case "room": return d["room"]
            case "type": return d["type"]
            case "icon": return d["icon"]
            # gold "on" highlight: not for heating, sensors or blinds (open is not "on")
            case "isOn": return d["type"] not in ("thermostat", "sensor", "blind", "garage", "lock") and bool(s.get("on")) and d["reachable"]
            case "reachable": return d["reachable"]
            case "heating": return bool(s.get("heating")) and d["reachable"]
            case "stateText": return state_text(d)
            case "hasDetail": return has_detail(d)
            case "targetTemp": return float(s.get("target_temp") or 20)
            case "minTemp": return float(m.get("min_temp", 10))
            case "maxTemp": return float(m.get("max_temp", 30))
            case "modeOff": return s.get("mode") == "off"
            case "batteryLow": return battery_low(d)
            case "alertLevel": return alert_level(d)
            case "warning": return air_warning(d)
        return None

    # --- maintenance ---
    def rooms(self, cat: str | None = None) -> list[str]:
        """Rooms with devices (of a menu area), in the order set in the settings."""
        return self.layout.sort({d["room"] for d in self.shown() if not cat or category(d) == cat})

    def device_rooms(self) -> dict[str, str]:
        return {d["id"]: d["room"] for d in self.all()}

    def base_rooms(self) -> dict[str, str]:
        return {d["id"]: d["baseRoom"] for d in self.all()}

    def _place(self, d: dict[str, Any]) -> dict[str, Any]:
        """Applies what was set on the panel: room, display name, kind (security sensors, switches,
        plugs), menu area and outdoor flag. "baseRoom", "baseName", "baseKind", "baseArea" … keep
        the values from Homebridge / config.yaml."""
        base = d.get("baseRoom", d["room"])
        base_name = d.get("baseName", d["name"])
        out = {**d, "baseRoom": base, "room": self.layout.room_of(d["id"], base),
               "baseName": base_name, "name": self.layout.names.get(d["id"]) or base_name,
               "hidden": d["id"] in self.layout.hidden,
               "favorite": d["id"] in self.layout.favorites,
               "grouped": d["id"] in self.grouped}
        meta = d.get("meta", {})
        base_outdoor = d.get("baseOutdoor", bool(meta.get("outdoor")))
        outdoor = self.layout.outdoor.get(d["id"], base_outdoor)
        meta = {**meta, "outdoor": outdoor} if outdoor else {k: v for k, v in meta.items() if k != "outdoor"}
        out.update(baseOutdoor=base_outdoor, meta=meta)
        base_area = d.get("baseArea", meta.get("area", ""))
        area = self.layout.areas.get(d["id"], base_area).replace("auto", "")
        meta = {**meta, "area": area} if area else {k: v for k, v in meta.items() if k != "area"}
        out.update(baseArea=base_area, meta=meta)
        key = next((k for k in KIND_KEYS if k in meta), None)
        if key:
            base_kind = d.get("baseKind", meta[key])
            kind = self.layout.kinds.get(d["id"], base_kind)
            if kind not in meta.get("kinds", ()):
                kind = base_kind
            base_icon = d.get("baseIcon", d["icon"])
            # follow the kind unless config.yaml set an icon of its own
            follows = base_icon == KIND_ICONS.get(base_kind) or base_icon in ("switch", "plug", "light")
            icon = KIND_ICONS[kind] if follows else base_icon
            out.update(baseKind=base_kind, baseIcon=base_icon, icon=icon, meta={**meta, key: kind})
        # security alerts off: set on the panel, by default for presence sensors
        kind = out["meta"].get("security")
        alerts = d["type"] in ("security", "garage", "lock") or bool(d.get("meta", {}).get("opening"))
        out["quiet"] = alerts and self.layout.quiet.get(d["id"], kind in QUIET_KINDS)
        return out

    def reassign(self) -> None:
        """Re-applies the room layout after it was edited (or the language changed)."""
        self._all = {k: self._place(d) for k, d in self._all.items()}
        rows = self._visible()
        if rows != self._rows:
            self.beginResetModel()
            self._rows = rows
            self.endResetModel()
        else:
            self.refresh_texts()

    def _visible(self) -> list[str]:
        if self._category == FAVORITES:      # every room, in the order set in the settings
            favs = [d for d in self.shown() + self.tiles() if d.get("favorite")]
            return [d["id"] for d in sorted(favs, key=lambda d: self.layout.favorite_rank(d["id"]))]
        devs = [d for d in self.shown() if self._room in (ALL_ROOMS, d["room"])
                and self._category in ("", category(d))]
        # alarms first, then open windows/doors; otherwise the order of rooms and devices – under
        # "All" by name instead
        alerts = {d["id"]: alert_level(d) for d in devs}
        base = self.by_name(devs) if self._room == ALL_ROOMS else self.ordered(devs)
        # the alarm system always comes first
        return [d["id"] for d in sorted(base, key=lambda d: (d["type"] != "alarm", -alerts[d["id"]]))]

    @staticmethod
    def by_name(devs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Alphabetically by the name on the tile – the display name (set on the panel or from
        Homebridge) without the room the tile shows above it, "Living Room Blinds" → "Blinds" –,
        as the panel language sorts ("Ä" with "A" in German) and "Lamp 2" before "Lamp 10".
        Same names: by room."""
        collator = QCollator(QLocale(i18n.locale_name()))
        collator.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        collator.setNumericMode(True)
        stable = sorted(devs, key=lambda d: d["id"])        # same names and rooms: always the same order
        stable = sorted(stable, key=lambda d: collator.sortKey(d["room"]))
        return sorted(stable, key=lambda d: collator.sortKey(short_name(d["name"], d["room"])))

    def ordered(self, devs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Room order, then the manual order in the room (settings), then kind of device,
        order from config.yaml and name."""
        room_rank = {r: i for i, r in enumerate(self.layout.all_rooms(d["room"] for d in self.all()))}
        return sorted(devs, key=lambda d: (room_rank.get(d["room"], 0), self.layout.device_rank(d["room"], d["id"]),
                                           self.RANK.get(d["type"], 0), d.get("order", 100), d["name"].casefold()))

    def set_category(self, cat: str, room: str) -> None:
        self._category = cat
        self._room = room
        self._relayout()

    def count(self, pred) -> int:
        """Counts devices shown on the home screen (hidden ones are left out)."""
        return sum(1 for d in self.shown() if pred(d))

    def favorites(self) -> list[dict[str, Any]]:
        """Favorite devices (also hidden ones) in their order."""
        return sorted((d for d in self._all.values() if d.get("favorite")),
                      key=lambda d: self.layout.favorite_rank(d["id"]))

    def shown(self) -> list[dict[str, Any]]:
        return [d for d in self.all() if not d.get("hidden") and not d.get("grouped")]

    def tiles(self) -> list[dict[str, Any]]:
        """Tiles of the panel itself (the Wi-Fi code): only among the favorites, not counted as devices."""
        return [d for d in self._all.values() if d.get("panelTile")]

    def _relayout(self) -> None:
        rows = self._visible()
        if rows != self._rows:
            self.beginResetModel()
            self._rows = rows
            self.endResetModel()

    def set_room(self, room: str) -> None:
        self._room = room
        self._relayout()

    def set_all(self, devices: list[dict[str, Any]]) -> None:
        """New devices from the backends; the tiles of the panel itself stay."""
        self.beginResetModel()
        tiles = {d["id"]: d for d in self.tiles()}
        self._all = {**{d["id"]: self._place(d) for d in devices}, **tiles}
        self._rows = self._visible()
        self.endResetModel()

    def upsert(self, d: dict[str, Any]) -> bool:
        """Returns True if the structure (room, name, order) changed."""
        old = self._all.get(d["id"])
        d = self._place(d)
        self._all[d["id"]] = d
        structural = (old is None or any(old.get(k) != d.get(k) for k in ("room", "name", "order", "hidden", "grouped", "favorite"))
                      or alert_level(old) != alert_level(d))
        if structural:
            self._relayout()
        elif d["id"] in self._rows:
            idx = self.index(self._rows.index(d["id"]))
            self.dataChanged.emit(idx, idx)
        return structural

    def remove(self, dev_id: str) -> None:
        if self._all.pop(dev_id, None) is not None:
            self._relayout()

    def get(self, dev_id: str) -> dict[str, Any] | None:
        return self._all.get(dev_id)

    def refresh_texts(self) -> None:
        """Re-reads all roles, e.g. after a language change (state texts are translated)."""
        if self._rows:
            self.dataChanged.emit(self.index(0), self.index(len(self._rows) - 1))

    def all(self) -> list[dict[str, Any]]:
        """Devices, without the tiles of the panel itself."""
        return [d for d in self._all.values() if not d.get("panelTile")]


class SettingsBridge(QObject):
    sectionsChanged = Signal()
    testFinished = Signal(bool, str)
    backupsChanged = Signal()

    def __init__(self, store: SettingsStore, controller: "Controller"):
        super().__init__(controller)
        self._store = store
        self._ctl = controller
        self._backups = Backups(store.path, __version__)

    # ---------- backups (Settings → System → Backups) ----------
    @Property("QVariantList", notify=backupsChanged)
    def backups(self) -> list[dict[str, Any]]:
        """Newest first, with a short text of what each one contains."""
        def plural(n: int, one: str, many: str) -> str:
            return one if n == 1 else many.format(n=n)
        out = []
        for b in self._backups.list():
            parts = [plural(b["rooms"], tr("1 room"), tr("{n} rooms")),
                     plural(b["favorites"], tr("1 favorite"), tr("{n} favorites"))]
            if b["groups"]:
                parts.append(plural(b["groups"], tr("1 group"), tr("{n} groups")))
            if b["virtual"]:
                parts.append(plural(b["virtual"], tr("1 virtual device"), tr("{n} virtual devices")))
            out.append({**b, "text": ", ".join(parts)})
        return out

    @Property(str, constant=True)
    def backupFolder(self) -> str:
        return str(self._backups.folder)

    @Slot(result=str)
    def createBackup(self) -> str:
        """Saves the current settings; returns an error text or ""."""
        try:
            self._store.save()                  # what is on screen is what gets saved
            self._backups.create()
        except (BackupError, OSError) as e:
            return tr("Backup failed: {error}").format(error=e)
        self.backupsChanged.emit()
        return ""

    @Slot(str, result=str)
    def restoreBackup(self, name: str) -> str:
        """Puts the settings of a backup back and restarts the app to load them."""
        try:
            self._backups.restore(name)
        except BackupError as e:
            return tr("Restore failed: {error}").format(error=e)
        self._ctl.restarting.emit(tr("Settings restored. Restarting the app …"))
        QTimer.singleShot(600, self._ctl._restart_app)
        return ""

    @Slot(str)
    def deleteBackup(self, name: str) -> None:
        try:
            self._backups.delete(name)
        except BackupError as e:
            self._ctl.toast.emit(str(e))
        self.backupsChanged.emit()

    @Property("QVariantList", notify=sectionsChanged)
    def sections(self) -> list[dict[str, Any]]:
        return self._store.schema()

    @Property(str, constant=True)
    def path(self) -> str:
        return str(self._store.path)

    @Slot(str, "QVariant", result=str)
    def validate(self, key: str, value: Any) -> str:
        return validate(key, value)[1] or ""

    @Slot(str, "QVariant", result="QVariant")
    def normalized(self, key: str, value: Any) -> Any:
        return validate(key, value)[0]

    @Slot("QVariantMap", result="QVariantMap")
    def save(self, changes: dict[str, Any]) -> dict[str, str]:
        errors = self._store.update(dict(changes))
        if not errors:
            self.sectionsChanged.emit()
            self._ctl.settings_saved(set(changes))
        return errors

    @Slot(str)
    def runAction(self, key: str) -> None:
        self._ctl.run_action(key)

    @Slot(str, "QVariant", str, str, str)
    def testMqtt(self, host: str, port: Any, protocol: str, user: str, password: str) -> None:
        for key, value in (("mqtt_host", host), ("mqtt_port", port), ("mqtt_protocol", protocol)):
            v, err = validate(key, value)
            if err:
                self.testFinished.emit(False, err)
                return
            if key == "mqtt_port":
                port = v
        cfg = MqttConfig(host=host.strip(), port=port, protocol=protocol, username=user or None,
                         password=password or None, timeout=4)
        fut = self._ctl.runner.submit(test_mqtt(cfg))
        fut.add_done_callback(lambda f: _emit_safely(self.testFinished, *f.result()))

    @Slot(str, "QVariant", str)
    def testConnection(self, host: str, port: Any, pin: str) -> None:
        for key, value in (("hap_host", host), ("hap_port", port), ("hap_pin", pin)):
            v, err = validate(key, value)
            if err:
                self.testFinished.emit(False, err)
                return
            if key == "hap_port":
                port = v
            if key == "hap_pin":
                pin = v

        async def probe():
            backend = HapBackend(HapBackendConfig(name="test", host=host.strip(), port=port, pin=pin, timeout=4))
            try:
                snaps = await backend.fetch()
                return True, tr("Connected: found {n} controllable devices").format(n=len(snaps))
            except BackendError as e:
                return False, str(e)
            except Exception as e:  # pragma: no cover - surface unexpected errors
                return False, tr("Connection failed: {error}").format(error=e)
            finally:
                await backend.stop()

        fut = self._ctl.runner.submit(probe())
        fut.add_done_callback(lambda f: _emit_safely(self.testFinished, *f.result()))


def _cached(fn):
    """The list is built once per `changed` signal (QML reads it from many places)."""
    name = fn.__name__

    def get(self):
        if name not in self._cache:
            self._cache[name] = fn(self)
        return self._cache[name]
    get.__name__ = name
    get.__doc__ = fn.__doc__
    return get


class RoomsBridge(QObject):
    """Room management in the settings (RoomsPage.qml). Changes apply and save immediately –
    except moving rooms and devices up and down: the page moves the rows itself, the new order
    is saved and shown on the home screen once the page is left (finishMoves), and written to
    the settings file a few seconds after the last move in case the panel loses power."""
    changed = Signal()
    SAVE_DELAY = 4000       # ms after the last move

    def __init__(self, store: SettingsStore, controller: "Controller"):
        super().__init__(controller)
        self._store = store
        self._ctl = controller
        self._cache: dict[str, Any] = {}
        self._moves_pending = False
        self._save_timer = QTimer(self, singleShot=True, interval=self.SAVE_DELAY, timeout=self.save_moves)

    def _moved(self) -> None:
        self._moves_pending = True
        self._save_timer.start()

    def save_moves(self) -> None:
        """Writes the order to the settings file (nothing on screen changes)."""
        self._save_timer.stop()
        self._store.rooms = self._layout.to_dict()
        self._store.save()

    @Slot()
    def finishMoves(self) -> None:
        """After moving: save the order, let the home screen and the lists follow."""
        if self._moves_pending:
            self._commit()

    def notify(self) -> None:
        """Lists changed: build them again when read. (Not a slot on `changed`: QML bindings
        hear about the signal before connected slots run and would read the old lists.)"""
        self._cache.clear()
        self.changed.emit()

    @property
    def _layout(self) -> RoomLayout:
        return self._ctl._model.layout

    def _commit(self) -> None:
        self._moves_pending = False
        self.save_moves()
        self._ctl._model.reassign()
        self._ctl._refresh_rooms()
        self._ctl.climateChanged.emit()     # hidden sensors leave the temperature average

    @Property("QVariantList", notify=changed)
    @_cached
    def rooms(self) -> list[dict[str, Any]]:
        dev_rooms = self._ctl._model.device_rooms()
        counts: dict[str, int] = {}
        for r in dev_rooms.values():
            counts[r] = counts.get(r, 0) + 1
        default = self._layout.default_room
        return [{"name": r, "count": counts.get(r, 0), "isDefault": r == default}
                for r in self._layout.all_rooms(dev_rooms.values())]

    KIND_LABELS = {"window": "Window", "door": "Door", "contact": "Contact", "glassbreak": "Glass break",
                   "leak": "Leak", "motion": "Motion", "presence": "Presence",
                   "smoke": "Smoke detector", "co": "CO detector",
                   "switch": "Switch", "plug": "Plug", "coffee": "Coffee machine",
                   "washer": "Washing machine", "dishwasher": "Dishwasher", "fan": "Fan",
                   "bulb": "Bulb", "ceiling": "Ceiling lamp", "spot": "Spotlight", "wall": "Wall lamp",
                   "table": "Table lamp", "desk": "Desk lamp", "floorlamp": "Floor lamp", "globe": "Globe lamp", "tube": "Fluorescent tube", "pendant": "Pendant light", "chandelier": "Chandelier",
                   "strip": "LED strip",
                   "generic": "Valve", "irrigation": "Irrigation", "shower": "Shower head", "faucet": "Faucet"}
    AREA_LABELS = {"": "Automatic", "light": "Lights", "climate": "Climate", "security": "Security"}

    @Property("QVariantList", notify=changed)
    @_cached
    def devices(self) -> list[dict[str, Any]]:
        devs = self._ctl._model.ordered(self._ctl._model.all())     # same order as the tiles
        virtual = {f"mqtt:{v['id']}": v for v in self._store.virtual}
        groups = {f"group:{g['id']}": g for g in self._store.groups}
        switch_groups = {f"choice:{g['id']}": g for g in self._store.switch_groups}
        out = []
        for d in devs:
            kinds = d.get("meta", {}).get("kinds", [])
            v, g = virtual.get(d["id"]), groups.get(d["id"])
            out.append({"id": d["id"], "name": d["name"], "baseName": d["baseName"], "icon": d["icon"],
                        "room": d["room"], "reachable": d["reachable"], "type": d["type"],
                        "grouped": bool(d.get("grouped")),
                        # virtual device (MQTT) and light group: edited in their own dialogs
                        "virtual": v or None, "group": g or None,
                        "switchGroup": switch_groups.get(d["id"]),
                        "kind": next((d["meta"][k] for k in KIND_KEYS if k in d.get("meta", {})), ""),
                        "hidden": bool(d.get("hidden")),
                        "favorite": bool(d.get("favorite")),
                        "area": d.get("meta", {}).get("area", ""),
                        "areas": [{"value": a, "label": tr(self.AREA_LABELS[a])} for a in ("", *AREAS)],
                        # temperature sensors can be marked as outdoor sensors (not thermostats)
                        "canOutdoor": d["type"] == "sensor" and d.get("state", {}).get("current_temp") is not None,
                        "outdoor": bool(d.get("meta", {}).get("outdoor")),
                        # security sensors (not leak, smoke, CO, glass break) can be kept out of alerts
                        "canQuiet": d["type"] in ("security", "garage", "lock") or bool(d.get("meta", {}).get("opening")),
                        "quiet": bool(d.get("quiet")),
                        "kinds": [{"value": k, "label": tr(self.KIND_LABELS[k]), "icon": KIND_ICONS[k]}
                                  for k in kinds] if len(kinds) > 1 else []})
        return out

    @Property("QVariantList", notify=changed)
    @_cached
    def favorites(self) -> list[dict[str, Any]]:
        """Favorites in their order, listed like the devices above."""
        ids = [d["id"] for d in self._ctl._model.favorites()]
        devs = {d["id"]: d for d in self.devices}
        # tiles of the panel itself (the Wi-Fi code): listed to be moved, set up elsewhere
        devs.update({d["id"]: {"id": d["id"], "name": d["name"], "icon": d["icon"], "room": tr("Wi-Fi for guests"),
                               "reachable": True, "hidden": False, "panelTile": True}
                     for d in self._ctl._model.tiles()})
        return [devs[i] for i in ids if i in devs]

    @Slot(str, int)
    def moveFavorite(self, dev_id: str, delta: int) -> None:
        self._layout.move_favorite(dev_id, delta, [d["id"] for d in self._ctl._model.favorites()])
        self._moved()

    @Slot(str, int)
    def moveDevice(self, dev_id: str, delta: int) -> None:
        """Moves a device up or down within its room (order of the tiles)."""
        m = self._ctl._model
        d = m.get(dev_id)
        if not d:
            return
        ids = [x["id"] for x in m.ordered(m.all()) if x["room"] == d["room"]]
        self._layout.move_device(d["room"], dev_id, delta, ids)
        self._moved()

    # ---------- virtual devices (MQTT) ----------
    @Slot("QVariantMap", result=str)
    def saveVirtual(self, values: dict[str, Any]) -> str:
        """New (no id) or changed virtual device; the MQTT connection restarts to subscribe."""
        name = " ".join(str(values.get("name", "")).split())
        topic = str(values.get("topic", "")).strip()
        if not name:
            return tr("Enter a name")
        if not topic:
            return tr("Enter an MQTT topic")
        vid = str(values.get("id") or "") or "v" + secrets.token_hex(3)
        try:
            dev = VirtualDevice(id=vid, name=name, topic=topic, unit=str(values.get("unit", "")).strip(),
                                json_key=str(values.get("jsonKey", "")).strip(),
                                decimals=int(values.get("decimals", 1)), icon=str(values.get("icon") or "gauge"))
        except ValueError as e:
            return str(e)
        self._store.virtual = [v for v in self._store.virtual if v.get("id") != vid] + [dev.model_dump()]
        room = values.get("room")
        if room:
            self._layout._set(f"mqtt:{vid}", str(room), BUILTIN_DEFAULT)
        if "favorite" in values:
            self._layout.set_favorite(f"mqtt:{vid}", bool(values["favorite"]))
        self._store.rooms = self._layout.to_dict()
        self._store.save()
        self._ctl.restart_backends()
        self.notify()
        return ""

    @Slot(str)
    def deleteVirtual(self, vid: str) -> None:
        self._store.virtual = [v for v in self._store.virtual if v.get("id") != vid]
        self._layout.assign.pop(f"mqtt:{vid}", None)
        self._layout.set_favorite(f"mqtt:{vid}", False)
        self._store.rooms = self._layout.to_dict()
        self._store.save()
        self._ctl.restart_backends()
        self.notify()

    @Slot(str, result=str)
    def lastValue(self, dev_id: str) -> str:
        """What the MQTT topic of a virtual device sent last, for its dialog."""
        d = self._ctl._model.get(dev_id)
        if not d:
            return ""
        topic = d.get("meta", {}).get("topic", "")
        backend = self._ctl.mqtt_backend()
        if not backend or topic not in backend.payloads:
            return tr("No value received yet")
        age = int(time.time() - backend.received[topic])
        return tr("Received {age} s ago: {value}").format(age=age, value=backend.payloads[topic][:60])

    # ---------- light groups ----------
    @Property("QVariantList", notify=changed)
    @_cached
    def lights(self) -> list[dict[str, Any]]:
        """Lights that can join a group (not groups themselves)."""
        m = self._ctl._model
        return [{"id": d["id"], "name": d["name"], "icon": d["icon"], "room": d["room"]}
                for d in m.ordered(m.all()) if d["type"] == "light" and not d.get("meta", {}).get("group")]

    @Slot("QVariantMap", result=str)
    def saveGroup(self, values: dict[str, Any]) -> str:
        name = " ".join(str(values.get("name", "")).split())
        room = str(values.get("room", ""))
        members = [str(x) for x in values.get("members", [])]
        if not name:
            return tr("Enter a name")
        lights = {d["id"]: d for d in self.lights}
        if not members:
            return tr("Choose at least one light")
        if any(m not in lights or lights[m]["room"] != room for m in members):
            return tr("All lights of a group must be in its room")
        gid = str(values.get("id") or "") or "g" + secrets.token_hex(3)
        group = {"id": gid, "name": name, "room": room, "members": members, "hide": bool(values.get("hide", True))}
        self._store.groups = [g for g in self._store.groups if g.get("id") != gid] + [group]
        if "favorite" in values:
            self._layout.set_favorite(f"group:{gid}", bool(values["favorite"]))
        self._store.save()
        self._ctl.refresh_groups()
        self._commit()
        return ""

    @Slot(str)
    def deleteGroup(self, gid: str) -> None:
        self._store.groups = [g for g in self._store.groups if g.get("id") != gid]
        self._layout.set_favorite(f"group:{gid}", False)
        self._store.save()
        self._ctl.refresh_groups()
        self._commit()

    # ---------- switch groups ----------
    @Property("QVariantList", notify=changed)
    @_cached
    def switches(self) -> list[dict[str, Any]]:
        """Switches, plugs and valves that can join a switch group."""
        m = self._ctl._model
        return [{"id": d["id"], "name": d["name"], "icon": d["icon"], "room": d["room"]}
                for d in m.ordered(m.all())
                if d["type"] in ("switch", "plug", "valve") and not d.get("meta", {}).get("choice")]

    @Slot("QVariantMap", result=str)
    def saveSwitchGroup(self, values: dict[str, Any]) -> str:
        name = " ".join(str(values.get("name", "")).split())
        room = str(values.get("room", ""))
        members = list(dict.fromkeys(str(x) for x in values.get("members", [])))
        area = str(values.get("area", ""))
        if not name:
            return tr("Enter a name")
        if len(members) < 2:
            return tr("Choose at least two switches")
        switches = {d["id"]: d for d in self.switches}
        if any(m not in switches or switches[m]["room"] != room for m in members):
            return tr("All switches of a group must be in its room")
        gid = str(values.get("id") or "") or "s" + secrets.token_hex(3)
        group = {"id": gid, "name": name, "room": room, "members": members, "hide": bool(values.get("hide", True)),
                 "allow_off": bool(values.get("allowOff", True)), "area": area if area in AREAS else ""}
        self._store.switch_groups = [g for g in self._store.switch_groups if g.get("id") != gid] + [group]
        if "favorite" in values:
            self._layout.set_favorite(f"choice:{gid}", bool(values["favorite"]))
        self._store.save()
        self._ctl.refresh_groups()
        self._commit()
        return ""

    @Slot(str)
    def deleteSwitchGroup(self, gid: str) -> None:
        self._store.switch_groups = [g for g in self._store.switch_groups if g.get("id") != gid]
        self._layout.set_favorite(f"choice:{gid}", False)
        self._store.save()
        self._ctl.refresh_groups()
        self._commit()

    @Slot(str, "QVariantMap", result=str)
    def saveDevice(self, dev_id: str, values: dict[str, Any]) -> str:
        """Saves what the device editor changed: name ("" = original), kind, room, area
        ("" = automatic), hidden, favorite, outdoor and quiet (no security alerts). Missing keys keep their value."""
        m = self._ctl._model
        d = m.get(dev_id)
        if not d:
            return tr("Device not found. It may have been removed from Homebridge.")
        meta = d.get("meta", {})
        name = values.get("name", d["name"])
        kind = values.get("kind", "")
        room = values.get("room", d["room"])
        area = values.get("area", meta.get("area", ""))
        if area and area not in AREAS:
            return tr("Choose one of the offered options")
        hidden = bool(values.get("hidden", d.get("hidden", False)))
        favorite = bool(values.get("favorite", d.get("favorite", False)))
        quiet = bool(values.get("quiet", d.get("quiet", False)))
        outdoor = bool(values.get("outdoor", meta.get("outdoor", False)))
        name, err = self._layout.check_device_name(name)
        if err:
            return err
        if room not in self._layout.all_rooms(m.device_rooms().values()):
            return tr("Room not found")
        self._layout.set_name(dev_id, name, d["baseName"])
        if kind and kind in d.get("meta", {}).get("kinds", []):
            self._layout.set_kind(dev_id, kind, d.get("baseKind", kind))
        self._layout.set_room(dev_id, room, d["baseRoom"], m.device_rooms())
        self._layout.set_hidden(dev_id, hidden)
        self._layout.set_favorite(dev_id, favorite)
        if d["type"] in ("garage", "lock") or meta.get("opening"):
            self._layout.set_quiet(dev_id, quiet)
        if d["type"] == "security":
            new_kind = kind if kind in meta.get("kinds", []) else meta.get("security", "")
            self._layout.set_quiet(dev_id, quiet, new_kind in QUIET_KINDS)
        self._layout.set_area(dev_id, area, d.get("baseArea", ""))
        if d["type"] == "sensor":
            self._layout.set_outdoor(dev_id, outdoor, d.get("baseOutdoor", False))
        self._commit()
        return ""

    @Property(str, notify=changed)
    def summary(self) -> str:
        n = len(self.rooms)
        return tr("1 room") if n == 1 else tr("{n} rooms").format(n=n)

    @Slot(str, result=str)
    def addRoom(self, name: str) -> str:
        _, err = self._layout.add(name, self._ctl._model.device_rooms())
        if not err:
            self._commit()
        return err or ""

    @Slot(str, str, result=str)
    def renameRoom(self, old: str, new: str) -> str:
        _, err = self._layout.rename(old, new, self._ctl._model.device_rooms())
        if not err:
            self._commit()
        return err or ""

    @Slot(str, result=str)
    def deleteRoom(self, name: str) -> str:
        m = self._ctl._model
        err = self._layout.delete(name, m.device_rooms(), m.base_rooms())
        if not err:
            self._commit()
        return err or ""

    @Slot(str, int)
    def moveRoom(self, name: str, delta: int) -> None:
        self._layout.move(name, delta, self._ctl._model.device_rooms())
        self._moved()

    @Slot(str, str, result=str)
    def assign(self, dev_id: str, room: str) -> str:
        m = self._ctl._model
        d = m.get(dev_id)
        if not d:
            return tr("Device not found. It may have been removed from Homebridge.")
        err = self._layout.set_room(dev_id, room, d["baseRoom"], m.device_rooms())
        if not err:
            self._commit()
        return err or ""


class ActivityFilter(QObject):
    """Reports touches and key presses (for the screen saver)."""

    TYPES = {QEvent.Type.MouseButtonPress, QEvent.Type.TouchBegin, QEvent.Type.KeyPress}

    def __init__(self, controller: "Controller"):
        super().__init__(controller)
        self._ctl = controller
        self._last = 0.0

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() in self.TYPES and time.monotonic() - self._last > 0.5:
            self._last = time.monotonic()
            self._ctl.userActivity.emit()
        return False


class Controller(QObject):
    _message = Signal(object)
    _updateResult = Signal(object)        # from the update thread: (kind, value)
    updateChanged = Signal()
    historyLoaded = Signal(str, int, "QVariantMap")    # device, days, {points, min, max, error}
    toast = Signal(str)
    deviceUpdated = Signal(str)
    userActivity = Signal()
    displayPowered = Signal(bool)     # the display was switched (the worker is done): on / off
    roomsChanged = Signal()
    currentRoomChanged = Signal()
    categoryChanged = Signal()
    summaryChanged = Signal()
    alarmPinChanged = Signal()
    detailRequested = Signal(str)     # show the detail view of a device (e.g. a motorized window)
    wifiRequested = Signal()          # the Wi-Fi tile was tapped: show the code
    confirmRequested = Signal(str)    # a garage door or lock tile was tapped: ask before opening/closing
    securityAlarm = Signal(str)       # new leak / glass break / smoke / CO alarm: wake up and show "Security"
    scenesChanged = Signal()
    statusChanged = Signal()
    climateChanged = Signal()
    themeChanged = Signal()
    idleChanged = Signal()
    upsideDownChanged = Signal()
    displayOffChanged = Signal()
    restarting = Signal(str)
    languageChanged = Signal()

    # Command used to reboot the device; overridable for tests
    reboot_command = ["systemctl", "reboot"]

    def __init__(self, base_cfg: AppConfig, store: SettingsStore, config_file: Path | None = None,
                 fullscreen: bool = False, restart_argv: list[str] | None = None,
                 updater: Updater | None = None, display_power: DisplayPower | None = None):
        super().__init__()
        # Command line for restarting the app: same interpreter, module and options
        self.restart_argv = restart_argv or [sys.executable, "-m", "app"]
        self._exec = os.execv   # replaced in tests
        self.base_cfg = base_cfg
        self.store = store
        self.runner = AsyncRunner()
        self._config_file = str(config_file or "")
        self._fullscreen = fullscreen
        default_room = base_cfg.panel.default_room
        self._model = DeviceModel(self, RoomLayout(
            store.rooms, lambda: tr(BUILTIN_DEFAULT) if default_room == BUILTIN_DEFAULT else default_room))
        self._settings = SettingsBridge(store, self)
        self._room_editor = RoomsBridge(store, self)
        self._rooms: list[str] = []
        self._room = ALL_ROOMS
        self._room_auto = True        # follow the first room until one is chosen
        self._sync_wifi_tile()
        self._category = self._start_category()
        self._model._category = self._category
        self._scenes = [{**s.model_dump(include={"id", "name", "icon", "room"}), "count": len(s.actions)}
                        for s in base_cfg.scenes]
        self._alarms: set[str] = set()
        self._since: dict[str, float] = {}           # security sensor -> time it was triggered
        self._since_timer = QTimer(self, interval=30_000, timeout=self._model.refresh_texts)
        self._since_timer.start()
        self._backends: dict[str, Any] = {}
        self._started = False
        i18n.set_language(i18n.resolve(store.get("language")))
        self._theme = self._compute_theme()
        fmt.set_alarm_armed(False)          # module state: a new controller starts disarmed
        self._mgr: DeviceManager | None = None
        self._sched: Scheduler | None = None
        self._pump: asyncio.Task | None = None
        self._message.connect(self._on_message)
        self._theme_timer = QTimer(self, interval=30_000, timeout=self._update_theme)
        self._theme_timer.start()
        self._display = display_power or DisplayPower()
        self._display_on = True                     # wanted state; switched in order by one worker
        self._display_worker = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        # Eve history read from the devices, kept next to settings.json
        self._history = DeviceHistory(Path(store.path).with_name("history.json"))
        # software update: checked a minute after the start and then once a day
        self._updater = updater or Updater()
        supported = self._updater.supported
        self._update: dict[str, Any] = {"state": "idle" if supported else "unsupported",
                                        "current": self._updater.installed() if supported else __version__,
                                        "latest": "", "error": ""}
        self._updateResult.connect(self._on_update_result)
        self._update_timer = QTimer(self, interval=24 * 3600_000, timeout=self.checkUpdate)
        if self._updater.supported:
            self._update_timer.start()

    # ---------- lifecycle ----------
    def effective_config(self) -> AppConfig:
        return apply_to_config(self.base_cfg, self.store.values, self.store.virtual)

    def restart_backends(self) -> None:
        """Reconnects with the current settings (Homebridge, MQTT, virtual devices)."""
        self._started = False
        self.statusChanged.emit()
        self.runner.submit(self._restart(self.effective_config()))

    def mqtt_backend(self) -> MqttBackend | None:
        if not self._mgr:
            return None
        return next((b for b in self._mgr.backends.values() if isinstance(b, MqttBackend)), None)

    # ---------- light groups ----------
    def refresh_groups(self) -> None:
        """Builds the group devices from their lights; called when a light or a group changes."""
        m = self._model
        ids = set()
        grouped = set()
        for g in self.store.groups:
            members = [m.get(x) for x in g.get("members", [])]
            members = [x for x in members if x]
            if g.get("hide", True):
                grouped |= {x["id"] for x in members}
            reachable = [x for x in members if x["reachable"]]
            on = [x for x in reachable if x["state"].get("on")]
            dimmable = [x for x in (on or reachable) if x["state"].get("brightness") is not None]
            state = {"on": bool(on), "on_count": len(on), "count": len(members)}
            if dimmable:
                state["brightness"] = round(sum(x["state"]["brightness"] for x in dimmable) / len(dimmable))
            caps = ["on"] + (["brightness"] if any("brightness" in x.get("capabilities", []) for x in members) else [])
            meta: dict[str, Any] = {"group": True, "members": [x["id"] for x in members]}
            source = on or reachable or members
            # color (RGB) and white tone (CCT) only if every light of the group has them
            if members and all("color" in x.get("capabilities", []) for x in members):
                caps.append("color")
                first = next((x for x in source if x["state"].get("hue") is not None), None)
                if first:
                    state.update(hue=first["state"]["hue"], saturation=first["state"].get("saturation", 0))
            if members and all("color_temp" in x.get("capabilities", []) for x in members):
                caps.append("color_temp")
                temps = [x["state"]["color_temp"] for x in source if x["state"].get("color_temp") is not None]
                if temps:
                    state["color_temp"] = round(sum(temps) / len(temps))
                # the range all lights can do
                meta.update(min_mired=max(x.get("meta", {}).get("min_mired", 140) for x in members),
                            max_mired=min(x.get("meta", {}).get("max_mired", 500) for x in members))
            gid = f"group:{g['id']}"
            ids.add(gid)
            m.upsert({"id": gid, "name": g["name"], "type": "light", "backend": "group", "room": g["room"],
                      "icon": "group", "state": state, "capabilities": caps, "reachable": bool(reachable),
                      "order": 100, "meta": meta})
        for g in self.store.switch_groups:
            members = [x for x in (m.get(i) for i in g.get("members", [])) if x]
            if g.get("hide", True):
                grouped |= {x["id"] for x in members}
            active = next((x for x in members if x["reachable"] and x["state"].get("on")), None)
            allow_off = bool(g.get("allow_off", True))
            # without "All off" the group is used like an option switch: never highlighted
            state = {"on": allow_off and active is not None, "active": active["id"] if active else "",
                     "active_name": short_name(active["name"], g["room"]) if active else ""}
            meta = {"choice": True, "members": [x["id"] for x in members], "allow_off": allow_off,
                    "options": [{"id": x["id"], "name": short_name(x["name"], g["room"]),
                                 "reachable": x["reachable"]} for x in members]}
            if g.get("area"):
                meta["area"] = g["area"]
            gid = f"choice:{g['id']}"
            ids.add(gid)
            m.upsert({"id": gid, "name": g["name"], "type": "switch", "backend": "group", "room": g["room"],
                      "icon": "choice", "state": state, "capabilities": ["on"],
                      "reachable": any(x["reachable"] for x in members), "order": 100, "meta": meta})
        for d in m.all():
            if (d.get("meta", {}).get("group") or d.get("meta", {}).get("choice")) and d["id"] not in ids:
                m.remove(d["id"])
        if grouped != m.grouped:
            m.grouped = grouped
            m.reassign()

    def start(self) -> None:
        self.runner.submit(self._restart(self.effective_config()))
        if self._updater.supported:
            QTimer.singleShot(60_000, self, self.checkUpdate)

    # ---------- software update ----------
    def _set_update(self, **values: Any) -> None:
        self._update = {**self._update, **values}
        self.updateChanged.emit()

    @Slot()
    def checkUpdate(self) -> None:
        if self._update["state"] in ("checking", "installing", "unsupported"):
            return
        self._set_update(state="checking", error="")

        def work() -> None:
            try:
                result = ("checked", self._updater.check())
            except UpdateError as e:
                result = ("failed", str(e))
            _emit_safely(self._updateResult, result)
        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def installUpdate(self) -> None:
        """Installs the latest release found by checkUpdate and restarts the app."""
        if self._update["state"] != "available":
            return
        tag = self._update["latest"]
        self._set_update(state="installing", error="")

        def work() -> None:
            try:
                self._updater.install(tag)
                result = ("installed", tag)
            except UpdateError as e:
                result = ("install failed", str(e))
            _emit_safely(self._updateResult, result)
        threading.Thread(target=work, daemon=True).start()

    def _on_update_result(self, result: tuple[str, Any]) -> None:
        kind, value = result
        if kind == "checked":
            self._set_update(state="available" if value.available else "current",
                             current=value.current, latest=value.latest)
        elif kind == "installed":
            log.info("Update %s installed, restarting", value)
            self.restarting.emit(tr("Update installed. Restarting the app …"))
            QTimer.singleShot(600, self._restart_app)
        else:
            log.warning("Update %s: %s", kind, value)
            self._set_update(state="available" if kind == "install failed" else "failed", error=value)
            if kind == "install failed":
                self.toast.emit(tr("Update failed: {error}").format(error=value))

    @Property("QVariantMap", notify=updateChanged)
    def updateInfo(self) -> dict[str, Any]:
        """State of the software update for Settings → System: text, button and whether it installs."""
        u = self._update
        state = u["state"]
        text = {
            "unsupported": tr("Only for installations with deploy/install.sh (git)"),
            "idle": tr("Looks for a new release on GitHub"),
            "checking": tr("Looking for updates …"),
            "current": tr("Version {version} is up to date").format(version=u["current"]),
            "available": tr("Version {latest} is available (installed: {current})").format(
                latest=u["latest"].lstrip("v"), current=u["current"]),
            "installing": tr("Installing version {latest} … The app restarts afterwards.").format(
                latest=u["latest"].lstrip("v")),
            "failed": tr("Update check failed: {error}").format(error=u["error"]),
        }[state]
        if state == "available" and u["error"]:
            text = tr("Update failed: {error}").format(error=u["error"])
        return {"state": state, "text": text, "latest": u["latest"].lstrip("v"),
                "install": state == "available",
                "busy": state in ("checking", "installing", "unsupported")}

    def shutdown(self) -> None:
        if self._room_editor._moves_pending:     # moved rows not saved yet
            self._room_editor.save_moves()
        self._room_editor._save_timer.stop()
        self._display_worker.shutdown(wait=True)
        if not self._display.is_on:          # never leave the screen dark (restart, update)
            self._display.set(True)
        # stop timers first: if Python later frees this object from another thread,
        # active Qt timers of a deleted object would crash the event loop
        self._theme_timer.stop()
        self._since_timer.stop()
        self._update_timer.stop()
        try:
            self.runner.submit(self._stop_manager()).result(timeout=3)
        except Exception:  # pragma: no cover
            pass
        self.runner.stop()

    async def _stop_manager(self) -> None:
        if self._pump:
            self._pump.cancel()
        if self._sched:
            self._sched.stop()
        if self._mgr:
            await self._mgr.stop()
        self._mgr = self._sched = self._pump = None

    async def _restart(self, cfg: AppConfig) -> None:
        await self._stop_manager()
        try:
            mgr = DeviceManager(cfg, create_backends(cfg), history=self._history)
        except ValueError as e:
            self.toast.emit(str(e))
            return
        queue = mgr.subscribe()
        self._mgr, self._sched = mgr, Scheduler(cfg, mgr)
        self._message.emit({"type": "snapshot", "devices": [], "backends": mgr.status})
        await mgr.start()
        self._sched.start()
        self._message.emit(mgr.snapshot_message())
        self._pump = asyncio.create_task(self._pump_loop(queue))

    async def _pump_loop(self, queue: asyncio.Queue) -> None:
        while True:
            self._message.emit(await queue.get())

    # ---------- system actions ----------
    def run_action(self, key: str) -> None:
        if key not in ACTIONS:
            self.toast.emit(tr("Unknown action: {key}").format(key=key))
        elif key == "restart_app":
            self.restarting.emit(tr("Restarting the app …"))
            QTimer.singleShot(600, self._restart_app)
        elif key == "reboot":
            self.restarting.emit(tr("Restarting the Raspberry Pi …"))
            self.runner.submit(self._reboot())

    def _restart_app(self) -> None:
        """Replaces the running process with a fresh start of the app."""
        log.info("Restarting app: %s", " ".join(self.restart_argv))
        self.shutdown()
        try:
            self._exec(self.restart_argv[0], self.restart_argv)
        except OSError as e:
            self.restarting.emit("")
            self.toast.emit(tr("Could not restart the app: {error}").format(error=e))

    async def _reboot(self) -> None:
        log.info("Rebooting: %s", " ".join(self.reboot_command))
        # subprocess.run in a worker thread: asyncio's child watcher in this non-main thread
        # can clash with Qt's own SIGCHLD handling
        try:
            proc = await asyncio.to_thread(subprocess.run, self.reboot_command, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.PIPE, timeout=15)
            err = proc.stderr
        except (OSError, subprocess.TimeoutExpired) as e:
            self.restarting.emit("")
            self.toast.emit(tr("Could not restart the Raspberry Pi: {error}").format(error=e))
            return
        if proc.returncode != 0:
            detail = err.decode(errors="replace").strip().splitlines()[-1:] or [f"exit code {proc.returncode}"]
            self.restarting.emit("")
            self.toast.emit(tr("Restart not allowed. Run deploy/install.sh again to allow it. ({detail})")
                            .format(detail=detail[0]))

    def settings_saved(self, keys: set[str]) -> None:
        if any(k.startswith("hap_") for k in keys):
            self._started = False
            self.statusChanged.emit()
            self.runner.submit(self._restart(self.effective_config()))
        if "theme" in keys:
            self._update_theme()
        if "alarm_pin" in keys:
            self.alarmPinChanged.emit()
        if keys & {"wifi_ssid", "wifi_favorite"}:
            self._sync_wifi_tile()
            self._refresh_rooms()
        if "language" in keys:
            self.apply_language()
        if "idle_seconds" in keys:
            self.idleChanged.emit()
        if "upside_down" in keys:
            self.upsideDownChanged.emit()
        if "display_off" in keys:
            self.displayOffChanged.emit()
        if "show_general" in keys:
            self._refresh_rooms()
        if any(k.startswith("mqtt_") for k in keys) and not any(k.startswith("hap_") for k in keys):
            self.restart_backends()

    # ---------- messages from the background thread ----------
    def _on_message(self, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        if kind == "snapshot":
            self._model.set_all([self._stamp(d) for d in msg.get("devices", [])])
            self.refresh_groups()
            self._backends = msg.get("backends", {})
            self._started = "title" in msg
            self._update_armed()
            self._refresh_rooms()
            self.climateChanged.emit()
            self.statusChanged.emit()
        elif kind == "device":
            d = self._stamp(msg["device"])
            structural = self._model.upsert(d)
            if d["type"] == "alarm" and self._update_armed():
                structural = True
            groups = [f"group:{g['id']}" for g in self.store.groups if d["id"] in g.get("members", [])] \
                + [f"choice:{g['id']}" for g in self.store.switch_groups if d["id"] in g.get("members", [])]
            if groups:
                self.refresh_groups()
            if structural:
                self._refresh_rooms()
            else:
                # an on/off change: room dots and "n on" / "n heating" in the menu follow at once
                self.summaryChanged.emit()
            self.deviceUpdated.emit(d["id"])
            for gid in groups:
                self.deviceUpdated.emit(gid)        # open group detail follows its lights
            self.climateChanged.emit()
        elif kind == "remove":
            self._model.remove(msg["id"])
            self.refresh_groups()
            self._refresh_rooms()
            self.deviceUpdated.emit(msg["id"])
            self.climateChanged.emit()
        elif kind == "status":
            self._backends = msg["backends"]
            self.statusChanged.emit()
        elif kind == "scene" and msg.get("errors"):
            self.toast.emit(tr("Scene only partly applied. Not reached: {names}").format(names=", ".join(msg["errors"])))

    def _stamp(self, d: dict[str, Any]) -> dict[str, Any]:
        """Remembers since when a window or door is open (shown as "Open for 25 min")."""
        if d.get("type") in ("security", "garage", "lock"):
            if d.get("state", {}).get("triggered"):
                self._since.setdefault(d["id"], time.time())
            else:
                self._since.pop(d["id"], None)
            d = {**d, "since": self._since.get(d["id"])}
        return d

    def _check_alarms(self) -> None:
        alarms = {d["id"]: d for d in self._model.shown() if alert_level(d) == 2}
        for dev_id in alarms.keys() - self._alarms:
            d = alarms[dev_id]
            self.securityAlarm.emit(tr("{state}: {room}, {name}").format(
                state=state_text(d), room=d["room"], name=short_name(d["name"], d["room"])))
        self._alarms = set(alarms)

    def _start_category(self) -> str:
        """The panel starts with the favorites if there are any, otherwise with the lights."""
        if self._model.all():
            return FAVORITES if any(d.get("favorite") for d in self._model.shown() + self._model.tiles()) else "light"
        return FAVORITES if self._model.layout.favorites else "light"

    def _tab_rooms(self) -> list[str]:
        if self._category == FAVORITES:     # favorites are listed without room tabs
            return []
        rooms = self._model.rooms(self._category)
        if not self.store.get("show_general"):
            rooms = [r for r in rooms if r != self._model.layout.default_room]
        return rooms

    def _refresh_rooms(self) -> None:
        rooms = self._tab_rooms()
        # after switching the menu entry (or at start) the first room is selected; "All" only
        # when chosen or when there are no rooms
        if self._room_auto or (self._room != ALL_ROOMS and self._room not in rooms):
            target = rooms[0] if rooms else ALL_ROOMS
            if target != self._room:
                self._room = target
                self._model.set_room(target)
                self.currentRoomChanged.emit()
                self.scenesChanged.emit()
        if rooms != self._rooms:
            self._rooms = rooms
            self.roomsChanged.emit()
        self._check_alarms()
        self.summaryChanged.emit()
        self._room_editor.notify()    # device counts and assignments in the settings

    # ---------- commands from QML ----------
    def _command(self, coro_factory) -> None:
        if not self._mgr:
            self.toast.emit(tr("Not connected to Homebridge yet."))
            return
        fut = self.runner.submit(coro_factory(self._mgr))

        def done(f: concurrent.futures.Future) -> None:
            try:
                report(f)
            except RuntimeError:        # the controller was deleted meanwhile (shutdown, tests)
                pass

        def report(f: concurrent.futures.Future) -> None:
            e = f.exception()
            if e is None:
                return
            if isinstance(e, DeviceNotFound):
                self.toast.emit(tr("Device not found. It may have been removed from Homebridge."))
            elif isinstance(e, (ValueError, BackendError)):
                self.toast.emit(str(e))
            else:
                self.toast.emit(tr("Command failed: {error}").format(error=e))
        fut.add_done_callback(done)

    @Slot(str, int)
    def loadHistory(self, dev_id: str, days: int) -> None:
        """Reads the history of a device (new entries only) and answers with historyLoaded:
        {kinds: ["temperature", "humidity", "pressure"] as far as the device has them,
         series: {kind: {points: [{t: ms, v: value}] of the last `days` days (at most 240), min, max}},
         since, until, error}. Only quantities the device shows now are offered: a weather
        history without a barometer, for example, still records an air pressure."""
        empty = {"kinds": [], "series": {}}
        if not self._mgr:
            self.historyLoaded.emit(dev_id, days, {**empty, "error": tr("Not connected to Homebridge yet.")})
            return
        mgr = self._mgr
        fut = self.runner.submit(mgr.device_history(dev_id))

        def done(f: concurrent.futures.Future) -> None:
            e = f.exception()
            if e is not None:
                log.warning("History of %s: %s", dev_id, e)
                result = {**empty, "error": tr("History could not be read: {error}").format(error=e)}
            else:
                now = time.time()
                dev = mgr.devices.get(dev_id)
                state = dev.state if dev else {}
                shown = {"temperature": "current_temp", "humidity": "humidity", "pressure": "pressure",
                         "power": "power"}
                result = {**empty, "error": "", "since": (now - days * 86400) * 1000, "until": now * 1000}
                for kind, points in f.result().items():
                    if shown[kind] not in state:
                        continue
                    pts = bucket(points, now - days * 86400, now)
                    # lowest and highest of the measured values (the chart's points are averages)
                    vals = [v for t, v in points if now - days * 86400 <= t <= now]
                    result["kinds"].append(kind)
                    result["series"][kind] = {"points": [{"t": t * 1000, "v": v} for t, v in pts],
                                              "min": min(vals) if vals else 0, "max": max(vals) if vals else 0}
                    if kind == "power":     # consumption in the period, from the unaveraged values
                        result["series"][kind]["energy"] = energy_kwh(points, now - days * 86400, now)
            _emit_safely(self.historyLoaded, dev_id, days, result)
        fut.add_done_callback(done)

    @Slot(str)
    def toggle(self, dev_id: str) -> None:
        d = self._model.get(dev_id)
        if not d:
            return
        if d["type"] == "wifi":                     # the Wi-Fi tile: show the code
            self.wifiRequested.emit()
            return
        if d.get("meta", {}).get("group"):          # a group: all lights on, or all off if any is on
            self.setAttrs(dev_id, {"on": not d["state"].get("on")})
            return
        if d.get("meta", {}).get("choice"):         # a switch group: on to the next switch
            self._select(d, self._next_choice(d))
            return
        if not d["reachable"]:
            self.toast.emit(tr("{name} is not reachable. Check the device and Homebridge.").format(name=d["name"]))
            return
        if d["type"] in ("garage", "lock"):         # never directly: the panel asks first
            self.confirmRequested.emit(dev_id)
            return
        if d.get("meta", {}).get("opening"):        # motorized window / door: open the controls
            self.detailRequested.emit(dev_id)
            return
        self.setAttrs(dev_id, {"on": not d["state"].get("on")})

    def _update_armed(self) -> bool:
        """Motion sensors only count while an alarm system is armed. Returns True if that changed."""
        armed = any(d["state"].get("armed") for d in self._model.all() if d["type"] == "alarm" and d["reachable"])
        if armed == fmt._alarm_armed:
            return False
        fmt.set_alarm_armed(armed)
        self._model._relayout()
        self._model.refresh_texts()
        return True

    @Property(bool, notify=alarmPinChanged)
    def alarmPinSet(self) -> bool:
        return bool(self.store.get("alarm_pin"))

    @Slot(result="QVariantMap")
    def wifiCode(self) -> dict[str, Any]:
        """The guest Wi-Fi of the settings as a QR code: {error, ssid, password, image (PNG data URI)}."""
        ssid = str(self.store.get("wifi_ssid") or "").strip()
        if not ssid:
            return {"error": tr("Enter the guest Wi-Fi under Settings → Wi-Fi for guests.")}
        wifi = Wifi(ssid, str(self.store.get("wifi_password") or ""))
        return {"error": "", "ssid": wifi.ssid, "password": wifi.password, "image": qr_image(wifi.uri())}

    def _sync_wifi_tile(self) -> None:
        """The "Wi-Fi QR code" tile in the favorites: there while it is switched on and a guest
        network is set; new ones go to the end of the favorites."""
        ssid = str(self.store.get("wifi_ssid") or "").strip()
        wanted = bool(self.store.get("wifi_favorite")) and bool(ssid)
        layout = self._model.layout
        if wanted != (WIFI_TILE in layout.favorites):
            layout.set_favorite(WIFI_TILE, wanted)
            self.store.rooms = layout.to_dict()
            self.store.save()
        if wanted:
            self._model.upsert({"id": WIFI_TILE, "name": tr("Wi-Fi QR code"), "type": "wifi", "backend": "panel",
                                "room": "", "icon": "wifi", "state": {"ssid": ssid}, "capabilities": [],
                                "reachable": True, "order": 100, "meta": {}, "panelTile": True})
        else:
            self._model.remove(WIFI_TILE)
        self._room_editor.notify()          # the favorites list in the settings

    @Slot(str, str, result=str)
    def disarm(self, dev_id: str, pin: str) -> str:
        """Disarms an alarm system; with a PIN set in the settings only with that PIN."""
        want = str(self.store.get("alarm_pin") or "")
        if want and pin != want:
            return tr("Wrong PIN")
        self._command(lambda m: m.command(dev_id, {"mode": "off"}))
        return ""

    @Slot(str, bool, str, result=str)
    def openClose(self, dev_id: str, open_: bool, pin: str) -> str:
        """Opens or closes a garage door, unlocks or locks a door lock; opening / unlocking needs the
        PIN of the alarm system if one is set."""
        want = str(self.store.get("alarm_pin") or "")
        if open_ and want and pin != want:
            return tr("Wrong PIN")
        self._command(lambda m: m.command(dev_id, {"on": open_}))
        return ""

    @Slot(str, "QVariantMap")
    def setAttrs(self, dev_id: str, attrs: dict[str, Any]) -> None:
        attrs = {k: (int(v) if isinstance(v, float) and v.is_integer() and k != "target_temp" else v)
                 for k, v in dict(attrs).items()}
        d = self._model.get(dev_id)
        if d and d["type"] == "alarm" and attrs.get("mode") == "off" and self.store.get("alarm_pin"):
            self.toast.emit(tr("Enter the PIN to disarm"))      # disarming goes through disarm()
            return
        if d and d["type"] in ("garage", "lock") and attrs.get("on") and self.store.get("alarm_pin"):
            # opening / unlocking goes through openClose()
            self.toast.emit(tr("Enter the PIN to unlock") if d["type"] == "lock" else tr("Enter the PIN to open"))
            return
        if d and d.get("meta", {}).get("choice"):
            # {"select": id} switches that one on and the others off; {"on": false}: all off
            target = str(attrs.get("select", "")) if "select" in attrs else ("" if attrs.get("on") is False else None)
            if target is not None:
                self._select(d, target)
            return
        if d and d.get("meta", {}).get("group"):
            for member in d["meta"]["members"]:
                md = self._model.get(member)
                if md and md["reachable"]:
                    caps = md.get("capabilities", [])
                    own = {k: v for k, v in attrs.items()
                           if k == "on" or GROUP_ATTR_CAPS.get(k, k) in caps}
                    self._command(lambda m, member=member, own=own: m.command(member, own))
            return
        self._command(lambda m: m.command(dev_id, attrs))

    def _next_choice(self, d: dict[str, Any]) -> str:
        """Next switch of a switch group: after the last one comes "all off" (if allowed), then the first."""
        ids = [o["id"] for o in d["meta"]["options"] if o["reachable"]]
        if not ids:
            return ""
        cur = d["state"].get("active", "")
        if cur not in ids:
            return ids[0]
        i = ids.index(cur) + 1
        if i < len(ids):
            return ids[i]
        return "" if d["meta"].get("allow_off") else ids[0]

    def _select(self, d: dict[str, Any], target: str) -> None:
        """Switch group: switches the other members off first, then the chosen one on."""
        meta = d["meta"]
        if not target and not meta.get("allow_off"):
            return
        if target and target not in meta["members"]:
            return
        others = [x for x in meta["members"] if x != target
                  and (md := self._model.get(x)) and md["reachable"] and md["state"].get("on")]

        async def run(m):  # noqa: ANN001, ANN202
            for x in others:
                await m.command(x, {"on": False})
            if target:
                await m.command(target, {"on": True})
        self._command(run)

    @Slot(str)
    def runScene(self, scene_id: str) -> None:
        self._command(lambda m: m.run_scene(scene_id))

    @Slot(str, result="QVariantMap")
    def device(self, dev_id: str) -> dict[str, Any]:
        d = self._model.get(dev_id)
        if not d:
            return {}
        return {**d, "shortName": short_name(d["name"], d["room"]), "stateText": state_text(d),
                "batteryLow": battery_low(d), "batteryText": battery_text(d)}

    @Slot(str)
    def selectCategory(self, cat: str) -> None:
        if cat == self._category:
            return
        self._category = cat
        self._room_auto = True
        self._model.set_category(cat, self._room)
        self.categoryChanged.emit()
        self._refresh_rooms()
        self.scenesChanged.emit()

    @Slot()
    def selectStart(self) -> None:
        """Back to the start page, e.g. after the screensaver."""
        self.selectCategory(self._start_category())

    @Slot(str)
    def selectRoom(self, room: str) -> None:
        self._room_auto = False
        if room != self._room:
            self._room = room
            self._model.set_room(room)
            self.currentRoomChanged.emit()
            self.scenesChanged.emit()

    def apply_language(self) -> None:
        """Switches the language at runtime: QML retranslates (see main.py), Python texts are rebuilt."""
        i18n.set_language(i18n.resolve(self.store.get("language")))
        self.languageChanged.emit()
        self._model.reassign()          # the default room name is translated
        self._sync_wifi_tile()          # its name too
        self._refresh_rooms()
        self._settings.sectionsChanged.emit()
        self.statusChanged.emit()
        self.climateChanged.emit()

    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return i18n.language()

    @Property(str, notify=languageChanged)
    def localeName(self) -> str:
        return i18n.locale_name()

    @Property(str, notify=languageChanged)
    def decimalPoint(self) -> str:
        return i18n.decimal_point()

    @Property(str, notify=languageChanged)
    def dateFormat(self) -> str:
        return i18n.date_format()

    # ---------- properties ----------
    @Property(QObject, constant=True)
    def devices(self) -> QObject:
        return self._model

    @Property(QObject, constant=True)
    def settings(self) -> QObject:
        return self._settings

    @Property(QObject, constant=True)
    def roomEditor(self) -> QObject:
        return self._room_editor

    @Property("QVariantList", notify=roomsChanged)
    def rooms(self) -> list[str]:
        return self._rooms

    @Property(str, notify=currentRoomChanged)
    def currentRoom(self) -> str:
        return self._room

    @Property("QVariantList", notify=scenesChanged)
    def scenes(self) -> list[dict[str, Any]]:
        return self._scenes

    @Property(str, notify=categoryChanged)
    def category(self) -> str:
        return self._category

    @Property("QVariantMap", notify=summaryChanged)
    def summary(self) -> dict[str, str]:
        """Short status per menu area, e.g. {"light": "3 on", "security": "2 alerts"}."""
        m = self._model
        on = m.count(_is_on_light)
        heating = m.count(lambda d: d["type"] == "thermostat" and d["reachable"] and d.get("state", {}).get("heating"))
        alerts = self.securityCount
        return {
            "light": tr("{n} on").format(n=on) if on else "",
            "climate": tr("{n} heating").format(n=heating) if heating else "",
            "security": (tr("1 alert") if alerts == 1 else tr("{n} alerts").format(n=alerts)) if alerts else "",
        }

    @Property("QVariantMap", notify=summaryChanged)
    def roomMarks(self) -> dict[str, str]:
        """Dot before a room tab: "alert" under Security (open window or door, alarm; motion
        only while the alarm system is armed), "on" under Lights (a light or switch is on)."""
        if self._category == "security":
            hit, mark = (lambda d: alert_level(d) > 0), "alert"
        elif self._category == "light":
            hit, mark = _is_on_light, "on"
        else:
            return {}
        return {d["room"]: mark for d in self._model.shown() if hit(d)}

    @Property("QVariantList", notify=summaryChanged)
    def batteries(self) -> list[dict[str, Any]]:
        """Every device with a battery, the emptiest first (almost empty ones on top)."""
        out = [{"id": d["id"], "name": d["name"], "room": d["room"], "icon": d["icon"],
                "level": d["state"].get("battery", -1), "low": battery_low(d), "text": battery_text(d)}
               for d in self._model.all()
               if "battery" in d.get("state", {}) or "battery_low" in d.get("state", {})]
        return sorted(out, key=lambda b: (not b["low"], b["level"] if b["level"] >= 0 else 101, b["name"]))

    @Property(int, notify=summaryChanged)
    def lowBatteryCount(self) -> int:
        return sum(1 for d in self._model.all() if battery_low(d))

    @Property(int, notify=summaryChanged)
    def securityCount(self) -> int:
        return self._model.count(lambda d: alert_level(d) > 0)

    @Property(bool, notify=statusChanged)
    def statusOk(self) -> bool:
        return self._started and bool(self._backends) and all(b["ok"] for b in self._backends.values())

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:
        if not self._backends:
            return tr("No Homebridge set up")
        if not self._started:
            return tr("Connecting …")
        bad = [n for n, b in self._backends.items() if not b["ok"]]
        if bad:
            if bad == ["homebridge"]:
                return tr("Homebridge not reachable")
            return tr("Not reachable: {names}").format(names=", ".join(bad))
        return tr("Connected")

    @Property(str, notify=statusChanged)
    def statusDetail(self) -> str:
        lines = [tr("{name}: {state} ({n} devices)").format(
                     name=n, state=tr("connected") if b["ok"] else b["error"] or tr("disconnected"), n=b["devices"])
                 for n, b in self._backends.items()]
        return "\n".join(lines)

    @Property(int, notify=climateChanged)
    def deviceCount(self) -> int:
        return len(self._model.all())

    def _avg_temp(self, outdoor: bool) -> str:
        temps = [d["state"]["current_temp"] for d in self._model.shown()
                 if d["reachable"] and d["state"].get("current_temp") is not None
                 and bool(d.get("meta", {}).get("outdoor")) == outdoor]
        return fmt_temp(sum(temps) / len(temps)) if temps else ""

    @Property(str, notify=climateChanged)
    def indoorTemp(self) -> str:
        """Average of all reachable thermostats and indoor sensors."""
        return self._avg_temp(outdoor=False)

    @Property(str, notify=climateChanged)
    def outdoorTemp(self) -> str:
        """Average of all reachable sensors marked `outdoor: true`; empty if there are none."""
        return self._avg_temp(outdoor=True)

    def _compute_theme(self) -> str:
        mode = self.store.get("theme")
        if mode != "auto":
            return mode
        hour = datetime.now(ZoneInfo(self.base_cfg.server.timezone)).hour
        return "dark" if hour >= NIGHT_FROM or hour < NIGHT_TO else "light"

    def _update_theme(self) -> None:
        t = self._compute_theme()
        if t != self._theme:
            self._theme = t
            self.themeChanged.emit()

    @Property(str, notify=themeChanged)
    def theme(self) -> str:
        return self._theme

    @Property(int, notify=displayOffChanged)
    def displayOffSeconds(self) -> int:
        """Display off this long after the screen saver started (0 = never)."""
        return int(self.store.get("display_off") or 0)

    @Slot(bool)
    def setDisplayPower(self, on: bool) -> None:
        """Called by Main.qml: off after the screen saver, on with the next touch or an alarm."""
        if on == self._display_on:
            return
        self._display_on = on
        try:
            fut = self._display_worker.submit(self._display.set, on)
        except RuntimeError:                  # shut down meanwhile
            return
        fut.add_done_callback(lambda f: _emit_safely(self.displayPowered, on))

    @Property(bool, notify=upsideDownChanged)
    def upsideDown(self) -> bool:
        return bool(self.store.get("upside_down"))

    @Property(int, notify=idleChanged)
    def idleSeconds(self) -> int:
        return int(self.store.get("idle_seconds"))

    @Property(bool, constant=True)
    def fullscreen(self) -> bool:
        return self._fullscreen

    @Property(str, notify=updateChanged)
    def version(self) -> str:
        return self._update["current"]

    @Property(str, constant=True)
    def configPath(self) -> str:
        return self._config_file
