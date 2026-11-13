"""Display texts for tiles (no Qt dependency, so they are easy to test)."""
from __future__ import annotations

import re
from typing import Any


def fmt_temp(v: Any) -> str:
    if v is None:
        return "–"
    return f"{float(v):.1f}"


def fmt_lux(v: Any) -> str:
    v = float(v)
    return f"{v:.1f} lx" if v < 10 else f"{v:,.0f} lx"


def sensor_parts(s: dict[str, Any]) -> list[str]:
    """Readings of a sensor as short texts, e.g. ["6.5 °C", "82%", "1014 hPa"]."""
    parts = []
    if s.get("current_temp") is not None:
        parts.append(f"{fmt_temp(s['current_temp'])} °C")
    if s.get("humidity") is not None:
        parts.append(f"{float(s['humidity']):.0f}%")
    if s.get("pressure") is not None:
        parts.append(f"{float(s['pressure']):.0f} hPa")
    if s.get("lux") is not None:
        parts.append(fmt_lux(s["lux"]))
    return parts


def short_name(name: str, room: str) -> str:
    """Tiles already show the room: "Living Room Heating" → "Heating"."""
    room = (room or "").strip()
    if not room or name.casefold() == room.casefold():
        return name
    short = re.sub(rf"(^|\s|-){re.escape(room)}(?=$|\s|-)", " ", name, count=1, flags=re.IGNORECASE)
    short = re.sub(r"\s+(in|in the|of|of the|at|at the)\s*$", "", short, flags=re.IGNORECASE)
    short = re.sub(r"\s{2,}", " ", short).strip(" -")
    return short or name


def state_text(d: dict[str, Any]) -> str:
    if not d.get("reachable", True):
        return "Not reachable"
    s = d.get("state", {})
    if d["type"] == "sensor":
        return ", ".join(sensor_parts(s)) or "No reading"
    if d["type"] == "blind":
        if s.get("obstructed"):
            return "Obstructed"
        if s.get("moving") == "opening":
            return f"Opening … {s.get('position', 0)}%"
        if s.get("moving") == "closing":
            return f"Closing … {s.get('position', 0)}%"
        pos = s.get("position", 0)
        return "Open" if pos >= 100 else "Closed" if pos <= 0 else f"{pos}% open"
    if d["type"] == "thermostat":
        if s.get("mode") == "off":
            return f"Off, {fmt_temp(s.get('current_temp'))} °C"
        prefix = "Heating, now" if s.get("heating") else "Now"
        return f"{prefix} {fmt_temp(s.get('current_temp'))} °C"
    if not s.get("on"):
        return "Off"
    if s.get("brightness") is not None:
        return f"{s['brightness']}%"
    if s.get("speed") is not None:
        return f"Speed {round(s['speed'])}%"
    if d["type"] == "plug" and s.get("in_use"):
        return "On, in use"
    return "On"


def has_detail(d: dict[str, Any]) -> bool:
    caps = d.get("capabilities", [])
    return d["type"] in ("thermostat", "sensor", "blind") or any(c in caps for c in ("brightness", "color", "color_temp", "speed"))
