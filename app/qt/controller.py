"""Brücke zwischen Geräteverwaltung (asyncio, eigener Thread) und der QML-Oberfläche."""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from PySide6.QtCore import (QAbstractListModel, QByteArray, QEvent, QModelIndex, QObject, Qt, QTimer,
                            Property, Signal, Slot)

from .. import __version__
from ..backends import BackendError, HapBackend, create_backends
from ..config import AppConfig, HapBackendConfig
from ..manager import DeviceManager, DeviceNotFound
from ..scheduler import Scheduler
from ..settings import SettingsStore, apply_to_config, validate
from .format import fmt_temp, has_detail, short_name, state_text

log = logging.getLogger(__name__)
ALL_ROOMS = ""
NIGHT_FROM, NIGHT_TO = 19, 7


class AsyncRunner:
    """Eigene asyncio-Schleife in einem Hintergrund-Thread, damit die Oberfläche nie blockiert."""

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
    """Geräte des gewählten Raums (oder aller Räume) für das Kachelraster."""

    ROLES = ("deviceId", "name", "shortName", "room", "type", "icon", "isOn", "reachable", "heating",
             "stateText", "hasDetail", "targetTemp", "minTemp", "maxTemp", "modeOff")

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._all: dict[str, dict[str, Any]] = {}
        self._rows: list[str] = []
        self._room = ALL_ROOMS
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
            case "isOn": return d["type"] != "thermostat" and bool(s.get("on")) and d["reachable"]
            case "reachable": return d["reachable"]
            case "heating": return bool(s.get("heating")) and d["reachable"]
            case "stateText": return state_text(d)
            case "hasDetail": return has_detail(d)
            case "targetTemp": return float(s.get("target_temp") or 20)
            case "minTemp": return float(m.get("min_temp", 10))
            case "maxTemp": return float(m.get("max_temp", 30))
            case "modeOff": return s.get("mode") == "off"
        return None

    # --- Pflege ---
    def rooms(self) -> list[str]:
        return sorted({d["room"] for d in self._all.values()}, key=str.casefold)

    def _visible(self) -> list[str]:
        devs = [d for d in self._all.values() if self._room in (ALL_ROOMS, d["room"])]
        devs.sort(key=lambda d: (d["room"].casefold(), d["type"] == "thermostat", d.get("order", 100),
                                 d["name"].casefold()))
        return [d["id"] for d in devs]

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
        self._all = {d["id"]: d for d in devices}
        self._rows = self._visible()
        self.endResetModel()

    def upsert(self, d: dict[str, Any]) -> bool:
        """Rückgabe True, wenn sich die Struktur (Raum, Name, Reihenfolge) geändert hat."""
        old = self._all.get(d["id"])
        self._all[d["id"]] = d
        structural = old is None or any(old.get(k) != d.get(k) for k in ("room", "name", "order"))
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
                return True, f"Verbunden: {len(snaps)} steuerbare Geräte gefunden"
            except BackendError as e:
                return False, str(e)
            except Exception as e:  # pragma: no cover - unerwartete Fehler sichtbar machen
                return False, f"Verbindung fehlgeschlagen: {e}"
            finally:
                await backend.stop()

        fut = self._ctl.runner.submit(probe())
        fut.add_done_callback(lambda f: self.testFinished.emit(*f.result()))


