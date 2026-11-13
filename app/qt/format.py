"""Display texts for tiles (no Qt dependency, so they are easy to test)."""
from __future__ import annotations

import re
from typing import Any

from ..i18n import fmt_number, tr


def fmt_temp(v: Any) -> str:
    if v is None:
        return "–"
    return fmt_number(float(v), 1)


def pct(v: Any) -> str:
    return tr("{pct}%").format(pct=round(float(v)))


def fmt_lux(v: Any) -> str:
    v = float(v)
    return tr("{lux} lx").format(lux=fmt_number(v, 1 if v < 10 else 0))


def sensor_parts(s: dict[str, Any]) -> list[str]:
    """Readings of a sensor as short texts, e.g. ["6.5 °C", "82%", "1014 hPa"]."""
    parts = []
    if s.get("current_temp") is not None:
        parts.append(tr("{temp} °C").format(temp=fmt_temp(s["current_temp"])))
    if s.get("humidity") is not None:
        parts.append(pct(s["humidity"]))
    if s.get("pressure") is not None:
        parts.append(tr("{hpa} hPa").format(hpa=fmt_number(float(s["pressure"]), 0, group=False)))
    if s.get("lux") is not None:
        parts.append(fmt_lux(s["lux"]))
    return parts


def short_name(name: str, room: str) -> str:
    """Tiles already show the room: "Living Room Heating" → "Heating"."""
    room = (room or "").strip()
    if not room or name.casefold() == room.casefold():
        return name
    short = re.sub(rf"(^|\s|-){re.escape(room)}(?=$|\s|-)", " ", name, count=1, flags=re.IGNORECASE)
    # leftover connecting words in the supported languages ("Light in the Bathroom" -> "Light")
    short = re.sub(r"\s+(in|in the|of|of the|at|at the|im|in der|der|des|vom|"
                   r"de|du|de la|dans|dans le|dans la|del|della|nel|nella|en|en el|en la)\s*$",
                   "", short, flags=re.IGNORECASE)
    short = re.sub(r"\s{2,}", " ", short).strip(" -")
    return short or name


def state_text(d: dict[str, Any]) -> str:
    if not d.get("reachable", True):
        return tr("Not reachable")
    s = d.get("state", {})
    if d["type"] == "sensor":
        return ", ".join(sensor_parts(s)) or tr("No reading")
    if d["type"] == "blind":
        if s.get("obstructed"):
            return tr("Obstructed")
        if s.get("moving") == "opening":
            return tr("Opening … {pct}").format(pct=pct(s.get("position", 0)))
        if s.get("moving") == "closing":
            return tr("Closing … {pct}").format(pct=pct(s.get("position", 0)))
        pos = s.get("position", 0)
        if pos >= 100:
            return tr("Open")
        if pos <= 0:
            return tr("Closed")
        return tr("{pct} open").format(pct=pct(pos))
    if d["type"] == "thermostat":
        temp = fmt_temp(s.get("current_temp"))
        if s.get("mode") == "off":
            return tr("Off, {temp} °C").format(temp=temp)
        if s.get("heating"):
            return tr("Heating, now {temp} °C").format(temp=temp)
        return tr("Now {temp} °C").format(temp=temp)
    if not s.get("on"):
        return tr("Off")
    if s.get("brightness") is not None:
        return pct(s["brightness"])
    if s.get("speed") is not None:
        return tr("Speed {pct}").format(pct=pct(s["speed"]))
    if d["type"] == "plug" and s.get("in_use"):
        return tr("On, in use")
    return tr("On")


def has_detail(d: dict[str, Any]) -> bool:
    caps = d.get("capabilities", [])
    return d["type"] in ("thermostat", "sensor", "blind") or any(
        c in caps for c in ("brightness", "color", "color_temp", "speed"))
