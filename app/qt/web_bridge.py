"""The panel's side of the web setup (app/web.py): starts and stops the server with the
settings, shows the code for connecting a browser and answers the requests of the web page
on the Qt main thread with the same code the settings pages use."""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import QObject, Qt, Signal, Slot

from .. import i18n, web
from ..i18n import tr
from ..settings import FIELDS_BY_KEY
from ..wifi import qr_image

if TYPE_CHECKING:
    from .controller import Controller

log = logging.getLogger(__name__)
# what the web page may change about a device (as the device editor on the panel)
DEVICE_KEYS = ("name", "room", "kind", "area", "hidden", "favorite", "outdoor", "quiet", "measureOnly", "mainMeter")
SECRET_KINDS = ("password", "code")


def web_texts() -> dict[str, str]:
    """Texts of the web page in the panel language."""
    return {
        "title": tr("Panel setup"),
        "pairTitle": tr("Connect this browser"),
        "pairHelp": tr("On the panel, open Settings → Web setup → Connect a browser and enter the code shown there."),
        "code": tr("Code"),
        "connect": tr("Connect"),
        "wrongCode": tr("Wrong or expired code. Show a new one on the panel."),
        "settings": tr("Settings"),
        "rooms": tr("Rooms"),
        "save": tr("Save"),
        "saved": tr("Saved"),
        "unchanged": tr("unchanged"),
        "signOut": tr("Sign out"),
        "addRoom": tr("Add room"),
        "rename": tr("Rename"),
        "delete": tr("Delete"),
        "name": tr("Name"),
        "room": tr("Room"),
        "kind": tr("Kind"),
        "showUnder": tr("Show under"),
        "favorite": tr("Favorite"),
        "hidden": tr("Hide on the home screen"),
        "outdoor": tr("Outdoor sensor"),
        "alerts": tr("Security alerts"),
        "measureOnly": tr("Only measure"),
        "mainMeter": tr("Main meter"),
        "devices": tr("Devices"),
        "notReachable": tr("Not reachable"),
        "newRoomName": tr("Name of the new room"),
        "deleteRoom": tr("Delete the room? Its devices move to the default room."),
        "offline": tr("The panel does not answer. Is it switched on and is web setup still on?"),
        "virtualGroups": tr("Virtual devices and groups"),
        "virtual": tr("Virtual device (MQTT)"),
        "lightGroup": tr("Light group"),
        "switchGroup": tr("Switch group"),
        "add": tr("Add"),
        "topic": tr("MQTT topic"),
        "unit": tr("Unit"),
        "jsonKey": tr("Value from JSON (optional)"),
        "decimals": tr("Decimal places"),
        "energyTopic": tr("Meter reading in kWh (optional)"),
        "energyKey": tr("Meter reading from JSON (optional)"),
        "members": tr("Members"),
        "hideMembers": tr("Hide the members on the home screen"),
        "allowOff": tr("All may be off"),
        "scenes": tr("Scenes"),
        "newScene": tr("New scene"),
        "takeNow": tr("Use current state"),
        "on": tr("On"),
        "off": tr("Off"),
        "brightness": tr("Brightness"),
        "position": tr("Position"),
        "target": tr("Target temperature"),
        "idleScene": tr("Double tap on the screen saver"),
        "weather": tr("Weather"),
        "places": tr("Places"),
        "search": tr("Search"),
        "placeHint": tr("Place name or coordinates such as 52.52, 13.41"),
        "default": tr("Default"),
        "makeDefault": tr("Make default"),
        "backups": tr("Backups"),
        "createBackup": tr("Back up now"),
        "restore": tr("Restore"),
        "restoreAsk": tr("Restore these settings? The panel restarts."),
        "deleteAsk": tr("Delete it?"),
        "edit": tr("Edit"),
        "cancel": tr("Cancel"),
    }