class ActivityFilter(QObject):
    """Meldet Berührungen/Tastendrücke (für den Ruhebildschirm)."""

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
    scenesChanged = Signal()
    statusChanged = Signal()
    climateChanged = Signal()
    themeChanged = Signal()
    idleChanged = Signal()

    def __init__(self, base_cfg: AppConfig, store: SettingsStore, config_file: Path | None = None,
                 fullscreen: bool = False):
        super().__init__()
        self.base_cfg = base_cfg
        self.store = store
        self.runner = AsyncRunner()
        self._config_file = str(config_file or "")
        self._fullscreen = fullscreen
        self._model = DeviceModel(self)
        self._settings = SettingsBridge(store, self)
        self._rooms: list[str] = []
        self._room = ALL_ROOMS
        self._scenes = [s.model_dump(include={"id", "name", "icon"}) for s in base_cfg.scenes]
        self._backends: dict[str, Any] = {}
        self._started = False
        self._theme = self._compute_theme()
        self._mgr: DeviceManager | None = None
        self._sched: Scheduler | None = None
        self._pump: asyncio.Task | None = None
        self._message.connect(self._on_message)
        self._theme_timer = QTimer(self, interval=30_000, timeout=self._update_theme)
        self._theme_timer.start()

    # ---------- Lebenszyklus ----------
    def effective_config(self) -> AppConfig:
        return apply_to_config(self.base_cfg, self.store.values)

    def start(self) -> None:
        self.runner.submit(self._restart(self.effective_config()))

    def shutdown(self) -> None:
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

    def settings_saved(self, keys: set[str]) -> None:
        if any(k.startswith("hap_") for k in keys):
            self._started = False
            self.statusChanged.emit()
            self.runner.submit(self._restart(self.effective_config()))
        if "theme" in keys:
            self._update_theme()
        if "idle_seconds" in keys:
            self.idleChanged.emit()

    # ---------- Nachrichten aus dem Hintergrund-Thread ----------
    def _on_message(self, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        if kind == "snapshot":
            self._model.set_all(msg.get("devices", []))
            self._backends = msg.get("backends", {})
            self._started = "title" in msg
            self._refresh_rooms()
            self.climateChanged.emit()
            self.statusChanged.emit()
        elif kind == "device":
            d = msg["device"]
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
            self.toast.emit("Szene nicht vollständig ausgeführt. Nicht erreicht: " + ", ".join(msg["errors"]))

    def _refresh_rooms(self) -> None:
        rooms = self._model.rooms()
        if self._room != ALL_ROOMS and self._room not in rooms:
            self._room = ALL_ROOMS
            self._model.set_room(ALL_ROOMS)
            self.currentRoomChanged.emit()
        if rooms != self._rooms:
            self._rooms = rooms
            self.roomsChanged.emit()

    # ---------- Befehle aus QML ----------
    def _command(self, coro_factory) -> None:
        if not self._mgr:
            self.toast.emit("Noch keine Verbindung zu Homebridge.")
            return
        fut = self.runner.submit(coro_factory(self._mgr))

        def done(f: concurrent.futures.Future) -> None:
            e = f.exception()
            if e is None:
                return
            if isinstance(e, DeviceNotFound):
                self.toast.emit("Gerät nicht gefunden. Es wurde eventuell aus Homebridge entfernt.")
            elif isinstance(e, (ValueError, BackendError)):
                self.toast.emit(str(e))
            else:
                self.toast.emit(f"Befehl wurde nicht ausgeführt: {e}")
        fut.add_done_callback(done)

    @Slot(str)
    def toggle(self, dev_id: str) -> None:
        d = self._model.get(dev_id)
        if not d:
            return
        if not d["reachable"]:
            self.toast.emit(f"{d['name']} ist nicht erreichbar. Prüfe Gerät und Homebridge.")
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
    def selectRoom(self, room: str) -> None:
        if room != self._room:
            self._room = room
            self._model.set_room(room)
            self.currentRoomChanged.emit()

    # ---------- Eigenschaften ----------
    @Property(QObject, constant=True)
    def devices(self) -> QObject:
        return self._model

    @Property(QObject, constant=True)
    def settings(self) -> QObject:
        return self._settings

    @Property("QVariantList", notify=roomsChanged)
    def rooms(self) -> list[str]:
        return self._rooms

    @Property(str, notify=currentRoomChanged)
    def currentRoom(self) -> str:
        return self._room

    @Property("QVariantList", notify=scenesChanged)
    def scenes(self) -> list[dict[str, Any]]:
        return self._scenes

    @Property(bool, notify=statusChanged)
    def statusOk(self) -> bool:
        return self._started and bool(self._backends) and all(b["ok"] for b in self._backends.values())

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:
        if not self._backends:
            return "Keine Homebridge eingerichtet"
        if not self._started:
            return "Verbinde …"
        bad = [n for n, b in self._backends.items() if not b["ok"]]
        if bad:
            return "Homebridge nicht erreichbar" if bad == ["homebridge"] else f"Nicht erreichbar: {', '.join(bad)}"
        return "Verbunden"

    @Property(str, notify=statusChanged)
    def statusDetail(self) -> str:
        lines = [f"{n}: {'verbunden' if b['ok'] else b['error'] or 'getrennt'} ({b['devices']} Geräte)"
                 for n, b in self._backends.items()]
        return "\n".join(lines)

    @Property(int, notify=climateChanged)
    def deviceCount(self) -> int:
        return len(self._model.all())

    @Property(str, notify=climateChanged)
    def indoorTemp(self) -> str:
        temps = [d["state"]["current_temp"] for d in self._model.all()
                 if d["reachable"] and d["state"].get("current_temp") is not None]
        return fmt_temp(sum(temps) / len(temps)) if temps else ""

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
