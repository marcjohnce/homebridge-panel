"""Bridge between device management (asyncio, own thread) and the QML UI."""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from PySide6.QtCore import (QAbstractListModel, QByteArray, QEvent, QModelIndex, QObject, Qt, QTimer,
                            Property, Signal, Slot)

from .. import __version__, i18n
from ..i18n import tr
from ..backends import BackendError, HapBackend, create_backends
from ..config import AppConfig, HapBackendConfig
from ..manager import DeviceManager, DeviceNotFound
from ..rooms import BUILTIN_DEFAULT, RoomLayout
from ..scheduler import Scheduler
from ..settings import ACTIONS, SettingsStore, apply_to_config, validate
from ..models import SECURITY_ICONS
from .format import alert_level, category, fmt_temp, has_detail, short_name, state_text

log = logging.getLogger(__name__)
ALL_ROOMS = ""
NIGHT_FROM, NIGHT_TO = 19, 7


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
             "stateText", "hasDetail", "targetTemp", "minTemp", "maxTemp", "modeOff", "alertLevel")
    # order inside a room: per menu area
    RANK = {"light": 0, "switch": 1, "plug": 1, "blind": 2, "thermostat": 0, "sensor": 1, "fan": 2}

    def __init__(self, parent: QObject | None = None, layout: RoomLayout | None = None):
        super().__init__(parent)
        self.layout = layout or RoomLayout()
        self._all: dict[str, dict[str, Any]] = {}
        self._rows: list[str] = []
        self._room = ALL_ROOMS
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
            case "isOn": return d["type"] not in ("thermostat", "sensor", "blind") and bool(s.get("on")) and d["reachable"]
            case "reachable": return d["reachable"]
            case "heating": return bool(s.get("heating")) and d["reachable"]
            case "stateText": return state_text(d)
            case "hasDetail": return has_detail(d)
            case "targetTemp": return float(s.get("target_temp") or 20)
            case "minTemp": return float(m.get("min_temp", 10))
            case "maxTemp": return float(m.get("max_temp", 30))
            case "modeOff": return s.get("mode") == "off"
            case "alertLevel": return alert_level(d)
        return None

    # --- maintenance ---
    def rooms(self, cat: str | None = None) -> list[str]:
        """Rooms with devices (of a menu area), in the order set in the settings."""
        return self.layout.sort({d["room"] for d in self.shown() if not cat or category(d) == cat})

    def device_rooms(self) -> dict[str, str]:
        return {d["id"]: d["room"] for d in self._all.values()}

    def base_rooms(self) -> dict[str, str]:
        return {d["id"]: d["baseRoom"] for d in self._all.values()}

    def _place(self, d: dict[str, Any]) -> dict[str, Any]:
        """Applies what was set on the panel: room, display name and the kind of security sensors.
        "baseRoom", "baseName" and "baseKind" keep the values from Homebridge / config.yaml."""
        base = d.get("baseRoom", d["room"])
        base_name = d.get("baseName", d["name"])
        out = {**d, "baseRoom": base, "room": self.layout.room_of(d["id"], base),
               "baseName": base_name, "name": self.layout.names.get(d["id"]) or base_name,
               "hidden": d["id"] in self.layout.hidden}
        meta = d.get("meta", {})
        if "security" in meta:
            base_kind = d.get("baseKind", meta["security"])
            kind = self.layout.kinds.get(d["id"], base_kind)
            if kind not in meta.get("kinds", ()):
                kind = base_kind
            base_icon = d.get("baseIcon", d["icon"])
            icon = SECURITY_ICONS[kind] if base_icon == SECURITY_ICONS.get(base_kind) else base_icon
            out.update(baseKind=base_kind, baseIcon=base_icon, icon=icon, meta={**meta, "security": kind})
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
        devs = [d for d in self.shown() if self._room in (ALL_ROOMS, d["room"])
                and self._category in ("", category(d))]
        room_rank = {r: i for i, r in enumerate(self.rooms())}
        # alarms first, then open windows/doors; otherwise by room, kind of device, order, name
        devs.sort(key=lambda d: (-alert_level(d), room_rank.get(d["room"], 0), self.RANK.get(d["type"], 0),
                                 d.get("order", 100), d["name"].casefold()))
        return [d["id"] for d in devs]

    def set_category(self, cat: str, room: str) -> None:
        self._category = cat
        self._room = room
        self._relayout()

    def count(self, pred) -> int:
        """Counts devices shown on the home screen (hidden ones are left out)."""
        return sum(1 for d in self.shown() if pred(d))

    def shown(self) -> list[dict[str, Any]]:
        return [d for d in self._all.values() if not d.get("hidden")]

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
        self.beginResetModel()
        self._all = {d["id"]: self._place(d) for d in devices}
        self._rows = self._visible()
        self.endResetModel()

    def upsert(self, d: dict[str, Any]) -> bool:
        """Returns True if the structure (room, name, order) changed."""
        old = self._all.get(d["id"])
        d = self._place(d)
        self._all[d["id"]] = d
        structural = (old is None or any(old.get(k) != d.get(k) for k in ("room", "name", "order", "hidden"))
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
        return list(self._all.values())


class SettingsBridge(QObject):
    sectionsChanged = Signal()
    testFinished = Signal(bool, str)

    def __init__(self, store: SettingsStore, controller: "Controller"):
        super().__init__(controller)
        self._store = store
        self._ctl = controller

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
        fut.add_done_callback(lambda f: self.testFinished.emit(*f.result()))


class RoomsBridge(QObject):
    """Room management in the settings (RoomsPage.qml). Changes apply and save immediately."""
    changed = Signal()

    def __init__(self, store: SettingsStore, controller: "Controller"):
        super().__init__(controller)
        self._store = store
        self._ctl = controller

    @property
    def _layout(self) -> RoomLayout:
        return self._ctl._model.layout

    def _commit(self) -> None:
        self._store.rooms = self._layout.to_dict()
        self._store.save()
        self._ctl._model.reassign()
        self._ctl._refresh_rooms()
        self._ctl.climateChanged.emit()     # hidden sensors leave the temperature average

    @Property("QVariantList", notify=changed)
    def rooms(self) -> list[dict[str, Any]]:
        dev_rooms = self._ctl._model.device_rooms()
        counts: dict[str, int] = {}
        for r in dev_rooms.values():
            counts[r] = counts.get(r, 0) + 1
        default = self._layout.default_room
        return [{"name": r, "count": counts.get(r, 0), "isDefault": r == default}
                for r in self._layout.all_rooms(dev_rooms.values())]

    KIND_LABELS = {"window": "Window", "door": "Door", "contact": "Contact", "glassbreak": "Glass break",
                   "leak": "Leak", "motion": "Motion"}

    @Property("QVariantList", notify=changed)
    def devices(self) -> list[dict[str, Any]]:
        devs = sorted(self._ctl._model.all(), key=lambda d: d["name"].casefold())
        out = []
        for d in devs:
            kinds = d.get("meta", {}).get("kinds", [])
            out.append({"id": d["id"], "name": d["name"], "baseName": d["baseName"], "icon": d["icon"],
                        "room": d["room"], "reachable": d["reachable"],
                        "kind": d.get("meta", {}).get("security", ""), "hidden": bool(d.get("hidden")),
                        "kinds": [{"value": k, "label": tr(self.KIND_LABELS[k])} for k in kinds] if len(kinds) > 1 else []})
        return out

    @Slot(str, str, str, str, bool, result=str)
    def saveDevice(self, dev_id: str, name: str, kind: str, room: str, hidden: bool = False) -> str:
        """Display name ("" = original), kind of a security sensor, room and hidden flag, saved together."""
        m = self._ctl._model
        d = m.get(dev_id)
        if not d:
            return tr("Device not found. It may have been removed from Homebridge.")
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
        self._commit()

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
    toast = Signal(str)
    deviceUpdated = Signal(str)
    userActivity = Signal()
    roomsChanged = Signal()
    currentRoomChanged = Signal()
    categoryChanged = Signal()
    summaryChanged = Signal()
    securityAlarm = Signal(str)       # new leak / glass break alarm: wake up and show "Security"
    scenesChanged = Signal()
    statusChanged = Signal()
    climateChanged = Signal()
    themeChanged = Signal()
    idleChanged = Signal()
    restarting = Signal(str)
    languageChanged = Signal()

    # Command used to reboot the device; overridable for tests
    reboot_command = ["systemctl", "reboot"]

    def __init__(self, base_cfg: AppConfig, store: SettingsStore, config_file: Path | None = None,
                 fullscreen: bool = False, restart_argv: list[str] | None = None):
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
        self._category = "light"
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
        self._mgr: DeviceManager | None = None
        self._sched: Scheduler | None = None
        self._pump: asyncio.Task | None = None
        self._message.connect(self._on_message)
        self._theme_timer = QTimer(self, interval=30_000, timeout=self._update_theme)
        self._theme_timer.start()

    # ---------- lifecycle ----------
    def effective_config(self) -> AppConfig:
        return apply_to_config(self.base_cfg, self.store.values)

    def start(self) -> None:
        self.runner.submit(self._restart(self.effective_config()))

    def shutdown(self) -> None:
        # stop timers first: if Python later frees this object from another thread,
        # active Qt timers of a deleted object would crash the event loop
        self._theme_timer.stop()
        self._since_timer.stop()
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
            mgr = DeviceManager(cfg, create_backends(cfg))
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
        if "language" in keys:
            self.apply_language()
        if "idle_seconds" in keys:
            self.idleChanged.emit()
        if "show_general" in keys:
            self._refresh_rooms()

    # ---------- messages from the background thread ----------
    def _on_message(self, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        if kind == "snapshot":
            self._model.set_all([self._stamp(d) for d in msg.get("devices", [])])
            self._backends = msg.get("backends", {})
            self._started = "title" in msg
            self._refresh_rooms()
            self.climateChanged.emit()
            self.statusChanged.emit()
        elif kind == "device":
            d = self._stamp(msg["device"])
            if self._model.upsert(d):
                self._refresh_rooms()
            self.deviceUpdated.emit(d["id"])
            self.climateChanged.emit()
        elif kind == "remove":
            self._model.remove(msg["id"])
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
        if d.get("type") == "security":
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

    def _tab_rooms(self) -> list[str]:
        if self._category == "scenes":
            rooms = self._model.layout.sort({s["room"] for s in self._scenes if s.get("room")})
        else:
            rooms = self._model.rooms(self._category)
        if not self.store.get("show_general"):
            rooms = [r for r in rooms if r != self._model.layout.default_room]
        return rooms

    def _refresh_rooms(self) -> None:
        rooms = self._tab_rooms()
        if self._room != ALL_ROOMS and self._room not in rooms:
            self._room = ALL_ROOMS
            self._model.set_room(ALL_ROOMS)
            self.currentRoomChanged.emit()
        if rooms != self._rooms:
            self._rooms = rooms
            self.roomsChanged.emit()
        self._check_alarms()
        self.summaryChanged.emit()
        self._room_editor.changed.emit()    # device counts and assignments in the settings

    # ---------- commands from QML ----------
    def _command(self, coro_factory) -> None:
        if not self._mgr:
            self.toast.emit(tr("Not connected to Homebridge yet."))
            return
        fut = self.runner.submit(coro_factory(self._mgr))

        def done(f: concurrent.futures.Future) -> None:
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

    @Slot(str)
    def toggle(self, dev_id: str) -> None:
        d = self._model.get(dev_id)
        if not d:
            return
        if not d["reachable"]:
            self.toast.emit(tr("{name} is not reachable. Check the device and Homebridge.").format(name=d["name"]))
            return
        self.setAttrs(dev_id, {"on": not d["state"].get("on")})

    @Slot(str, "QVariantMap")
    def setAttrs(self, dev_id: str, attrs: dict[str, Any]) -> None:
        attrs = {k: (int(v) if isinstance(v, float) and v.is_integer() and k != "target_temp" else v)
                 for k, v in dict(attrs).items()}
        self._command(lambda m: m.command(dev_id, attrs))

    @Slot(str)
    def runScene(self, scene_id: str) -> None:
        self._command(lambda m: m.run_scene(scene_id))

    @Slot(str, result="QVariantMap")
    def device(self, dev_id: str) -> dict[str, Any]:
        d = self._model.get(dev_id)
        if not d:
            return {}
        return {**d, "shortName": short_name(d["name"], d["room"]), "stateText": state_text(d)}

    @Slot(str)
    def selectCategory(self, cat: str) -> None:
        if cat == self._category:
            return
        self._category = cat
        self._model.set_category(cat, self._room)
        self.categoryChanged.emit()
        self._refresh_rooms()
        self.scenesChanged.emit()

    @Slot(str)
    def selectRoom(self, room: str) -> None:
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

    @Property("QVariantList", notify=scenesChanged)
    def visibleScenes(self) -> list[dict[str, Any]]:
        """Scenes of the selected room; "All" shows every scene, whole-house scenes first."""
        if self._room != ALL_ROOMS:
            return [s for s in self._scenes if s.get("room") == self._room]
        return sorted(self._scenes, key=lambda s: s.get("room") is not None)

    @Property(str, notify=categoryChanged)
    def category(self) -> str:
        return self._category

    @Property("QVariantMap", notify=summaryChanged)
    def summary(self) -> dict[str, str]:
        """Short status per menu area, e.g. {"light": "3 on", "security": "2 alerts"}."""
        m = self._model
        on = m.count(lambda d: category(d) == "light" and d["type"] != "blind" and d["reachable"]
                     and bool(d.get("state", {}).get("on")))
        heating = m.count(lambda d: d["type"] == "thermostat" and d["reachable"] and d.get("state", {}).get("heating"))
        alerts = self.securityCount
        return {
            "light": tr("{n} on").format(n=on) if on else "",
            "climate": tr("{n} heating").format(n=heating) if heating else "",
            "scenes": "",
            "security": (tr("1 alert") if alerts == 1 else tr("{n} alerts").format(n=alerts)) if alerts else "",
        }

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

    @Property(int, notify=idleChanged)
    def idleSeconds(self) -> int:
        return int(self.store.get("idle_seconds"))

    @Property(bool, constant=True)
    def fullscreen(self) -> bool:
        return self._fullscreen

    @Property(str, constant=True)
    def version(self) -> str:
        return __version__

    @Property(str, constant=True)
    def configPath(self) -> str:
        return self._config_file
