"""Weather for QML (panel.weather): the places of the settings, their weather (fetched in the
background every 15 minutes) and the place search for the settings page."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QLocale, QObject, QTimer, Signal, Slot

from .. import i18n, weather
from ..i18n import tr

if TYPE_CHECKING:
    from .controller import Controller

log = logging.getLogger(__name__)
REFRESH_MS = 15 * 60_000


def _deg(v: float | None) -> str:
    return "–" if v is None else str(round(v)).replace("-", "−")


class WeatherBridge(QObject):
    changed = Signal()                      # places or their weather
    searchDone = Signal("QVariantList", str)    # places found, error
    _result = Signal(str, object, str)      # from the background: place id, data, error

    def __init__(self, ctl: "Controller"):
        super().__init__(ctl)
        self._ctl = ctl
        self._store = ctl.store
        self._data: dict[str, dict[str, Any]] = {}      # place id -> {"data", "error", "time"}
        self._loading: set[str] = set()
        # replaced in tests; the demo shows made-up weather (no network needed)
        demo = ctl.base_cfg.demo.enabled
        self.fetch = (lambda lat, lon: _as_coro(weather.demo(lat, lon))) if demo else weather.fetch
        self.find = weather.search
        self._result.connect(self._on_result)
        self._timer = QTimer(self, interval=REFRESH_MS, timeout=self.refresh)
        self._timer.start()

    # ---------- places ----------
    @property
    def places(self) -> list[dict[str, Any]]:
        return self._store.weather_places

    def default(self) -> dict[str, Any] | None:
        return next((p for p in self.places if p["default"]), None)

    def _save(self) -> None:
        self._store.weather_places = weather.clean(self._store.weather_places)
        self._store.save()
        self.changed.emit()
        self._ctl.weather_places_changed()

    @Property("QVariantList", notify=changed)
    def placeList(self) -> list[dict[str, Any]]:
        """For the settings: [{id, name, coords, default}] in their order."""
        return [{"id": p["id"], "name": p["name"], "default": p["default"],
                 "coords": f"{p['lat']:.2f}, {p['lon']:.2f}"} for p in self.places]

    @Slot(str, float, float, result=str)
    def addPlace(self, name: str, lat: float, lon: float) -> str:
        name = " ".join(name.split())[:weather.MAX_PLACE_NAME]
        if not name:
            return tr("Please enter a name.")
        if any(p["name"].casefold() == name.casefold() for p in self.places):
            return tr("There is already a place named \"{name}\".").format(name=name)
        pid = weather.new_id({p["id"] for p in self.places})
        self._store.weather_places.append({"id": pid, "name": name, "lat": round(lat, 4), "lon": round(lon, 4),
                                           "default": not self.places})
        self._save()
        self._load(pid)
        return ""

    @Slot(str, result=str)
    def addCoordinates(self, text: str) -> str:
        """A place typed as coordinates ("52.52, 13.41"), named by them; "" or an error."""
        coords = weather.parse_coordinates(text)
        if coords is None:
            return tr("Enter a place name or coordinates such as 52.52, 13.41.")
        return self.addPlace(f"{coords[0]:.2f}, {coords[1]:.2f}", *coords)

    @Slot(str, result=bool)
    def isCoordinates(self, text: str) -> bool:
        return weather.parse_coordinates(text) is not None

    @Slot(str, str, result=str)
    def renamePlace(self, pid: str, name: str) -> str:
        name = " ".join(name.split())[:weather.MAX_PLACE_NAME]
        if not name:
            return tr("Please enter a name.")
        if any(p["name"].casefold() == name.casefold() and p["id"] != pid for p in self.places):
            return tr("There is already a place named \"{name}\".").format(name=name)
        for p in self.places:
            if p["id"] == pid:
                p["name"] = name
        self._save()
        return ""

    @Slot(str)
    def deletePlace(self, pid: str) -> None:
        self._store.weather_places = [p for p in self.places if p["id"] != pid]
        self._data.pop(pid, None)
        self._save()

    @Slot(str)
    def setDefault(self, pid: str) -> None:
        for p in self.places:
            p["default"] = p["id"] == pid
        self._save()

    @Slot(str, int)
    def movePlace(self, pid: str, delta: int) -> None:
        places = self.places
        i = next((k for k, p in enumerate(places) if p["id"] == pid), None)
        if i is None:
            return
        j = max(0, min(len(places) - 1, i + delta))
        places.insert(j, places.pop(i))
        self._save()

    # ---------- search ----------
    @Slot(str)
    def search(self, text: str) -> None:
        """Looks for places by name; answers with searchDone([{name, region, lat, lon}], error)."""
        async def run() -> None:
            try:
                found = await self.find(text.strip(), i18n.language())
                err = "" if found else tr("No place found for \"{name}\".").format(name=text.strip())
            except weather.WeatherError as e:
                found, err = [], tr("Search failed: {error}").format(error=e)
            except Exception as e:  # noqa: BLE001
                found, err = [], tr("Search failed: {error}").format(error=e)
            try:
                self.searchDone.emit(found, err)
            except RuntimeError:
                pass
        self._ctl.runner.submit(run())

    # ---------- weather ----------
    @Slot()
    def refresh(self) -> None:
        for p in self.places:
            self._load(p["id"])

    def _load(self, pid: str) -> None:
        p = next((x for x in self.places if x["id"] == pid), None)
        if p is None or pid in self._loading:
            return
        self._loading.add(pid)

        async def run() -> None:
            try:
                data, err = await self.fetch(p["lat"], p["lon"]), ""
            except weather.WeatherError as e:
                data, err = None, str(e)
            except Exception as e:  # noqa: BLE001
                data, err = None, str(e) or type(e).__name__
            try:
                self._result.emit(pid, data, err)
            except RuntimeError:
                pass
        self._ctl.runner.submit(run())

    def _on_result(self, pid: str, data: Any, err: str) -> None:
        self._loading.discard(pid)
        old = self._data.get(pid, {})
        if data is not None:
            self._data[pid] = {"data": data, "error": "", "time": time.time()}
        else:
            log.warning("Weather for %s: %s", pid, err)
            # keep the last weather; say why it is not new
            self._data[pid] = {**old, "error": err}
        self.changed.emit()

    def view(self, pid: str | None) -> dict[str, Any]:
        """What the weather view shows for a place: {name, state: "loading" | "error" | "ok", error,
        now: {temp, text, kind, night, feels, humidity, wind}, days: [{day, kind, text, max, min, rain}]}."""
        p = next((x for x in self.places if x["id"] == pid), None)
        if p is None:
            return {"state": "none"}
        entry = self._data.get(pid, {})
        data = entry.get("data")
        out: dict[str, Any] = {"id": pid, "name": p["name"], "error": entry.get("error", "")}
        if data is None:
            out["state"] = "error" if entry.get("error") else "loading"
            return out
        cur = data["current"]
        kind, text = weather.describe(cur["code"])
        locale = QLocale(i18n.locale_name())
        today = date.today()

        def day_name(iso: str) -> str:
            d = date.fromisoformat(iso)
            if d == today:
                return tr("Today")
            return locale.dayName(d.isoweekday(), QLocale.FormatType.ShortFormat)

        days = []
        for d in data["days"]:
            k, t = weather.describe(d["code"])
            rain = ""
            if d.get("rain_chance") is not None and d["rain_chance"] >= 20:
                rain = tr("{pct} %").format(pct=round(d["rain_chance"]))
            days.append({"day": day_name(d["date"]), "kind": k, "text": tr(t), "max": _deg(d["max"]),
                         "min": _deg(d["min"]), "rain": rain})
        stamp = time.strftime("%H:%M", time.localtime(entry["time"])) if entry.get("time") else ""
        out.update(state="ok", updated=stamp, now={
            "temp": _deg(cur["temp"]), "text": tr(text), "kind": kind, "night": not cur["day"],
            "feels": _deg(cur["feels"]), "humidity": "–" if cur["humidity"] is None else str(round(cur["humidity"])),
            "wind": "–" if cur["wind"] is None else str(round(cur["wind"]))}, days=days)
        return out

    @Property("QVariantMap", notify=changed)
    def idle(self) -> dict[str, Any]:
        """The weather of the default place now, for the screen saver ({} without)."""
        p = self.default()
        v = self.view(p["id"]) if p else {}
        if v.get("state") != "ok":
            return {}
        return {"name": v["name"], **v["now"], "max": v["days"][0]["max"] if v["days"] else "",
                "min": v["days"][0]["min"] if v["days"] else ""}

    @Property("QVariantMap", notify=changed)
    def current(self) -> dict[str, Any]:
        """The weather of the place chosen in the tabs of the weather view."""
        p = next((x for x in self.places if x["name"] == self._ctl.currentRoom), self.default())
        return self.view(p["id"] if p else None)


async def _as_coro(value: Any) -> Any:
    await asyncio.sleep(0)
    return value
