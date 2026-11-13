"""Display texts for tiles (no Qt dependency, so they are easy to test)."""
from __future__ import annotations

import re
from typing import Any


def fmt_temp(v: Any) -> str:
    if v is None:
        return "–"
    return f"{float(v):.1f}"


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
    return d["type"] == "thermostat" or any(c in caps for c in ("brightness", "color", "color_temp", "speed"))