class WebBridge(QObject):
    _call = Signal(object)
    paired = Signal()             # a browser has just connected: close the code on the panel

    def __init__(self, controller: "Controller", path: Path):
        super().__init__(controller)
        self._ctl = controller
        self.pairing = web.Pairing(path)
        self.server: web.WebServer | None = None
        self._call.connect(self._run, Qt.ConnectionType.BlockingQueuedConnection)

    # ---------- running requests on the main thread ----------
    def _run(self, job: tuple[Callable[[], Any], dict[str, Any]]) -> None:
        fn, out = job
        try:
            out["result"] = fn()
        except Exception as e:  # noqa: BLE001 - handed to the server thread
            out["error"] = e

    def call(self, fn: Callable[[], Any]) -> Any:
        if threading.current_thread() is threading.main_thread():
            return fn()
        out: dict[str, Any] = {}
        self._call.emit((fn, out))
        if "error" in out:
            raise out["error"]
        return out.get("result")

    # ---------- server ----------
    def apply(self) -> None:
        """Starts, restarts or stops the server as the settings say."""
        store = self._ctl.store
        enabled, port = bool(store.get("web_enabled")), int(store.get("web_port"))
        if self.server and (not enabled or self.server.port != port):
            self.stop()
        if enabled and not self.server:
            try:
                self.server = web.WebServer(port, self.pairing, self.handle)
            except OSError as e:
                log.warning("Web setup not started: %s", e)
                self._ctl.toast.emit(tr("Web setup could not start on port {port}: {error}").format(port=port, error=e))
                return
            self.server.call = self.call
            self.server.search = self.search_places
            self.server.start()

    def stop(self) -> None:
        if self.server:
            self.server.stop()
            self.server = None

    def url(self) -> str:
        port = self.server.port if self.server else int(self._ctl.store.get("web_port"))
        return f"http://{web.local_address()}:{port}/"

    @Slot(result="QVariantMap")
    def newCode(self) -> dict[str, Any]:
        """A new code for connecting a browser: {url, code, image} (the QR code opens the page
        with the code filled in); {error} while web setup is off."""
        if not self.server:
            return {"error": tr("Switch on web setup first.")}
        code = self.pairing.new_code()
        return {"url": self.url(), "code": f"{code[:3]} {code[3:]}", "image": qr_image(f"{self.url()}#code={code}")}

    def sign_out_all(self) -> None:
        self.pairing.forget()
        self._ctl.toast.emit(tr("All browsers are signed out."))

    # ---------- requests of the web page (main thread) ----------
    def handle(self, method: str, path: str, body: dict[str, Any], authorized: bool) -> tuple[int, dict[str, Any]]:
        if not authorized:
            if path == "/api/state":
                return 401, {"error": "pair", "t": web_texts(), "name": self._ctl._settings.panel_name(),
                             "lang": i18n.language()}
            return 401, {"error": "pair"}
        if method == "GET" and path == "/api/state":
            return 200, self.state()
        if method != "POST":
            return 404, {"error": "not found"}
        if path == "/api/settings":
            errors = self.save_settings(body.get("changes") or {})
            return (400 if errors else 200), {"errors": errors, **self.state()}
        if path == "/api/device":
            err = self.save_device(str(body.get("id", "")), body.get("values") or {})
            return (400 if err else 200), {"error": err, **self.state()}
        ops = {"/api/room": self.room, "/api/virtual": self.virtual, "/api/group": self.group,
               "/api/scene": self.scene, "/api/weather": self.weather, "/api/backup": self.backup}
        if path in ops:
            result = ops[path](str(body.get("op", "")), body)
            extra = result if isinstance(result, dict) else {"error": result or ""}
            return (400 if extra.get("error") else 200), {**extra, **self.state()}
        return 404, {"error": "not found"}

    def search_places(self, text: str) -> dict[str, Any]:
        """Weather place search, run in the server thread (it waits for Open-Meteo)."""
        ctl = self._ctl
        try:
            found = ctl.runner.submit(ctl._weather.find(text.strip(), i18n.language())).result(timeout=20)
        except Exception as e:  # noqa: BLE001 - shown on the page
            return {"places": [], "error": tr("Search failed: {error}").format(error=e)}
        err = "" if found else tr("No place found for \"{name}\".").format(name=text.strip())
        return {"places": found, "error": err}

    def state(self) -> dict[str, Any]:
        sections = []
        for s in self._ctl.store.schema():
            fields = []
            for f in s["fields"]:
                if f["kind"] in ("action", "page", "update") or f["key"].startswith("web_"):
                    continue
                if f["kind"] in SECRET_KINDS:     # never sent out: only whether one is set
                    f = {**f, "value": "", "isSet": bool(f["value"])}
                fields.append(f)
            if fields:
                sections.append({**s, "fields": fields})
        ed = self._ctl._room_editor
        devices = [{k: d.get(k) for k in ("id", "name", "baseName", "room", "type", "reachable", "kind", "kinds",
                                          "hidden", "favorite", "area", "areas", "canOutdoor", "outdoor", "canQuiet",
                                          "quiet", "canMeasureOnly", "measureOnly", "canMainMeter", "mainMeter")}
                   for d in ed.devices if not d.get("grouped")]
        ctl = self._ctl
        by_id = {d["id"]: d for d in ed.devices}
        virtual = [{**v, "room": by_id.get(f"mqtt:{v['id']}", {}).get("room", ""),
                    "favorite": bool(by_id.get(f"mqtt:{v['id']}", {}).get("favorite")),
                    "mainMeter": bool(by_id.get(f"mqtt:{v['id']}", {}).get("mainMeter"))} for v in ctl.store.virtual]
        return {"name": ctl._settings.panel_name(), "t": web_texts(), "lang": i18n.language(), "sections": sections,
                "rooms": ed.rooms, "devices": devices, "virtual": virtual,
                "groups": ctl.store.groups, "switchGroups": ctl.store.switch_groups,
                "lights": ed.lights, "switches": ed.switches,
                "scenes": sorted(({"id": x["id"], "name": x["name"], "room": x["room"], "count": len(x["devices"]),
                                   "active": x["id"] in ctl._active_scenes} for x in ctl.store.scenes),
                                 key=lambda x: (x["room"].casefold(), x["name"].casefold())),
                "places": ctl._weather.placeList, "backups": ctl._settings.backups}

    def save_settings(self, changes: dict[str, Any]) -> dict[str, str]:
        clean = {}
        for key, value in changes.items():
            f = FIELDS_BY_KEY.get(key)
            if f is None or key.startswith("web_") or f.kind in ("action", "page", "update"):
                continue
            if f.kind in SECRET_KINDS and value in ("", None):      # empty: leave as it is
                continue
            clean[key] = value
        return self._ctl._settings.save(clean) if clean else {}

    def save_device(self, dev_id: str, values: dict[str, Any]) -> str:
        return self._ctl._room_editor.saveDevice(dev_id, {k: v for k, v in values.items() if k in DEVICE_KEYS})

    def virtual(self, op: str, body: dict[str, Any]) -> str:
        ed = self._ctl._room_editor
        if op == "delete":
            ed.deleteVirtual(str(body.get("id", "")))
            return ""
        return ed.saveVirtual(body.get("values") or {})

    def group(self, op: str, body: dict[str, Any]) -> str:
        ed = self._ctl._room_editor
        switch = body.get("kind") == "switch"
        if op == "delete":
            (ed.deleteSwitchGroup if switch else ed.deleteGroup)(str(body.get("id", "")))
            return ""
        return (ed.saveSwitchGroup if switch else ed.saveGroup)(body.get("values") or {})

    def scene(self, op: str, body: dict[str, Any]) -> str | dict[str, Any]:
        ctl = self._ctl
        sid = str(body.get("id", ""))
        if op == "draft":
            return {"draft": ctl.scene_draft(sid, str(body.get("room", "")))}
        if op == "capture":
            return {"capture": ctl.sceneCapture(str(body.get("device", "")))}
        if op == "delete":
            ctl.deleteScene(sid)
            return ""
        devices = body.get("devices")
        return ctl.saveScene(sid, str(body.get("name", "")), str(body.get("room", "")),
                             devices if isinstance(devices, dict) else {}, bool(body.get("favorite")),
                             bool(body.get("idle")))

    def weather(self, op: str, body: dict[str, Any]) -> str:
        w = self._ctl._weather
        pid = str(body.get("id", ""))
        if op == "add":
            try:
                return w.addPlace(str(body.get("name", "")), float(body["lat"]), float(body["lon"]))
            except (KeyError, TypeError, ValueError):
                return tr("Choose one of the offered options")
        if op == "coords":
            return w.addCoordinates(str(body.get("text", "")))
        if op == "rename":
            return w.renamePlace(pid, str(body.get("name", "")))
        if op == "delete":
            w.deletePlace(pid)
        elif op == "default":
            w.setDefault(pid)
        elif op == "move":
            w.movePlace(pid, -1 if int(body.get("delta", 0)) < 0 else 1)
        return ""

    def backup(self, op: str, body: dict[str, Any]) -> str:
        s = self._ctl._settings
        name = str(body.get("name", ""))
        if op == "create":
            return s.createBackup()
        if op == "restore":
            return s.restoreBackup(name)
        if op == "delete":
            s.deleteBackup(name)
        return ""

    def room(self, op: str, body: dict[str, Any]) -> str:
        ed = self._ctl._room_editor
        name = str(body.get("name", ""))
        if op == "add":
            return ed.addRoom(name)
        if op == "rename":
            return ed.renameRoom(name, str(body.get("new", "")))
        if op == "delete":
            return ed.deleteRoom(name)
        if op == "move":
            ed.moveRoom(name, -1 if int(body.get("delta", 0)) < 0 else 1)
            ed.finishMoves()
            return ""
        return tr("Unknown action: {key}").format(key=op)
